---
slug: session-guard-fail-fast
title: Session-tree failure-pattern guard with abort authority (fail fast, not fail slow)
status: approved
created: 2026-10-07
revised: [2026-10-07]
related: [rm-022, rm-023, rm-024, rm-026, rm-044]
---

# Plan: session-guard-fail-fast

## Goal / Approach

**Goal:** an orchestrating session's full subagent tree (workers and workers'
workers) is observed continuously out-of-band; when it falls into a known
failure pattern, the guard acts within one poll — bounded recovery where the
delegated-result contract allows it, **abort of the session** otherwise — so a
broken run fails in minutes with a dated record instead of silently burning
an hour.

**Approach:** a new stdlib Python supervisor, `scripts/session_guard.py`,
sibling to `scripts/watch_agent.py` (RM-022). It enumerates the session tree
from opencode's read-only SQLite DB (`session.parent_id` walk, depth capped at
2 per `reference/agent-teams.md`), reuses `watch_agent`'s pure liveness
analysis per node (no duplicated liveness logic), matches a versioned failure-
pattern registry, and escalates per pattern: flag → kill failing children →
abort the root session. Abort is a process-group kill (SIGTERM, then SIGKILL
after a grace period) because `opencode session` exposes only `list`/`delete`
— there is no abort subcommand (verified 2026-10-07) — and is always recorded:
one `ABORT` sentinel file with pattern + evidence + UTC timestamp, plus exactly
one run-log record `kind=agent` / `outcome=stopped` (the enum value already in
`skills/observing-runs/references/schema.md`). Two launch modes: `--wrap`
(guard owns the root process group; abort is mechanical) and observe mode
(attaches to a live tree read-only; root kill requires an explicit
`--kill-root` + `--root-pid`, never a `pgrep` guess). Like `watch_agent`, the
guard is transient supervision: read-only on the DB and session streams, it
never injects into an observed agent's context.

**Pattern registry v1** (each grounded in an observed incident):

| Pattern | Detector signal | Default action |
|---|---|---|
| `empty-result` | child's final result is empty or fails its declared contract markers (`scripts/validate_delegated_result.py` reuse) | flag; second occurrence in the same wave escalates |
| `permission-auto-reject` | `permission requested: external_directory … auto-rejecting` / `permission denied: <tool> <path>` in stream or stderr; evidence names the denied path | flag + suggest `--allow-dirs`; escalates if it is the wave's shared failure |
| `identical-retry-loop` | ≥ 2 relaunches of the same agent + same prompt digest after failed results within a window (RM-024's bounded sequence exceeded) | **abort session** |
| `dead-stream` | dispatched child with zero log lines / no session id in the event stream (RM-026 class) | flag (classification limited by RM-026) |
| `stalled` / `blocking-wait` | `watch_agent` verdicts (heartbeat age, session quiet gaps > `--call-seconds`) | kill the stalled child |
| `wave-failure` | ≥ `--wave-ratio` (default 0.6) of one dispatch wave's children failing with a shared pattern (the incident: 3 of 5 empty) | **abort session** |
| `budget-exceeded` | tree wall clock > `--budget-minutes` | **abort session** |

## Acceptance Criteria

1. **Tree enumeration** — given a fixture DB with a root, two children, one
   grandchild, and one unrelated root, the guard reports exactly the root's
   descendants (depth ≤ 2) and excludes the unrelated root —
   `python3 scripts/test_session_guard.py` (tree cases) exits 0.
2. **`empty-result` detection** — a fixture child whose final assistant text
   is empty, and a fixture child whose result lacks its declared contract's
   markers (via `validate_delegated_result.py`), both match `empty-result`
   with evidence naming the child session id — asserted in
   `test_session_guard.py`.
3. **`permission-auto-reject` detection** — a fixture stream containing
   `permission requested: external_directory` + `auto-rejecting` matches
   `permission-auto-reject` (not generic `empty-result`) and its evidence
   names the denied path — asserted in `test_session_guard.py`.
4. **`identical-retry-loop` detection** — two fixture relaunches of the same
   agent + prompt digest following failed results inside the window match
   `identical-retry-loop`, and the pattern's default action is root abort
   (RM-024's bound enforced mechanically) — asserted in
   `test_session_guard.py`.
5. **Liveness reuse** — a fixture session with a quiet gap >
   `--call-seconds` yields `stalled`/`blocking-wait` through the imported
   `watch_agent.analyze_session`/`verdict` functions; the guard contains no
   second liveness implementation — asserted in `test_session_guard.py`.
6. **`wave-failure` detection** — a fixture wave of five children where three
   fail with a shared pattern matches `wave-failure` at the default ratio
   0.6 — asserted in `test_session_guard.py`.
7. **`budget-exceeded` detection** — a fixture tree whose age exceeds
   `--budget-minutes` matches `budget-exceeded` — asserted in
   `test_session_guard.py`.
8. **Abort mechanics (`--wrap`)** — on an abort-class pattern the guard (a)
   terminates the owned root process group (SIGTERM then SIGKILL after
   grace), (b) writes an `ABORT` sentinel containing pattern name, evidence,
   and UTC timestamp, (c) emits exactly one run-log record `kind=agent` with
   `outcome=stopped` and `detail` naming the pattern, (d) exits with the
   documented abort code — asserted in `test_session_guard.py` against a real
   short-lived fake root process (`subprocess`), a temp sentinel path, and a
   stubbed run-log sink.
9. **Observe-mode safety** — with no `--kill-root`/`--root-pid`, a pattern
   fire in observe mode kills nothing and produces only the sentinel +
   non-zero exit; with `--kill-root --root-pid` it kills exactly that pid's
   group — asserted in `test_session_guard.py`.
10. **Read-only, non-interfering supervision** — the guard's only DB
    connection uses a `file:…?mode=ro` URI (asserted by a unit check on its
    connect helper) and its only write surfaces are the sentinel file and its
    own single run-log record (asserted by the abort-mechanics test's call
    accounting).
11. **Docs contract** — `reference/subagent-supervision.md` gains a
    session-tree-guard section (pattern table, escalation ladder, sentinel
    contract, launch contract), and `reference/agent-teams.md` +
    `reference/delegated-result-contract.md` cite the guard — verified by
    `grep -l session_guard reference/subagent-supervision.md
    reference/agent-teams.md reference/delegated-result-contract.md` listing
    all three files.
12. **Gate wiring** — `python3 scripts/test_session_guard.py` runs in the
    CI offline unit suites and the CONTRIBUTING gate list, exiting 0 —
    verified by the command's exit code and `git diff main --
    .github/workflows/ci.yml` showing the added entry.
13. **Live smoke on a real tree** — `python3 scripts/session_guard.py
    --parent <root-id> --once --json` returns a per-node verdict tree for a
    live session tree; the dated JSON is pasted into the PR description.
    Retrospective check: run against root `ses_ef8102f5dffevLUPFG0feyKAX8`
    (the trigger incident) must flag `empty-result` on the PR 16/17/18
    reviewer children — verified by the PR description containing the JSON.

## Files to Modify

- scripts/session_guard.py — new; tree enumeration (`parent_id` walk, depth
  ≤ 2), pattern registry v1 (pure detectors + default-action map), escalation
  executor (child kill / root abort / sentinel / run-log record), CLI:
  `--root|--parent|--cwd` selectors, `--once|--watch N`, `--budget-minutes`,
  `--wave-ratio`, `--call-seconds`, `--wrap -- <cmd>`, `--kill-root
  --root-pid`, `--sentinel PATH`, `--json`, documented exit codes
  (0 clean, 2 warned, 5 abort, 4 unknown).
- scripts/test_session_guard.py — new hermetic suite: synthetic session-tree
  DB fixtures (tmp sqlite file), pattern-detector cases, fake root process
  for the kill path, stubbed run-log sink; offline, no network, no live DB.
- scripts/watch_agent.py — no behavior change; only what is needed to make
  `analyze_session` / `verdict` / `read_heartbeat` importable as pure
  functions by the guard (they already are module-level).
- .github/workflows/ci.yml — add `python3 scripts/test_session_guard.py` to
  the offline unit-suite list.
- CONTRIBUTING.md — add the same command to the gates block.
- reference/subagent-supervision.md — new section "Session-tree guard":
  pattern table, escalation ladder (flag → kill children → abort session),
  sentinel + run-log record contract, `--wrap` vs observe-mode launch rules,
  mandatory-by-contract for dispatch waves (parallel to the visibility-flag
  mandate).
- reference/agent-teams.md — supervision bullet: a dispatch wave runs under
  the session-tree guard; cite the abort authority.
- reference/delegated-result-contract.md — consumers list the guard as the
  mechanical enforcer of "never loop on an identical retry" (RM-024).
- docs/ROADMAP.md — add RM-045 row (category observability) referencing this
  plan; note that on delivery RM-024's acceptance ("a flaky delegation ends
  within a bounded sequence instead of unbounded identical relaunches") is
  mechanically enforced and RM-044 items remain separate.

## Scope

**Included**

- The guard (both launch modes), pattern registry v1 with the seven patterns
  above, abort mechanics with the sentinel + single run-log record.
- Hermetic test suite; CI/CONTRIBUTING gate wiring.
- The three reference-doc updates and the RM-045 roadmap row.
- A dated live-smoke record, including the retrospective run on the trigger
  incident's tree.

**Excluded**

- RM-026 (subagent sessions missing from `opencode.log`): the guard flags
  `dead-stream` but cannot classify beyond it until upstream logs exist.
- RM-044's three hardening items (heartbeat UTC-format pin, bash-`ask`
  heartbeat injection, empty result without `--contract` recorded success) —
  tracked separately; the guard only *detects* their symptoms.
- Automatic retry or vehicle-switching: retries stay the orchestrator's
  bounded choice per `reference/delegated-result-contract.md`; the guard
  enforces the bound (abort on `identical-retry-loop`), it never relaunches.
- `dispatch_agent.py --guard` auto-launch wrapper (follow-up once the guard
  is proven; note in RM-044/RM-024).
- Plugin/hook-based observation (opencode plugin events lack per-skill
  attribution — `reference/opencode-integration.md`).
- Any change to opencode itself (e.g. an upstream `session abort` command;
  worth an upstream request, out of scope here).
- UI/dashboard, remote or cross-machine sessions, telemetry export.

## Schema / Type Impacts

None to any database schema. The guard is a read-only consumer of
opencode.db (session/message/part rows) and reuses the existing run-log
schema — `outcome: stopped` is already an allowed enum value
(`skills/observing-runs/references/schema.md`); no schema change.

Two new file-level contracts (not schemas, but stable surfaces):

- **ABORT sentinel** — `<sentinel path>` (default
  `.scratch/session-guard/ABORT.<root-session-id>`) written exactly once per
  abort: JSON with `pattern`, `evidence`, `sessions`, `ts` (UTC, `Z` format),
  `root_session_id`.
- **Guard CLI exit codes** — 0 clean, 2 warned (flag/child-kill only), 5
  abort performed, 4 unknown (DB unavailable / unclassifiable).

## Verification

From `CONTRIBUTING.md` (the gates every PR passes), plus the new suite:

```
python3 scripts/test_session_guard.py
python3 scripts/test_watch_agent.py
python3 scripts/test_dispatch_agent.py
python3 scripts/test_validate_delegated_result.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/check_typed_evals.py --base main
python3 scripts/test_changed_files.py && python3 scripts/test_eval_report.py \
  && python3 scripts/test_eval_workflows.py && python3 scripts/test_quarantine.py \
  && python3 scripts/test_stall_timeout.py && python3 scripts/test_typed_evals.py
node skills/managing-github-issues/evals/fixtures/unit.test.mjs
node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs
bash -n install.sh
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

Plus AC11's `grep -l session_guard reference/…` doc check and AC13's dated
live-smoke JSON in the PR description.

## Open Questions

1. **Escalation ladder defaults.** Proposed: single isolated pattern → flag
   or kill that child; `identical-retry-loop`, `wave-failure`,
   `budget-exceeded` → root abort; `--kill-root` escalates any abort-class
   pattern to root. (The user's directive "ready to abort the session" is
   the headline behavior; this ladder keeps a lone transient blip from
   nuking a healthy session.)
2. **Root-kill mechanism in observe mode.** Proposed: root kill only with
   explicit `--root-pid` or under `--wrap` (the guard owns the process
   group); never `pgrep`-guess a pid from a session id.
3. **`--wave-ratio` default 0.6** (the incident was 3 of 5 empty), tunable.
4. **Retry budget encoded in `identical-retry-loop`:** cap 2 identical
   relaunches within 30 min, keyed by agent + prompt digest (RM-024 says
   "retried at most twice on the same vehicle").
5. **`--budget-minutes` default 45.** Children are already ≤ 10-min
   checkpoints per RM-022 §1; the incident's wave ran 52–54 min per child.
6. **Mandatory-by-contract?** Proposed: yes — any dispatch wave runs under a
   guard, mirroring the "> 10 min ⇒ visibility flags" mandate; enforcement
   is by citation in this pass, mechanical via `dispatch_agent.py --guard`
   later (Excluded).
7. **Stack-reference gap:** this is the library repo itself (stdlib Python +
   markdown skills); no bundled `references/stacks/` matches — generic
   planning applied, no stack-specific concerns.

## History

- 2026-10-07 — created (design pass, status draft). **Trigger incident:**
  paragon-learning-network root session `ses_ef8102f5dffevLUPFG0feyKAX8`
  ("paragon-ln.com DNS/email audit + Supabase takeover", agent=architect)
  fanned out five `reviewer` children at 2026-10-07T11:48:48–57Z (`Review
  PR 16/17/18/21/22`); 3 of 5 (PR 16/17/18) ended with empty/malformed
  results whose last text is the parent's retry nudge `Your previous run
  returned an EMPTY result — that is a failed run, not…`; 2 of 5 (PR 21/22)
  returned real reviews; all five ran 52–54 min (to 12:40–12:43Z) with no
  supervision abort and the parent then waited ~1 h unattended — evidence
  read live from opencode.db (session + part rows) 2026-10-07. **Gap check
  (2026-10-07):** `scripts/watch_agent.py` is single-session
  (`find_session … ORDER BY time_updated DESC LIMIT 1`) and flag-only (exit
  codes, no kill); RM-024's bounded retry is unimplemented prose (backlog);
  `opencode session` offers only `list`/`delete` (verified via `opencode
  session --help`) — no abort command, so abort must be process-group kill.
  Existing building blocks reused: `watch_agent` liveness analysis,
  `validate_delegated_result.py` contract markers, run-log `outcome=stopped`.
  **UX consult skipped — no user-facing UI** (internal tooling; the skip is
  the closure signal per the design skill). Proposed roadmap row **RM-045**
  lands with the implement pass (see Files to Modify).
- 2026-10-07 — user approved the plan (`status: approved`); Open Questions 1–6
  stand at their proposed defaults (escalation ladder as drafted; root kill
  only via `--wrap` or explicit `--root-pid`; wave-ratio 0.6; retry cap 2 in
  30 min; budget 45 min; mandatory-by-contract by citation). Implement pass
  starts 2026-10-07.
- 2026-10-07 — **implemented** on branch `feat/session-guard-fail-fast`
  (unmerged; no PR opened). Delivered: `scripts/session_guard.py` (pattern
  registry v1, tree enumeration, abort mechanics), `scripts/test_session_guard.py`
  (11 hermetic cases), CI + CONTRIBUTING gate wiring, §5 in
  `reference/subagent-supervision.md`, citations in
  `reference/agent-teams.md` + `reference/delegated-result-contract.md`,
  ROADMAP row RM-045 (status `in-progress` — flip to `done` + PR link at
  merge). **Red-first:** AC1–AC10 authored pre-implementation; 10/10 failed
  with `scripts/session_guard.py missing — session-tree guard not
  implemented` (the missing behavior, not fixture noise); post-implementation
  10/10 green. **Coverage gate:** no mislayered AC test (AC8/AC9 stay
  subprocess-level — they prove real process-group kill and CLI exit codes);
  one expansion on a real gap — `test_dead_stream_detection` (the registry's
  `dead-stream` detector had no AC), proven break→red (`sessions: []` defect
  named)→restore→green; no other high-value gap found. **Mechanical
  deviations (Step 4, none contract-breaking):** (1) CLI carries test seams
  `--db`, `--fixed-now` (+ `--logs-dir`, `--stall-seconds`, explicit
  `--retry-cap`/`--retry-window-min`); `--budget-minutes 0` disables. (2)
  `--wrap -- CMD` is split by hand — argparse REMAINDER mishandles the `--`
  separator. (3) `kill-child` is surfaced with session ids, not executed:
  an in-session Task child has no separate pid (its kill is the root abort)
  and a run-vehicle child is already bounded by `dispatch_agent.py --timeout`
  — ladder rung preserved as reporting, root abort stays mechanical. (4)
  Budget is literal tree wall clock (`now − root.time_created`); a long-lived
  root in observe mode tunes `--budget-minutes` or sets 0. (5) `wave_min_children=2`
  — a solo dispatch is not a wave. **Verification:** every command in the
  plan's `## Verification` exits 0 (11/11 `test_session_guard.py`; full
  offline chain; validate_skill; node suites; yamllint). **AC13 live smoke
  (2026-10-07T19:15Z, read-only):** `session_guard.py --parent
  ses_ef8102f5dffevLUPFG0feyKAX8 --once --json` — 14 nodes, verdict `abort`;
  `empty-result` flagged on exactly the three empty reviewers (PR 16/17/18 →
  `0KbYoS`, `0ddLo4`, `pVkqvR`); `wave-failure` evidence reads `wave@1791388128200:
  3/5 children failed with empty-result` — the incident shape, detected.
  JSON archived at `.scratch/session-guard/smoke-2026-10-07.json` (goes in
  the PR description at merge). UX/runtime-UI validation skipped — CLI
  tooling, no visible UI (explicit negative). Status left `approved` per the
  user's convention; RM-045 row flip deferred to the merge step.
- 2026-10-07 — **independent review + fix pass.** Review via `reviewer`
  subagent (Task `ses_ee4a1c83effeNVJAXGEUXk2OUu`, read-only). Delegated
  result **valid** per RM-023 (`Verdict` + `Findings` markers present;
  outcome recorded `clean` — a real request-changes verdict, not silence).
  Verdict: **request-changes** (2 major, 4 minor, 3 nit). All findings fixed
  in-pass: (1) major — observe mode now honors `--watch N` (continuous
  re-scan; exits on the first abort-class fire so the one-sentinel/one-record
  contract holds) + `test_observe_watch_rescans`; (2) major — `kill_group`
  probes GROUP liveness (`killpg(pgid, 0)`) and always SIGKILLs the group
  after grace, never early-returning because a reaped leader is gone;
  discriminating `test_kill_group_spares_no_lingering_member` (setsid leader
  exits and is reaped, SIGTERM-ignoring member survives SIGTERM) — proven
  break (leader-only probe → red "member survived the group abort") → restore
  → 15/15 green; AC8 fixture now also spawns a grandchild and polls both pid
  handshakes; (3) unknown `--contract` exits 4 + test; (4) missing root
  session exits 4, never a clean pass over an empty node set + test; (5)
  RM-045 row no longer pins a drifting test count; (6) `permission-auto-reject`
  evidence carries the `--allow-dirs` hint (plan registry text), asserted in
  AC3 and stated in §5; (7) wrap mode waits 0.3s between spawn and first scan
  (startup-handshake race) + pidfile polling in AC8; (8) retry-loop evidence
  uses a stable sha256 "title digest" (was PYTHONHASHSEED-randomized `hash()`);
  (9) `delegated-result-contract.md` says "(with `--contract`)" for marker
  validation. Suite now 15 cases (10 AC + 5 expansion/review-fix); full plan
  `## Verification` re-run — every command exits 0. Reviewer note: the review
  did not execute the suite (read-only discipline); the fix pass did.

### Follow-ups

- `dispatch_agent.py --guard` auto-launch wrapper (plan Excluded; candidate
  for RM-024/RM-044 hardening once the guard is proven live).
- At merge: flip RM-045 to `done` with the PR link; consider a one-line
  RM-024 note that its acceptance is now mechanically enforced by
  `identical-retry-loop`.
