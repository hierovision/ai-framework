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
import { observe, tick } from "./state.ts";

const Plugin = { define: (d) => d };
const clock = () => 1_000_000;

function fakeCtx(events, {
  list = [], failSubscribe = false, syntheticFails = false, get, location,
} = {}) {
  const synthetic = [];
  const prompts = [];
  const logs = [];
  let signal = null;
  const ctx = {
    options: {},
    location: location ?? undefined,
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

test("only the instance owning the parent location emits", async () => {
  // The managed service activates the plugin once per location; every
  // instance sees the same event, so the non-owning ones must stay silent.
  const { ctx, synthetic } = fakeCtx([childCreated()], {
    location: { directory: "/work" },
    get: async ({ sessionID }) => ({
      id: sessionID, location: { directory: "/other" },
    }),
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 0);
  assert.doesNotMatch(handle.state.degradation ?? "", /unverified/);
});

test("the owning location emits exactly once", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated()], {
    location: { directory: "/work/" },
    get: async ({ sessionID }) => ({
      id: sessionID, location: { directory: "/work" },
    }),
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 1);
  assert.equal(synthetic[0].sessionID, "ses_parent");
  assert.equal(synthetic[0].delivery, "steer");
  assert.equal(synthetic[0].resume, false);
});

test("a depth-2 child routes its milestone to the root orchestrator", async () => {
  const root = "ses_root";
  const worker = "ses_worker";
  const { ctx, synthetic } = fakeCtx([childCreated("ses_leaf", worker)], {
    location: { directory: "/work" },
    get: async ({ sessionID }) => {
      if (sessionID === worker) {
        return { id: worker, parentID: root, location: { directory: "/work" } };
      }
      if (sessionID === root) {
        return { id: root, location: { directory: "/work" } };
      }
      return null;
    },
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 1);
  assert.equal(synthetic[0].sessionID, root);
  assert.doesNotMatch(handle.state.degradation ?? "", /unverified/);
});

test("a nested child under a title-marked vehicle routes to the TUI root", async () => {
  const root = "ses_root";
  const vehicle = "ses_vehicle";
  const { ctx, synthetic } = fakeCtx([childCreated("ses_grandchild", vehicle)], {
    location: { directory: "/work" },
    get: async ({ sessionID }) => {
      if (sessionID === vehicle) {
        return {
          id: vehicle, parentID: null,
          title: `[delegate:${root}] build: vehicle run`,
          location: { directory: "/work" },
        };
      }
      if (sessionID === root) {
        return { id: root, location: { directory: "/work" } };
      }
      return null;
    },
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 1);
  assert.equal(synthetic[0].sessionID, root);
  assert.doesNotMatch(handle.state.degradation ?? "", /unverified/);
});

test("an unresolvable parent chain fails closed with a visible reason", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated("ses_leaf", "ses_missing")], {
    get: async () => null,
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  assert.equal(synthetic.length, 0);
  assert.match(handle.state.degradation, /unverified orchestrator ses_missing/);
});

test("the health record is written on state changes only", async () => {
  const dir = mkdtempSync(join(tmpdir(), "rm069-health2-"));
  try {
    const file = join(dir, "health.json");
    const writes: Array<Record<string, unknown>> = [];
    const { ctx } = fakeCtx([
      childCreated(),
      // no milestone and no state change: must not rewrite the record
      { type: "session.usage.updated", data: { sessionID: "ses_child", cost: 1 } },
      { type: "session.usage.updated", data: { sessionID: "ses_child", cost: 2 } },
    ]);
    const handle = startObserver(ctx, {
      now: clock, intervalMs: 0, healthFile: file,
      onHealthWrite: (record) => writes.push(record),
    });
    await handle.done;
    // Deterministic property: exactly two writes, one per state change
    // (init -> connected, stream end -> disconnected). The no-op usage events
    // must not add a write. Timestamps come from the injected clock, so no
    // wall-clock equality assumption is involved.
    assert.deepEqual(writes.map((w) => w.connection),
      ["connected", "disconnected"]);
    assert.equal(writes.length, 2);
    assert.equal(writes[0].updated, clock());
    assert.equal(writes[1].updated, clock());
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

test("a historical bootstrap emits no synthetic stalls and never reads running", async () => {
  const { ctx, synthetic } = fakeCtx([], {
    list: [{
      id: "ses_old", parentID: "ses_parent", title: "historical", agent: "planner",
      time: { created: 1_000, updated: 2_000 }, outcome: "succeeded",
    }],
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  const d = handle.state.delegates.get("ses_old");
  assert.ok(d);
  assert.equal(d.status, "completed", "the real SessionInfo.outcome is read");
  assert.equal(d.terminal?.outcome, "completed");
  assert.equal(d.stale, true);
  assert.equal(d.lastActivityAt, 2_000, "the store's last event, not the boot clock");
  assert.equal(tick(handle.state, 999_999_000).milestones.length, 0);
  assert.equal(synthetic.length, 0);
});

test("a discovered row promoted by a non-touch event never stalls on the server path", async () => {
  // 19 h-old list entry, no outcome: the first event must refresh the clock,
  // otherwise the next tick classifies it dead and injects a synthetic stall.
  const { ctx, synthetic } = fakeCtx([
    { type: "session.usage.updated", data: { sessionID: "ses_old", cost: 0.1 } },
  ], {
    list: [{
      id: "ses_old", parentID: "ses_parent", title: "historical", agent: "planner",
      time: { created: 1_000, updated: 2_000 },
    }],
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  const d = handle.state.delegates.get("ses_old");
  assert.equal(d.provenance, "observed");
  assert.equal(d.lastActivityAt, clock(), "the observation time, not the store timestamp");
  const flushed = tick(handle.state, clock());
  assert.equal(flushed.milestones.length, 0);
  assert.equal(synthetic.length, 0);
  assert.equal(d.status, "running");
});

test("a store-terminal child emits nothing on a tick or a replayed create", async () => {
  const { ctx, synthetic } = fakeCtx([], {
    list: [{
      id: "ses_done", parentID: "ses_parent", title: "finished", agent: "planner",
      time: { created: 999_000, updated: 999_900 }, outcome: "succeeded",
    }],
  });
  const handle = startObserver(ctx, { now: clock, intervalMs: 0 });
  await handle.done;
  const d = handle.state.delegates.get("ses_done");
  assert.equal(d.status, "completed");
  const replayed = observe(handle.state, {
    type: "session.created",
    data: { sessionID: "ses_done", parentID: "ses_parent", title: "finished" },
  });
  assert.deepEqual(replayed.milestones, [], "a replayed create emits no start");
  const replay = tick(handle.state, clock());
  assert.equal(replay.milestones.length, 0);
  assert.equal(synthetic.length, 0);
  assert.equal(d.status, "completed");
});

test("disable-by-config leaves the stream silent", async () => {
  const { ctx, synthetic } = fakeCtx([childCreated()]);
  const handle = startObserver(ctx, {
    now: clock, intervalMs: 0, config: { enabled: false },
  });
  await handle.done;
  assert.equal(synthetic.length, 0);
});
