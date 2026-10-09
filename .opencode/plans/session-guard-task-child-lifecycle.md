---
slug: session-guard-task-child-lifecycle
title: Fix session_guard false empty-result/wave-failure/stalled verdicts on in-session-Task children
status: approved
created: 2026-10-09
related: [facilitating-product-vision-skill]
---

# Plan: session-guard-task-child-lifecycle

## Goal / Approach

Goal: `scripts/session_guard.py` stops false-failing healthy in-session
Task dispatch waves. Today it (a) classifies a still-streaming child as
`empty-result` (compounding into a `wave-failure` abort at ratio ≥ 0.6), and
(b) flags a completed child `STALLED`/`DEAD` because post-completion event
silence is read as a stall. Observed live 2026-10-09: a 3-lane research wave (sessions
`ses_edebd8e7fffe…`, `ses_edebd604affe…`, `ses_edebd273bffe…`) — all
three results received non-empty and marker-valid, result texts verified
present in `opencode.db`, while the guard emitted `empty-result` ×3 →
`wave-failure` abort, then `stalled`/`DEAD` ×2 on a post-completion re-scan.

Triage verdict (user directive 2026-10-09: fix now vs roadmap-row): **fix
now**. Severity is real — the guard is the fail-fast safety tool whose
authority depends on trust (RM-045), in-session Task is the framework's
NORMAL dispatch lane (`reference/agent-teams.md` lane policy), and the
approved `facilitating-product-vision-skill` implement pass will dispatch
subagents under the mandatory supervision contract, so the false verdicts
would misclassify healthy work mid-implementation. Fix-first sequencing is
recorded in the skill plan's History.

Approach: opencode.db carries no session completion column, so completion is
inferred honestly from the two signals the guard already reads — a non-empty
final result text (`result_text`) and no tool call in flight
(`analyze_session`'s running set). Add `has_result` to the analysis, then
re-order the guard's per-child classification:

1. `permission-auto-reject` (unchanged — a denial explains the death).
2. `dead-stream` — zero messages and zero parts (unchanged).
3. `has_result` (non-empty result text AND no in-flight tool call) → the
   child is done: **no** `empty-result` hit and **no** STALLED/DEAD liveness
   hit; with `--contract`, the completed text is still marker-validated.
4. In-flight tool call OR last event within the stall window → the child is
   streaming: **no** result-level classification yet (STALLED/DEAD tracking
   stays for genuinely hung children).
5. Otherwise (quiet past the stall window, no in-flight call, empty result)
   → `empty-result` — RM-023's real failure shape, now detected at the right
   moment instead of mid-run.

`wave-failure` counts only actually-failed children, so in-flight and
completed children stop inflating the ratio. Detection latency for a truly
dead child moves from "first scan" to "after the stall window" — accepted;
the watchdog's BLOCKING/heartbeat patterns cover the in-flight window.

Tests are red-first: the new hermetic cases fail against the current code
(proving the defect), then pass after the fix. Suites stay green: the
existing 15 guard cases and 8 watch cases are regression guards — none may
be weakened or skipped (cardinal rule).

## Acceptance Criteria

1. **In-flight child is never `empty-result`.** A fixture child whose last
   event is recent (≤ stall window) and whose final assistant message has no
   text part yet produces no `empty-result` hit. — Verifier: new hermetic
   case in `scripts/test_session_guard.py` fails on current code (red),
   passes after the fix; `python3 scripts/test_session_guard.py` exits 0.
2. **Completed child is never STALLED/DEAD and never `empty-result`.** A
   fixture child with a non-empty result text part and no in-flight tool,
   quiet past the stall window, produces no `stalled` and no `empty-result`
   hit. — Verifier: new hermetic case, red → green as in AC1.
3. **Dead-empty child is still classified (regression guard).** A fixture
   child with an empty result, no in-flight call, quiet past the stall
   window still produces the `empty-result` hit (RM-023's shape must keep
   failing loudly). — Verifier: new hermetic case asserting the hit; green
   before and after the fix.
4. **`wave-failure` counts only real failures.** A wave of 1 genuinely
   failed + 2 in-flight children produces no `wave-failure` hit (1/3 < the
   0.6 default ratio). — Verifier: new hermetic case, red → green.
5. **`watch_agent.verdict` treats a completed session as done.** With the
   analysis reporting a completed result (non-empty final text, no in-flight
   call), `verdict()` returns OK — not STALLED/DEAD — regardless of quiet
   age. — Verifier: new case in `scripts/test_watch_agent.py`, red → green;
   `python3 scripts/test_watch_agent.py` exits 0.
6. **Contract mode preserved.** With `--contract` declared, a COMPLETED
   child whose text is missing the contract markers still fails validation
   (`empty-result` hit with the malformed marker named); an in-flight child
   is skipped, not marked. — Verifier: new hermetic case, red → green.
7. **Live incident-tree re-scan.** The recorded 2026-10-09 wave tree
   (root `ses_edec99dc1ffeIrvrBMcc4ZTvq5` with its three completed children)
   re-scanned post-fix produces no `empty-result`, no `wave-failure`, and no
   `stalled` hit for the completed children. — Verifier: `python3
   scripts/session_guard.py --root ses_edec99dc1ffeIrvrBMcc4ZTvq5 --once
   --json` (run with the real `opencode.db`) shows none of those three
   patterns for the child sessions.
8. **Full offline gate stays green.** All hermetic suites in the CI
   `quality-gates` list pass. — Verifier: the CONTRIBUTING.md offline-gate
   command block exits 0 on the branch.

## Files to Modify

- `scripts/session_guard.py` — add `has_result` computation; re-order the
  per-child result/liveness classification per the approach; `wave-failure`
  counts only actually-failed children
- `scripts/watch_agent.py` — `analyze_session` reports `has_result` (final
  text part non-empty + no in-flight tool); `verdict()` skips the
  STALLED/DEAD quiet classification for a completed session
- `scripts/test_session_guard.py` — new hermetic cases for ACs 1–4, 6
  (red-first; the `_make_db`/`_result_session` fixture builders already
  simulate sessions/messages/parts — extend, do not weaken)
- `scripts/test_watch_agent.py` — new case for AC5
- `reference/subagent-supervision.md` — §5 note: in-session-Task children
  follow the same lifecycle rules; a mid-run scan never yields
  `empty-result`; a completed child is `done`, not stalled
- `docs/ROADMAP.md` — delivery row **RM-047** (pre-assigned; the skill plan
  holds RM-046 — do not renumber)

## Scope

**Included**

- The classification fix in `session_guard.py` + the `has_result`/`verdict`
  change in `watch_agent.py` (shared analysis, both supervision surfaces)
- Red-first hermetic tests for every behavior change; regression guards for
  the existing shapes (dead-stream, permission-auto-reject, identical-retry,
  budget, wave-failure-on-real-failures)
- The dated §5 contract note + the RM-047 delivery row
- Branch `fix/session-guard-task-child-lifecycle` → PR (RM-036 contract:
  lands branch + PR without prompting; merge is user-gated)

**Excluded**

- Any change to `dispatch_agent.py`'s result recording (RM-044 item 3 is a
  separate, already-tracked row)
- Any change to the failure-pattern registry's semantics or thresholds
  (ratios, stall windows stay as shipped)
- Heartbeat protocol changes (RM-044 item 1 — separate row)
- The `facilitating-product-vision-skill` implementation (separate plan,
  sequenced after this fix)

## Schema / Type Impacts

None.

## Verification

- `python3 scripts/test_session_guard.py`
- `python3 scripts/test_watch_agent.py`
- `python3 scripts/test_validate_delegated_result.py && python3
  scripts/test_delegated_result_contract.py`  # no cross-module drift
- `python3 scripts/registry.py --check`  # untouched, stays green
- `python3 scripts/session_guard.py --root ses_edec99dc1ffeIrvrBMcc4ZTvq5
  --once --json`  # live incident tree, post-fix (AC7)
- The remaining offline-gate block from CONTRIBUTING.md on the PR branch

## Open Questions

- **OQ1 — `has_result` strictness for text-only interim turns.** The
  parts-only view cannot distinguish "final assistant message" from "an
  interim turn's text part" without a message-role join.
  *Proposed default:* `analyze_session` treats the session's LAST text part
  as the result tail (matching `result_text`'s last-assistant-message
  behavior closely enough because a newer turn inserts newer parts), and the
  no-in-flight-tool gate handles the streaming case. If the implementer's
  red test shows a real false-done case, prefer the message-role join over
  loosening the gate.

## History

- 2026-10-09 — **Approved** by the user's directive ("fix it now depending
  on severity and whether it will interfere"); severity/interference verdict
  recorded in Goal/Approach. Execution split: D1 (code + red-first tests +
  suites green + branch commit) / D2 (live re-scan, push, PR, RM-047 row,
  plan staging).
- 2026-10-09 — **D1 complete** (implementer dispatch
  `ses_ede888d72ffeode3jSjKNIRtRm`, commit `1675a94` on
  `fix/session-guard-task-child-lifecycle`, +211/−21): red-first proof
  captured — 16/20 pre-fix with each new case failing on the named missing
  behavior (AC1 empty-result on an in-flight child; AC2 stalled on a
  completed child; AC4/AC6 wave-failure inflation); post-fix 20/20 guard +
  12/12 watch + the full CONTRIBUTING.md offline gate exit 0. One mechanical
  plan-vs-reality adjustment (implementing-features Step 4 class):
  the existing `stuck1` liveness fixture asserted `stalled` on a child
  carrying a COMPLETE result text — under AC2/AC5 semantics that child is
  `done`, so the fixture now models a genuinely hung child (`text=None`)
  and still asserts `blocking-wait` + `stalled`; no assertion weakened or
  removed, and the case is green before and after the fix. The plan's "8
  watch cases" count was stale (11 before, 12 after) — corrected here, no
  behavioral impact.
- 2026-10-09 — **D2 complete** (this PR). AC7 live re-scan of the recorded
  2026-10-09 incident tree (`python3 scripts/session_guard.py --root
  ses_edec99dc1ffeIrvrBMcc4ZTvq5 --once --json --budget-minutes 0`) shows no
  `empty-result`, no `wave-failure`, and no `stalled` for the three completed
  children (`ses_edebd8e7fffe…`, `ses_edebd604affe…`, `ses_edebd273bffe…`) —
  the fix classifies all three as done. The scan's only hit is an unrelated
  `permission-auto-reject` flag on the later D1-implementer session
  `ses_ede888d72ffe…`, whose part blob contains the guard's own
  `permission denied` regex literals (read back from `session_guard.py` /
  `reference/subagent-supervision.md`); recorded as a detector false positive
  (tool output is scanned as session content) for the orchestrator — not one
  of AC7's three lifecycle patterns and not an AC7 failure. RM-047 row lands
  in `docs/ROADMAP.md`; branch `fix/session-guard-task-child-lifecycle`
  pushed, PR opened.
- 2026-10-09 — Triage of the RM-027 candidate captured during the
  `facilitating-product-vision-skill` design pass: live evidence (3/3 false
  `empty-result` → false `wave-failure` abort; post-completion
  `stalled`/`DEAD` ×2; result texts verified present in `opencode.db`),
  severity judged real (safety-tool trust + the normal dispatch lane +
  imminent interference with the approved implement pass), disposition
  **fix now** per the user's directive ("either roadmap or fix it now
  depending on severity and whether it will interfere"). The guard's own
  false-abort record already sits in `logs/run-2026-10-09.jsonl`
  (`agent=session-guard, outcome=stopped`) — kept as the incident evidence;
  no separate GitHub issue is opened because the fix lands in this pass and
  RM-047 is the durable record.
