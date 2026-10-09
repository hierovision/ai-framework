---
slug: session-guard-task-child-lifecycle
title: Fix session_guard false empty-result/wave-failure/stalled verdicts on in-session-Task children
status: approved
created: 2026-10-09
revised: [2026-10-09]
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

### Revised 2026-10-09 — second detector gap folded (permission-scan precision)

Discovered during D2's live re-scan (reported by the implementer, verified
against the code): `_part_blob` concatenates ALL parts — tool outputs
included — so a child that merely READS a file containing denial-shaped
literals (the guard's own source lines 80–82, or
`reference/subagent-supervision.md` §1, which quotes the denial format)
false-triggers `permission-auto-reject`. Observed on D1's implementer
session (`ses_ede888d72ffe…`) during the AC7 re-scan. Same trust-erosion
class, same file, and a live interference vector for the
`facilitating-product-vision-skill` implement pass (its subagents read the
supervision reference by citation) — folded into this plan and PR rather
than spawned separately, per the same severity/interference test the user
set. Durable record: row **RM-048** (pre-assigned; RM-047 = the lifecycle
fix, already written).

9. **Denials are read from denial carriers, not arbitrary tool output.**
   The permission scan reads only tool parts whose `state.status` is
   `"error"` (the denial carrier — the existing AC3 fixture shows that
   shape), applies `PERMISSION_RE` to that error output, and fires only
   when the denial part is the child's LATEST event and the child is not
   done (a child that got denied, recovered, and completed is not a
   denial-death). A child whose SUCCESSFUL tool output merely contains
   denial-shaped text produces no `permission-auto-reject` hit, no failed
   classification, and no `wave-failure` inflation. — Verifier: two new
   hermetic cases in `scripts/test_session_guard.py` — (i) successful-output
   false-positive case (line-numbered guard-source text in a completed
   tool's output → no hit), red → green; (ii) recovered-child case (denial
   part followed by later events, no hit) — plus the existing AC3 case
   stays green (regression guard).
10. **Live re-scan fully clean.** The AC7 re-scan of the incident tree —
    now including D1's implementer session (`ses_ede888d72ffe…`) — shows
    no `empty-result`, no `wave-failure`, no `stalled`, and no
    `permission-auto-reject` hit on any child. — Verifier: `python3
    scripts/session_guard.py --root ses_edec99dc1ffeIrvrBMcc4ZTvq5 --once
    --json --budget-minutes 0` — no hits for any child session.

### Revised 2026-10-09 (2) — review verdict request-changes: OQ1 resolved, done predicate tightened

Independent review of PR #105 (reviewer dispatch, 2026-10-09) returned
**request-changes** with one major: the `done` predicate
(`has_result = non-empty text + no in-flight tool`) over-approximates
completion — a still-streaming text-only child, a hung child carrying
interim text plus trailing completed tool parts (the pre-fix `stuck1`
shape, a TRUE positive the fix traded away), and a denial preceded by
interim text each go permanently silent. OQ1 is resolved by the terminal
marker instead of a loosened gate — verified against the live DB (the
2026-10-09 incident children's last assistant messages end
`step-start → reasoning → text → step-finish`):

11. **Conservative `done` predicate (terminal marker).** A child is done
    only when its LAST assistant message carries BOTH a non-empty text
    part AND a terminal `step-finish` part, AND no tool call is in flight.
    A message without `step-finish` is an unfinished turn regardless of
    the text it already emitted. The three silent shapes above are each
    NOT done and surface under the normal rules (streaming → no hits;
    quiet + unfinished turn → STALLED via liveness; denial-as-latest-event
    → `permission-auto-reject`). — Verifier: three red-first hermetic
    cases pinning those shapes, red → green; the AC2/AC3/AC5 cases stay
    green (a real completed turn still classifies done).
12. **One completion predicate across both surfaces.**
    `watch_agent.analyze_session`'s `has_result` and the guard's done
    predicate are the SAME semantics (parts-view derivation of the
    terminal-marker rule), so the two supervision surfaces cannot disagree
    on a session's state. — Verifier: a hermetic case asserting the two
    surfaces agree on the three shapes and on a real completed turn; plus
    the denial-latest-event comparison keyed on max `time_created` (not
    part index), so a timestamp tie cannot downgrade a denial-death to
    `empty-result` — hermetic case red → green.

## Files to Modify

- `scripts/session_guard.py` — add `has_result` computation; re-order the
  per-child result/liveness classification per the approach; `wave-failure`
  counts only actually-failed children. Revised 2026-10-09: the permission
  scan narrows to error-state tool parts (denial carriers), gated on the
  denial being the latest event and the child not done (AC9)
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
  holds RM-046 — do not renumber). Revised 2026-10-09: RM-048 row added for
  the permission-scan precision fix (same PR, separate durable record)

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

- **OQ1 — RESOLVED (revision 2).** The completion predicate is the terminal
  marker (`step-finish` after a non-empty text part in the last assistant
  message + no in-flight tool), not a loosened gate; the interim-text
  shapes surface under the normal stalled/permission rules (ACs 11–12).

## History

- 2026-10-09 — **Revision 2 (review-driven).** Independent review of
  PR #105: **request-changes**, one major — the `done` predicate
  over-approximates completion (three silent true-positive shapes; the
  pre-fix `stuck1` stall shape traded away). OQ1 resolved by terminal
  marker (`step-finish` after the non-empty text part in the last
  assistant message — verified in the live DB), not by loosening the gate;
  ACs 11–12 added (conservative predicate; one shared predicate across
  both surfaces + timestamp-keyed denial recency). D4 executes on the same
  branch/PR. Minors folded: divergent `has_result` definitions (watch vs
  guard) unified; denial latest-event keyed on max `time_created`. Plan
  retirement note (AGENTS.md rule 4 / #102 convention): this plan is
  deleted at merge time — its essence lives in RM-047/RM-048 +
  `reference/subagent-supervision.md` §5.
- 2026-10-09 — **Revision: second detector gap folded (AC9/AC10, RM-048).**
  D2's live re-scan surfaced the `_part_blob` scan-surface false positive
  (a child reading the guard's own source / the supervision doc's quoted
  denial format false-triggers `permission-auto-reject`; observed on D1's
  session `ses_ede888d72ffe…`). Verified against `PERMISSION_RE` (line 80)
  and the AC3 fixture's denial carrier (error-state tool part). Folded into
  this plan + PR per the user's severity/interference test; D3 executes it
  on the same branch.
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
- 2026-10-09 — **D3 complete (revised scope: AC9/AC10, RM-048).** The
  permission scan no longer reads `_part_blob`'s all-parts concatenation
  (tool output included); it reads ONLY denial carriers — tool parts whose
  `state.status == "error"` — applies `PERMISSION_RE` to that error output
  (`state.output`, the AC3 fixture shape, and `state.error`, the field real
  opencode error parts carry), and fires only when the denial part is the
  child's LATEST event and the child is not done. A recovered child (denial
  followed by later events) and a child whose SUCCESSFUL tool output merely
  quotes denial-shaped text (reading `session_guard.py`'s own `PERMISSION_RE`
  literals or `reference/subagent-supervision.md`'s quoted format) no longer
  false-trigger. Red-first: 20/22 guard pre-fix — both new cases
  (`test_permission_scan_ignores_successful_tool_output`,
  `test_permission_scan_ignores_recovered_child`) failing on
  `permission-auto-reject` — → 22/22 post-fix; AC3's denial-carrier case
  stays green; watch 12/12 unchanged; the full CONTRIBUTING.md offline gate
  exits 0. AC10 live re-scan of the incident tree
  (`python3 scripts/session_guard.py --root ses_edec99dc1ffeIrvrBMcc4ZTvq5
  --once --json --budget-minutes 0`) is `clean` with zero hits — the three
  pre-fix false positives (`ses_ede888d72ffe…` + `ses_ede812608ffe…` +
  `ses_ede7b68b6ffe…`, all quoting the guard's own source from completed
  tool output) are gone. RM-048 lands in `docs/ROADMAP.md`; PR #105 body
  updated.
- 2026-10-09 — **D4 complete (revision 2 scope only: AC11/AC12; review
  request-changes major closed).** The done predicate is now the terminal
  `step-finish` marker — a non-empty last text part immediately followed by
  `step-finish` with no tool in flight — implemented once as
  `watch_agent.has_terminal_result(parts, running)` and called by both
  surfaces (`analyze_session`'s `has_result`; `session_guard`'s per-child
  `done`), so the two supervision surfaces share one predicate. The
  permission scan's recency test is now `denial["ms"] == max(time_created)`
  instead of part index (AC12 tie fix). Red-first: 23/26 guard pre-fix —
  `test_hung_interim_text_restored_stalled` (`[]`; the interim-text hung
  child was marked done and went silent), `test_denial_preceded_by_text_restored`
  (`[]`; the text made the child done and suppressed the denial),
  `test_denial_latest_event_keyed_on_timestamp_not_index`
  (`['empty-result','stalled']`; the index-keyed check downgraded the denial
  to empty-result) — → 26/26 post-fix; `test_streaming_text_only_child_not_done`
  is green both ways (regression guard on the streaming shape). Watch 13/13
  (the AC5 completed fixture now models the real `text → step-finish` turn;
  new `test_two_surfaces_agree_on_completion` pins the three shapes and the
  shared-predicate identity). Full CONTRIBUTING.md offline gate exits 0.
  AC10 re-scan (live opencode.db, `--budget-minutes 0`): all six incident
  children classify `done` (no `empty-result`/`wave-failure`/`stalled`/
  `permission-auto-reject` hit); the only hit is a pre-existing
  `blocking-wait` on the newer reviewer session `ses_ede753cdbffe…` (a
  genuine 545s quiet gap), identical under the D3 commit `f229583` on the
  same live DB — the tree grew from six to eight children after D3 (the
  PR-#105 review dispatch), independent of this predicate change; recorded,
  not narrowed. RM-047 row updated with the dated tightening sentence; PR
  #105 body carries the revision section.
