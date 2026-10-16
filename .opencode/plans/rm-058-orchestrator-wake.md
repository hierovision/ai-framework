---
slug: rm-058-orchestrator-wake
title: Wake the orchestrator on subagent terminal state; worktree-safe dispatch; per-dispatch permission profile
status: draft
created: 2026-10-15
revised: [2026-10-15, 2026-10-16]
related: [rm-056-eval-lane-fallback]
---

# Plan: rm-058-orchestrator-wake

## Owner-frozen policy (user directive 2026-10-12, restated 2026-10-15 — binding on this plan)

1. The owner can interact with the orchestrator while a background subagent
   runs; the child stays detached (setsid) and the orchestrator's turns stay
   free. This already works and must not regress.
2. A terminal-state child (success / failure / abort) informs the orchestrator
   WITHOUT an owner ping. The orchestrator conversation is the ONLY sink —
   no email, no phone, no external push channel, no external service.
3. The wake path must respect AGENTS.md rule 1 (never
   `opencode run --continue` from a parent session that shares the session
   store; no parent-session store corruption from sibling processes).
4. Worktree-safe dispatch: any child that touches branches runs in its OWN git
   worktree, so the parent/agent working tree stays on main. This removes the
   entire failure class seen live 2026-10-13 (child commits landing on the
   wrong parent branch; parent commits landing on a child branch). The interim
   parent rule ("no parent git commit/switch while a child dispatch is live")
   is replaced by this mechanism.
5. Per-dispatch permission profile: the dispatch contract carries a
   least-privilege default profile per agent class so recon reads never die on
   the first turn. Chronic instance (docs/roadmap-detail/RM-058.md,
   2026-10-14): three dispatches died mid-recon on
   `permission denied: external_directory` for `~/repos/temp/*`,
   `~/.config/opencode/*`, `~/.local/share/opencode/*`, each recoverable only
   by a manual `--allow-dirs` retry.
6. A dispatch is NEVER declared "running" before it actually runs; an
   orchestrator status claim is gated on a real poll of the child's durable
   state.

## Goal / Approach

One sentence: when a detached subagent dispatch reaches a terminal state
(success / failure / abort), the orchestrator conversation receives a wake
report within 5 minutes without the owner pinging, while every dispatch runs
branch-safe in its own git worktree with a least-privilege permission profile.

Technical strategy: keep the detached-dispatch model unchanged and add
(1) a detached **completion-observer** (`scripts/observe_completion.py`,
spawned by the dispatcher when `--wake-to <orchestrator-session-id>` is
given) polling the ONE durable supervision surface — the heartbeat file teed
by `dispatch_agent.py` plus the run-log record it already emits
(`skills/observing-runs`, `scripts/log_run.py`) — no event-hook parallel
surface; (2) a wake delivery sent **through the orchestrator's own
server** via `opencode run --attach <wake-url> --session <orchestrator>
--agent <orchestrator-agent> --format json <wake-text>` so the live TUI
renders it (the 2026-10-15 smoke proved the bare `--session` form runs a
non-rendered ghost turn), gated on the orchestrator session being quiescent
(no tool in flight and no unclosed assistant step per `watch_agent`'s
predicates) with bounded retry;
(3) `--worktree <name>` on `dispatch_agent.py` (branch `dispatch/<name>`,
worktree at `.scratch/worktrees/<name>` under AGENTS.md rule 3) so the parent
tree physically cannot leave main; (4) a per-agent-class permission profile
file (`scripts/dispatch-profiles.json`) merged with explicit `--allow-dirs`;
and (5) the status-claim gate expressed as heartbeat line-ownership: the
observer appends its own tagged lines and the orchestrator claims states only
from polled heartbeat evidence, never by assertion.

## Design decisions (each with evidence)

### D1. Completion-observer = watchdog loop, NOT an opencode event hook

Evidence from the installed opencode (1.18.18, probed 2026-10-15):

- Hooks are TypeScript plugins, not config keys; plugin events include
  `session.idle` (`reference/opencode-integration.md`, dated). A plugin can
  observe a child session's idle, but the same reference records the
  hook path as aspirational and not attributable, and a plugin runs
  **inside each opencode process** — it cannot gate the wake on rule-1
  quiescence of the *orchestrator* session, cannot bound the 5-minute SLA,
  and cannot be tested hermetically without executing plugin code.
- The dispatcher already writes a durable, exactly-once terminal envelope:
  one `DONE ok` / `BLOCKED <detail>` heartbeat line (every outcome branch,
  in a `finally`) and exactly one `kind=agent` run-log record
  (`scripts/log_run.py`). This is the same durable surface the run log
  writes — the observer consumes it instead of inventing a parallel one.
- A polling loop with a 30 s interval meets the 5-minute SLA with margin and
  degrades honestly exactly where `watch_agent.py` already degrades
  (heartbeat-only when the DB is absent).

Decision: watchdog loop. `session.idle` is recorded in Open Questions as the
future alternative, not implemented.

**Terminal signal definitions** (what "terminated" means, where it lives):

| Outcome | Primary signal (disk) | Corroboration |
|---|---|---|
| success | heartbeat file terminal line `DONE ok` (dispatcher-written, exactly one) | run-log record `kind=agent, outcome=success`; `watch_agent.has_terminal_result(parts, running)` true for the child session in the DB when available |
| failure | heartbeat terminal line `BLOCKED <detail>` + run-log record `outcome=failure` (contract-invalid result; denial is named) | DB completion predicate |
| abort / error | heartbeat terminal `BLOCKED <detail>` + run-log record `outcome=error` / `stopped`, or — when the dispatcher dies before its terminal line — the liveness window: no heartbeat/session event for 2× the stall window with no tool in flight (`watch_agent` DEAD semantics) | DB |

Correlation key between the heartbeat and the run-log record: the heartbeat
file is the dispatch's identity (task name in its `# progress:` header); the
dispatcher prints `run_log=<path>` on completion. The observer matches the
latest `kind=agent` record whose timestamp is within the child's heartbeat
window and whose `agent` matches the dispatch. Corroboration is best-effort;
the dispatcher-written terminal heartbeat line is authoritative — the child
process cannot write it (dispatcher owns that file region; cross-check only
hardens the verdict when the DB is present).

### D2. The wake path (revised 2026-10-16: server-reachable orchestrator)

Who writes what / who reads what / what triggers the turn. Supersedes the
2026-10-15 draft steps 3–5 after the live smoke proved the bare
`opencode run --session` vehicle invisible to a live TUI (History,
2026-10-15). Probe evidence: opencode 1.19.1, throwaway session
`ses_ebb7770e5ffeSsiBTw1KzDydfz` and TUI-on-`4568`, 2026-10-16.

Unchanged from the 2026-10-15 draft (and implemented): the dispatcher spawns
`scripts/observe_completion.py` detached (`start_new_session=True`) right
after the child's `session_id=` prints (its plumbing flags incl.
`--child-session/--result/--logs-dir/--worktree/--branch` per the History
deviation note), and the observer polls the heartbeat + run-log + read-only
DB every 30 s (D1, D5 line ownership).

**Evidence for every claim below (probes P1–P8, 2026-10-16):**

- P3/P4/P8 — `opencode run --attach http://127.0.0.1:<port> --session <sid>
  --agent <agent> --format json "<text>"` exits **0 in ≤ 15 s** (observed
  3 s / 14 s / 3 s) after streaming one early event (`step_start`) whose
  payload names the target sessionID; **the turn then runs on the attached
  server** (after client exit, the session's export shows the appended user
  message and the assistant reply). Delivery is fast because generation is
  server-side — the wake subprocess never holds a generation.
- P8 — with a TUI launched as `opencode --port 4568 --session <sid>` the
  process **listens** (curl `GET /session` → 200), and the attach-delivered
  wake **rendered live in the TUI**: the pty capture
  (`.scratch/rm-058-vehicle-design/tui.capture`) contains the injected
  `DISPATCH WAKE …` text with the running-turn indicator; the assistant turn
  recorded `agent=curator` / the agent's own model binding.
- P4 — agent semantics are **not inherited from the session**: without
  `--agent`, the appended message records `agent=build` (opencode's default
  primary agent — the exact 2026-10-15 ghost-turn shape); with
  `--agent curator` both the user message and the assistant turn record
  `agent=curator` and the agent's own model binding (glm-5.3-flash). So the
  wake must force the agent explicitly, and `--model` is dropped (the
  agent's binding decides — the draft's `--model <orchestrator-binding>` is
  removed).
- P1 — `--attach` against an unreachable port fails **in ≤ 1 s, rc=1**
  (error surfaced, no turn run) — the current 180 s hang class is
  structurally gone with the attach vehicle.
- P2 — a server (headless or TUI) writes **no port/state file**
  (`~/.local/share/opencode/`, `~/.local/state/opencode/` carry no
  server-port artifact), so the URL cannot be discovered from disk; it must
  travel with the dispatch contract (below).
- Default TUI launch (no `--port`) holds no listening socket (the 2026-10-15
  `ss` diagnosis); only an explicit non-zero `--port` establishes the HTTP
  server the wake needs.

The revised design:

1. **Launch workflow (owner, one-line change).** The owner launches the
   orchestrator TUI on a known port with the wake URL in the environment:
   `OPENCODE_WAKE_URL=http://127.0.0.1:4096 opencode --port 4096`.
   (Equivalent-but-two-process alternative: `opencode serve --port 4096` +
   `opencode attach http://127.0.0.1:4096`; rejected for v1 — one process,
   one env is simpler, and `attach` is interactive.) Trade-off named: the
   fixed port must be free — a collision fails visible at TUI launch, and
   the owner picks a stable high port once.
2. **Dispatch contract additions.** `--wake-to <sid>` gains two companions:
   `--wake-url <url>` (resolved from `OPENCODE_WAKE_URL` when omitted; the
   worker context inherits the env from the TUI launch, and the orchestrator
   may also pass the flag explicitly) and `--wake-agent <name>` (the agent
   the orchestrator session runs as — required, preflight `exit 2` when
   `--wake-to` is given without it, because P4 shows the alternative is a
   `build`-agent ghost). No state file is read (P2: none exists).
3. **Delivery (attach vehicle).** The observer delivers:
   `opencode run --attach <wake-url> --session <orchestrator-sid> --agent
   <wake-agent> --format json "<wake-text>"` — still an explicit session id,
   never `--continue` (rule 1 unchanged). The subprocess streams stdout;
   **acceptance proof** = the first streamed event naming the orchestrator
   sessionID, or a client exit 0 (whichever first). On acceptance proof the
   observer appends exactly one terminal `WAKE <outcome>` heartbeat line and
   stops — it does NOT wait for wake-turn generation (server-side, ~3 m15 s
   observed 2026-10-15), and it does not kill the accepted client early: it
   lets the client exit within `WAKE_SUBPROCESS_TIMEOUT`. No `--dir` on the
   wake (P4 verified: the client ran in the ai-framework cwd, the session
   lives in another project — the id identifies it server-side). If the
   client neither streams evidence nor exits by the timeout, the attempt
   failed and is retried per step 5.
4. **No attach target ⇒ immediate honest deferral (no subprocess).** If
   `--wake-url` cannot be resolved (not given, env unset), the observer
   still supervises the child, but at terminal state writes exactly one
   `WAKE_DEFERRED <outcome> reason=no-attach-target` and stops — it never
   spawns the legacy `--session` form (the ghost vehicle). The durable wake
   text already sits in the heartbeat and the run-log record; the
   orchestrator's next turn reads it (D2 step 6 semantics below).
5. **Bounded retry / escalation.** If delivery fails (rc≠0, no acceptance
   evidence within `WAKE_SUBPROCESS_TIMEOUT`, deadline pressure), the
   observer waits one poll interval and retries until `WAKE_DEADLINE`
   (default 300 s, unchanged — the 5-minute SLA measures *delivery*, not
   generation), then writes exactly one
   `WAKE_DEFERRED <outcome> reason=<detail>` and stops. While the owner is
   interacting, the gate below holds; wake-at-quiescence or
   wake-deferred-at-deadline, nothing hangs.
6. **Orchestrator turn semantics (unchanged from the 2026-10-15 draft):**
   the wake text is the D7 block; the orchestrator turn reports to the
   owner in ≤ 2 turns, lands the worktree branch, runs cleanup; the
   orchestrator conversation is the only sink; nothing is sent anywhere
   else.

**Rule-1 / concurrency gate (revised — the 2026-10-15 latent finding is
folded in).** The observer delivers only when the orchestrator session is
quiescent, where quiescent means ALL of:

- **No tool part in flight** — `watch_agent.analyze_session`'s running
  predicate (unchanged);
- **No unclosed assistant step** — the newest assistant message's step-part
  sequence must be *closed* (its last step part is `step-finish`). A
  trailing `step-start` means a model call is mid-generation: no tool is
  running, `time_updated` only advances at `step-finish`, and the old
  predicate read such a turn as quiescent (the 2026-10-15 live smoke's
  3m15s call is the instance). Computed in the observer from the already
  loaded parts — no new surface, no RM-059 vocabulary;
- **`time_updated` stable across two polls** — retained as a belt, no
  longer load-bearing alone.

With the attach vehicle the gate's job narrows to "do not inject a user
message into a turn the owner owns"; the SQLite-writer race of the draft
(two servers writing one store) disappears — wake writes and TUI writes go
through the one server. The gate stays because the owner-frozen policy 1
(interaction mid-dispatch) must not regress. Delivery is now ≤ 15 s, so the
gate costs almost nothing.

Concurrent-interaction safety: the wake never uses `--continue` (rule 1);
it targets an explicit session id through the session's own server, gated
on quiescence, so a wake write never lands inside an in-flight orchestrator
turn, and the owner's mid-dispatch interaction happens through the same
conversation with turns it already owns.

### D3. Worktree-safe dispatch

- New flag `--worktree <name>` on `dispatch_agent.py` (optional; profile
  default per D4). Fresh dispatch: verify the parent repo checkout is on
  `main` (`git -C <repo> symbolic-ref HEAD` — refuse with exit 2 otherwise,
  so a dispatch never runs from a detached branch of the parent); run
  `git worktree add --branch dispatch/<name> .scratch/worktrees/<name>`
  from the repo root; launch `opencode run --dir <worktree-path>` instead of
  the invoking cwd. A `--session` resume with the same `--worktree <name>`
  reuses the existing worktree (append semantics; a missing/locked worktree
  exits 2 before opencode launches).
- Branch naming: `dispatch/<name>` (name = the task slug the dispatcher
  heartbeat already carries). The parent's tree cannot leave `main`: the
  child runs with `--dir` pointed at the worktree, so the child's commits,
  branch switches, and PR operations are physically confined to the
  worktree checkout. The 2026-10-13 failure class (child commits on the
  parent's branch; parent commits on a child branch) is removed by
  construction, not by discipline.
- What replaces the interim rule: the parent rule "no parent git
  commit/switch while a child dispatch is live" (recorded live 2026-10-13)
  is replaced by: the parent may commit on `main` freely while a
  `--worktree` dispatch is live; the child's landing happens after
  completion, on the orchestrator's side, by cherry-pick / merge of
  `dispatch/<name>` from a clean, verified worktree — the same landing
  authority the orchestrator already holds ("anything uncommitted on the
  branch only; the orchestrator lands",
  `reference/subagent-supervision.md` §3).
- Cleanup: the observer's terminal wake text names
  `.scratch/worktrees/<name>` and `dispatch/<name>`. The orchestrator
  removes them after landing:
  `git worktree remove .scratch/worktrees/<name>` +
  `git branch -D dispatch/<name>` (a dirty worktree blocks — never forced —
  and the leftover is reported in the wake). The heartbeat final line
  records the cleanup. No background reaper process is added.
- The edit surface in `scripts/dispatch_agent.py` is: one flag, one
  worktree-setup function (~40 lines, invoked between preflight and launch),
  and one `--dir` substitution in `opencode_argv`. No other behavior changes
  without `--worktree`.

### D4. Per-dispatch permission profile

- Shape: `scripts/dispatch-profiles.json` — a map of profile name →
  `{allow_dirs: [external paths], worktree: bool, timeout: int}` with
  a `default` profile. Profile names match the agent classes the framework
  dispatches: `architect`, `implementer`, `reviewer`, `council`, `planner`,
  `test`, `meta-loop` (compound keys are resolved by longest-prefix match on
  the agent name, e.g. `council-architecture` → `council`,
  `vision-critic-fast` → `reviewer`; an exact agent-key entry wins).
  Least-privilege defaults for v1 (read roots only; each new path class is
  justified by the 2026-10-14 chronic instance):
  - all classes: `.scratch/` is inside the working tree — no grant needed.
  - recon classes (`architect`, `reviewer`, `council`, `planner`):
    `$HOME/repos`, `$HOME/.config/opencode`, `$HOME/.local/share/opencode`
    (the three denied paths); grant file keys remain the existing
    `<abs-dir>/** -> allow` shape.
  - `implementer`, `test`: `$HOME/repos` only (framework work touches
    sibling consumer repos; config/session runs are not build inputs).
- Declared where: the JSON file under `scripts/` (framework-owned, diffable,
  citable), NOT agent frontmatter — opencode parses agent frontmatter and an
  unknown key is a compatibility risk (validated layout,
  `reference/opencode-integration.md`). NOT a dispatch flag default only —
  flags stay for overrides.
- Merge rule: profile grants are the **default**; explicit `--allow-dirs`
  entries are added on top (union; same `<abs>/** -> allow` entries,
  `setdefault` already wins for caller-supplied settings in
  `permission_config`). The applied profile name and the unioned dirs are
  written into the dispatcher envelope line and echoed as the pre-launch
  line `profile=<name> allow_dirs=<n>` so the expansion is visible before
  launch.
- `--profile none` disables defaults (exact current behavior kept for
  hermetic A/B). `--worktree` also honors the profile's `worktree: true`
  unless overridden on the command line.
- Denial without a silent first-turn death: already classified
  (`permission_denied` → `permission denied: <tool> <path>` — AC13 of the
  visibility pass) and now **additionally** surfaced pre-flight: the deny
  happens on a write to an ungranted path; dispatches with a profile still
  name the denial in the terminal heartbeat `BLOCKED` line and the run-log
  `detail`, and the wake carries it — the orchestrator is told which path
  was denied and whether a profile exists that covers it. No silent empty
  result.

### D5. The status-claim gate (poll-gated, not asserted)

Enforcement lives in the heartbeat line-ownership contract + the observer's
state machine, all on the one durable surface:

- `scripts/observe_completion.py` appends exactly these heartbeat lines, in
  order: one `SURVEY running` after the first poll that finds real child
  evidence (≥1 child-owned heartbeat line beyond the dispatcher envelope, or
  the child session row present in the DB with ≥1 part), then a terminal
  `WAKE <outcome>` or `WAKE_DEFERRED <outcome> reason=<detail>` line (the
  `reason=` token is part of the tag's format since the 2026-10-16
  amendment: `no-attach-target`, `deadline`, or the delivery failure
  detail). It never writes
  `SURVEY running` from the launch record alone.
- The dispatch contract adds one rule to
  `reference/subagent-supervision.md` §2's line-ownership block: **an
  orchestrator may claim a dispatch `running` / `complete` / `failed` only
  from polled durable lines** (heartbeat child lines, `SURVEY` / `WAKE`
  observations, `watch_agent --json` output, or the run-log record) — never
  from the launch command itself. The launch envelope proves intent (`START`
  before launch); `SURVEY running` is the first proof the child actually
  runs; `WAKE` / heartbeat terminal `DONE`/`BLOCKED` is the only completion
  proof. This closes today's failure class (a "running" claim from the
  launch echo with a dead child).
- Not a separate state file: the heartbeat is the single supervision surface
  already parsed by `watch_agent.read_heartbeat` (unknown tags parse as RAW
  entries without harming the parser — verified behavior of the regex
  fallback); the observer's tags re-use that tolerance.

### D6. The RM-059 seam (named interface, no collision)

- RM-058's completion-observer consumes ONLY:
  `watch_agent.read_heartbeat`, `watch_agent.db`/`find_session`/
  `load_parts`/`analyze_session`/`has_terminal_result` (completion
  predicate + the in-flight running list), and `watch_agent.now_iso`. It
  **never calls `watch_agent.verdict`** and never emits the strings
  STALLED / DEAD / BLOCKING / OK / WARN — the liveness vocabulary is
  RM-059's.
- Quiet-but-non-terminal is `AWAITING` (the observer's own classification):
  from the 2026-10-12/13 evidence (STALLED false-positive on advancing
  `step_start` / `step_finish` streams), the observer treats any heartbeat
  or stream delta in the window as activity and defers the *verdict* on
  quiescence entirely to RM-059's state-delta-gated predicate. The
  interface contract, stated as one line in
  `reference/subagent-supervision.md` (the wake section): the completion
  gate = a heartbeat terminal line in the run-log-written durable surface;
  the intervention gate (stall verdict) = RM-059, owner of
  `watch_agent.verdict`. Two different questions, two different emitters,
  one shared durable surface.

### D7. Wake text format (the dispatch contract's wake clause)

The wake text is a fixed-shape block so the orchestrator turn can act on it
without re-deriving state:

```
DISPATCH WAKE <agent> <outcome=success|failure|error|aborted>
task=<heartbeat # progress: line>  child=<session_id>
result=<path>  log=<run-log path>  heartbeat=<path>
detail=<one line, failure/aborted only | omitted on success>
worktree=<path> branch=<dispatch/<name>>  # only when --worktree was used
landing=<not-yet|done>; cleanup needed: <worktree + branch | none>
```

The wake turn's job: report to the owner in ≤ 2 turns, land the worktree
branch if the brief authorized it, run cleanup, emit nothing to the
run log itself (the record already exists — the orchestrator turn is a
reader here, not a run).

## Acceptance Criteria

1. **Wake-on-success within SLA, owner-ping-free, via the attach vehicle.**
   A hermetic contract test (`python3 scripts/test_observe_completion.py`,
   watch 5) runs a stub dispatch that terminates success with `--wake-to`
   pointing at an orchestrator session in a fixture DB
   (`OPENCODE_DB_PATH`) and a fixture `--wake-url`; the test's stub
   `opencode` records the exact argv and asserts it contains `--attach
   <wake-url>`, `--session <orchestrator-sid>`, `--agent <wake-agent>`,
   `--format json`, and never `--continue` and never `--model`. The stub
   streams one event line naming the orchestrator sessionID then exits 0;
   within 300 s of the heartbeat terminal line the test records exactly one
   delivery attempt, and the heartbeat ends with exactly one `WAKE
   success` line — asserted in `scripts/test_observe_completion.py`.
2. **Wake enumerates failure and abort.** Same harness with a
   contract-invalid stub result (markers missing) and with a killed
   stub dispatcher (no terminal line, liveness window short): the wake
   received carries `outcome=failure`+detail naming the missing markers, and
   `outcome=aborted`+detail naming the liveness basis — asserted in the same
   test file.
3. **Rule-1 gate, generation-safe (revised).** Two hermetic cases in
   `scripts/test_observe_completion.py`:
   - *In-flight tool:* while the fixture orchestrator session shows a tool
     part in flight (in-flight predicate true), the observer issues zero
     wake invocations across the window; after a part lands
     (`has_terminal_result` shape) the wake is issued once exactly.
   - *Mid-generation (the 2026-10-15 latent finding):* a fixture
     orchestrator session whose newest assistant message ends with an open
     `step-start` part, no tool in flight, and `time_updated` stable across
     two polls reads **NOT quiescent** (zero deliveries); after the
     fixture's `step-finish` part lands, exactly one delivery is issued.
     Asserted in the same test file.
4. **Deadline / no-target escalation is durable, not silent.** Three
   hermetic cases, each writing exactly one final `WAKE_DEFERRED <outcome>
   reason=<detail>` heartbeat line and exiting (asserted in the same test
   file): (a) the deadline forced short with the orchestrator session
   continuously busy — the stub received zero accepted deliveries, reason
   names the gate; (b) no `--wake-url` resolvable — the stub received zero
   invocations at all, `reason=no-attach-target`, written at the first
   terminal poll without spawning `opencode`; (c) the stub exits 1 (server
   refuses) on every attempt until deadline — retries bounded by the
   deadline, `reason=` names the refusal.
5. **Worktree safety (the 2026-10-13 class).** In a fixture git repo
   squashed to the plan's shape, a stub dispatch with `--worktree t1`
   commits a file "on a child branch": after
   `python3 scripts/test_dispatch_agent.py`'s worktree suite, the parent
   checkout's HEAD is unchanged still on `main` with zero new commits, the
   commit lands on `dispatch/t1` inside `.scratch/worktrees/t1` only, and a
   dispatch launched while the parent is not on `main` exits 2 before
   opencode launches (no session created). Red-first rehearsal: the suite
   must fail (parent-branch mutation observed) when the same stub runs
   WITHOUT `--worktree` — the pre-fix reproduction of the 2026-10-13
   incident.
6. **Permission profile (the 2026-10-14 chronic instance).** For each of the
   three recorded denied roots (`~/repos/temp/*`, `~/.config/opencode/*`,
   `~/.local/share/opencode/*`), the recon-class profile (`architect`) and
   `test` class result in an OPENCODE_CONFIG_CONTENT environment handed to
   the stub whose `permission.external_directory` map contains
   `<abs>/** -> allow` for the unioned dirs (profile + explicit
   `--allow-dirs`), with explicit entries winning on overlap — hermetic
   stub asserts the env in `scripts/test_dispatch_agent.py`. The denial
   classification (a brief that presents denied-path
   `external_directory` text) still names the denial in `BLOCKED` detail
   and the run-log `detail`, never an empty result.
7. **No status claim without a poll.** The heartbeat line set produced by a
   full stub dispatch is inspectable: before any child-owned line exists,
   zero `SURVEY running` lines are present; after the first child-owned
   line, exactly one; terminal `WAKE` line is last (or `WAKE_DEFERRED` on
   escalation). Hermetic assertion in `scripts/test_observe_completion.py`.
8. **Live smoke proves a rendered, agent-correct wake (revised
   procedure).** A person runs the following on opencode 1.19.1 and checks
   the listed observations — each check names where it is observed:
   1. `OPENCODE_WAKE_URL=http://127.0.0.1:4096 opencode --port 4096` — TUI
      opens. *Observed:* the TUI came up (a fixed port the owner chose).
   2. From the orchestrator conversation, dispatch a small recon brief with
      `--wake-to <this-session-id> --wake-agent <the agent this session runs
      as>` (wake-url resolved from the env). Mid-run, the owner sends an
      unrelated message in the TUI and it completes a turn. *Observed:* the
      unrelated turn completes in the live conversation (owner-frozen
      policy 1 intact).
   3. Success path: after the child's heartbeat terminal `DONE ok` line,
      within ≤ 5 min the wake appears **in the TUI conversation itself** —
      the `DISPATCH WAKE <agent> outcome=success` block streams in as a user
      message and the orchestrator's agent answers, without any owner ping.
      *Observed:* the block is visible in the TUI (not just
      `opencode export`), and the turn's agent is the session's agent (the
      TUI turn reads as the session's agent, and `opencode export <sid>`
      shows the wake user message recorded `agent=<wake-agent>`, never
      `build`).
   4. Failure path: a contract-invalid stub brief — the rendered wake
      carries `outcome=failure` and names the missing markers. *Observed*
      in the TUI.
   5. Degrade path: repeat with the TUI launched **without**
      `OPENCODE_WAKE_URL` and without `--wake-url`. *Observed:* after the
      child's terminal line, `tail` of the heartbeat shows
      `WAKE_DEFERRED <outcome> reason=no-attach-target` within one poll
      interval and the observer exits; `opencode export <sid>` shows no
      appended message (no ghost turn), and no subprocess lingers (no
      multi-minute hang).
   The checklist is recorded at the handoff; not testable hermetically.
9. **RM-059 seam intact.** `scripts/observe_completion.py` contains no call
   to `watch_agent.verdict` and no STALLED/DEAD/BLOCKING string; quiet
   non-terminal state is labeled `AWAITING` — asserted by a source-grep
   test in `scripts/test_observe_completion.py` (and the integration over
   `has_terminal_result` via the fixture DB).
10. **Run-log discipline unchanged.** The stub dispatch still emits exactly
    one `kind=agent` record with agent/model/outcome validated against
    `log_run`'s schema (the observer reads it; it never writes one) —
    existing assertions in `scripts/test_dispatch_agent.py` remain green.

## Files to Modify

- `scripts/dispatch_agent.py` — add `--worktree <name>`, `--wake-to
  <orchestrator-session-id>`, `--wake-url <url>` (resolved from env
  `OPENCODE_WAKE_URL` when omitted), `--wake-agent <name>` (required with
  `--wake-to`; preflight exit 2 otherwise), `--profile <name|auto|none>`
  (default `auto`); worktree setup under preflight; profile env merge; spawn
  `scripts/observe_completion.py` detached after `session_id=` is printed,
  forwarding `--wake-url`/`--wake-agent`; wake lines (`WAKE` tag) are
  written only by the spawn. Keep the edit
  surface minimal and documented (docstring flags list).
- `scripts/observe_completion.py` — the completion-observer (D2/D5/D6):
  poll loop, terminal classification, correlation, rule-1 quiescence gate
  (revised: closed-assistant-step signal), **attach-vehicle delivery**
  (`--attach <wake-url> --session <sid> --agent <wake-agent> --format
  json`, acceptance proof, bounded retry, deadline escalation with
  `reason=`), `WAKE_SUBPROCESS_TIMEOUT` 180 → 60 (per attempt, bounds
  pre-acceptance only), and the `AWAITING` classification — never the
  RM-059 liveness vocabulary (STALLED/DEAD/BLOCKING/OK/WARN).
- `scripts/dispatch-profiles.json` — NEW; per-class least-privilege
  defaults (D4).
- `scripts/test_observe_completion.py` — hermetic contract tests for
  AC1–AC5, AC7, AC9 (stub `opencode` on PATH recording argv, fixture DB
  via `OPENCODE_DB_PATH`, injectable sleep for the poll loop); the stub
  identifies a wake delivery by `--attach` and asserts the exact vehicle
  argv (AC1), the open-`step-start` gate case (AC3), and the three
  `WAKE_DEFERRED reason=` cases (AC4).
- `scripts/test_dispatch_agent.py` — extend: worktree setup/teardown on a
  fixture git repo (AC5), profile env merge (AC6), `--wake-to` spawns the
  observer with the resolved/forwarded `--wake-url`/`--wake-agent`
  (AC1 integration point), preflight `--wake-to` without `--wake-agent`
  exits 2 before launch, the launch-echo claim rules (AC7).
- `reference/subagent-supervision.md` — the wake contract lives here
  (this is the reference doc the dispatch contract must cite): §2
  line-ownership gains the observer's three tags (`SURVEY` / `WAKE` /
  `WAKE_DEFERRED`) and the poll-gated status-claim rule (D5); a short new
  §Wake cites D2 (wake vehicle + rule-1 gate), D3 (worktree landing +
  cleanup), D6 (RM-059 seam), D7 (wake text format) by name — no new
  protocol body beyond the mechanism this plan defines.
- `.gitignore` — only if the implement-time check shows it: verify at
  implement time that the existing `.scratch/` ignore covers
  `.scratch/worktrees/`; add a `.scratch/worktrees/*` entry only if the
  worktree checkouts dirty the parent git status.

## Scope

### Included

- The completion-observer script + its hermetic contract tests.
- `dispatch_agent.py`: worktree dispatch, permission profile, `--wake-to`
  observer spawn, minimal flag/dispatcher envelope additions.
- Wake path into the orchestrator conversation with rule-1 quiescence gate
  and escalation; fixed wake text format (D7).
- Status-claim gate as heartbeat line-ownership + supervision-reference
  citation.
- Profile denial surfacing via the existing `BLOCKED`/run-log detail
  classification.
- Replacing of the interim no-parent-git rule (recorded in D3) — the
  supervision reference paragraph is amended to point at the mechanism.

### Excluded

- No portable push channel, external service, email/phone — the
  orchestrator conversation is the only sink (owner-frozen policy 2).
- No RM-059 verdict redesign: the STALLED-on-generation false positive and
  its state-delta predicate stay owned by RM-059; only the seam is named
  (D6).
- No opencode plugin development (`session.idle` hook — Open Question).
- No skill-body changes except the minimal
  `reference/subagent-supervision.md` wake-contract citation (this is the
  reference doc the wake contract must cite; no SKILL.md touched).
- No consumer propagation: consumers use the live symlinks; consumers see
  the new flags automatically in `dispatch_agent.py` behavior.
- No DB/schema changes; no generated types.
- No in-session-Task wake (this plan covers the run-vehicle path; Task
  children already surface in-tree).

## Schema / Type Impacts

None. No DB, generated types, or schema/API contract changes; the only
contract-shaped artifact is the wake text block (D7) and the profile JSON
(D4) — both new files/scripts under version control, not deployed.

## Verification

Hermetic (the project's real command shape — standalone scripts, stub
opencode, no model calls):

```bash
python3 scripts/test_dispatch_agent.py          # extended: AC5, AC6, AC7
python3 scripts/test_observe_completion.py      # new: AC1–AC5, AC7, AC9
python3 scripts/test_watch_agent.py             # regression (reader tolerant of observer tags)
python3 scripts/test_session_guard.py           # regression (guard shares DB readers)
python3 scripts/test_validate_delegated_result.py  # regression
```

Red-first rehearsals recorded before implementation (each cited in
commit/PR body):

- the 2026-10-13 wrong-branch instance reproduced by the pre-fix stub
  dispatch WITHOUT `--worktree` (suite step asserts the pre-fix state,
  then the fix restores it), the same shape the historical guard used;
- the three 2026-10-14 permission deaths: pre-profile the stub env has no
  external_directory grants (current behavior), post-profile the unioned
  map carries each root — the third (`~/.local/share/opencode/*`) is the
  schema-verification fixture itself.

Live smoke: the revised AC8 procedure (steps 1–5 above) — manual checklist
recorded at handoff; owner interaction required. The degrade path (step 5)
can be exercised by the owner alone. The worktree landing live check from
the 2026-10-15 draft (parent HEAD on `main`, commit on `dispatch/<name>`,
post-landing cleanup) is unchanged by this amendment and is exercised the
first time a `--worktree` dispatch is used in anger (D3).

## Open Questions

- **RESOLVED 2026-10-16 — wake append while the owner is typing in the
  TUI.** The D2 amendment replaced the cross-server SQLite-writer risk: the
  wake goes through the orchestrator's own server (`--attach`), so the TUI
  and the wake share one writer. The residual question — injecting a user
  message while the owner's turn is in flight — is held by the revised
  quiescence gate (no tool in flight, no unclosed assistant step, stable
  `time_updated`) plus the `WAKE_DEFERRED` escalation. No open default.
  Supersedes the draft's "switch the wake vehicle to `opencode attach` as
  an implement-time amendment" note.
- **`session.idle` plugin hook as a second observer** — future narrowing of
  latency from 30 s to event-driven. Out of scope now; recorded here so it
  is not rediscovered. Proposed default: revisit when opencode plugin
  attribution facts change (`reference/opencode-integration.md` re-check).
- **Profile granularity for `test`** — `test-writer`/`debugger` files may
  need the consumer's `.scratch/` trees; currently `.scratch` is in-tree,
  so the profile carries `$HOME/repos` only. Proposed default: add nothing
  now; extend `scripts/dispatch-profiles.json` on first recorded denial,
  never pre-emptively (the chronic-instance discipline).

## History

- 2026-10-15 — draft (RM-058 design pass). Decisions D1–D7 recorded from
  probe of opencode 1.18.18, `scripts/dispatch_agent.py`,
  `scripts/watch_agent.py`, `scripts/log_run.py` (observing-runs schema
  owner = `skills/observing-runs/references/schema.md`),
  `reference/{agent-teams,opencode-integration,subagent-supervision,delegated-result-contract,technical-english}.md`,
  ADR-0008-repo-memory-tiers (plan lifecycle), AGENTS.md rules 1/3/4,
  detail files RM-058/RM-059 (seam named in D6), chronic instances
  2026-10-13 (wrong-branch) and 2026-10-14 (permission profile).
- 2026-10-15 — UX consult skipped: no user-facing UI (this item is
  dispatcher/watchdog infrastructure; screens/forms/dialogs none) —
  council-ux consult not warranted.
- 2026-10-15 — Consult outcome: skipped (one-line reason: no external
  design-consult lens needed — single durable-surface supervision stack
  with an already-frozen owner policy; the item's open design dimensions
  were resolved against recorded evidence D1–D7 above).
- 2026-10-15 — **Implemented** (implement pass, branch
  `feat/rm-058-orchestrator-wake`). Delivered: `scripts/observe_completion.py`
  (D1 terminal table, D2 wake + rule-1 quiescence gate, D5 `SURVEY`/`WAKE`/
  `WAKE_DEFERRED` line ownership, D6 `AWAITING` classification, D7 wake text),
  `scripts/dispatch-profiles.json` (D4), `--worktree`/`--wake-to`/`--profile`
  on `scripts/dispatch_agent.py` (D2/D3/D4), the reference wake contract
  (`reference/subagent-supervision.md` §2 + §6), and hermetic tests.
  - Verification (all exit 0): `test_dispatch_agent.py` (24 cases),
    `test_observe_completion.py` (7 cases), `test_watch_agent.py` (13),
    `test_session_guard.py` (26), `test_validate_delegated_result.py` (7).
  - Red-first evidence: `test_observe_completion.py` failed pre-implementation
    with `scripts/observe_completion.py missing`; against `main`'s
    `dispatch_agent.py` the new dispatch cases failed with `unrecognized
    arguments: --profile/--wake-to/--worktree`, while the AC5 rehearsal step
    (dispatch WITHOUT `--worktree`) passed by mutating the parent branch — the
    2026-10-13 reproduction.
  - Mechanical deviations (feature unchanged): (1) `dispatch-profiles.json`
    carries a top-level `aliases` map because the plan's own example
    (`vision-critic-fast → reviewer`) is not expressible by longest-prefix
    alone; (2) the observer spawn adds plumbing args the D7 wake text needs
    (`--child-session`, `--result`, `--logs-dir`, `--worktree`, `--branch`)
    beyond D2's five; (3) profile `worktree` ships `false` for every class in
    v1 (explicit `--worktree <name>` is the enabling path) so "no behavior
    change without the new flags" holds and no test mutates a real repo — the
    honor logic exists and is unit-tested; (4) AC5's worktree suite lives in
    `test_dispatch_agent.py`; `test_observe_completion.py` covers AC1–AC4,
    AC7, AC9; (5) `--timeout` default is now `None` (effective default still
    600) so a profile timeout can apply; (6) `.gitignore` unchanged — the
    existing `.scratch/` entry already covers `.scratch/worktrees/`.
  - Not exercised hermetically (owner manual): AC8 live smoke (concurrent
    owner interaction + real wake turn) — checklist in the handoff.
- 2026-10-15 — **Live-smoke defect diagnosis: H1 (wake vehicle) confirmed,
  H2 (gate) refuted. No code change — STOP, blocked on a design pass.** The
  AC8 live smoke (detached `architect` dispatch, `--wake-to
  ses_edc9935acffeRgTjT2aQYvLhUD`, opencode **1.19.1**) failed: the observer's
  `opencode run --session <orch> --format json "DISPATCH WAKE …"` ran the full
  `WAKE_SUBPROCESS_TIMEOUT` (180 s) and was killed; no `WAKE` line. Evidence
  from the opencode event log
  (`~/.local/share/opencode/log/opencode.log`) and the session store:
  - **H2 refuted.** At delivery (~20:03:31) the orchestrator session was
    idle: its last TUI turn ended 20:02:36.518 (`step-finish`), the injected
    wake is the next part (20:03:31.070), and the next turn starts
    20:03:36.146. `orchestrator_quiescent()` correctly read quiescent — no
    tool in flight, `time_updated` stable across two polls.
  - **H1 confirmed.** The wake turn ran in the *subprocess's own server*, not
    the live TUI. Log: `run=e59d1f4c` (**agent=`build`**, opencode's default
    primary agent) processed it 20:03:31→20:06:46; the live TUI is
    `run=be145e63` (**agent=`curator`**) and never saw those events.
    `opencode run --session` starts its own local server (`--port` default
    random), so a second process runs a *ghost* turn — persisted to
    `opencode.db` but never rendered in the TUI. It also ignored the session's
    agent (`build`, not `curator`) and took 3m15s > the 180 s timeout, so it
    was killed mid-turn.
  - Vehicle-in-isolation check (`opencode run` then `opencode run --session
    <id>` on a throwaway, non-TUI session): both exit 0 quickly — the vehicle
    is sound for an unheld session; the defect is specific to a live TUI-held
    session.
  - The plan's pre-authorized remedy (`opencode attach` against the TUI
    server) is infeasible on 1.19.1: the TUI process holds **no LISTENING
    socket** (`ss -tlnp` / `/proc/<pid>/net/tcp`; the only localhost listeners
    are VS Code server pids 689448/689889) — there is no HTTP URL to attach
    to. `opencode attach` is also interactive, not a fire-and-forget wake.
    The only in-process vehicle is a plugin (this environment already loads
    `~/.config/opencode/plugins/auto-compact-at-threshold.js`), which the
    plan's Excluded list forbids without a design pass.
  - **Change: none.** STOP per the H1 branch. `reference/subagent-supervision.md`
    §6 carries a dated caveat that this vehicle does not deliver a visible
    turn to a live TUI.
  - Secondary latent finding (not this smoke's cause): the quiescence gate's
    `time_updated`-stability signal is blind to a *mid-generation* turn — a
    step's `time_updated` lands at `step-finish`, so a long model call with no
    tool in flight can read as quiescent. Recorded for the design pass.
- 2026-10-16 — **Design amendment: D2 revised to the attach vehicle
  (server-reachable orchestrator).** Probes of installed opencode 1.19.1
  (throwaway session `ses_ebb7770e5ffeSsiBTw1KzDydfz`, scratch
  `.scratch/rm-058-vehicle-design/`, artifacts `p3/p4/p8.json`,
  `serve.log`, `tui.capture`):
  - P3/P8 — `opencode run --attach http://127.0.0.1:<port> --session <sid>
    --agent <agent> --format json <text>` exits 0 in 3–14 s while the turn
    runs on the attached server (assistant reply present in the session
    export after client exit); a TUI launched `opencode --port 4568
    --session <sid>` holds the LISTENING socket (curl 200) and **rendered
    the delivered wake live** (capture shows the `DISPATCH WAKE …` text +
    running-turn indicator).
  - P4 — agent semantics are not inherited: without `--agent` the appended
    message records `agent=build` (the 2026-10-15 ghost shape); with
    `--agent curator` both messages record `agent=curator` and curator's own
    model binding → wake forces `--agent`, drops `--model`.
  - P1 — attach to an unreachable port fails ≤ 1 s rc=1 → honest
    degradation, no hang class.
  - P2 — servers write no port/state file (`~/.local/share/opencode`,
    `~/.local/state/opencode`) → URL travels via `OPENCODE_WAKE_URL` env /
    `--wake-url` flag, with required companion `--wake-agent` (preflight
    exit 2 missing).
  - Changes: D2 rewritten (launch workflow, dispatch contract, attach
    delivery + acceptance proof, no-target deferral, bounded retry);
    quiescence gate gains the closed-assistant-step signal (generation
    blindness folded in); `WAKE_DEFERRED` tags gain `reason=`;
    `WAKE_SUBPROCESS_TIMEOUT` 180 → 60 s; AC1/AC3/AC4/AC8 revised; Files to
    Modify updated; Open Question #1 resolved. D1 (except the gate text it
    defers to — its child liveness table is unchanged), D3, D4, D6, D7
    intact: the vehicle does not force any change in them (wake text D7
    unchanged; D5 changed only by the `reason=` token).
- 2026-10-16 — Consult outcome: skipped (one-line reason: no external
  design-consult lens needed — the owner pinned the direction
  ("server-reachable orchestrator, do not re-litigate"); the amendment's
  open dimensions were resolved against direct probe evidence of the
  installed 1.19.1 recorded above).
- 2026-10-16 — **Implemented (attach-vehicle amendment).** Delivered the D2
  delta on branch `feat/rm-058-orchestrator-wake` (commit to follow):
  - `scripts/observe_completion.py` — `deliver()` now runs `opencode run
    --attach <wake-url> --session <sid> --agent <wake-agent> --format json
    <wake-text>` (never `--continue`; never `--model`). Acceptance proof =
    the first streamed event naming the orchestrator session, or a client
    exit 0, whichever first; the client is then allowed to exit within
    `WAKE_SUBPROCESS_TIMEOUT` (**180 → 60**, per attempt, bounds
    pre-acceptance only). No resolvable URL → `WAKE_DEFERRED <outcome>
    reason=no-attach-target` at the first terminal poll with **zero**
    subprocess spawns. The final `WAKE_DEFERRED` carries `reason=` naming the
    gate (`quiescence-gate`) or the delivery refusal. The gate adds
    `_assistant_step_closed` (a trailing `step-start` reads mid-generation) as
    the load-bearing signal and keeps `time_updated` stability as the belt.
  - `scripts/dispatch_agent.py` — added `--wake-url <url>` (resolved from
    `OPENCODE_WAKE_URL` when omitted) and `--wake-agent <name>` (preflight
    exit 2 with `--wake-to` when missing); both forwarded to the spawned
    observer.
  - `scripts/test_observe_completion.py` — stub identifies the wake by
    `--attach`; AC1 asserts the exact attach argv and the absence of
    `--continue`/`--model`; AC3b asserts the open-`step-start` gate case;
    AC4a/b/c assert the three `reason=` cases (gate / no-attach-target /
    bounded-refusal).
  - `scripts/test_dispatch_agent.py` — asserts `--wake-url`/`--wake-agent`
    forwarding (explicit and `OPENCODE_WAKE_URL`-resolved) and the
    missing-`--wake-agent` preflight exit 2.
  - `reference/subagent-supervision.md` §6 — implementation-status line
    flipped to implemented.
  - Verification (all exit 0): `test_observe_completion.py` (10 cases),
    `test_dispatch_agent.py` (24), `test_watch_agent.py` (13),
    `test_session_guard.py` (26), `test_validate_delegated_result.py` (7);
    `python3 -m py_compile` clean on both touched scripts.
  - Red-first evidence: against the pre-amendment `deliver()`, AC1's stub
    recorded zero invocations (`[]` — no `--attach`); AC4b wrote a legacy
    `WAKE success` via the `--session` ghost vehicle instead of
    `reason=no-attach-target`; AC4a wrote the old `WAKE_DEFERRED …
    heartbeat=` form; AC4c's refusal was never invoked. The first red was the
    absent `--wake-url`/`--wake-agent` CLI contract (verified before the
    flags were added).
  - Coverage gate: no rebalance needed (the AC tests are already at the
    cheapest layer that exercises the seam — observer loop + stub `opencode`
    + fixture DB). One gap the implementation revealed was closed: AC4c now
    asserts the refusal was **retried** (≥2) and **bounded** by the deadline
    (≤8), not merely attempted once.
  - Mechanical deviations (feature unchanged): none — the plan's Files to
    Modify matched on disk; `--model` was removed from the observer CLI (the
    amended D2 says the wake must never use it). No `docs/ROADMAP.md` change
    (roadmap closure is owned by the orchestrator at merge).
  - Not exercised hermetically (owner manual, AC8): the live fixed-port TUI
    smoke (AC8 steps 1–5) was deliberately NOT run — it needs the owner and a
    live TUI; the procedure is recorded in AC8.

### Follow-ups

- **Wake vehicle (H1, blocks AC8).** RESOLVED BY THE 2026-10-16 D2
  AMENDMENT (design decided; **implemented 2026-10-16** — see the History
  entry above; only the owner-manual AC8 live smoke remains): server-reachable
  orchestrator — owner launches the TUI with an
  explicit `--port`, the URL travels via `OPENCODE_WAKE_URL`/`--wake-url`,
  delivery is `opencode run --attach <url> --session <sid> --agent
  <wake-agent> --format json` (probe-proven render, agent-correct, ≤ 15 s,
  fails fast), and no-target / refusal degrades to bounded
  `WAKE_DEFERRED reason=…`. The draft's `opencode attach` remedy and the
  plugin alternative are both superseded in favor of the attach vehicle
  (plugins stay excluded).
- **Quiescence-gate generation-blindness.** RESOLVED BY D2 AMENDMENT
  (2026-10-16): the quiescence predicate now requires the newest assistant
  message's step sequence to be closed (a trailing `step-start` reads busy),
  not `time_updated` stability alone; hermetic regression case in AC3.

- AC8 live smoke and roadmap closure are owned by the orchestrator at merge;
  `docs/ROADMAP.md` was deliberately not touched by this pass.
- `session.idle` opencode plugin hook (latency narrowing) stays an Open
  Question, unimplemented.
- `test` profile granularity for consumer `.scratch/` trees: extend
  `dispatch-profiles.json` on the first recorded denial, never pre-emptively.
