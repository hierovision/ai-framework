---
slug: rm-058-orchestrator-wake
title: Wake the orchestrator on subagent terminal state; worktree-safe dispatch; per-dispatch permission profile
status: approved
created: 2026-10-15
revised: [2026-10-15]
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
surface; (2) a wake delivery that appends to the orchestrator session via
explicit `opencode run --session <orchestrator> --format json <wake-text>`
(rule-1-sanctioned form), gated on the orchestrator session being quiescent
(no tool in flight per `watch_agent`'s running predicate) with bounded retry;
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

### D2. The wake path

Who writes what / who reads what / what triggers the turn:

1. At dispatch time the orchestrator passes one new flag:
   `--wake-to <orchestrator-session-id>` (the orchestrator's own session id).
   The dispatcher, immediately after the stream names the child's
   `session_id` (line it already prints), spawns
   `scripts/observe_completion.py --heartbeat <hb> --agent <name>
   --dir <dispatch-dir> --orchestrator-session <sid> --deadline 300`
   detached (`start_new_session=True`) so it survives after the owner
   switch. One orchestrator command now dispatches child + observer.
2. The observer loops every 30 s: it polls the heartbeat file for a
   dispatcher terminal line and, for corroboration, the run-log daily file
   and the fixture/real DB (`OPENCODE_DB_PATH` honored, read-only URI via
   `watch_agent.db`). Each poll is appended to the heartbeat file owned by
   the observer (third writer, distinct tag — see D5 line ownership).
3. On terminal state the observer builds a wake text from **durable state
   only** (outcome, child session id, heartbeat path, result path, run-log
   path, termination detail) and delivers it with
   `opencode run --session <orchestrator-sid> --format json --model
   <orchestrator-binding> <wake-text>` — an **explicit `--session`**, the
   exact form AGENTS.md rule 1 sanctions; `--continue` is never used.
   The wake text appends to the orchestrator conversation, which generates
   one orchestrator turn: the orchestrator reads the wake, reports to the
   owner, and resumes its own agenda. The orchestrator conversation is the
   only sink; nothing is sent anywhere else.
4. **Rule-1 / concurrency gate:** the observer delivers the wake only when
   the orchestrator session row is quiescent — no tool part in flight (the
   same running predicate `watch_agent.analyze_session` computes) and
   `session.time_updated` stable across two polls. While the owner is
   interacting, the orchestrator turns busy and the wake waits; retries are
   bounded by the deadline (default 300 s) — wake-at-fifth-minute or as soon
   as the session quiesces.
5. **Honest escalation (the only non-automatic path):** if the deadline
   expires — the owner holds the orchestrator continuously busy for
   > 5 minutes, or the `opencode run --session` append fails — the observer
   retries until the deadline, then writes exactly one terminal
   observation line to the heartbeat (`WAKE_DEFERRED <outcome> <paths>`) and
   stops. The durable wake summary already sits in the heartbeat and the
   run-log record; the orchestrator's next turn (owner-initiated or
   triggered by any later interaction) reads the heartbeat before
   reporting status. The design does not assert a wake that cannot happen
   while the owner owns the turn.

Concurrent-interaction safety: the wake never uses `--continue` (rule 1);
it targets an explicit session id and waits for store quiescence, so a wake
write never races an in-flight orchestrator turn, and the owner's
mid-dispatch interaction happens through the same conversation with turns it
already owns.

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
  `WAKE <outcome>` or `WAKE_DEFERRED <outcome>` line. It never writes
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

1. **Wake-on-success within SLA, owner-ping-free.** A hermetic contract
   test (`python3 scripts/test_observe_completion.py`, watch 5) runs a stub
   dispatch that terminates success with
   `--wake-to` pointing at an orchestrator session in a fixture DB
   (`OPENCODE_DB_PATH`); within 300 s of the heartbeat terminal line the
   test's stub `opencode` receives exactly one `run --session
   <orchestrator-sid>` invocation whose message matches the fixed wake
   shape (`DISPATCH WAKE` line, task/child/result/log paths, no `--continue`
   anywhere) — asserted in `scripts/test_observe_completion.py`.
2. **Wake enumerates failure and abort.** Same harness with a
   contract-invalid stub result (markers missing) and with a killed
   stub dispatcher (no terminal line, liveness window short): the wake
   received carries `outcome=failure`+detail naming the missing markers, and
   `outcome=aborted`+detail naming the liveness basis — asserted in the same
   test file.
3. **Rule-1 gate.** While the fixture orchestrator session shows a tool
   part in flight (in-flight predicate true), the observer issues zero
   wake invocations across the window; after a part lands
   (`has_terminal_result` shape) the wake is issued once exactly —
   asserted in the same test file.
4. **Deadline escalation is durable, not silent.** With the deadline forced
   short and the orchestrator session continuously in-flight, the observer
   writes exactly one `WAKE_DEFERRED <outcome>` heartbeat line and exits —
   asserted in the same test file.
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
8. **No accidental regression of concurrent interaction.** Live smoke
   (procedure in Verification): with a real detached dispatch running, the
   orchestrator conversation accepts a mid-run owner message and completes
   an unrelated turn while the child's heartbeat advances and `SURVEY`
   lines appear; after terminal, the wake turn lands without any owner
   ping. Smoke checklist is recorded in the handoff (not testable hermetically).
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
  <orchestrator-session-id>`, `--profile <name|auto|none>` (default
  `auto`); worktree setup under preflight; profile env merge; spawn
  `scripts/observe_completion.py` detached after `session_id=` is printed;
  wake lines (`WAKE` tag) are written only by the spawn. Keep the edit
  surface minimal and documented (docstring flags list).
- `scripts/observe_completion.py` — NEW; the completion-observer (D2/D5/D6):
  poll loop, terminal classification, correlation, rule-1 quiescence gate,
  bounded wake delivery via explicit `--session`, deadline escalation, and
  the `AWAITING` classification — never the RM-059 liveness vocabulary
  (STALLED/DEAD/BLOCKING/OK/WARN).
- `scripts/dispatch-profiles.json` — NEW; per-class least-privilege
  defaults (D4).
- `scripts/test_observe_completion.py` — NEW; hermetic contract tests for
  AC1–AC5, AC7, AC9 (stub `opencode` on PATH, `OPENCODE_DB_PATH` fixture,
  injectable sleep for the poll loop).
- `scripts/test_dispatch_agent.py` — extend: worktree setup/teardown on a
  fixture git repo (AC5), profile env merge (AC6), `--wake-to` spawns the
  observer (AC1 integration point), the launch-echo claim rules (AC7).
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

Live smoke (manual, checklist recorded at handoff; owner interaction
required):

1. Detached dispatch of a small recon brief that reads
   `~/.config/opencode/` (the second chronic path) with `--wake-to <this
   orchestrator session>`; verify: mid-run an owner message gets a
   completed unrelated turn (concurrent interaction intact); ≤ 5 min after
   the terminal heartbeat line the conversation shows the `DISPATCH WAKE`
   block without the owner pinging.
2. A `--worktree` dispatch whose stub is replaced by a real one-line
   commit: confirm the parent tree's HEAD stayed on `main` and the commit
   is on `dispatch/<name>` inside the worktree; land it per D3; cleanup
   verified by `git worktree list` (post-cleanup worktree absent).
3. One intentional failure (contract-missing markers stub brief) → the
   wake arrives with `outcome=failure` + named detail.

## Open Questions

- **Wake append while the owner is typing in the TUI** — SQLite-level,
  not tool-level races between the TUI server and the wake's `opencode run
  --session` write. Mitigated by the quiescence gate (D2 step 4) + the
  escalation (deferral, AC4), which covers the observable failure mode
  (no write attempted while a tool is in flight). Proposed default:
  proceed; if live smoke shows a real race, switch the wake vehicle to
  `opencode attach` against the TUI's server (`opencode attach <url>`
  exists on 1.18.18) as an implement-time amendment recorded in History.
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

### Follow-ups

- **Wake vehicle (H1, blocks AC8).** `opencode run --session` cannot deliver
  a visible wake to a live TUI session (it runs a ghost turn in its own
  server). Needs a design pass: (a) require the orchestrator to be reachable
  as a server (`opencode serve` + `opencode attach`, or `opencode --port N`)
  and deliver with `opencode run --attach <url>`; or (b) an in-process
  `session.idle` plugin. The plan's Open Question #1 remedy as written
  (`opencode attach`) is infeasible (no server URL; attach is interactive).
- **Quiescence-gate generation-blindness.** Harden `orchestrator_quiescent()`
  with a part-recency signal (age of the newest part), not `time_updated`
  stability alone; add a regression test for the mid-generation case.

- AC8 live smoke and roadmap closure are owned by the orchestrator at merge;
  `docs/ROADMAP.md` was deliberately not touched by this pass.
- `session.idle` opencode plugin hook (latency narrowing) stays an Open
  Question, unimplemented.
- `test` profile granularity for consumer `.scratch/` trees: extend
  `dispatch-profiles.json` on the first recorded denial, never pre-emptively.
