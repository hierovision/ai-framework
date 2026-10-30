import assert from "node:assert/strict";
import test from "node:test";

import definition, {
  createDefinition,
  readThreshold,
  countTokens,
  limitsFromModels,
  PLUGIN_ID,
} from "./index.js";

const Plugin = { define: (d) => d };

function fakeCtx({ models = [], events = [] } = {}) {
  const logs = [];
  const compactions = [];
  let cleanup = null;
  let aborted = false;
  const ctx = {
    model: {
      list: async () => models,
    },
    session: {
      compact: async ({ sessionID }) => {
        compactions.push(sessionID);
      },
    },
    log: {
      info: async (message, extra) => logs.push({ level: "info", message, extra }),
      warn: async (message, extra) => logs.push({ level: "warn", message, extra }),
      error: async (message, extra) => logs.push({ level: "error", message, extra }),
    },
    event: {
      subscribe: ({ signal } = {}) => ({
        async *[Symbol.asyncIterator]() {
          for (const event of events) {
            if (signal?.aborted) { aborted = true; return; }
            yield event;
          }
        },
      }),
    },
  };
  return {
    ctx,
    logs,
    compactions,
    setCleanup: (fn) => { cleanup = fn; },
    cleanup: () => cleanup?.(),
    wasAborted: () => aborted,
  };
}

const assistant = (sid, tokens, providerID = "opencode-go", modelID = "m") => ({
  type: "message.updated",
  properties: { info: { role: "assistant", sessionID: sid, providerID, modelID, tokens } },
});

const idle = (sid) => ({ type: "session.idle", properties: { sessionID: sid } });

test("threshold parsing accepts fractions and percentages", () => {
  assert.equal(readThreshold("0.5"), 0.5);
  assert.equal(readThreshold("60%"), 0.6);
  assert.equal(readThreshold("0"), 0.5);
  assert.equal(readThreshold("2"), 0.5);
  assert.equal(readThreshold("nope"), 0.5);
  assert.equal(readThreshold(undefined), 0.5);
});

test("token accounting matches opencode's overflow check", () => {
  assert.equal(countTokens({ total: 10, input: 99 }), 10);
  assert.equal(countTokens({ input: 1, output: 2, cache: { read: 3, write: 4 } }), 10);
  assert.equal(countTokens({}), null);
  assert.equal(countTokens(null), null);
});

test("model limits normalize array and provider-list shapes", () => {
  const a = limitsFromModels([{ providerID: "p", id: "m", limit: { context: 100 } }]);
  assert.equal(a.get("p/m"), 100);
  const b = limitsFromModels({ models: [{ provider: { id: "p" }, id: "m", context: 50 }] });
  assert.equal(b.get("p/m"), 50);
});

test("crossing the threshold compacts once on idle, then re-arms below", async () => {
  process.env.OPENCODE_AUTOCOMPACT_THRESHOLD = "50%";
  const f = fakeCtx({
    models: [{ providerID: "opencode-go", id: "m", limit: { context: 100 } }],
    events: [
      assistant("s1", { total: 60 }),
      idle("s1"),
      idle("s1"),             // already fired: no second compaction
      assistant("s1", { total: 10 }), // below the line -> re-arm
      assistant("s1", { total: 80 }),
      idle("s1"),
    ],
  });
  const def = createDefinition(Plugin);
  assert.equal(def.id, PLUGIN_ID);
  const cleanup = await def.setup(f.ctx);
  f.setCleanup(cleanup);
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(f.compactions, ["s1", "s1"]);
  cleanup();
  delete process.env.OPENCODE_AUTOCOMPACT_THRESHOLD;
});

test("unknown context limit never compacts", async () => {
  const f = fakeCtx({
    models: [],
    events: [assistant("s2", { total: 9999 }), idle("s2")],
  });
  const cleanup = await createDefinition(Plugin).setup(f.ctx);
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(f.compactions, []);
  cleanup();
});

test("startup marker is emitted", async () => {
  const f = fakeCtx({ models: [] });
  const cleanup = await createDefinition(Plugin).setup(f.ctx);
  await new Promise((r) => setTimeout(r, 10));
  assert.ok(f.logs.some((l) => l.message.includes("initialized")), f.logs);
  cleanup();
});

test("startup marker reaches stderr when the context has no log domain", async () => {
  // V2 2.1.4's plugin context has no `log` domain (probed 2026-10-29:
  // app/location/options/agent/event/model/... but no log/logger). The
  // startup marker must therefore land on the loader/standalone log stream
  // (process.stderr with `--print-logs`), not an unobservable console.log.
  const writes = [];
  const original = process.stderr.write;
  process.stderr.write = (chunk) => {
    writes.push(String(chunk));
    return true;
  };
  try {
    const f = fakeCtx({ models: [] });
    delete f.ctx.log;
    const cleanup = await createDefinition(Plugin).setup(f.ctx);
    await new Promise((r) => setTimeout(r, 10));
    cleanup();
  } finally {
    process.stderr.write = original;
  }
  assert.ok(
    writes.some((line) => line.includes("auto-compact-at-threshold initialized")),
    writes,
  );
});

test("startup marker carries the loader-probe token when the env sets one", async () => {
  // The post-smoke loader probe passes a per-run token; echoing it in the
  // record attributes the marker to the plugin copy that probe staged.
  process.env.OPENCODE_LOADER_PROBE_TOKEN = "lp-token-1";
  try {
    const f = fakeCtx({ models: [] });
    const cleanup = await createDefinition(Plugin).setup(f.ctx);
    await new Promise((r) => setTimeout(r, 10));
    cleanup();
    const startup = f.logs.find((l) => l.message.includes("initialized"));
    assert.ok(startup, f.logs);
    assert.equal(startup.extra.probe, "lp-token-1", f.logs);
  } finally {
    delete process.env.OPENCODE_LOADER_PROBE_TOKEN;
  }
});

test("startup marker omits the probe token outside a probe run", async () => {
  delete process.env.OPENCODE_LOADER_PROBE_TOKEN;
  const f = fakeCtx({ models: [] });
  const cleanup = await createDefinition(Plugin).setup(f.ctx);
  await new Promise((r) => setTimeout(r, 10));
  cleanup();
  const startup = f.logs.find((l) => l.message.includes("initialized"));
  assert.ok(startup, f.logs);
  assert.ok(!("probe" in startup.extra), f.logs);
});

test("cleanup aborts the subscription", async () => {
  const f = fakeCtx({ models: [] });
  let signalRef = null;
  f.ctx.event.subscribe = ({ signal } = {}) => {
    signalRef = signal;
    return {
      async *[Symbol.asyncIterator]() {
        await new Promise((resolve) => {
          const timer = setTimeout(resolve, 100);
          signal?.addEventListener("abort", () => {
            clearTimeout(timer);
            resolve();
          }, { once: true });
        });
      },
    };
  };
  const cleanup = await createDefinition(Plugin).setup(f.ctx);
  assert.equal(typeof cleanup, "function", "setup must return cleanup");
  cleanup();
  await new Promise((r) => setTimeout(r, 25));
  assert.equal(signalRef?.aborted, true,
    "cleanup must abort the event subscription");
});

test("default export is a Plugin.define definition with id + setup", () => {
  assert.equal(definition.id, PLUGIN_ID);
  assert.equal(typeof definition.setup, "function");
});
