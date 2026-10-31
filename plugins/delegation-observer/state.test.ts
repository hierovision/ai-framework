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
  healthPath,
  markActive,
  observe,
  parseDelegationTitle,
  parseHealthRecord,
  tick,
  tuiConfig,
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

test("a real form.created event (data.form.sessionID) is needs-input", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  // Exact 2.1.4 shape: FormCreated.data = { form: FormInfo1 } — the session
  // id is nested, not top-level (client types.d.ts FormCreated/FormInfo1).
  const r = observe(state, event("form.created", {
    form: { id: "form_1", sessionID: "ses_c", title: "Pick a target", fields: [] },
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "waiting");
  assert.equal(d.needsInput.kind, "form");
  assert.equal(d.needsInput.detail, "Pick a target");
  assert.equal(r.milestones.filter((m) => m.kind === "needs-input").length, 1);
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

test("a rejected permission is a denial warning, never a resume", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("permission.asked", {
    sessionID: "ses_c", action: "external_directory", resources: ["/etc/**"],
  }));
  advance(40_000);
  const r = observe(state, event("permission.replied", {
    sessionID: "ses_c", requestID: "p1", reply: "reject",
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "warning");
  assert.equal(d.needsInput, null);
  assert.match(d.warning, /denied/);
  assert.equal(r.milestones.filter((m) => m.kind === "resume").length, 0);
  assert.equal(r.milestones.filter((m) => m.kind === "denied").length, 1);
  // later real activity resumes the row
  observe(state, contentTool("ses_c", "t9", "read", "running", { path: "a" }));
  assert.equal(d.status, "running");
  assert.equal(d.warning, null);
});

test("a 600s generation that ends normally is not marked dead", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, event("session.step.started", {
    sessionID: "ses_c", assistantMessageID: "m1",
  }));
  advance(650_000);
  // the step ends normally after the generation budget: activity refreshes
  observe(state, event("session.step.ended", {
    sessionID: "ses_c", assistantMessageID: "m1", finish: "stop",
    cost: 0.1, tokens: { input: 10, output: 5 },
  }));
  advance(6_000);
  tick(state, clock);
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "running");
  assert.equal(d.openStep, false);
  assert.equal(d.cost, 0.1);
  assert.equal(d.tokens.input, 10);
});

test("repeated content updates for one tool call never count as thrash", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  let thrash = 0;
  for (let i = 0; i < 5; i += 1) {
    const r = observe(state, contentTool("ses_c", "call_1", "shell",
      "running", { command: "pytest -q" }));
    thrash += r.milestones.filter((m) => m.kind === "thrash").length;
    advance(500);
  }
  assert.equal(thrash, 0);
  assert.equal(state.delegates.get("ses_c").loop.count, 1);
  // three genuinely distinct calls with the same target do flag thrash
  for (let i = 2; i <= 3; i += 1) {
    const r = observe(state, contentTool("ses_c", `call_${i}`, "shell",
      "running", { command: "pytest -q" }));
    thrash += r.milestones.filter((m) => m.kind === "thrash").length;
  }
  assert.equal(thrash, 1);
  assert.equal(state.delegates.get("ses_c").loop.count, DEFAULTS.loopRepeats);
});

test("the same call seen via tool.called and content.updated counts once", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  observe(state, toolCalled("ses_c", "call_1", { command: "git status" }));
  observe(state, contentTool("ses_c", "call_1", "shell", "running",
    { command: "git status" }));
  assert.equal(state.delegates.get("ses_c").loop.count, 1);
});

test("a vendor retry raises a warning milestone and never reads OK", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  const r = observe(state, event("session.status", {
    sessionID: "ses_c", type: "retry",
    status: { type: "retry", attempt: 2, message: "provider overloaded" },
  }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "warning");
  assert.match(d.warning, /retry/);
  assert.equal(r.milestones.filter((m) => m.kind === "retry").length, 1);
  // a repeated retry for the same attempt does not repeat the milestone
  const again = observe(state, event("session.status", {
    sessionID: "ses_c", type: "retry", status: { type: "retry", attempt: 2 },
  }));
  assert.equal(again.milestones.filter((m) => m.kind === "retry").length, 0);
});

test("a pre-existing child keeps its real start time", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_c", parentID: "ses_p", title: "pre-existing", agent: "planner",
    time: { created: 500_000 },
  });
  assert.equal(state.delegates.get("ses_c").startedAt, 500_000);
});

test("the marker sanitizes orchestrator/agent and round-trips", () => {
  const title = delegationTitle({
    orchestratorID: "ses_p\n]inject",
    agent: "impl]\n:er",
    task: "a]b c",
  });
  assert.ok(!title.includes("\n"), title);
  const parsed = parseDelegationTitle(title);
  assert.ok(parsed, title);
  assert.match(parsed.orchestratorID, /^[A-Za-z0-9_-]+$/);
  assert.match(parsed.agent, /^[A-Za-z0-9_.-]+$/);
  assert.equal(parseDelegationTitle("[delegate:] a: b"), null);
  assert.equal(parseDelegationTitle("[delegate:ses_p] : b"), null);
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

test("the shared health record round-trips and rejects junk", () => {
  const path = healthPath("/repo/");
  assert.equal(path, "/repo/.scratch/delegation-observer/health.json");
  assert.equal(healthPath(null), null);
  const parsed = parseHealthRecord(JSON.stringify({
    connection: "disconnected", degradation: "event stream ended", updated: 5,
  }));
  assert.deepEqual(parsed, {
    connection: "disconnected", degradation: "event stream ended", updated: 5,
  });
  assert.equal(parseHealthRecord("not json"), null);
  assert.equal(parseHealthRecord(""), null);
});

test("the TUI threshold seam merges env under forwarded options", () => {
  const withOption = createState(tuiConfig(
    { options: { delegationObserver: { stallSeconds: 9 } } },
    { DELEGATION_OBSERVER_STALL_SECONDS: "5" },
  ), now);
  assert.equal(withOption.config.stallSeconds, 9, "a forwarded option wins");
  const onlyEnv = createState(tuiConfig({}, { DELEGATION_OBSERVER_STALL_SECONDS: "5" }), now);
  assert.equal(onlyEnv.config.stallSeconds, 5);
  const fromDefaults = createState(tuiConfig({}, {}), now);
  assert.equal(fromDefaults.config.stallSeconds, DEFAULTS.stallSeconds);
});

test("the TUI config env source carries every TUI-relevant value", () => {
  const cfg = tuiConfig({}, {
    DELEGATION_OBSERVER_ENABLED: "false",
    DELEGATION_OBSERVER_STALL_SECONDS: "7",
    DELEGATION_OBSERVER_STALE_GRACE_SECONDS: "90",
    DELEGATION_OBSERVER_HEALTH_FILE: "/tmp/h.json",
    DELEGATION_OBSERVER_STATUS_FILE: "/tmp/s.json",
  });
  assert.equal(cfg.enabled, false);
  assert.equal(cfg.stallSeconds, 7);
  assert.equal(cfg.staleGraceSeconds, 90);
  assert.equal(cfg.healthFile, "/tmp/h.json");
  assert.equal(cfg.statusFile, "/tmp/s.json");
  // per-key precedence: a forwarded option wins; the env only fills gaps
  const kept = tuiConfig({
    options: {
      delegationObserver: {
        enabled: true, stallSeconds: 11, staleGraceSeconds: 45,
        healthFile: "/opt/h.json", statusFile: "/opt/s.json",
      },
    },
  }, {
    DELEGATION_OBSERVER_ENABLED: "0",
    DELEGATION_OBSERVER_STALL_SECONDS: "5",
    DELEGATION_OBSERVER_STALE_GRACE_SECONDS: "90",
    DELEGATION_OBSERVER_HEALTH_FILE: "/tmp/h.json",
    DELEGATION_OBSERVER_STATUS_FILE: "/tmp/s.json",
  });
  assert.equal(kept.enabled, true, "options win over env");
  assert.equal(kept.stallSeconds, 11);
  assert.equal(kept.staleGraceSeconds, 45, "options win over env for the grace window too");
  assert.equal(kept.healthFile, "/opt/h.json");
  assert.equal(kept.statusFile, "/opt/s.json");
  // invalid env values are ignored and gaps stay unfilled
  const invalid = tuiConfig({}, {
    DELEGATION_OBSERVER_ENABLED: "nonsense",
    DELEGATION_OBSERVER_STALL_SECONDS: "0",
    DELEGATION_OBSERVER_STALE_GRACE_SECONDS: "-5",
  });
  assert.equal(invalid.enabled, undefined);
  assert.equal(invalid.stallSeconds, undefined);
  assert.equal(invalid.staleGraceSeconds, undefined);
  // the TUI state built from that source actually uses the value
  const state = createState(tuiConfig({}, {
    DELEGATION_OBSERVER_STALE_GRACE_SECONDS: "90",
  }), now);
  assert.equal(state.config.staleGraceSeconds, 90);
});

test("a clock-classified failed row returns to running on real activity", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  advance((DEFAULTS.stallSeconds * 2 + 5) * 1000);
  tick(state, clock);
  assert.equal(state.delegates.get("ses_c").status, "failed");
  observe(state, contentTool("ses_c", "t1", "read", "running", { path: "a" }));
  const d = state.delegates.get("ses_c");
  assert.equal(d.status, "running");
  assert.equal(d.warning, null);
});

// --- liveness from evidence, not discovery (live defect, 2026-10-30) ------
//
// The TUI bootstraps from `session.list()`, which returns every child session
// the store has ever seen. Association alone is not evidence of life: a row is
// running only when the live active map says so or the session produced an
// event in this process. Quiet comes from the session's real last event, never
// from the observer's own boot clock.

test("a discovered session with no events is never running", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_old", parentID: "ses_parent", title: "historical task",
    agent: "implementer",
    time: { created: clock - 20 * 3_600_000, updated: clock - 19 * 3_600_000 },
  });
  const d = state.delegates.get("ses_old");
  assert.ok(d);
  assert.notEqual(d.status, "running");
  assert.equal(d.lastActivityAt, clock - 19 * 3_600_000,
    "quiet is the session's last event, not observer boot");
  assert.equal(d.stale, true);
  const res = tick(state, clock);
  assert.equal(res.milestones.length, 0, "a stale row never emits a milestone");
  assert.notEqual(d.status, "running");
});

test("only the live active map can make a discovered session running", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_idle", parentID: "ses_parent", title: "idle child",
    active: false, time: { created: clock - 3_600_000, updated: clock - 30_000 },
  });
  assert.notEqual(state.delegates.get("ses_idle").status, "running",
    "discovery alone is not liveness");

  associateSessionInfo(state, {
    id: "ses_live", parentID: "ses_parent", title: "live child",
    active: true, time: { created: clock - 3_600_000, updated: clock - 30_000 },
  });
  const live = state.delegates.get("ses_live");
  assert.equal(live.status, "running");
  assert.equal(live.stale, false);
  assert.equal(live.lastActivityAt, clock - 30_000);
});

test("the host live map is what promotes and demotes a discovered row", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_live", parentID: "ses_parent", title: "live child",
    time: { created: clock - 3_600_000, updated: clock - 30_000 },
  });
  assert.notEqual(state.delegates.get("ses_live").status, "running");
  markActive(state, "ses_live", true);
  const d = state.delegates.get("ses_live");
  assert.equal(d.status, "running");
  assert.equal(d.stale, false);
  markActive(state, "ses_live", false);
  assert.equal(d.status, "unknown", "losing the live map is not a stall claim");
});

test("the stale grace window is configurable and defaults to ten minutes", () => {
  assert.equal(DEFAULTS.staleGraceSeconds, 600);
  const recent = fresh();
  associateSessionInfo(recent, {
    id: "ses_recent", parentID: "ses_parent", title: "just started",
    time: { created: clock - 300_000, updated: clock - 120_000 },
  });
  const d = recent.delegates.get("ses_recent");
  assert.equal(d.status, "unknown");
  assert.equal(d.stale, false, "a child younger than the grace window stays visible");

  const tight = createState({ staleGraceSeconds: 60 }, now);
  associateSessionInfo(tight, {
    id: "ses_recent", parentID: "ses_parent", title: "just started",
    time: { created: clock - 300_000, updated: clock - 120_000 },
  });
  assert.equal(tight.delegates.get("ses_recent").stale, true);
});

test("an active-map row is never stall-classified without an observed event", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_live", parentID: "ses_parent", title: "live child",
    active: true, time: { created: clock - 3_600_000, updated: clock - 30_000 },
  });
  advance((DEFAULTS.stallSeconds * 2 + 5) * 1000);
  const quietTick = tick(state, clock);
  assert.equal(quietTick.milestones.length, 0,
    "the store's last event is not this process's observation clock");
  const d = state.delegates.get("ses_live");
  assert.equal(d.status, "running");
  assert.equal(d.warning, null);
  // once it really produces events, the documented watchdog semantics apply
  observe(state, contentTool("ses_live", "t1", "read", "completed", { path: "a" }));
  advance((DEFAULTS.stallSeconds + 1) * 1000);
  const warned = tick(state, clock);
  assert.equal(warned.milestones.filter((m) => m.kind === "stall").length, 1);
  assert.equal(d.status, "warning");
});

test("the live map read before association makes a live child running", () => {
  // This is the TUI bootstrap order: refreshActive() fills the map, then the
  // discovery list is associated, so a live-but-old child renders running on
  // its first paint instead of unknown until the next timer tick.
  const state = fresh();
  markActive(state, "ses_live", true);
  associateSessionInfo(state, {
    id: "ses_live", parentID: "ses_parent", title: "live child",
    time: { created: clock - 20 * 3_600_000, updated: clock - 19 * 3_600_000 },
  });
  const d = state.delegates.get("ses_live");
  assert.equal(d.status, "running");
  assert.equal(d.stale, false);
  assert.equal(d.provenance, "discovered");
});

test("a session terminal in the store never re-enters running", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_done", parentID: "ses_parent", title: "finished task",
    time: { created: clock - 72 * 3_600_000, updated: clock - 70 * 3_600_000 },
    outcome: "succeeded",
  });
  const d = state.delegates.get("ses_done");
  assert.equal(d.status, "completed");
  assert.equal(d.terminal?.outcome, "completed");
  assert.equal(tick(state, clock).milestones.length, 0);
  // a replayed busy/step event never revives a terminal row
  observe(state, event("session.status", {
    sessionID: "ses_done", type: "busy", status: { type: "busy" },
  }));
  observe(state, event("session.step.started", {
    sessionID: "ses_done", assistantMessageID: "m1",
  }));
  assert.equal(d.status, "completed");
  assert.equal(d.lastActivityAt, clock - 70 * 3_600_000);
});

// --- the real host contract: `outcome`, not a DB-column alias --------------
//
// 2.1.4 `SessionInfo.outcome` is `"succeeded" | "failed" | "interrupted"`
// (`@opencode/client` promise/generated/types.d.ts). Bootstrap must read that
// field; the alias normalisation is defence only.

test("a store-terminal row is completed at bootstrap from the real outcome field", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_done", parentID: "ses_parent", title: "recent completion",
    // recent: inside the grace window, so only the outcome can classify it
    time: { created: clock - 120_000, updated: clock - 60_000 },
    outcome: "succeeded",
  });
  const d = state.delegates.get("ses_done");
  assert.equal(d.status, "completed");
  assert.equal(d.terminal?.outcome, "completed");
  assert.equal(d.stale, true, "history, even when recent");
  assert.equal(d.lastActivityAt, clock - 60_000);
  assert.equal(tick(state, clock).milestones.length, 0);
});

test("the store outcome outranks the live map and cannot be demoted", () => {
  const state = fresh();
  // A finished session the map still calls running: the outcome wins.
  associateSessionInfo(state, {
    id: "ses_race", parentID: "ses_parent", title: "finished but busy",
    active: true,
    time: { created: clock - 120_000, updated: clock - 60_000 },
    outcome: "failed",
  });
  const d = state.delegates.get("ses_race");
  assert.equal(d.status, "failed");
  assert.equal(d.terminal?.outcome, "failed");
  // the live map saying "running" cannot resurrect it...
  markActive(state, "ses_race", true);
  assert.equal(d.status, "failed", "the map cannot revive a store-terminal row");
  // ...and a demotion cannot erase the outcome (the terminal guard owns it)
  markActive(state, "ses_race", false);
  assert.equal(d.status, "failed");
  assert.equal(d.terminal?.outcome, "failed");
  assert.equal(d.stale, true);

  // A row first seen live, whose outcome arrives on a later list refresh.
  associateSessionInfo(state, {
    id: "ses_late", parentID: "ses_parent", title: "outcome arrives late",
    active: true,
    time: { created: clock - 120_000, updated: clock - 30_000 },
  });
  const late = state.delegates.get("ses_late");
  assert.equal(late.status, "running");
  associateSessionInfo(state, {
    id: "ses_late", parentID: "ses_parent", title: "outcome arrives late",
    time: { created: clock - 120_000, updated: clock - 30_000 },
    outcome: "interrupted",
  });
  assert.equal(late.status, "failed", "a later list refresh terminalizes the row");
  markActive(state, "ses_late", true);
  assert.equal(late.status, "failed");
  markActive(state, "ses_late", false);
  assert.equal(late.status, "failed", "the late outcome survives both map answers");
});

test("a recent completed child is never revived by later events", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_recent", parentID: "ses_parent", title: "just finished",
    time: { created: clock - 120_000, updated: clock - 30_000 },
    outcome: "succeeded",
  });
  const d = state.delegates.get("ses_recent");
  const result = observe(state, event("session.status", {
    sessionID: "ses_recent", type: "busy", status: { type: "busy" },
  }));
  assert.equal(result.milestones.length, 0);
  const usage = observe(state, event("session.usage.updated", {
    sessionID: "ses_recent", cost: 0.1, tokens: { input: 1, output: 1 },
  }));
  assert.equal(usage.milestones.length, 0);
  assert.equal(d.status, "completed");
  assert.equal(d.stale, true);
});

test("the first real event refreshes the observation clock (F2)", () => {
  // Every first event that does not itself touch must still reset the clock:
  // a 19 h-old store timestamp is not this process's quiet time.
  const firsts = [
    ["session.created", (sid) => event("session.created", { sessionID: sid, title: "x" })],
    ["session.renamed", (sid) => event("session.renamed", { sessionID: sid, title: "renamed" })],
    ["session.usage.updated", (sid) => event("session.usage.updated", {
      sessionID: sid, cost: 0.01, tokens: { input: 1, output: 1 },
    })],
    ["text-only content", (sid) => event("session.message.content.updated", {
      sessionID: sid, messageID: "m1",
      content: [{ type: "text", text: "working" }],
    })],
    ["reply without pending input", (sid) => event("permission.replied", {
      sessionID: sid, requestID: "p1", reply: "once",
    })],
  ];
  for (const [label, make] of firsts) {
    const state = fresh();
    associateSessionInfo(state, {
      id: "ses_old", parentID: "ses_parent", title: "historical",
      time: { created: clock - 20 * 3_600_000, updated: clock - 19 * 3_600_000 },
    });
    advance(1_000);
    observe(state, make("ses_old"));
    const d = state.delegates.get("ses_old");
    assert.equal(d.provenance, "observed", label);
    assert.equal(d.lastActivityAt, clock, `${label}: the clock is the observation time`);
    assert.equal(d.stale, false, label);
    // no false stall/dead immediately after promotion
    advance(5_000);
    const res = tick(state, clock);
    assert.equal(res.milestones.length, 0, `${label}: no stall right after promotion`);
    assert.notEqual(d.status, "failed", label);
    // the real window still applies afterwards
    advance((DEFAULTS.stallSeconds + 1) * 1000);
    const warned = tick(state, clock);
    assert.equal(warned.milestones.filter((m) => m.kind === "stall").length, 1, label);
  }
});

test("a 19 h-old discovered row plus one usage event never stalls or dies", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_old", parentID: "ses_parent", title: "historical",
    time: { created: clock - 20 * 3_600_000, updated: clock - 19 * 3_600_000 },
  });
  assert.equal(state.delegates.get("ses_old").stale, true);
  advance(2_000);
  observe(state, event("session.usage.updated", {
    sessionID: "ses_old", cost: 0.2, tokens: { input: 5, output: 2 },
  }));
  const res = tick(state, clock);
  assert.equal(res.milestones.length, 0);
  assert.equal(state.delegates.get("ses_old").status, "running");
  assert.equal(state.delegates.get("ses_old").warning, null);
});

// --- archived is final -----------------------------------------------------

test("an archived session is stale even when the live map calls it running", () => {
  const state = fresh();
  // the host's live map really does say running for this id
  markActive(state, "ses_arch", true);
  associateSessionInfo(state, {
    id: "ses_arch", parentID: "ses_parent", title: "archived child",
    active: true,
    time: { created: clock - 120_000, updated: clock - 60_000, archived: clock - 30_000 },
  });
  const d = state.delegates.get("ses_arch");
  assert.equal(d.archived, true);
  assert.equal(d.stale, true, "archived outranks live");
  markActive(state, "ses_arch", true);
  assert.equal(d.stale, true, "the map cannot revive an archived row");
  assert.notEqual(d.status, "running");
  observe(state, contentTool("ses_arch", "t1", "read", "completed", { path: "a" }));
  assert.equal(d.stale, true, "events cannot revive an archived row");
  assert.equal(tick(state, clock).milestones.length, 0);
});

test("an archived row never emits a start milestone on a replayed create", () => {
  // Reviewer repro: discovered-live row (so `associate` did not pre-mark
  // `start`) -> archive -> replayed session.created must emit nothing.
  const state = fresh();
  markActive(state, "ses_arch", true);
  associateSessionInfo(state, {
    id: "ses_arch", parentID: "ses_parent", title: "archived child",
    time: { created: clock - 120_000, updated: clock - 60_000 },
  });
  const d = state.delegates.get("ses_arch");
  assert.equal(d.status, "running");
  assert.equal(d.emitted.has("start"), false, "the live branch did not pre-mark start");
  advance(1_000);
  observe(state, event("session.archived", { sessionID: "ses_arch" }));
  assert.equal(d.archived, true);
  advance(1_000);
  const replay = observe(state, event("session.created", {
    sessionID: "ses_arch", parentID: "ses_parent", title: "archived child",
  }));
  assert.deepEqual(replay.milestones, [], "no synthetic start for archived history");
  const renamed = observe(state, event("session.renamed", {
    sessionID: "ses_arch", title: "renamed child",
  }));
  assert.deepEqual(renamed.milestones, []);
  assert.equal(d.archived, true, "the replay does not un-archive the row");
});

test("archive after start hides an observed row, unarchive restores it", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  const d = state.delegates.get("ses_c");
  assert.equal(d.stale, false);
  advance(1_000);
  observe(state, event("session.archived", { sessionID: "ses_c" }));
  assert.equal(d.archived, true);
  assert.equal(d.stale, true);
  // the clock refresh must not resurrect the archive on the next tick
  advance(5_000);
  tick(state, clock);
  assert.equal(d.stale, true, "archived outranks observed provenance");
  advance(1_000);
  const archivedEvent = observe(state, contentTool("ses_c", "t1", "read", "running", { path: "a" }));
  assert.equal(archivedEvent.milestones.length, 0, "an archived row emits nothing");
  assert.equal(d.status, "running"); // status untouched, but the row is hidden
  advance(1_000);
  observe(state, event("session.unarchived", { sessionID: "ses_c" }));
  assert.equal(d.archived, false);
  assert.equal(d.stale, false);
});

// --- timestamps: absent, created-only, clock skew --------------------------

test("missing and skewed timestamps never fabricate a live clock", () => {
  const state = fresh();
  // no time at all: no evidence -> stale immediately, quiet unknown
  associateSessionInfo(state, { id: "ses_none", parentID: "ses_parent", title: "no time" });
  const none = state.delegates.get("ses_none");
  assert.equal(none.lastActivityAt, null);
  assert.equal(none.startedAt, null);
  assert.equal(none.stale, true);
  assert.equal(tick(state, clock).milestones.length, 0);

  // created only: inside the grace window it stays visible as unknown
  associateSessionInfo(state, {
    id: "ses_created", parentID: "ses_parent", title: "created only",
    time: { created: clock - 60_000 },
  });
  const created = state.delegates.get("ses_created");
  assert.equal(created.stale, false);
  assert.equal(created.status, "unknown");
  assert.equal(created.lastActivityAt, null);

  // a future timestamp is not negative quiet and is not stale
  associateSessionInfo(state, {
    id: "ses_future", parentID: "ses_parent", title: "clock skew",
    time: { created: clock + 60_000, updated: clock + 30_000 },
  });
  const future = state.delegates.get("ses_future");
  assert.equal(future.stale, false);
  assert.equal(tick(state, clock).milestones.length, 0);
});

test("a replayed create never emits start or terminal for store-terminal history", () => {
  const state = fresh();
  associateSessionInfo(state, {
    id: "ses_done", parentID: "ses_parent", title: "finished",
    time: { created: clock - 120_000, updated: clock - 60_000 },
    outcome: "succeeded",
  });
  const d = state.delegates.get("ses_done");
  assert.equal(d.emitted.has("start"), true);
  assert.equal(d.emitted.has("terminal"), true);
  const created = observe(state, event("session.created", {
    sessionID: "ses_done", parentID: "ses_parent", title: "finished",
  }));
  assert.equal(created.milestones.length, 0);
  const terminal = observe(state, event("session.execution.succeeded", {
    sessionID: "ses_done",
  }));
  assert.equal(terminal.milestones.length, 0);
  assert.equal(d.status, "completed");
});

test("a name-less tool.called waits for the content update to label the call", () => {
  const state = fresh();
  observe(state, child("ses_c", "ses_p"));
  const called = { type: "session.tool.called", data: {
    sessionID: "ses_c", id: "call_1", input: { command: "echo LOOP" },
  } };
  const r = observe(state, called);
  assert.equal(r.milestones.filter((m) => m.kind === "first-tool").length, 0);
  advance(DEFAULTS.milestoneMinIntervalSeconds * 1000 + 1);
  const labelled = observe(state, contentTool("ses_c", "call_1", "shell",
    "running", { command: "echo LOOP" }));
  assert.equal(labelled.milestones.filter((m) => m.kind === "first-tool").length, 1);
  assert.match(labelled.milestones[0].text, /shell: echo LOOP/);
  assert.equal(state.delegates.get("ses_c").loop.count, 1);
});
