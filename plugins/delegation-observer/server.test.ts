/**
 * Server-part tests (RM-069 AC1, AC5, AC7, AC11): association from the event
 * stream, synthetic parent milestones without model turns, one terminal
 * milestone, and visible degradation when the stream fails.
 *
 * Run: node --test plugins/delegation-observer/server.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { PLUGIN_ID, createDefinition, startObserver } from "./server.ts";

const Plugin = { define: (d) => d };
const clock = () => 1_000_000;

function fakeCtx(events, {
  list = [], failSubscribe = false, syntheticFails = false, get,
} = {}) {
  const synthetic = [];
  const prompts = [];
  const logs = [];
  let signal = null;
  const ctx = {
    options: {},
    session: {
      list: async () => ({ data: list, cursor: {} }),
      synthetic: async (input) => {
        if (syntheticFails) throw new Error("synthetic rejected");
        synthetic.push(input);
        return { id: "msg_x", sessionID: input.sessionID };
      },
      prompt: async (input) => prompts.push(input),
      get: get ?? (async ({ sessionID }) => ({ id: sessionID })),
    },
    event: {
      subscribe: (options = {}) => {
        signal = options.signal ?? null;
        if (failSubscribe) throw new Error("stream closed");
        return {
          async *[Symbol.asyncIterator]() {
            for (const event of events) yield event;
          },
        };
      },
    },
  };
  return { ctx, synthetic, prompts, logs, signal: () => signal };
}

const childCreated = (sid = "ses_child", parent = "ses_parent") => ({
  type: "session.created",
  data: { sessionID: sid, parentID: parent, title: "drill", agent: "implementer" },
});

test("the definition is a V2 server plugin with the observer id", () => {
  const definition = createDefinition(Plugin);
  assert.equal(definition.id, PLUGIN_ID);
  assert.equal(typeof definition.setup, "function");
});

test("association and milestones go to the orchestrator, never the child", async () => {
  const { ctx, synthetic } = fakeCtx([
    childCreated(),
    {
      type: "permission.asked",
      data: { sessionID: "ses_child", action: "read", resources: ["x"] },
    },
  ]);
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.ok(synthetic.length >= 2);
  assert.ok(synthetic.every((s) => s.sessionID === "ses_parent"));
  assert.ok(synthetic.some((s) => /needs input/.test(s.text)));
  assert.equal(synthetic[0].description, "delegation-observer milestone");
});

test("terminal completion emits exactly one synthetic milestone", async () => {
  const { ctx, synthetic, prompts } = fakeCtx([
    childCreated(),
    { type: "session.execution.succeeded", data: { sessionID: "ses_child" } },
    { type: "session.execution.succeeded", data: { sessionID: "ses_child" } },
  ]);
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.filter((s) => /completed/.test(s.text)).length, 1);
  assert.equal(prompts.length, 0); // never starts a model turn
});

test("a child that cannot be associated produces no synthetic traffic", async () => {
  const { ctx, synthetic } = fakeCtx([
    {
      type: "session.created",
      data: { sessionID: "ses_orphan", parentID: null, title: "plain", agent: "x" },
    },
  ]);
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 0);
});

test("bootstrap association covers children that predate the observer", async () => {
  const { ctx, synthetic } = fakeCtx([], {
    list: [{ id: "ses_child", parentID: "ses_parent", title: "pre-existing", agent: "planner" }],
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.ok(handle.state.delegates.has("ses_child"));
  assert.equal(synthetic.length, 0); // no start milestone for a pre-existing child
});

test("a failing event stream is recorded, not thrown", async () => {
  const { ctx } = fakeCtx([], { failSubscribe: true });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(handle.state.connection, "disconnected");
  assert.match(handle.state.degradation, /stream closed/);
  assert.match(handle.lastLog(), /stream ended/);
});

test("a rejected synthetic message degrades visibly but does not stop observation", async () => {
  const { ctx } = fakeCtx([
    childCreated(),
    {
      type: "permission.asked",
      data: { sessionID: "ses_child", action: "read", resources: ["x"] },
    },
  ], { syntheticFails: true });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.match(handle.state.degradation, /synthetic/);
  const failures = handle.lastLog()
    .split("\n")
    .filter((line) => line.includes("synthetic milestone failed"));
  assert.equal(failures.length, 2); // observation continued past the first failure
});

test("an unverified orchestrator never receives a synthetic milestone", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated()], {
    get: async ({ sessionID }) => ({ id: sessionID, parentID: "ses_other" }),
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 0);
  assert.match(handle.state.degradation, /unverified orchestrator ses_parent/);
  assert.match(handle.lastLog(), /unverified orchestrator/);
});

test("a session lookup failure fails closed with a visible reason", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated()], {
    get: async () => { throw new Error("not found"); },
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 0);
  assert.match(handle.state.degradation, /unverified orchestrator/);
});

test("degradation is published in the shared health record", async () => {
  const dir = mkdtempSync(join(tmpdir(), "rm069-health-"));
  try {
    const file = join(dir, "health.json");
    const { ctx } = fakeCtx([], { failSubscribe: true });
    const handle = startObserver(ctx, {
      now: clock, intervalMs: 0, healthFile: file,
    });
    await handle.done;
    const record = JSON.parse(readFileSync(file, "utf8"));
    assert.equal(record.connection, "disconnected");
    assert.match(record.degradation, /stream closed/);
    assert.equal(typeof record.updated, "number");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("teardown aborts the event subscription", async () => {
  const { ctx, signal } = fakeCtx([], {});
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.ok(signal(), "subscribe received a signal");
  assert.equal(signal().aborted, false);
  await handle.stop();
  assert.equal(signal().aborted, true);
});

test("disable-by-config leaves the stream silent", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated()]);
  const handle = startObserver(ctx, {
    now: clock, intervalMs: 0, config: { enabled: false },
  });
  await handle.done;
  assert.equal(synthetic.length, 0);
});
