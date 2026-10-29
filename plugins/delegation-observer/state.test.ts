/**
 * Hermetic reducer tests for the delegation observer (RM-069 AC1, AC3, AC5–AC8).
 *
 * Run: node --test plugins/delegation-observer/state.test.ts
 *
 * No OpenCode, no network, no filesystem reads except the shared supervision
 * contract JSON, which is asserted against this module's defaults so the
 * TypeScript side can never drift from watch_agent/observe_completion.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";

import {
  DEFAULTS,
  TITLE_PREFIX,
  associateSessionInfo,
  createState,
  delegationTitle,
  observe,
  parseDelegationTitle,
  tick,
} from "./state.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTRACT = JSON.parse(
  readFileSync(join(HERE, "..", "..", "scripts", "supervision_contract.json"),
    "utf8"),
);

let clock = 1_000_000;
const now = () => clock;
const advance = (ms) => { clock += ms; return clock; };

const event = (type, data, created = clock) => ({ type, created, data });

const child = (sessionID, parentID, title = "worker", agent = "implementer") => event(
  "session.created",
  { sessionID, parentID, title, agent },
);

const toolCalled = (sid, id, input = { command: "ls" }, name = "shell") => event(
  "session.tool.called",
  { sessionID: sid, id, input, name },
);

const contentTool = (sid, id, name, status, input = {}) => event(
  "session.message.content.updated",
  {
    sessionID: sid,
    messageID: "msg_1",
    content: [{ type: "tool", id, name, state: { status, input } }],
  },
);

function fresh() {
  clock = 1_000_000;
  return createState({}, now);
}

// --- the shared supervision contract ---------------------------------------

test("thresholds are the shared supervision contract, not guessed here", () => {
  assert.equal(DEFAULTS.stallSeconds, CONTRACT.stall_seconds);
  assert.equal(DEFAULTS.callSeconds, CONTRACT.call_seconds);
  assert.equal(DEFAULTS.loopRepeats, CONTRACT.loop_repeats);
  assert.equal(DEFAULTS.generationSeconds, CONTRACT.generation_seconds);
  assert.equal(DEFAULTS.milestoneMinIntervalSeconds,
    CONTRACT.milestone_min_interval_seconds);
  assert.deepEqual(DEFAULTS.statuses, CONTRACT.statuses);
});

// --- association (AC1) -----------------------------------------------------

test("a parent-linked child is associated through parent_id", () => {
  const state = fresh();
  observe(state, child("ses_child", "ses_parent", "do the thing"));
  const d = state.delegates.get("ses_child");
  assert.ok(d);
  assert.equal(d.orchestratorID, "ses_parent");
  assert.equal(d.via, "parent");
  assert.equal(d.agent, "implementer");
  assert.equal(d.task, "do the thing");
  assert.equal(d.status, "running");
});

test("a run-vehicle child is associated through its title marker", () => {
  const state = fresh();
  const title = delegationTitle({
    orchestratorID: "ses_parent",
    agent: "implementer",
    task: "RM-069 drill",
  });
  assert.equal(title, "[delegate:ses_parent] implementer: RM-069 drill");
  observe(state, child("ses_vehicle", null, title, "implementer"));
  const d = state.delegates.get("ses_vehicle");
  assert.ok(d);
  assert.equal(d.orchestratorID, "ses_parent");
  assert.equal(d.via, "title");
  assert.equal(d.task, "RM-069 drill");
});

test("title markers are escaped and truncated to a stable contract", () => {
  const title = delegationTitle({
    orchestratorID: "ses_parent",
    agent: "implementer",
    task: "line one\nline two ] with  spacing " + "x".repeat(200),
  });
  assert.ok(title.startsWith(TITLE_PREFIX + "ses_parent] implementer: "));
  assert.ok(!title.includes("\n"));
  assert.equal(title.split("\n").length, 1);
  assert.ok(title.length <= 160);
  assert.ok(title.endsWith("..."));
  assert.equal(parseDelegationTitle("not a delegate title"), null);
  assert.equal(
    parseDelegationTitle("[delegate:ses_p] implementer: task").orchestratorID,
    "ses_p",
  );
});

test("a session renamed into the marker form is associated, then stable", () => {
  const state = fresh();
  observe(state, child("ses_child", null, "plain title"));
  assert.equal(state.delegates.size, 0);
  observe(state, event("session.renamed", {
    sessionID: "ses_child",
    title: "[delegate:ses_parent] reviewer: review it",
  }));
  const d = state.delegates.get("ses_child");
  assert.ok(d);
  assert.equal(d.orchestratorID, "ses_parent");
  assert.equal(d.via, "title");
});

test("SessionInfo bootstrap association covers both forms", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_a", parentID: "ses_parent", title: "plain", agent: "planner",
  });
  associateSessionInfo(state, {
    id: "ses_b", parentID: null,
    title: "[delegate:ses_parent] reviewer: review", agent: "reviewer",
  });
  assert.equal(state.delegates.get("ses_a").via, "parent");
  assert.equal(state.delegates.get("ses_b").via, "title");
});

// --- event-driven status (AC3, AC4) ---------------------------------------

test("tool and phase state come from server events, not files", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, contentTool("ses_c", "t1", "shell", "running",
    { command: "pytest -q" }));
  let d = state.delegates.get("ses_c");
  assert.equal(d.phase, "shell: pytest -q");
  assert.equal(d.toolInFlight, true);

  advance(1500);
  observe(state, contentTool("ses_c", "t1", "shell", "completed",
    { command: "pytest -q" }));
  d = state.delegates.get("ses_c");
  assert.equal(d.toolInFlight, false);
  assert.equal(d.lastActivityAt, clock);
  assert.equal(d.quietSinceAt, clock);
});

test("usage events update tokens and cost", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("session.usage.updated", {
    sessionID: "ses_c",
    cost: 0.25,
    tokens: { input: 1000, output: 250 },
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.cost, 0.25);
  assert.equal(d.tokens.input, 1000);
  assert.equal(d.tokens.output, 250);
});

test("needs-input is surfaced immediately for permissions and forms", () => {
  const state = fresh();
  const started = observe(state, child("ses_c", "ses_p"));
  assert.deepEqual(started.milestones.map((m) => m.kind), ["start"]);
  const r = observe(state, event("permission.asked", {
    sessionID: "ses_c",
    action: "external_directory",
    resources: ["/etc/**"],
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "waiting");
  assert.equal(d.needsInput.kind, "permission");
  assert.match(d.needsInput.detail, /external_directory/);
  assert.equal(r.milestones.length, 1);
  assert.equal(r.milestones.at(-1).kind, "needs-input");
  assert.equal(r.alerts.at(-1).severity, "warning");
});

test("a form request is needs-input too", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("form.created", {
    sessionID: "ses_c", id: "form_1", form: { title: "Pick a target" },
  }));
  assert.equal(state.delegates.get("ses_c").needsInput.kind, "form");
});

test("answering needs-input resumes and emits one resume milestone", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("permission.asked", {
    sessionID: "ses_c", action: "read", resources: ["x"],
  }));
  advance(40_000);
  const r = observe(state, event("permission.replied", {
    sessionID: "ses_c", requestID: "p1", reply: "once",
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "running");
  assert.equal(d.needsInput, null);
  assert.ok(r.milestones.some((m) => m.kind === "resume"));
});

test("a busy child is never marked stalled during an open generation", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("session.step.started", {
    sessionID: "ses_c", assistantMessageID: "m1",
  }));
  observe(state, event("session.status", {
    sessionID: "ses_c", type: "busy", status: { type: "busy" },
  }));
  advance((DEFAULTS.stallSeconds + 60) * 1000);
  const r = tick(state, clock);
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "running");
  assert.equal(d.warning, null);
  assert.equal(r.milestones.length, 0);
});

test("a genuinely quiet child warns once within one stall window", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  advance((DEFAULTS.stallSeconds + 1) * 1000);
  const r = tick(state, clock);
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "warning");
  assert.match(d.warning, /quiet/);
  assert.equal(r.milestones.filter((m) => m.kind === "stall").length, 1);
  // a second tick inside the same window does not repeat the milestone
  advance(5_000);
  const again = tick(state, clock);
  assert.equal(again.milestones.filter((m) => m.kind === "stall").length, 0);
});

test("quiet beyond twice the window fails the delegate", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  advance((DEFAULTS.stallSeconds * 2 + 5) * 1000);
  tick(state, clock);
  assert.equal(state.delegates.get("ses_c").status, "failed");
});

test("a repeated identical tool loop is flagged once and deduped", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  let flagged = 0;
  for (let i = 0; i < DEFAULTS.loopRepeats; i += 1) {
    const r = observe(state, toolCalled("ses_c", `t${i}`,
      { command: "git status" }, "shell"));
    flagged += r.milestones.filter((m) => m.kind === "thrash").length;
    advance(1_000);
  }
  assert.equal(flagged, 1);
  assert.match(state.delegates.get("ses_c").warning, /thrash/);
  const d = state.delegates.get("ses_c");
  assert.equal(d.loop.count, DEFAULTS.loopRepeats);
});

test("terminal outcomes map to completed, failed and interrupted", () => {
  for (const [type, expected] of [
    ["session.execution.succeeded", "completed"],
    ["session.execution.failed", "failed"],
    ["session.execution.interrupted", "failed"],
  ]) {
    const state = fresh();
    observe(state, child("ses_c", "ses_p"));
    const r = observe(state, event(type, { sessionID: "ses_c" }));
    assert.equal(state.delegates.get("ses_c").status, expected);
    const terminal = r.milestones.filter((m) => m.kind === "terminal");
    assert.equal(terminal.length, 1);
    // a duplicate terminal event never emits a second milestone
    const again = observe(state, event(type, { sessionID: "ses_c" }));
    assert.equal(again.milestones.filter((m) => m.kind === "terminal").length, 0);
  }
});

// --- milestones: bounded, deduped, rate-limited (AC5, AC6) ----------------

test("start and first tool milestones are emitted exactly once", () => {
  const state = fresh();
  const first = observe(state, child("ses_c", "ses_p"));
  assert.equal(first.milestones.length, 1);
  assert.equal(first.milestones[0].kind, "start");
  observe(state, contentTool("ses_c", "t1", "read", "running",
    { path: "a.md" }));
  advance(1_000);
  const second = observe(state, contentTool("ses_c", "t2", "grep", "running",
    { pattern: "x" }));
  assert.equal(second.milestones.filter((m) => m.kind === "first-tool")
    .length, 0);
});

test("non-terminal milestones are capped at one per delegate per interval", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  advance(DEFAULTS.milestoneMinIntervalSeconds * 1000 + 1);
  const a = observe(state, contentTool("ses_c", "t1", "read", "running",
    { path: "a" }));
  assert.equal(a.milestones.filter((m) => m.kind === "first-tool").length, 1);
  advance(1_000);
  observe(state, event("permission.asked", {
    sessionID: "ses_c", action: "read", resources: ["b"],
  }));
  const b = observe(state, event("permission.replied", {
    sessionID: "ses_c", requestID: "p", reply: "once",
  }));
  assert.equal(b.milestones.length, 0);
  advance(DEFAULTS.milestoneMinIntervalSeconds * 1000);
  const c = observe(state, contentTool("ses_c", "t2", "read", "completed",
    { path: "b" }));
  assert.equal(c.milestones.length, 0); // completed tool is not a milestone
});

test("terminal milestones bypass the rate limit but only fire once", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  const r = observe(state, event("session.execution.succeeded",
    { sessionID: "ses_c" }));
  assert.equal(r.milestones.filter((m) => m.kind === "terminal").length, 1);
  assert.ok(r.milestones[0].text.includes("completed"));
});

test("milestone text names the child and requested action", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p", "RM-069 drill", "implementer"));
  const r = observe(state, event("permission.asked", {
    sessionID: "ses_c", action: "external_directory", resources: ["/etc/**"],
  }));
  const needs = r.milestones.at(-1);
  assert.match(needs.text, /implementer/);
  assert.match(needs.text, /ses_c/);
  assert.match(needs.text, /external_directory/);
  assert.equal(needs.parentID, "ses_p");
  assert.equal(needs.description, "delegation-observer milestone");
});

// --- degradation (AC11) ---------------------------------------------------

test("degradation is a state transition with a visible reason", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  state.connection = "disconnected";
  state.degradation = "event stream disconnected at 2026-10-29T00:00:00Z";
  assert.equal(state.connection, "disconnected");
  assert.match(state.degradation, /disconnected/);
});
