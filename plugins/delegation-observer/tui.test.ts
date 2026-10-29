/**
 * Pure projection / command tests for the delegation TUI (RM-069 AC4, AC9,
 * AC11). JSX rendering is exercised by the live drill, not a synthetic DOM
 * harness: everything decision-bearing is pure and asserted here.
 *
 * Run: node --test plugins/delegation-observer/tui.test.ts
 */
import assert from "node:assert/strict";
import test from "node:test";

import { createState, observe, tick } from "./state.ts";
import {
  createControls,
  degradationBanner,
  footerStatus,
  projectDelegate,
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
  observe(state, {
    type: "session.created",
    data: { sessionID: "ses_b", parentID: "ses_parent", title: "b", agent: "planner" },
  });
  clock += 1_000;
  observe(state, {
    type: "permission.asked",
    data: { sessionID: "ses_b", action: "read", resources: ["x"] },
  });
  const rows = visibleRows(state, clock);
  assert.deepEqual(rows.map((r) => r.sessionID), ["ses_b", "ses_child"]);
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

test("controls disable actions the row cannot accept, with a reason", () => {
  const state = seeded();
  let controls = createControls(state.delegates.get("ses_child"), {});
  const byId = Object.fromEntries(controls.map((c) => [c.id, c]));
  assert.equal(byId.focus.enabled, true);
  assert.equal(byId.steer.enabled, true);
  assert.equal(byId.interrupt.enabled, true);

  observe(state, {
    type: "session.execution.succeeded",
    data: { sessionID: "ses_child" },
  });
  controls = createControls(state.delegates.get("ses_child"), {});
  const done = Object.fromEntries(controls.map((c) => [c.id, c]));
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
    degradationBanner({ pluginLoaded: true, runningSessions: 2, associated: 0 }),
    /2 running.*no delegate association.*watchdog/,
  );
  assert.equal(degradationBanner({ pluginLoaded: true, runningSessions: 1, associated: 1 }), null);
});
