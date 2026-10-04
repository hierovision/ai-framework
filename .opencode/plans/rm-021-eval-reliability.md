---
slug: rm-021-eval-reliability
title: Close RM-021 — a qualifying green weekly eval run with no silent drops
status: approved
created: 2026-10-03
revised: [2026-10-03]
related: [rm-003, rm-016, rm-028]
---

# Plan: rm-021-eval-reliability

## Goal / Approach

Goal: the scheduled weekly `eval-behavioral` run on `main` qualifies green
under `reference/eval-green-run-definition.md` with zero silent eval drops —
closing RM-021's acceptance ("a weekly run qualifies green; no silent drops")
and unblocking RM-003 AC4's first green-run record.

The roadmap row is stale: the prompt/typed migration backlog is already
closed by PRs #43–#71 and #76, and a local `coverage-gaps` run shows only
6 legacy evals, all deferred network-dependent (`optimizing-model-routing`
#1–#3, `validating-against-official-docs` #1–#3). Root-causing the
2026-10-01 monthly full run (run 36850910903, artifacts downloaded to
`.scratch/rm-021/`) found the actual remainder:

1. **One weekly default terminally stalls**: `modeling-threats#1` died on
   all 3 attempts (240 s no-event stalls; 727 s consumed). The timeout
   handler discards the captured stderr, so the cause is not yet resolvable
   from the artifact. The same eval stalled 4× in the 2026-09-30 pass.
2. **A fixture-copy path escape crashes the shard**: `observing-runs#2`
   lists `../../../scripts/eval-report.py`; `invoke_opencode` joins it onto
   the temp workdir, so `os.makedirs` resolves to `/scripts` →
   `PermissionError` → unhandled → the implement shard died and silently
   dropped 4 evals (`observing-runs#2`, `triaging-requirements#1–3`). The
   report's `zero_eval_skills` caught `triaging-requirements` only.
3. **Two content false-reds survive #76**: `refining-issue-acceptance#2/#3`
   assert artifacts (`signup-refined-body.md`, `issue-42-proposed-body.md`)
   that their prompts never name — the agents wrote other filenames; and
   `reviewing-security#4` asserts the phrase `ownership`, absent from the
   captured correct report (which contains `cross-tenant`, `tenant`,
   `route.ts`).
4. **The green-run definition is stale**: it sizes the suite at ~63 evals
   (now 26 weekly defaults / 110 full included) and its "any infra error is
   not green" wording disqualifies infra deaths that the runner's own
   fresh-retry design recovers — every recent run has recovered deaths.

Approach: make fixture provisioning contained and layout-correct, isolate
each eval so one crash cannot drop the rest, assert selected-vs-recorded
completeness, and persist stall stderr; add a targeted `skills` dispatch
input so heavy evals can be reproduced and fix-verified cheaply; apply an
evidence-based remedy to `modeling-threats#1`; close the two content
false-reds; amend the green-run definition (dated, user-approved) to
final-verdict completion semantics with recorded lane-health; rehearse on
the lane; then let the first scheduled weekly run qualify and record it.

`modeling-threats#1` decision rule (choose on captured evidence, record the
choice + stderr in History): model-resolution error → fix the CI lane
override; `external_directory` auto-reject → prompt/workdir-layout fix;
provider hang/timeout → per-eval timeout override or vehicle switch with a
dated record; genuinely too-heavy task → split the eval while preserving
its behavior.

## Acceptance Criteria

1. **Fixture provisioning is contained and layout-correct.** For
   `observing-runs#2`'s file list, every destination resolves under the
   workdir, and files land at the layout the prompt promises
   (`skills/observing-runs/scripts/query_runs.py`,
   `scripts/eval-report.py`); a path escaping the repo is skipped, never
   crashing. Verifier: new hermetic case
   (`test_fixture_copy_contained_layout`) in
   `skills/authoring-skills/scripts/test_runner.py`; the file exits 0.

2. **An eval-level crash can never drop the rest of the shard.** An
   unexpected exception while running one eval is recorded as that eval's
   infra error and the runner continues; before exit it asserts every
   selected eval has a final record, exiting non-zero and naming any
   missing. Verifier: hermetic test injecting a raising `get_output` for
   one of ≥2 evals — the second still runs, the first gets an error
   record, and the completeness assertion names it; part of
   `test_runner.py`, which exits 0.

3. **Records carry the eval key; the report separates terminal from
   recovered infra.** `kind=eval` records carry optional `eval:
   "<skill>#<id>"` (schema owner updated); `failure-taxonomy` reports
   `terminal_infra` (evals with no final content verdict) and
   `recovered_infra` (deaths retried to a verdict) per eval. Verifier:
   `python3 skills/observing-runs/scripts/test_log.py` and
   `python3 scripts/test_eval_report.py` exit 0; a synthetic logs dir with
   one recovered and one terminal death yields the two counts.

4. **Stall diagnosis is possible from artifacts.** A timed-out invocation
   persists the captured server stderr next to the synthetic stall stream
   (redacted, bounded — same path as dead-session stderr today).
   Verifier: extended `scripts/test_stall_timeout.py` and a synthetic
   timeout case in `test_runner.py` write `<...>-stderr.log`; both exit 0.

5. **Targeted dispatch exists.** `.github/workflows/eval-behavioral.yml`
   accepts a `skills` dispatch input that restricts the run to the named
   skills (intersected per shard; combined with `full` for depth), so a
   single heavy eval is reproducible without a full-suite run. Verifier:
   `python3 scripts/test_eval_workflows.py` exits 0 and asserts the input
   is wired to `--skill`.

6. **`modeling-threats#1` reaches a final PASS on the lane.** With stall
   stderr captured and the targeted dispatch, the cause is classified and
   the decision-rule remedy applied; two consecutive targeted runs
   (`gh workflow run eval-behavioral.yml -f skills=modeling-threats`)
   show a final content PASS for that eval. Verifier: both run logs show
   `PASS modeling-threats#1` and `terminal_infra=0` for it; the captured
   stderr (when any retry occurred) is cited in History.

7. **The two content false-reds are closed.** `refining-issue-acceptance`
   #2/#3 prompts name their output artifact (`signup-refined-body.md` /
   `issue-42-proposed-body.md`) and pass on the lane;
   `reviewing-security#4`'s expect replaces `ownership` with a token from
   the captured correct report (`cross-tenant`) and passes. Verifier:
   targeted dispatches show PASS for each; `python3
   scripts/check_typed_evals.py --base main` exits 0.

8. **Green-run definition reconciled (dated amendment).** The definition
   states: condition 1 = every included eval reaches a final content
   verdict and all are PASS; a terminal infra failure disqualifies
   (incomplete signal); recovered infra deaths are recorded as
   `infra_retried` lane-health data, not a disqualifier; current depth
   (26 weekly defaults / 110 full) and budget; and that RM-021 is
   satisfied by the weekly default-depth variant. `scripts/eval-report.py
   green-run-status` drops the hardcoded 2026-09-21/28 candidate text and
   records `depth` + `infra_retried` on `--record`. Verifier:
   `python3 scripts/test_eval_report.py` exits 0 and the amendment is
   dated in the file. (Approval item — Open Question 1.)

9. **A scheduled run qualifies green and is recorded.** The first
   scheduled weekly run after the fixes meet the amended definition
   (`failure-taxonomy`: all final content verdicts PASS, `terminal_infra=0`;
   `coverage-gaps`: no missing evals; within the weekly budget).
   `python3 scripts/eval-report.py green-run-status --record --run-id <id>
   --date <d> --duration-min <n> --all-pass --quarantine-flips 0
   --artifact-url <url>` emits `"achieved": true`; the run id, date,
   duration, and artifact URL are recorded in `docs/ROADMAP.md` (RM-021 →
   done with a reconciled remaining-text; RM-003's green-run note updated)
   and in this plan's History. Verifier: the emitted JSON, the roadmap
   rows, and the uploaded report artifact link.

## Files to Modify

- `skills/authoring-skills/scripts/run_behavioral_eval.py` — fixture-copy
  containment + repo-layout mapping; per-eval exception isolation;
  selected-vs-recorded completeness assertion; stall stderr capture;
  `eval` key on emitted records.
- `skills/authoring-skills/scripts/test_runner.py` — new hermetic cases:
  fixture layout/containment, crash isolation + completeness, stall
  stderr, `eval` key on records.
- `skills/observing-runs/scripts/log_run.py` — optional `eval` field in
  `FIELD_TYPES`.
- `skills/observing-runs/references/schema.md` — document `eval` (row +
  example).
- `skills/observing-runs/scripts/test_log.py` — validation case for the
  new field.
- `scripts/eval-report.py` — per-eval terminal/recovered infra in
  `failure-taxonomy`; missing-eval surfacing; green-run-status text/fields.
- `scripts/test_eval_report.py` — cases for the above.
- `scripts/test_stall_timeout.py` — stall stderr persistence assertion.
- `.github/workflows/eval-behavioral.yml` — `skills` dispatch input;
  comment corrections (110 included, depth policy).
- `scripts/test_eval_workflows.py` — assert the dispatch input wiring.
- `skills/refining-issue-acceptance/evals/evals.json` — #2/#3 prompts name
  their output artifacts.
- `skills/reviewing-security/evals/evals.json` — #4 phrase retune.
- `reference/eval-green-run-definition.md` — dated amendment (completion
  semantics, depth/size, budget, candidates).
- `docs/ROADMAP.md` — at closure only: RM-021 row reconciled, RM-003
  green-run note updated.
- `skills/modeling-threats/evals/evals.json` and/or the runner — only if
  the evidence directs the remedy there (decision rule above).

## Scope

**Included**
- Harness hardening: fixture containment, per-eval isolation,
  completeness assertion, stall-stderr capture, `eval` key in records,
  targeted dispatch input.
- `modeling-threats#1` remedy to a repeatable final PASS (the one weekly
  default with a terminal death).
- The two evidenced content false-reds (`refining-issue-acceptance`
  #2/#3, `reviewing-security#4`).
- Green-run definition amendment + report/record support.
- Lane rehearsals, qualification of the first scheduled weekly run, and
  the roadmap closure.

**Excluded**
- RM-016 (sanitized skill staging / answer-key exposure) — own row,
  unchanged.
- Non-default terminal infra evals from the 2026-10-01 full run
  (`authoring-skills#1`, `sourcing-external-skills#7`): their captured
  stderr (`external_directory` auto-rejects) is cited as a closure
  follow-up; not required for the weekly acceptance.
- Changing the weekly lane model or depth policy (user directive
  2026-09-29) — this plan works within `opencode-go/deepseek-v4.1-flash`
  at default depth.
- Auto-qualification inside the CI report job — the manual `--record`
  flow per RM-003 AC4 stays.
- RM-024 / RM-026 delegation-retry and log-classification work.
- Any further eval migration sweep — the backlog is closed.

## Schema / Type Impacts

- Run-log schema (single source of truth:
  `skills/observing-runs/scripts/log_run.py` + `references/schema.md`):
  add optional `eval` (string, `<skill>#<id>`) to `kind=eval` records.
  No required-field or kind-enum change; readers tolerate absence (older
  logs).
- No database tables, generated types, or API contracts.

## Verification

Hermetic (offline CI suites):

```markdown
- python3 skills/authoring-skills/scripts/test_runner.py
- python3 skills/observing-runs/scripts/test_log.py
- python3 scripts/test_stall_timeout.py
- python3 scripts/test_eval_report.py
- python3 scripts/test_eval_workflows.py
- python3 scripts/test_quarantine.py
- python3 scripts/check_typed_evals.py --base main
- python3 skills/authoring-skills/scripts/validate_skill.py --all
- python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

Live (CI lane, targeted via the new input):

```markdown
- gh workflow run eval-behavioral.yml -f skills=modeling-threats   # ×2, AC6
- gh workflow run eval-behavioral.yml -f skills=refining-issue-acceptance -f full=true
- gh workflow run eval-behavioral.yml -f skills=reviewing-security
- gh workflow run eval-behavioral.yml                              # weekly rehearsal, 26 defaults
```

Qualification: the first scheduled Monday run after the fixes — inspect its
uploaded `eval-report-<id>` artifacts (`failure-taxonomy.json`,
`coverage-gaps.json`, `green-run-status.json`) and run the `--record`
command from AC9.

## Open Questions

1. **Completion semantics (approval-critical).** Proposed default: an
   included eval counts as failed only when its *final* verdict is
   missing (terminal infra) or not PASS; recovered infra deaths are
   recorded as `infra_retried` health data, not a disqualifier. Strict
   alternative: keep "any `outcome=error` record disqualifies", which
   requires a perfectly clean lane across all attempts. The amendment is
   dated and explicit either way.
2. **Qualifying depth.** Proposed default: the weekly default-depth run
   (26 evals) qualifies, matching RM-021's wording and the 2026-09-29
   depth directive; the monthly full sweep stays a separate health
   signal. Alternative: require a full-suite scheduled run to qualify
   (stronger, ~60 min, may surface the two excluded non-default deaths).
3. **Live rehearsal spend.** Proposed default: approve the targeted
   dispatches plus one default-depth rehearsal (~30–45 runner minutes on
   the flat-rate Go lane, no marginal model cost).

## History

- 2026-10-03 — approved (user, in-session). Open Questions 1–3 accepted as
  their proposed defaults (final-verdict completion semantics; weekly
  default-depth run qualifies; live rehearsal spend approved). Status →
  approved; dispatched to `implementer` via the run-vehicle.
- 2026-10-03 — initial draft (design pass). Root-caused the real
  remainder from the 2026-10-01 monthly run artifacts (run 36850910903,
  saved to `.scratch/rm-021/`) and git history; the roadmap row's
  "45 legacy prompts" is stale. RM-021 has never had a plan artifact
  (git history holds no `.opencode/plans/rm-021*`). UX consult:
  `no user-facing UI — council-ux consult skipped` per Step 5b.
  Research basis: RM-021 row + `docs/ROADMAP.md` next-session entry
  (RM-003 AC4 overlap); run 36850910903 artifacts (failure taxonomy
  38 infra / 8 content, per-eval streams, implement shard job log
  `PermissionError: '/tmp/beval-.../../../../scripts'`, absent stall
  stderr); `skills/authoring-skills/scripts/run_behavioral_eval.py`
  (`invoke_opencode`, `run_eval`, `main`, `augment_prompt`,
  `_persist_event_streams`); `scripts/eval-report.py`
  (`green_run_status`, `failure-taxonomy`);
  `reference/eval-green-run-definition.md`;
  `.github/workflows/eval-behavioral.yml`; `docs/ADRs/ADR-0008-repo-memory-tiers.md`.
- 2026-10-03 — implementation pass AC1–AC8. Fixture-copy containment +
  repo-relative layout (`_copy_fixture_files`), per-eval exception isolation +
  selected-vs-recorded completeness assertion, `eval` key on final records,
  stall stderr capture, `skills` workflow dispatch input wired to `--skill`,
  failure-taxonomy `terminal_infra`/`recovered_infra`, green-run-status
  `depth`/`infra_retried`, eval prompt/phrase retunes for the two content
  false-reds, and the dated green-run definition amendment. Hermetic
  verification green (test_runner.py, test_log.py, test_stall_timeout.py,
  test_eval_report.py, test_eval_workflows.py, test_quarantine.py,
  check_typed_evals.py, validate_skill.py --all, yamllint). Live rehearsals
  and AC9 scheduled-run qualification pending.
- 2026-10-03 — rehearsal AC6 run #1 (37137725702) FAILED: `modeling-threats#1`
  terminal infra (dead session, no work). Captured stderr (AC4) shows the
  agent leaving the fixture root to probe the CI checkout
  (`.github/workflows/*`, `*behavioral*`) and being auto-rejected
  (`external_directory`); all retries ended without artifacts. Per-change run
  37137720026: 10/11 shards green (the previously red false-positives pass);
  the sole red `designing-architecture#1` is the same class (denied read of
  `~/.config/opencode/agents/council-ux.md`; fresh retries died with no
  events). AC6 remedy + rerun pending. Separately, the report job merged
  shard artifacts from a flat layout the merge step doesn't expect
  (`download-artifact` landed files directly under `shards/`, no
  per-artifact dirs), so `merge-eval-logs.py` output 0 records/0 streams and
  `failure-taxonomy.json` was vacuously empty — AC9 qualification would be
  false-green until the merge step locates `run-*.jsonl` in either layout.
- 2026-10-04 — AC6 first targeted PASS (run 37164974025, after the loader fix
  made the 600 s override effective): `modeling-threats#1` final
  `eval_pass: true`, 95,581 in / 21,430 out, **410 s** — the old 240 s timeout
  would have killed it, so the per-eval override is the operative fix.
  `failure-taxonomy`: records=1, pass=1, `terminal_infra=[]`. Per-change
  37164976610 on the same head: all shards green including
  `modeling-threats` and the `refining-issue-acceptance` prompt fix. Second
  consecutive targeted run 37165645759 passed (2026-10-04 00:45:35Z) —
  **AC6 met** (two consecutive PASS). PR #91: all 14 checks green, mergeable.
  Residual-stall context: opencode issue
  #52513 (per-session retry state; parallel sessions storm a throttled
  provider) and #52962 (Go pooled account-wide usage) are the community
  reports to weigh if stalls recur.
- 2026-10-04 — the 600 s timeout did not take effect in run 37164171405:
  `load_skill_evals` normalizes eval dicts with a fixed field list and dropped
  `timeout`, so `eval_timeout` fell back to 240 s (the stall record still said
  240). The loader carries the field now; unit test added; AC6 rerun re-tests
  the 600 s hypothesis.
- 2026-10-04 — per-change flake exposed `refining-issue-acceptance#1`'s latent
  false-red: its prompt never named `issue-42-refined.md` (the AC7 gap fixed
  only for #2/#3), and a stall-fragmented run missed the artifact assertion
  (two premature stops + two dead fresh retries, then a content miss).
  Prompt now names the output file, matching #2/#3; re-verified by the
  per-change lane.
- 2026-10-03 — AC6 remedy experiment (decision rule: provider hang/timeout →
  per-eval timeout override, dated). Evidence: three 240 s invocations of
  `modeling-threats#1` with zero events/stderr/tokens, while the same CI lane
  and model passed `designing-architecture` concurrently (37139299698,
  17:09–17:12) and a local ping answered. Added per-eval `timeout` support
  (manifest override > `BEVAL_TIMEOUT_SECONDS` > 240) and set
  `modeling-threats#1` to 600 s; a vehicle switch or eval split is the next
  branch if it still stalls. Per-change 37139299698 fully green (sandbox
  config-read fix validated); report-pipeline fix validated (taxonomy shows
  3 records + `terminal_infra`).
- 2026-10-03 — post-PR fix slice (AC2). The per-change lane invokes the
  runner without `--logs-dir`, so the completeness check received `None` and
  false-failed every selected eval after they had passed (verified:
  `observing-runs#1` record `eval_pass=true` alongside "no final record").
  `_final_eval_keys` and the call site now resolve
  `log_run.DEFAULT_LOGS_DIR`; a regression test runs the CLI without
  `--logs-dir`. Rehearsals AC6/AC7 and the AC9 watch continue.
