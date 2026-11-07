---
slug: rm-074-observer-signal-quality
title: Make delegation-observer signals actionable, attributed, progress-aware, and rebuild-safe
status: draft
created: 2026-11-07
revised: [2026-11-07]
related: [RM-070, RM-072]
---

# Plan: rm-074-observer-signal-quality

## Goal / Approach

**Goal:** An owner sees only current or recently terminal delegates, can tell
which root session each signal belongs to, is not warned about normal editing,
and never receives a second attention wake for the same child condition after
an observer rebuild.

**Approach:** Deliver four workstreams in one implement pass. Keep the pure
reducer and projections decision-bearing, keep `tui.tsx` presentational, and
leave the existing host APIs and trusted-root wake path unchanged.

### WS1 — Terminal aging and sidebar hygiene

- Add outcome-specific display windows: `terminalGraceSeconds` for completed
  delegates (default 300 seconds) and `failedTerminalGraceSeconds` for terminal
  failures (default 3600 seconds). Both are TUI display settings, not server
  supervision thresholds. Carry them through the existing options/env seam.
- Change observed-terminal staleness to use `terminal.at`. Preserve immediate
  staleness for store-terminal rows that were never observed, archived rows,
  and the existing discovery/liveness rules. A clock-classified `failed` row
  without `d.terminal` remains actionable; it is not terminal failure.
- Project `terminalAt` and use one sidebar-eligibility projection for the
  sidebar and footer. Stale/archived rows never render there. The hidden-count
  line moves out of the sidebar and footer and remains only in `session.panel`.
  A stale-only model produces no sidebar heading or lines.
- Keep the sidebar cap at eight delegate rows. Existing non-stale `unknown`
  rows keep their current visibility and control semantics.

### WS2 — Root scope and labelling

- Add a pure, bounded, cycle-safe bulk association helper that indexes the
  existing `session.list()` result and resolves each delegate's display
  `rootID` through `parentID`/`parent_id`, with the existing title marker as
  fallback. Use it in server bootstrap and in the TUI bootstrap/refresh path.
  Do not add an active-session lookup or change `session.list()`.
- Keep `orchestratorID` as the immediate association used by the existing
  trusted-root resolver. `rootID` is presentation metadata only; it must not
  bypass or replace `resolveParent`, the root trust check, or the same-directory
  gate. An unresolved/cyclic chain is labelled unresolved and must never guess
  another root.
- Label each sidebar/panel row with its owning root rather than filtering to an
  active root or spending extra lines on group headings. Use the shortest root
  prefix unique among the listed roots in the capped sidebar, lengthening on a
  collision; use the full root id in the panel and toast/attention title and
  message body. Root B's milestone must never be labelled root A. The display
  prefix is added in the TUI only; the server's synthetic wake text is unchanged.

### WS3 — Progress-aware thrash

- Count a loop over a stable fingerprint of the complete tool input plus the
  resolved tool name and target, not over the target alone. Canonicalize object
  keys before fingerprinting so semantically identical input is stable. Keep
  the existing call-id guard so event re-delivery counts once. A changed edit
  payload starts a new loop sequence; identical calls accumulate.
- Preserve the existing condition key (`thrash:<target>`) for RM-070 dedupe;
  the input fingerprint classifies progress and must not multiply wake
  conditions. Do not infer file progress merely from a successful tool status.
- Keep `loopRepeats=3` for bash/shell/read/grep and other tools. Source the
  existing edit/write threshold of 8 from `watch_agent.py` through the generated
  supervision contract as `editWriteLoopRepeats` /
  `edit_write_loop_repeats`. The Python change names the existing constant; it
  does not change watchdog behavior.

### WS4 — Wake dedupe across observer rebuilds

- Expose the reducer's existing condition key on `Milestone` as internal
  metadata. In `server.ts`, guard wake-eligible attention delivery
  (`thrash`/`stall`/`needs-input`/`denied`) with a persistent per-condition
  claim under `<location>/.scratch/delegation-observer/attention-claims/`.
  Use an atomic exclusive-create claim file named by a hash of child id plus
  condition key. Record child, root, condition, wake flag, observer pid,
  location, and timestamp for post-hoc evidence.
- Check the claim only after the existing trusted-root and same-directory
  gates. An existing claim suppresses the duplicate synthetic and writes a
  structured dedupe log. A rejected synthetic releases its new claim so a later
  observer can retry. Untrusted or out-of-location milestones never create a
  claim. Routine, retry, and terminal delivery do not use this ledger.
- Claim before sending to prefer no duplicate over a crash-time double wake.
  Document the remaining crash window: a process can die after claiming and
  before sending, so this is at-most-once delivery, not transactional
  exactly-once delivery. Keep `attentionWakes` and `maxAttentionWakes` per
  observer process; do not persist or reinterpret the cap.
- Add an internal `claimsDirectory` start option for hermetic tests. Default to
  the location-derived path, or the health-file sibling when explicitly
  supplied. A location-less test/host without an injected directory retains
  in-process dedupe only and logs that durable dedupe is unavailable.

## Acceptance Criteria

1. **Observed terminal rows age at the configured outcome boundary.** With a
   fixed clock, an observed completed row is sidebar-eligible for
   `now - terminal.at < 300_000 ms` and stale at `>= 300_000 ms`; an observed
   terminal-failed row is eligible for `< 3_600_000 ms` and stale at
   `>= 3_600_000 ms`. A 2-minute completed row is present and a 12-hour one is
   absent. Store-terminal-but-never-observed rows remain immediately stale;
   archived rows remain stale; running/waiting/warning and non-terminal failed
   rows do not age through these windows.
   **Verify:** `state.test.ts` test `observed terminal rows age by outcome` and
   `tui.test.ts` test `terminal visibility uses terminal at and outcome grace`
   pass under `node --test plugins/delegation-observer/state.test.ts
   plugins/delegation-observer/tui.test.ts`.

2. **Sidebar and footer contain current signals, not history accounting.**
   `model.sidebar()` returns the eligible display lines, including a recent
   terminal row, and returns `[]` for a stale-only state. The real strip uses
   that projection, so stale-only state renders neither `Delegates` nor
   `N stale delegates hidden`. The footer never emits a hidden-count line.
   A pure `panelHistoryLine` helper returns
   `N stale delegates hidden (alt+g to inspect)` for the panel alone; the real
   panel uses it and retains history access. Eight eligible delegate rows
   remain the default cap; stale rows do not consume it.
   **Verify:** `tui.test.ts` tests `sidebar hides stale rows and keeps history
   in the panel` and `stale only state has no sidebar or footer count`, plus
   `model.test.ts` test `the sidebar projection is empty for stale only rows`,
   pass under `node --test plugins/delegation-observer/tui.test.ts
   plugins/delegation-observer/model.test.ts`.

3. **Terminal display configuration is deterministic and host-independent.**
   Defaults are `terminalGraceSeconds=300` and
   `failedTerminalGraceSeconds=3600`. `DELEGATION_OBSERVER_TERMINAL_GRACE_SECONDS`
   and `DELEGATION_OBSERVER_FAILED_TERMINAL_GRACE_SECONDS` fill missing options;
   forwarded options win per key; zero, negative, non-numeric, and non-finite
   values are ignored. `projectDelegate` exposes the exact numeric `terminalAt`
   or `null`. The server-only `attentionEnvConfig` does not acquire either TUI
   display key.
   **Verify:** `state.test.ts` tests `terminal grace config defaults env and
   option precedence` and the existing `the server attention env seam excludes
   TUI-only keys`, plus `tui.test.ts` test `terminal at is projected without
   fabrication`, pass under `node --test
   plugins/delegation-observer/state.test.ts
   plugins/delegation-observer/tui.test.ts`.

4. **Bootstrap and rebuild attribute every row to its own root.** A fixture
   with roots A and B, a direct child of A, a nested child below a worker of A,
   and a title-marked vehicle for B produces `rootID=A` for A's descendants and
   `rootID=B` for the vehicle. Rebuilding state from the same session list
   reproduces the same labels. A cycle or missing parent produces an unresolved
   label, never the other root. No active-session property is added to the host
   mock.
   **Verify:** `state.test.ts` test `bulk association resolves roots across a
   store rebuild`, `tui.test.ts` test `rows carry their owning root label`, and
   `model.test.ts` test `two roots keep bootstrap and event rows attributed`
   pass under `node --test plugins/delegation-observer/state.test.ts
   plugins/delegation-observer/tui.test.ts
   plugins/delegation-observer/model.test.ts`.

5. **Toasts name the owning root without changing wake routing.** An attention
   milestone for root B produces toast and attention titles and message bodies
   containing full root B and not root A; a root A milestone names A. Terminal
   notices carry the same attribution. Existing server tests for depth-2
   routing, title-marked vehicles, trusted roots, and same-directory emission
   remain green, and the `session.synthetic` destination/text/`resume` rules are
   unchanged.
   **Verify:** `model.test.ts` test `attention and terminal toasts name their
   owning root` and the existing `server.test.ts` root/trust suite pass under
   `node --test plugins/delegation-observer/model.test.ts
   plugins/delegation-observer/server.test.ts`.

6. **Normal edits do not thrash; identical non-progress calls still do.** Six
   distinct edit payloads for one file, each with a new call id and changed
   `oldString`/`newString`, emit zero thrash. Three identical failing
   bash/shell/read calls emit exactly one thrash at the third distinct call.
   Seven identical edit/write calls emit none and the eighth emits exactly one.
   Re-delivering one call id still counts once.
   **Verify:** `state.test.ts` tests `distinct edits to one file are progress
   not thrash`, `three identical failing calls thrash once`, and `edit and
   write loops fire at eight while other tools use three` pass. The existing
   `state.test.ts:281-300` block `repeated content updates for one tool call
   never count as thrash` remains byte-unchanged and green under
   `node --test plugins/delegation-observer/state.test.ts`.

7. **The edit/write threshold has one owner and a generated contract.**
   `watch_agent.DEFAULT_LOOP_REPEATS` remains 3,
   `watch_agent.EDIT_WRITE_LOOP_REPEATS` is 8, the generated JSON contains
   `edit_write_loop_repeats: 8`, and `DEFAULTS.editWriteLoopRepeats` equals it.
   Seven identical edits still produce no Python loop hit and eight produce
   one; bash behavior is unchanged.
   **Verify:** `state.test.ts` test `thresholds are the shared supervision
   contract, not guessed here`, `scripts/test_watch_agent.py` test
   `test_edit_write_loop_threshold`, and `scripts/test_supervision_contract.py`
   pass. `python3 scripts/supervision_contract.py --check` exits 0 without a
   generated-file edit after regeneration.

8. **One attention condition is not re-delivered after a rebuild.** Observer A
   receives three identical failing calls for child C/condition K and emits
   exactly one matching `session.synthetic` with `resume:true`. After A stops,
   fresh observer B uses the same claims directory, bootstraps C as
   pre-existing, and replays the sequence. B emits zero matching synthetics;
   the combined count remains one. A distinct condition on C still follows the
   current wake rules. The claim record contains C, K, root, wake, pid,
   location, and timestamp, and B logs the dedupe skip.
   **Verify:** `server.test.ts` test `attention condition is not redelivered
   after observer rebuild` passes under
   `node --test plugins/delegation-observer/server.test.ts`. The fixture uses
   the persisted 2026-11-07 metadata shape but synthetic event payloads; tests
   never read the production database or logs. The healthy 2026-11-07 edit
   sequence belongs to AC6 and now produces zero wakes, so it is not reused as
   a valid thrash condition here.

9. **Wake authority, cap, and failure behavior do not drift.** The existing
   per-child cap tests, disabled-wake tests, routine/terminal non-wake tests,
   untrusted-root tests, and same-directory tests stay green. An untrusted
   milestone creates no claim. A rejected first synthetic releases the claim;
   a second observer may deliver it. A second distinct condition still consumes
   only the current process's existing cap.
   **Verify:** existing `state.test.ts` test `attention wakes are capped per
   child and the excess stays context`, existing `server.test.ts` cap/trust
   tests, and new `server.test.ts` tests `untrusted attention creates no durable
   claim` and `a rejected synthetic releases its durable claim` pass under
   `node --test plugins/delegation-observer/state.test.ts
   plugins/delegation-observer/server.test.ts`.

10. **Every new guard has red-first or break/restore evidence.** Before the
    production edit, every test for absent new behavior fails for the named
    missing behavior. Regression/characterization cases start green instead of
    manufacturing a false red: these include `state.test.ts:281-300`, identical
    failing calls at threshold 3, call-id dedupe, cap/trust/routine/terminal
    behavior, and Python's existing edit/write-8 policy. The new no-claim and
    rejected-send rollback cases are proven by targeted mutation because they
    can also pass before a ledger exists. `mutation-check.mjs` adds proofs named
    `observed-terminal-never-ages`, `sidebar-includes-stale`,
    `root-uses-immediate-parent`, `loop-ignores-input-fingerprint`,
    `edit-write-uses-generic-loop-cap`, `wake-claim-ignored-on-rebuild`,
    `untrusted-creates-claim`, and `rejected-send-keeps-claim`. Each mutation
    turns its mapped test red, restores the source byte-for-byte, and leaves
    the full suite green. Existing mutation anchors affected by the
    terminal/sidebar changes are updated to equivalent guards, not deleted.
    **Verify:** red-first output and the named pre-green characterization cases
    are stored outside git under `.scratch/rm-074/red-first/` and cited in the
    implementation PR; `node plugins/delegation-observer/mutation-check.mjs`
    exits 0 with all eight new proofs and zero failures.

## Files to Modify

- `plugins/delegation-observer/state.ts` — terminal grace config/staleness;
  bulk root association; root/condition metadata; canonical input fingerprint;
  per-class loop threshold.
- `plugins/delegation-observer/view.ts` — `rootID`/`terminalAt` row fields;
  shared sidebar eligibility and root labels; footer/panel history policy.
- `plugins/delegation-observer/model.ts` — bulk bootstrap/refresh association;
  sidebar projection; root-labelled toast/attention titles and message bodies.
- `plugins/delegation-observer/server.ts` — bulk bootstrap; persistent
  attention claims; successful-emission/dedupe/durability logs.
- `plugins/delegation-observer/tui.tsx` — render the model sidebar projection
  and root/terminal fields; keep the hidden-count line only in the panel.
- `plugins/delegation-observer/state.test.ts` — fixed-clock terminal/config,
  root, progress/threshold, and unchanged wake-cap coverage. Keep lines 281–300
  byte-unchanged.
- `plugins/delegation-observer/tui.test.ts` — terminal visibility, sidebar /
  footer / panel policy, and root projection coverage.
- `plugins/delegation-observer/model.test.ts` — two-root bootstrap/events,
  stale-only sidebar projection, and root-labelled toast coverage with no
  active-session API.
- `plugins/delegation-observer/server.test.ts` — rebuild replay, claim contents,
  rejected-send rollback, and untrusted/no-claim coverage.
- `plugins/delegation-observer/mutation-check.mjs` — eight new break/restore
  proofs and equivalent updates to affected existing anchors.
- `plugins/delegation-observer/README.md` — new display config, root labels,
  progress semantics, claim storage/durability ceiling, and verification.
- `scripts/watch_agent.py` — name the existing edit/write threshold as
  `EDIT_WRITE_LOOP_REPEATS=8` and use that constant; no behavior change.
- `scripts/test_watch_agent.py` — characterize seven versus eight identical
  edits and unchanged bash threshold behavior.
- `scripts/supervision_contract.py` — publish
  `edit_write_loop_repeats` from the watchdog owner.
- `scripts/supervision_contract.json` — regenerate with
  `python3 scripts/supervision_contract.py --write`; never hand-edit.
- `scripts/test_supervision_contract.py` — assert the new generated threshold
  equals its watchdog owner.
- `reference/subagent-supervision.md` — §7 observer display/classification and
  at-most-once attention-delivery contract; retain RM-070 cap/wake rules.
- `docs/ADRs/ADR-0015-observable-delegation.md` — dated RM-074 amendment for
  display aging/root labels/progress classification and durable condition
  claims; explicitly retain trusted-root, terminal-wake, and per-process-cap
  decisions.
- `docs/roadmap-detail/RM-074.md` — implementation evidence, final decisions,
  verification results, live-drill result, and closure evidence.
- `docs/ROADMAP.md` — same-PR RM-074 status/horizon/counters/PR-link closure per
  `reference/git-workflow.md` §Roadmap closure.
- `.opencode/plans/rm-074-observer-signal-quality.md` — record implementation
  deviations/evidence in History during the pass; retire before merge after the
  durable docs carry the essence, per AGENTS.md rule 4.

## Scope

### Included

- Observed-terminal aging, two TUI display grace settings, terminal timestamp
  projection, sidebar/footer hygiene, and panel-only history accounting.
- Host-independent root attribution and root-labelled rows/toasts from the
  existing session list and title marker.
- Full-input progress fingerprints, edit/write threshold 8, other-tool
  threshold 3, and generated supervision-contract propagation.
- Persistent attention-condition claims across observer rebuilds, diagnostic
  claim/log evidence, and rejected-send rollback.
- Unit/model/server tests, red-first evidence, mutation proofs, observer
  documentation, and same-PR roadmap closure.

### Excluded

- No active-root filtering and no host/plugin API additions; no change to
  `session.list()` or any host binding.
- No change to RM-070/ADR-0015 wake kinds, `resume` behavior, per-process
  `maxAttentionWakes` semantics, trusted-root gate, or same-directory gate.
- No change to the Python terminal wake, `scripts/observe_completion.py`,
  quiescence/deadline behavior, dispatch vehicle, or session guard.
- No RM-072 routine-milestone coalescing and no broader TUI redesign.
- No new milestone kinds, association registry, or synthesized rows for
  unassociable running children; the existing association-gap banner remains.
- No pruning/compaction of claim files and no transactional exactly-once claim
  across a process crash; those need separate operational evidence and design.
- No production database/log reads in tests and no committed `.scratch`
  captures, claim files, logs, or `node_modules`.
- No watchdog behavior change beyond naming/exporting its existing edit/write
  threshold; no edit to generated JSON by hand.
- No dependency/version changes and no package manifest/lockfile changes.

## Schema / Type Impacts

No database, SQL migration, generated database type, RPC, or host/plugin API
change.

Internal TypeScript types change additively:

- `ObserverConfig` gains `terminalGraceSeconds`, `failedTerminalGraceSeconds`,
  and `editWriteLoopRepeats`.
- `Delegate` and `DelegateRow` gain display `rootID`/resolution metadata;
  `DelegateRow` also gains `terminalAt: number | null`.
- `Milestone` gains the existing reducer condition key as internal delivery
  metadata. The `session.synthetic` request shape and RM-070 `wake`/`attention`
  metadata semantics stay unchanged.
- `scripts/supervision_contract.json` additively gains
  `edit_write_loop_repeats`, generated from `watch_agent.py` by
  `scripts/supervision_contract.py`. Regenerate it; never hand-edit it.

The runtime claim files are local observer state, not a shared schema or a new
host API. Claim existence is the dedupe marker; the JSON content is diagnostic.
A malformed record must not crash startup or be treated as a different
condition. A claim-directory I/O failure falls back to in-process dedupe and
logs that durable dedupe is unavailable.

## Verification

### Red-first protocol

1. Add the AC tests before their production guards. Run each focused file and
   save the expected failure output under `.scratch/rm-074/red-first/`.
   Characterization tests for unchanged behavior are the explicit exception:
   they must start green and stay green.
2. Implement only this plan. Do not weaken, skip, delete, or broaden a test to
   make it pass. Update expected sidebar history text only where AC2 changes
   that contract, and add assertions for the replacement behavior.
3. Add the eight mutation proofs. The checked-in mutation runner must prove
   the expected test fails, restore every source byte, and rerun the full suite.
4. Record red-first filenames, pre-green characterization cases, final counts,
   and any mechanical plan deviations in the implementation PR and plan
   History.

### Commands

```bash
npm ci --prefix plugins/delegation-observer --no-audit --no-fund
python3 scripts/supervision_contract.py --write
python3 scripts/supervision_contract.py --check
python3 scripts/test_supervision_contract.py
python3 scripts/test_watch_agent.py
node --test plugins/delegation-observer/state.test.ts
node --test plugins/delegation-observer/tui.test.ts
node --test plugins/delegation-observer/server.test.ts
node --test plugins/delegation-observer/model.test.ts
node --test plugins/delegation-observer/state.test.ts plugins/delegation-observer/tui.test.ts plugins/delegation-observer/server.test.ts plugins/delegation-observer/model.test.ts plugins/delegation-sentinel/sentinel.test.ts
npm run typecheck --prefix plugins/delegation-observer
node plugins/delegation-observer/mutation-check.mjs
python3 scripts/check_roadmap_verbatim.py
git diff --check
```

The implementer also runs each new focused test before the production change,
as required by AC10; the commands above are the final gate, not a substitute for
that red-first record.

### Live TUI drill and manual-validation handoff

After the hermetic gates, run an isolated two-root/two-child TUI drill on a
disposable service. Capture the sidebar, footer, and `session.panel` at a fixed
test-clock boundary where possible. The evidence must show root A/B labels, no
 cross-root toast label, a recent completed row, its disappearance at five
 minutes, a terminal failure retained for 60 minutes, no stale-count outside
 the panel, no thrash for six distinct edits, one thrash for three identical
 failing calls, and no duplicate wake after restarting the observer against the
 same claims directory. Store captures under `.scratch/rm-074/live/` and cite
 them in the PR; do not commit them.

The live drill must specifically review short-root label comprehension,
 truncation at 64 columns, the empty stale-only sidebar, and panel-only history
 access. These are residual UX checks because no plan-time council-ux lens could
 run. Do not claim the visual drill from hermetic projection tests alone.

## Open Questions

1. **What caused the reported duplicate wake?** **Default: unresolved; proceed
   with the rebuild-safe claim ledger because AC8 requires that behavior
   independently, add delivery/dedupe evidence, and do not change `d.emitted`
   on speculation.** The live store contains no duplicate persisted server
   synthetic for the identified child/target, but current telemetry cannot
   distinguish a TUI or host re-delivery from an unlogged observer rebuild. See
   History for the exact evidence and missing records.
2. **Should rows/toasts be filtered to the currently active root instead of
   labelled?** **Default: no; label rows and toasts with the resolved root.**
   The TUI context has no active-session binding, and adding one violates the
   boundary. Labels make a directory-wide notice attributable without hiding a
   signal that may need attention.
3. **Should terminal grace use one scalar or outcome-specific settings?**
   **Default: `terminalGraceSeconds=300` for completed and
   `failedTerminalGraceSeconds=3600` for failed, with separate env keys.** Two
   flat settings express the two required policies and preserve the existing
   options-over-env precedence. `terminalGraceSeconds` alone cannot represent
   both windows.
4. **Should the sidebar cap tighten from eight to five after aging lands?**
   **Default: keep eight delegate rows.** Aging removes the observed noise;
   reducing the cap would hide actionable rows without new evidence.
5. **Should RM-072 and RM-074 share one implement pass?** **Default: no; keep
   separate passes and rebase RM-072 after this pass.** They share files but
   have independent ACs and mutation proofs. Combining them would make review
   and rollback less precise.
6. **What happens to non-stale `unknown` rows?** **Default: preserve current
   visibility and controls.** They are recent, unproven sessions rather than
   stale history. Changing their liveness semantics is outside RM-074.
7. **Which delivery guarantee applies if the process crashes between claim and
   synthetic?** **Default: claim-before-send with rollback on a rejected send,
   documented as at-most-once.** The alternative can duplicate after a crash;
   the host offers no transaction that could provide exactly-once delivery.
8. **Which stack-specific planning reference applies?** **Default: use the
   plugin's checked-in TypeScript/Node `node:test`, `tsc`, generated-contract,
   and mutation-check conventions.** `designing-architecture` has no
   TypeScript/Node stack reference; creating one is outside this item.

## History

- 2026-11-07 — Initial draft from RM-074. Four workstreams, 10 ACs, explicit
  exclusions, generated-threshold propagation, red-first/mutation requirements,
  and a rebuild-safe attention-claim design. No implementation performed.
- 2026-11-07 — Code research confirmed the reported mechanisms: `isStale`
  exempts every observed-terminal row; both server and TUI associate an
  unfiltered directory list; toasts have no root label; the loop counter uses
  only the target and generic threshold 3; `d.emitted` dedupes only inside one
  reducer instance. The existing server `resolveParent` already owns trusted
  root routing and remains unchanged.
- 2026-11-07 — Duplicate-wake investigation: `writeLog` (`server.ts:57`) writes
  JSON only to stderr, while `healthPath` (`state.ts:1044`) writes connection /
  degradation state, not milestone history. The live
  `/home/hierovision/.local/share/opencode/log/opencode.log` contained plugin
  loader records but zero `"service":"delegation-observer"` JSON records for
  2026-11-07. `/home/hierovision/repos/ai-framework/.scratch/delegation-observer/health.json`
  was `connected` with `degradation:null` and carried no delivery evidence.
  A read-only query of `/home/hierovision/.local/share/opencode/opencode.db`
  found exactly one synthetic for reported child
  `ses_e497f5995ffeU7Stx34rfzdZ19` and target `docs/ROADMAP.md`: parent
  `ses_e612d58beffesvNWJDEmMuaE7d`, sequence 4050, observer pid 2055769,
  location `/home/hierovision/repos/ai-framework`, `wake:true`, text count
  `x3`; no matching `x6` or `x10` synthetic existed for that child/target.
  Across all 16 thrash synthetics on 2026-11-07 at query time, exact
  parent+text duplicate groups were zero. **Missing evidence:** successful-emission stderr records,
  a per-observer init/rebuild correlation for the event, per-TUI toast /
  attention delivery records, and the host's user-visible duplicate surface.
  The observed duplicate cause is therefore unconfirmed; the persistent store
  does not support a double server emission for the identified target.
- 2026-11-07 — UX consult skipped: `council-ux` is not an available subagent in
  this session, and the required general-agent fallback failed with
  `Subagent depth limit reached (1)`. No result was treated as a clean consult.
  Root-label/truncation/empty-state concerns are assigned to the live TUI drill
  in Verification; no UI evidence was invented.
- 2026-11-07 — Stack detection found TypeScript/Node with `node:test`, `tsc`,
  Python contract generators, and a custom mutation runner. No matching
  `designing-architecture` stack reference exists; the generic planning path
  and the repository's own verification contracts apply.
- 2026-11-07 — Implemented on `feat/rm-074-observer-signal-quality` from
  `origin/main` at `081ac48`. The frontmatter read `status: draft`; the
  spawning session explicitly confirmed the plan as approved, so the pass
  proceeded (approval is recorded here rather than silently assumed).
  Delivered WS1–WS4 as written: outcome display windows (`terminalGraceSeconds`
  300 s / `failedTerminalGraceSeconds` 3600 s, env under options, invalid
  values ignored) and `terminalAt`; one `eligibleRows` sidebar/footer
  projection with `panelHistoryLine` panel-only and the 8-row cap; bounded
  cycle-safe `indexSessions`/`associateSessionList`/`applyRootAssociations`
  used by server bootstrap and TUI bootstrap/refresh, with display-only
  `rootID`, unresolved cycles/missing parents, sidebar unique-prefix labels and
  full-root panel/toast titles; canonical full-input loop fingerprints with
  `editWriteLoopRepeats` 8 sourced from `watch_agent.EDIT_WRITE_LOOP_REPEATS`
  through the regenerated contract (other tools 3); `Milestone.conditionKey`
  plus durable claim files (`wx`, post trust/location gates, claim-before-send,
  rollback on rejected send, location-less in-process fallback + log), with the
  at-most-once ceiling documented. No contract-level mismatch and no scope
  change; `state.test.ts:281–300` remains byte-identical. Verification: 152
  plugin tests (158 with the sentinel), 54 mutation proofs including the eight
  named ones, typecheck, Python contract/watch tests, roadmap-verbatim,
  v2-surfaces and `git diff --check` all exit 0. Red-first output is stored
  outside git under `.scratch/rm-074/red-first/`. The live TUI drill could not
  run headless and is a manual-validation handoff in PR #165, not claimed as
  passed.
  ### Follow-ups
  - The live TUI drill (two roots, label comprehension, 64-column truncation,
    empty stale-only sidebar, aging boundaries, restart dedupe) needs a
    disposable service and stays with the owner before merge.
  - Claim-file pruning/compaction and a transactional exactly-once guarantee
    remain out of scope (they need separate operational evidence).
