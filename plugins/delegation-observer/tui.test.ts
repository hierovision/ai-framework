/**
 * Pure projection / command tests for the delegation TUI (RM-069 AC4, AC9,
 * AC11). JSX rendering is exercised by the live drill, not a synthetic DOM
 * harness: everything decision-bearing is pure and asserted here.
 *
 * Run: node --test plugins/delegation-observer/tui.test.ts
 */
import assert from "node:assert/strict";
import test from "node:test";

import { associateSessionInfo, createState, observe, tick } from "./state.ts";
import {
  associationGap,
  createControls,
  degradationBanner,
  footerStatus,
  isChildSession,
  isLiveStatus,
  projectDelegate,
  readLiveMap,
  readStatusSnapshot,
  selectableRows,
  sidebarLines,
  visibleRows,
} from "./view.ts";

let clock = 1_000_000;
const now = () => clock;

function seeded() {
  clock = 1_000_000;
  const state = createState({}, now);
  observe(state, {
    type: "session.created",
    data: {
      sessionID: "ses_child", parentID: "ses_parent",
      title: "RM-069 drill", agent: "implementer",
    },
  });
  observe(state, {
    type: "session.message.content.updated",
    data: {
      sessionID: "ses_child", messageID: "m1",
      content: [{
        type: "tool", id: "t1", name: "shell",
        state: { status: "running", input: { command: "pytest -q" } },
      }],
    },
  });
  observe(state, {
    type: "session.usage.updated",
    data: {
      sessionID: "ses_child", cost: 0.42,
      tokens: { input: 1200, output: 300 },
    },
  });
  return state;
}

test("a delegate row carries every decision-grade field", () => {
  const state = seeded();
  clock += 12_500;
  const row = projectDelegate(state.delegates.get("ses_child"), clock);
  assert.equal(row.sessionID, "ses_child");
  assert.equal(row.agent, "implementer");
  assert.equal(row.task, "RM-069 drill");
  assert.equal(row.status, "running");
  assert.equal(row.phase, "shell: pytest -q");
  assert.equal(row.elapsedMs, 12_500);
  assert.equal(row.quietMs, 12_500);
  assert.equal(row.tokensIn, 1200);
  assert.equal(row.tokensOut, 300);
  assert.equal(row.cost, 0.42);
  assert.equal(row.warning, null);
  assert.equal(row.parentID, "ses_parent");
  assert.equal(row.via, "parent");
});

test("status transitions surface in the projection", () => {
  const state = seeded();
  observe(state, {
    type: "permission.asked",
    data: { sessionID: "ses_child", action: "read", resources: ["x"] },
  });
  let row = projectDelegate(state.delegates.get("ses_child"), clock);
  assert.equal(row.status, "waiting");
  assert.match(row.needsInput, /read/);

  clock += 500_000;
  tick(state, clock);
  row = projectDelegate(state.delegates.get("ses_child"), clock);
  assert.equal(row.status, "waiting"); // needs-input outranks stall: no false stall
  assert.match(row.needsInput, /read/);

  observe(state, {
    type: "session.execution.succeeded",
    data: { sessionID: "ses_child" },
  });
  row = projectDelegate(state.delegates.get("ses_child"), clock);
  assert.equal(row.status, "completed");
  assert.equal(row.terminal, "completed");
});

test("rows are ordered attention-first, then newest", () => {
  const state = seeded();
  clock += 1_000;
  observe(state, {
    type: "session.created",
    data: { sessionID: "ses_b", parentID: "ses_parent", title: "b", agent: "planner" },
  });
  // no attention state: newest first
  let rows = visibleRows(state, clock);
  assert.deepEqual(rows.map((r) => r.sessionID), ["ses_b", "ses_child"]);
  observe(state, {
    type: "permission.asked",
    data: { sessionID: "ses_child", action: "read", resources: ["x"] },
  });
  rows = visibleRows(state, clock);
  assert.deepEqual(rows.map((r) => r.sessionID), ["ses_child", "ses_b"]);
});

test("footer and sidebar summaries are compact and countable", () => {
  const state = seeded();
  observe(state, {
    type: "session.created",
    data: { sessionID: "ses_b", parentID: "ses_parent", title: "b", agent: "planner" },
  });
  observe(state, {
    type: "permission.asked",
    data: { sessionID: "ses_b", action: "read", resources: ["x"] },
  });
  const rows = visibleRows(state, clock);
  assert.equal(footerStatus(rows), "delegates 2 · 1 running · 1 waiting");
  const lines = sidebarLines(rows, 6);
  assert.match(lines[0], /planner/);
  assert.match(lines[0], /waiting/);
  assert.match(lines[1], /implementer/);
  assert.ok(lines.every((l) => l.length <= 64));
});

test("footer is empty when nothing is delegated", () => {
  const state = createState({}, now);
  assert.equal(footerStatus(visibleRows(state, clock)), "");
  assert.deepEqual(sidebarLines([], 4), []);
});

test("controls stay available while a row is waiting or merely quiet", () => {
  const state = seeded();
  observe(state, {
    type: "permission.asked",
    data: { sessionID: "ses_child", action: "read", resources: ["x"] },
  });
  let byId = Object.fromEntries(createControls(state.delegates.get("ses_child"), {})
    .map((c) => [c.id, c]));
  assert.equal(byId.interrupt.enabled, true, "a waiting child can be interrupted");
  assert.equal(byId.steer.enabled, true, "a waiting child can still be steered");

  // clock-classified failure is not a terminal state: controls remain
  const dead = createState({}, now);
  observe(dead, {
    type: "session.created",
    data: { sessionID: "ses_d", parentID: "ses_parent", title: "d", agent: "x" },
  });
  clock += 1_000_000;
  tick(dead, clock);
  assert.equal(dead.delegates.get("ses_d").status, "failed");
  byId = Object.fromEntries(createControls(dead.delegates.get("ses_d"), {})
    .map((c) => [c.id, c]));
  assert.equal(byId.interrupt.enabled, true, "dead-but-not-terminal stays actionable");

  observe(state, {
    type: "session.execution.succeeded",
    data: { sessionID: "ses_child" },
  });
  const done = Object.fromEntries(createControls(state.delegates.get("ses_child"), {})
    .map((c) => [c.id, c]));
  assert.equal(done.steer.enabled, false);
  assert.match(done.steer.reason, /terminal/);
  assert.equal(done.interrupt.enabled, false);
});

test("control calls are the exact typed client calls", async () => {
  const calls = [];
  const client = {
    session: {
      prompt: async (input) => { calls.push(["prompt", input]); },
      interrupt: async (input) => { calls.push(["interrupt", input]); },
    },
  };
  const ui = { tabs: { focus: (sid) => { calls.push(["focus", sid]); return true; } } };
  const controls = createControls({ sessionID: "ses_child", status: "running", terminal: null }, { client, ui });
  const byId = Object.fromEntries(controls.map((c) => [c.id, c]));
  await byId.focus.run();
  await byId.steer.run("try the other fixture");
  await byId.interrupt.run();
  assert.deepEqual(calls, [
    ["focus", "ses_child"],
    ["prompt", { sessionID: "ses_child", text: "try the other fixture", delivery: "steer" }],
    ["interrupt", { sessionID: "ses_child" }],
  ]);
});

test("steer refuses an empty prompt without calling the client", async () => {
  const calls = [];
  const controls = createControls({ sessionID: "s", status: "running", terminal: null }, {
    client: {
      session: {
        prompt: async (input) => calls.push(input),
        interrupt: async () => {},
      },
    },
    ui: { tabs: { focus: () => true } },
  });
  const steer = controls.find((c) => c.id === "steer");
  const result = await steer.run("   ");
  assert.equal(result.ok, false);
  assert.equal(result.reason, "empty-prompt");
  assert.equal(calls.length, 0);
});

test("degradation banner names the reason and the fallback", () => {
  assert.match(
    degradationBanner({ pluginLoaded: false }),
    /not loaded.*watchdog/,
  );
  assert.match(
    degradationBanner({ pluginLoaded: true, pluginState: "failed: boom" }),
    /load failed.*boom.*watchdog/,
  );
  assert.match(
    degradationBanner({ pluginLoaded: true, connection: "disconnected" }),
    /disconnected.*last known.*watchdog/,
  );
  assert.match(
    degradationBanner({ pluginLoaded: true, disabled: true }),
    /disabled.*watchdog/,
  );
  assert.match(
    degradationBanner({ pluginLoaded: true, serverHealth: "synthetic failed: nope" }),
    /server.*synthetic failed.*watchdog/,
  );
  assert.match(
    degradationBanner({ pluginLoaded: true, runningChildren: 2, associatedActive: 0 }),
    /2 running child.*no delegate association.*watchdog/,
  );
  assert.equal(degradationBanner({
    pluginLoaded: true, runningChildren: 1, associatedActive: 1,
  }), null);
});

test("the orchestrator/root is never counted as an unassociated child", () => {
  const sessions = [
    { id: "ses_root", parentID: undefined, title: "owner session", status: "busy" },
    { id: "ses_child", parentID: "ses_root", title: "worker", status: "running" },
  ];
  assert.deepEqual(associationGap(sessions, [
    { sessionID: "ses_child", status: "running", terminal: null },
    { sessionID: "ses_root", status: "running", terminal: null },
  ]), { runningChildren: 1, associatedActive: 1, unassociated: 0 });
  // a busy root alone is not a gap
  assert.deepEqual(associationGap([sessions[0]], []),
    { runningChildren: 0, associatedActive: 0, unassociated: 0 });
  // an unknown status is not liveness (live defect, 2026-10-30): a store of
  // historical children must not read as "N running, N unassociated"
  assert.deepEqual(associationGap([
    { id: "ses_child", parentID: "ses_root", title: "worker" },
    { id: "ses_child2", parentID: "ses_root", title: "worker 2", status: "idle" },
  ], []), { runningChildren: 0, associatedActive: 0, unassociated: 0 });
  // a run-vehicle child is recognised by its marker
  assert.equal(isChildSession({
    id: "ses_v", title: "[delegate:ses_root] reviewer: review",
  }), true);
  assert.deepEqual(associationGap([
    sessions[1],
    { id: "ses_v", title: "[delegate:ses_root] reviewer: review", status: "running" },
  ], [{ sessionID: "ses_child", status: "running", terminal: null }]),
  { runningChildren: 2, associatedActive: 1, unassociated: 1 });
});

test("two delegates with different last events never share a quiet value", () => {
  clock = 1_000_000;
  const state = createState({}, now);
  associateSessionInfo(state, {
    id: "ses_a", parentID: "ses_p", title: "a",
    time: { created: clock - 3_600_000, updated: clock - 600_000 },
  });
  associateSessionInfo(state, {
    id: "ses_b", parentID: "ses_p", title: "b",
    time: { created: clock - 3_600_000, updated: clock - 60_000 },
  });
  clock += 5_000;
  const a = projectDelegate(state.delegates.get("ses_a"), clock);
  const b = projectDelegate(state.delegates.get("ses_b"), clock);
  assert.notEqual(a.quiet, b.quiet, "quiet is per session, not per observer boot");
  assert.equal(a.quietMs, 605_000);
  assert.equal(b.quietMs, 65_000);
});

test("historical rows collapse to one line and never claim to be running", () => {
  clock = 1_000_000;
  const state = createState({}, now);
  for (const [id, hours] of [["ses_h1", 20], ["ses_h2", 19], ["ses_h3", 18]]) {
    associateSessionInfo(state, {
      id, parentID: "ses_p", title: id, agent: "implementer",
      time: { created: clock - hours * 3_600_000, updated: clock - hours * 3_600_000 + 60_000 },
    });
  }
  // a genuinely live child still renders in full
  observe(state, {
    type: "session.created",
    data: { sessionID: "ses_now", parentID: "ses_p", title: "current", agent: "implementer" },
  });
  // a child that is terminal in the store but was never observed here is
  // history too: it must not sit in the strip as a fresh completion
  associateSessionInfo(state, {
    id: "ses_done", parentID: "ses_p", title: "ses_done", agent: "implementer",
    time: { created: clock - 3_600_000, updated: clock - 50_000 },
    outcome: "succeeded",
  });
  const rows = visibleRows(state, clock);
  assert.equal(rows.length, 5, "the panel keeps every row");
  assert.equal(rows.filter((r) => r.stale).length, 4);
  assert.ok(rows.filter((r) => r.stale).every((r) => r.status !== "running"),
    "a discovered row is never rendered as running");
  const lines = sidebarLines(rows, 8);
  assert.equal(lines.length, 2, "one live line plus one collapsed stale line");
  assert.match(lines[0], /implementer/);
  assert.match(lines[0], /running: starting/);
  assert.equal(lines[1], "4 stale delegates hidden");
  assert.equal(footerStatus(rows), "delegates 1 · 1 running");
});

test("the fallback status snapshot is parsed only when it is real", () => {
  const parsed = readStatusSnapshot(JSON.stringify({
    ts: "2026-10-29T20:00:00Z",
    agent: "architect",
    child: "ses_c",
    outcome: "success",
    terminal: true,
    heartbeat: "/tmp/x.log",
  }));
  assert.equal(parsed.agent, "architect");
  assert.equal(parsed.outcome, "success");
  assert.equal(parsed.terminal, true);
  assert.equal(readStatusSnapshot("not json"), null);
  assert.equal(readStatusSnapshot(""), null);
  assert.equal(readStatusSnapshot(JSON.stringify({ outcome: "" })), null);
});

// --- the live status map (liveness source) and its failure mode -----------

test("the live map reads the 2.1.4 status contract and never throws", () => {
  // `ctx.data.session.status` is "idle" | "running" on 2.1.4.
  assert.equal(isLiveStatus("running"), true);
  assert.equal(isLiveStatus("idle"), false);
  // object-shaped status is accepted as defence, anything else is not live
  assert.equal(isLiveStatus({ type: "running" }), true);
  assert.equal(isLiveStatus({ type: "idle" }), false);
  assert.equal(isLiveStatus(undefined), false);
  assert.equal(isLiveStatus(null), false);

  const sessions = [
    { id: "ses_live" },
    { id: "ses_idle" },
    { sessionID: "ses_alias" },
    { id: "" },
  ];
  const statuses: Record<string, string> = {
    ses_live: "running", ses_idle: "idle", ses_alias: "running",
  };
  const map = readLiveMap(() => sessions, (id) => statuses[id] ?? "idle");
  assert.equal(map.available, true);
  assert.deepEqual(map.entries, [
    { sessionID: "ses_live", live: true },
    { sessionID: "ses_idle", live: false },
    { sessionID: "ses_alias", live: true },
  ]);
  assert.equal(map.sessions.length, 4);

  // a throwing list or status is an unavailable map, not an empty one
  assert.deepEqual(readLiveMap(() => { throw new Error("no data"); }, () => "running"),
    { available: false, entries: [], sessions: [] });
  assert.deepEqual(readLiveMap(() => sessions, () => { throw new Error("no status"); }),
    { available: false, entries: [], sessions: [] });
  assert.deepEqual(readLiveMap(() => null, () => "running"),
    { available: false, entries: [], sessions: [] });
});

test("an unavailable live map degrades visibly instead of hiding rows", () => {
  const banner = degradationBanner({ pluginLoaded: true, liveMap: "unavailable" });
  assert.match(banner, /cannot read the live session status map/);
  assert.match(banner, /hidden as stale/);
  assert.match(banner, /watchdog\/observer fallback/);
  assert.equal(degradationBanner({ pluginLoaded: true, liveMap: "ok" }), null);
});

test("stale rows are not selectable and not actionable", async () => {
  clock = 1_000_000;
  const state = createState({}, now);
  observe(state, {
    type: "session.created",
    data: { sessionID: "ses_now", parentID: "ses_p", title: "current", agent: "implementer" },
  });
  associateSessionInfo(state, {
    id: "ses_old", parentID: "ses_p", title: "history", agent: "implementer",
    time: { created: clock - 20 * 3_600_000, updated: clock - 19 * 3_600_000 },
  });
  const rows = visibleRows(state, clock);
  assert.deepEqual(selectableRows(rows).map((r) => r.sessionID), ["ses_now"]);

  const stale = rows.find((r) => r.sessionID === "ses_old");
  const calls = [];
  const byId = Object.fromEntries(createControls(stale, {
    client: {
      session: {
        prompt: async (input) => calls.push(["prompt", input]),
        interrupt: async (input) => calls.push(["interrupt", input]),
      },
    },
  }).map((c) => [c.id, c]));
  assert.equal(byId.steer.enabled, false);
  assert.equal(byId.interrupt.enabled, false);
  assert.match(byId.steer.reason, /collapsed history/);
  const steer = await byId.steer.run("try again");
  assert.equal(steer.ok, false);
  assert.equal(steer.reason, "stale");
  const interrupt = await byId.interrupt.run();
  assert.equal(interrupt.ok, false);
  assert.equal(interrupt.reason, "stale");
  assert.equal(calls.length, 0, "no client call for collapsed history");
  assert.equal(byId.focus.enabled, true, "viewing history stays possible");
});

test("an all-stale set reports the collapsed count in the footer", () => {
  clock = 1_000_000;
  const state = createState({}, now);
  for (const [id, hours] of [["ses_h1", 20], ["ses_h2", 19]]) {
    associateSessionInfo(state, {
      id, parentID: "ses_p", title: id,
      time: { created: clock - hours * 3_600_000, updated: clock - hours * 3_600_000 },
    });
  }
  const rows = visibleRows(state, clock);
  assert.equal(rows.length, 2);
  assert.equal(footerStatus(rows), "2 stale delegates hidden");
  assert.deepEqual(sidebarLines(rows, 8), ["2 stale delegates hidden"]);
  assert.deepEqual(selectableRows(rows), []);
  assert.equal(footerStatus([]), "");
});
