---
slug: rm-056-eval-lane-fallback
title: Log-proven per-run eval fallback to the deepseek-v4.1-flash direct API lane, marked in the report — never silent, never a re-bind
status: approved
created: 2026-10-12
revised: [2026-10-13]
related: [rm-052-053-vision-roadmap-schema, rm-021-eval-reliability]
---

# Plan: rm-056-eval-lane-fallback

## Goal / Approach

One sentence: a weekly/per-change eval that cannot complete because of the
MODEL or the opencode service switches, for that run only, to the
`deepseek/deepseek-flash` direct API lane — with the degradation proven
from the run's own log records first — and every lane switch is recorded
and marked in the eval report so pass rates stay comparable.

Strategy (evidence-grounded, minimal edit surface):

1. **Trigger from RM-021's diagnosed classes only.** The two infra roots
   are model-resolution deaths (`ProviderModelNotFoundError` at ~2 s per
   turn, run 36455843309) and dead streams (the wrapper
   `UnknownError: Unexpected server error`, 44 in the same run). The
   runner already detects both (`is_model_resolution_error`,
   `MODEL_RESOLUTION_RE`, `_error_signature`, the consecutive-death
   counter in main). The fallback reuses those detectors; it does not
   invent new ones. The external-directory auto-reject class
   (`/tmp/audit-report-*`) is explicitly NOT a trigger — it is an env
   permission failure, not a lane/service degradation.
2. **Switch = re-binding the `--model` argument the runner already
   passes**, not a new invocation path. The direct-key lane is
   opencode's `deepseek/` provider prefix authenticated by
   `DEEPSEEK_API_KEY` — proven end-to-end by ADR-0002 (superseded as the
   *default*, not as a capability) and already accepted by
   `assert_ci_free_model` ("legacy direct-key lane, retained for
   developer-local runs"). No new env plumbing: add the repo secret to
   the two eval workflows' job env exactly like `OPENCODE_API_KEY` today.
3. **Honesty by record shapes + report surfaces, not code comments.**
   Two run-log annotation records (`lane-degradation-evidence:` then
   `lane-switch:`, both `kind=eval`, `eval_pass=None` so they never
   count as verdicts), the actual lane in every record's `model` field,
   a `lane` field in `green-run-status.json`, and lane surfaces in
   `failure-taxonomy`.
4. **Standing mechanics stay untouched:** quarantine, typed assertions,
   the fresh-retry backoff (5 s/15 s), the early-abort threshold value,
   the `--model`-wins precedence, and the Go-first routing policy
   (RM-039 / ADR-0013) itself.

### Owner-frozen policy (RM-034; dated 2026-10-11, RM-052/053 design review)

An eval that cannot complete because of the MODEL or the opencode service
falls back to the **deepseek-v4.1-flash direct API lane** — and only with
the degradation **proven from logs** before the switch. A per-run lane
switch, never a silent re-bind: the run-log records the degraded-service
evidence + an explicit lane-switch record; the eval report marks the
fallback lane so pass rates stay comparable (a fallback-carried green
run records it as such, honestly). Routing policy itself stays RM-039 /
`docs/ADRs/ADR-0013-model-routing-policy.md`'s domain — persistent
degradation escalates to a routing review instead of the lane silently
staying on fallback. Economics: the fallback reuses the measured
direct-key lane (~$0.68/weekly off-peak run, user directive 2026-09-21)
and its CI-secret handling. Eval semantics unchanged (quarantine /
typed assertions per the existing protocols). RM-021's recorded incident
classes are the standing evidence base.

## Design decisions (each with reasoning)

### D1 — The log-proof trigger (observables, thresholds, evidence location)

Trigger evaluated where the runner already aggregates road-log evidence —
in the run-loop over final records. Two trigger classes, either suffices:

| Trigger | Exact observable | Threshold (tunable, default) | Record fields read |
|---|---|---|---|
| T1: consecutive model-resolution deaths | Final records (`kind=eval`, `eval_pass` set) whose `detail` matches `is_model_resolution_error()` (`Model not found|ProviderModelNotFound`), counted consecutively — the counter the early-abort already maintains | `BEVAL_FALLBACK_DEATHS` = 3 (same value as the current early abort) | final `outcome=error` record `detail` per eval; annotations carry the same class in `(cause)` |
| T2: provider-dead share of the run | Final records `outcome=error` (dead terminal infra) whose error signature resolves provider-classed: `ProviderModelNotFoundError` / dead-session `UnknownError` wrapper — NOT the `external_directory auto-reject` class | `BEVAL_FALLBACK_INFRA_SHARE` = 50 (% of evals attempted so far), only when ≥ `BEVAL_FALLBACK_MIN_ATTEMPTED` = 6 evals have been attempted | the per-eval records' `outcome`, `detail`, `eval` keys |

Evidence location: the trigger needs NO new capture — the per-eval
records already persist the class in `detail` (e.g.
`dead session: UnknownError ref=err_1 (ProviderModelNotFoundError:
Model not found ...)`; the resolved cause came from the server-log
stderr capture landed by RM-021). The evidence record cites the
triggering counts + eval keys as its `detail`.

Classification helper (new, inside the runner):
`is_provider_classed_error(detail)` returns True iff
`is_model_resolution_error(detail)` OR the recorded error signature is
the dead-session `UnknownError` wrapper class, AND NOT
`_resolved_cause` output starts with `external_directory auto-reject`.
Rate-limit/timeout classes (TRANSIENT_RE) are deliberately NOT triggers:
they self-heal with the existing backoff, and a Go-lane 429 escaping to
the direct key is the same model on a different route — treat trigger
scope creep as a routing-policy question (RM-039/ADR-0013), not an
eval-lane question.

Per-eval fallback trigger (covers the per-change single-canary case):
an eval whose ALL dead turns are provider-classed — ≥
`BEVAL_FALLBACK_EVAL_DEATHS` = 3 dead turns — falls back for its next
attempt (bounded by `BEVAL_FALLBACK_MAX_RERUNS` per eval). The evidence
for one eval = its own annotation records (each fresh-retry already
logged with the class in `detail`), which is "proven from logs" at
single-eval granularity.

Constants (new, with defaults; env-overridable so workflows need no
runner edits):

```
BEVAL_FALLBACK_ENABLED          default unset (disabled; CI opts in)
BEVAL_FALLBACK_MODEL            default "deepseek/deepseek-flash"
BEVAL_FALLBACK_DEATHS           default 3
BEVAL_FALLBACK_INFRA_SHARE      default 50   (percent)
BEVAL_FALLBACK_MIN_ATTEMPTED    default 6
BEVAL_FALLBACK_EVAL_DEATHS      default 3    (per-eval path)
BEVAL_FALLBACK_MAX_RERUNS       default 1    (per eval)
BEVAL_FALLBACK_RUN_CEILING_USD  default 3.00 (D5)
BEVAL_FALLBACK_REVIEW_AFTER     default 2    (events, D4)
BEVAL_FALLBACK_REVIEW_WINDOW_DAYS default 30
BEVAL_FALLBACK_REVIEW_COVER     default 50   (percent of one run, D4)
```

### D2 — Switch mechanics (invocation path, secrets, session-record attribution)

- **Invocation path: unchanged.** `invoke_opencode` →
  `opencode run --model <id>` already takes the model id as an argument;
  the switch changes the id passed to the remaining/re-attempted calls
  (`args.model` becomes the fallback id inside the runner process — a
  mutable lane holder, not a re-exec). Continuations/retries/nudges
  inherit the lane through the same `model=` parameter that exists
  today. No `OPENCODE_CONFIG_CONTENT` regeneration: for THIS repo the
  agent override map is empty (every persona Go-bound), so nothing to
  re-point; consumer repos with non-empty override maps are out of
  scope.
- **Secret handling (CI-only):** `DEEPSEEK_API_KEY` is a
  repository-level secret consumed via `${{ secrets.DEEPSEEK_API_KEY }}`
  in the runner-step `env:` of both eval workflows — the exact pattern
  `OPENCODE_API_KEY` uses today (`consumed by the runner; never
  echoed`). Runner-side redaction already covers it:
  `_redact()` scrubs `DEEPSEEK_API_KEY` from persisted streams/stderr,
  and `sandbox_env` passes credentials through while scrubbing
  `GITHUB_*`/`RUNNER_*`. GitHub CI additionally masks the value in step
  logs. The structural guard in `test_eval_workflows.py` that today
  asserts "no DEEPSEEK_API_KEY anywhere" is updated to the stricter
  intent: the secret may appear ONLY as `${{ secrets.DEEPSEEK_API_KEY }}`
  inside a job/step `env:` mapping, never inside a `run:` script, never
  printed.
- **Gate on availability:** a switch requires `BEVAL_FALLBACK_ENABLED=1`
  AND `DEEPSEEK_API_KEY` present. Without either, behavior is exactly
  today's: threshold reached → evidence still recorded
  (`lane-degradation-evidence:` record) → early abort exit 3 (or the
  `lane-fallback-unavailable` stderr line + exit 3 when the flag is set
  but the key is missing). Log always proves the degradation, even when
  the fallback cannot serve it.
- **Session-record attribution:** every record keeps
  "the log should record what actually ran" — final verdicts produced on
  the fallback lane carry `model="deepseek/deepseek-flash"` (per-eval
  records get the lane via the `model=` argument `run_eval` already
  accepts). Downstream `kind=agent` records (dispatch path) are
  untouched by this plan: they already record the resolved model; the
  no-silent-rebind rule is enforced on the eval runner's own writes.
- **At most one switch per run.** The fallback lane itself dying is
  recorded as today's infra errors; no yoyo, no second switch.

### D3 — Marking + comparability (fields/phrase, and where)

- **Run-log phrase (reserved detail prefixes):** records written by the
  switch carry `detail` starting exactly
  `lane-degradation-evidence: ` (counts/classes/keys, ≤ 512 chars) and
  `lane-switch: <primary-id or "environment default"> -> deepseek/deepseek-flash; per-run; evidence: <eval keys>` —
  both `kind=eval`, `skill=None`, `agent=None`, `eval_pass=None`,
  both with `outcome="error"` — because the schema's outcome enum has
  no "not-a-verdict" value and `success` would fabricate a quality
  signal; `eval_pass=None` annotation records are already excluded
  from pass rates (query_runs skips `eval_pass=None` before counting).
  **IMPORTANT (verified in-research):** `log_run.build_record` DROPS
  unknown keys — lane marks MUST ride `detail` prefixes + `model`, not
  novel per-record fields.
- **Green-run status:** `scripts/eval-report.py green-run-status
  --record` gains `--lane {primary,fallback}` (default `primary`)
  → the achieved shape adds `"lane": <primary|fallback>` and
  `"fallback_carried": <bool>`; the not-achieved shape adds the same
  keys harmlessly (readers tolerate additive fields).
  Phrase adopted everywhere: **"fallback-carried (lane: fallback)"**.
  `reference/eval-green-run-definition.md` gains ONE clause: a run
  qualifies with `lane: fallback` recorded; all four conditions
  unchanged; the lane mark is the comparability control (both lanes
  serve DeepSeek-V4.1-Flash, the same model family — pass rates stay
  comparable and are only comparable ACROSS lanes when the lane mark
  is visible).
- **Failure taxonomy:** `failure_taxonomy()` gains two surfaced lists
  built from `kind=eval` records (no stream re-reads): `lane_evidence`
  (records with the evidence prefix) and `lane_switches` (records with
  the switch prefix), so the merged weekly report shows a degraded run
  without reading raw logs. Per-verdict lane attribution stays in
  `per_skill` (each row carries `model`).
- **Baseline routes:** `reference/eval-green-run-definition.md` (green
  run semantics), `scripts/eval-report.py` + the report artifacts (the
  "eval report" the row names), and the run-log JSONL itself. No new
  report surface outside these.

### D4 — Per-run scope + escalation to a ROUTING review

- **Per-run only, mechanically:** the runner holds the lane in process
  state; it writes no config, no commit, no manifest change. A second
  run starts on the primary lane (verified by an AC). The switch record
  says `per-run` so any future reader can see the scope in the log
  itself.
- **Escalation signal (counts + recency):** new
  `scripts/eval-report.py lane-status --logs-dir logs/
  [--out PATH]` scans `kind=eval` lane-switch records across
  `run-*.jsonl` within `BEVAL_FALLBACK_REVIEW_WINDOW_DAYS` (30) and
  emits `{fallback_events, event_dates, max_run_cover_pct,
  routing_review: {needed, basis}}`. Events = distinct UTC dates with a
  switch record (deduped; one degraded weekly run is one event).
  `needed` when: events ≥ `BEVAL_FALLBACK_REVIEW_AFTER` (2) within the
  window, OR any single event carried ≥ `BEVAL_FALLBACK_REVIEW_COVER`
  (50%) of that run's included evals. `basis` names the dates + counts.
- **Where escalation lands:** the weekly report job computes the status,
  uploads it, and prints a `$GITHUB_STEP_SUMMARY` line — `Routing
  review needed per RM-056: <basis>; land it in RM-040's next monthly
  routing/sustainability slot (2026-11-01) or earlier per the owner.`
  The routing-review row/slot is RM-040's (Go Plus sustainability,
  2026-11-01, per ADR-0013's review trigger, batched with RM-011's ALM
  review) — this plan makes NO docs/ROADMAP.md edits (ROADMAP is the
  migration pass's working product and never staged by RM-056). The
  routing review itself is RM-039/ADR-0013's domain by owner ruling.

### D5 — Spend guardrails (defaults proposed)

- **Measured economics (no new metering):** every eval record already
  carries provider-reported `cost` (the runner records it from
  step-finish events). The fallback ledger = sum of `cost` over
  fallback-attributed records. Measured anchors: ~$0.68/weekly
  off-peak for the direct-key lane at the 2026-09-21 suite size
  (ADR-0002); today's weekly default depth (26 evals) is proportionally
  cheaper; the off-peak window (01:00–04:00 / 06:00–10:00 UTC Mon–Fri
  are PEAK off DeepSeek pricing — the 10:30 UTC Monday cron sits in the
  50%-price region) is kept by the existing schedule; no new cron.
- **Hard per-run ceiling:** `BEVAL_FALLBACK_RUN_CEILING_USD` = 3.00
  (~4× the measured weekly fallback run). When the measured
  fallback-lane spend crosses it: write a
  `lane-fallback-ceiling:` record, `return 4` (distinct exit), stop
  re-attempting. Rationale: the ceiling fires only when the SECOND lane
  is degenerate (stuck re-runs, runaway retries) — halting then is
  honest, and $3 is ~4 weeks of standing fallback spend.
- **Structural cap (no hard weekly dollar cap):** the escalation rule
  (≥2 events/30 days → routing review) is the standing constraint; a
  periodic dollar cap would tax a legitimate recovery. Also bounded:
  each verdict-less eval re-attempted at most `MAX_RERUNS` = 1 time, at
  most one switch per run — dollars per degraded run are bounded by
  design, not by another knob.

### D6 — Verification posture (red-first, hermetic; detailing)

Rehearsal uses RM-021's recorded incident classes as replay candidates
via two new hermetic stub modes in `stub_result()` (no opencode, no
network, deterministic — the established `--stub-output` contract gains
two modes, `ALL`/`:MISS:`/`:FLAKY:` semantics untouched):

- `:FALLBACK-DRILL:` — the drill candidate for T1: each selected eval's
  first `BEVAL_FALLBACK_DEATHS` turns return the recorded dead-stream
  shape (`FATAL_STREAM` variant whose signature resolves to
  `ProviderModelNotFoundError`, matching run 36455843309); once the
  runner's threshold fires and the lane switches, further calls return
  a passing typed synthesis (the healthy direct-key lane). Exercises:
  evidence record → switch record → per-run re-attempts → fallback
  verdicts → report marking.
- `:EXTERNAL-REJECT:` — the named NEGATIVE candidate: the recorded
  external-directory auto-reject turn shape (RM-021's second root,
  2026-09-28). Asserts NO evidence/switch records ever appear — the
  trigger never fires for this class.

Plus `lane-status` escalation tests over seeded multi-day logs and
green-run `--lane` round-trips in `test_eval_report.py`.

Live smoke (procedures, not CI):

1. **Primary-healthy assertion:** dispatch
   `eval-behavioral` (`skills: authoring-skills`, `full: false`); after
   the run, the report job summary shows `Lane: primary` and the merged
   `failure-taxonomy.json` shows `lane_switches: []`. A local equivalent:
   run one canary with the real lane healthy and grep the seeded
   `--logs-dir` (never the repo `logs/`) for zero lane records.
2. **Real-switch rehearsal (optional, dated when run):** one runner call
   against a deliberately non-resolvable model id on the same gateway
   (e.g. `--model opencode-go/deepseek-v4.1-flash-typo` → the recorded
   `ProviderModelNotFoundError` class is replayed against the REAL
   resolver), with `--default --skill <a small canary>`,
   `--logs-dir .scratch/rm-056-design/replay/`, `--no-quarantine`.
   Asserts: exit 0 after fallback, the three record shapes, real
   fallback cost in the records (~one canary, <$0.05). Never writes the
   repo's `logs/`; never writes quarantine (CI-owned).
3. **Comparison honesty (the row's "where feasible" clause):** the
   reporting mechanism makes per-lane verdicts visible
   (`aggregate` per-skill rows carry `model`; `failure-taxonomy`
   surfaced lists) — verified over seeded logs with both lanes
   present. A live primary-vs-fallback comparison run is recorded
   honestly when a real degradation window occurs (not fabricated for
   test's sake).

## Acceptance Criteria

1. **Degradation is proven from logs before any switch.** In the
   `:FALLBACK-DRILL:` rehearsal, the run-log shows ≥ 3 terminal
   `outcome=error` records whose `detail` resolves to the
   ProviderModelNotFoundError class, then exactly ONE
   `lane-degradation-evidence:` record and ONE `lane-switch:` record,
   in that order, both `kind=eval` with `eval_pass=None` and
   `model` naming the lane each record is about — verifier:
   `python3 skills/authoring-skills/scripts/test_runner.py` (extended
   drill tests assert record shapes/order/counts from a seeded
   `--logs-dir`); the human-visible equivalent:
   `python3 skills/authoring-skills/scripts/run_behavioral_eval.py
   --skill <drill-skill> --skills-root <drill fixture root>
   --logs-dir .scratch/rm-056-design/drill --stub-output
   :FALLBACK-DRILL: --no-quarantine` then grep the seeded log.
2. **Fallback verdicts are lane-attributed.** Every final verdict
   record produced after the switch carries
   `model="deepseek/deepseek-flash"`, and pre-switch annotations keep
   the primary lane/context — verifier: drill tests assert all
   post-switch verdict records' `model` field and the one-switch-max
   invariant (`exactly one lane-switch:` record even though re-attempts
   occur).
3. **Default-off + unavailable-key behavior unchanged.** (a) Without
   `BEVAL_FALLBACK_ENABLED`, a drill run records zero lane switch
   records and stops at 3 consecutive deaths with exit 3; (b) with the
   flag set but no `DEEPSEEK_API_KEY`, it emits
   `lane-fallback-unavailable: DEEPSEEK_API_KEY not set` on stderr,
   still records the evidence record, exits 3, and runs no fallback
   eval — verifier: `python3 skills/authoring-skills/scripts/test_runner.py`.
4. **The external-directory class never triggers.** A `:EXTERNAL-REJECT:`
   drill run records zero `lane-degradation-evidence:` /
   `lane-switch:` records and terminates like today (non-zero, red) —
   verifier: `python3 skills/authoring-skills/scripts/test_runner.py`.
5. **Per-run scope, never a re-bind.** A second drill process on a
   fresh logs dir still starts (and, absent trigger conditions, stays)
   on the primary lane; the repo diff contains NO change to
   `agents/*.md` model bindings, eval manifests, `--model` pins in the
   runner-step `run:` scripts (only `env:`/secret additions), or
   `reference/model-routing.md` — verifier: `git diff main...HEAD
   --name-only` listing the change set and asserting none of those
   files changed (asserted by the plan's own review, plus
   `python3 scripts/test_eval_workflows.py` still green with the SAME
   `opencode-go/deepseek-v4.1-flash` pin assertion).
6. **Report marks a fallback-carried run.** `green-run-status --record
   --lane fallback` emits `lane: "fallback"` +
   `fallback_carried: true` (default/missing flag → `primary`/`false`);
   `failure-taxonomy` surfaces `lane_evidence`/`lane_switches` lists
   from seeded logs; `aggregate` per-skill rows carry per-record
   `model` so cross-lane pass comparison is readable — verifier:
   `python3 scripts/test_eval_report.py` (extended seeded-fixture
   tests) + CLI:
   `python3 scripts/eval-report.py green-run-status --record --run-id r
   --date 2026-10-12 --duration-min 15 --all-pass --lane fallback` then
   `python3 scripts/eval-report.py failure-taxonomy --logs-dir <seeded>`
   over a fixture dir built by the tests.
7. **Green-run definition carries the clause.**
   `reference/eval-green-run-definition.md` documents the `lane`
   field + the fallback-carried qualifying condition + the
   comparability note — verifier: the updated
   `test_eval_report.py` doc-grep assertion (the file is referenced by
   `green-run-status`'s `definition` field) and manual read at
   approval.
8. **Escalation fires on the owner's threshold.** With seeded logs: two
   distinct-date lane-switch records within 30 days →
   `routing_review.needed is True` with a basis naming the dates; one
   event → `needed is False`; one event covering ≥50% of its run's
   included evals → `needed is True` — verifier:
   `python3 scripts/test_eval_report.py` +
   `python3 scripts/eval-report.py lane-status --logs-dir <seeded>`.
9. **Spend ceiling stops the run honestly.** A drill forced past
   `BEVAL_FALLBACK_RUN_CEILING_USD` (set to `0.01` in the test) writes
   a `lane-fallback-ceiling:` record and exits 4 after the threshold,
   with no further fallback re-attempts started — verifier:
   `python3 skills/authoring-skills/scripts/test_runner.py`.
10. **CI wiring + secret handling.** Both eval workflows carry
    `BEVAL_FALLBACK_ENABLED: "1"` and
    `DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}` ONLY inside the
    runner-step `env:` (never in a `run:` script, never echoed); yml is
    yamllint-clean — verifier:
    `python3 scripts/test_eval_workflows.py` (extended structural
    assertions) + `python3 -m yamllint -c .yamllint.yaml
    .github/workflows/`.
11. **Primary-healthy path stays primary.** A drill run under the
    enabled flag whose outputs contain NO degradation (stub `ALL`
    equivalent) records zero lane records — verifier:
    `python3 skills/authoring-skills/scripts/test_runner.py` + live
    smoke 1 (workflow_dispatch, `Lane: primary` in the merged report).
12. **Eval semantics unchanged (quarantine / typed assertions).** The
    full offline suite that pins those semantics stays green with no
    edits to their semantics: `python3 scripts/test_quarantine.py`,
    the matcher/canary-replay tests inside
    `python3 skills/authoring-skills/scripts/test_runner.py` (incl.
    `test_seven_canaries_replay_fixtures`), and the run-log schema
    owner stay green unmodified — verifier:
    `python3 skills/observing-runs/scripts/test_log.py &&
    python3 skills/observing-runs/scripts/test_query.py`.

## Files to Modify

- `skills/authoring-skills/scripts/run_behavioral_eval.py` — the lane
  fallback: constants (D1), `is_provider_classed_error()` (new pure
  helper), per-eval + per-run switch logic replacing/augmenting the
  early-abort branch (threshold reached + enabled + key present →
  evidence record, switch record, lane re-bind, verdict-less re-attempt
  pass), the spend-ceiling guard + exit 4, and two new stub modes
  (`:FALLBACK-DRILL:`, `:EXTERNAL-REJECT:`) in `stub_result()`; all
  lane marks ride `detail` prefixes + `model` (no new record fields).
- `skills/authoring-skills/scripts/test_runner.py` — red-first drill
  tests (AC 1-5, 9, 11) using the existing stub/get_output injection
  pattern; constants for the drill streams mirror RM-021's recorded
  shapes (`FATAL_STREAM` exists; add a resolved-cause variant).
- `scripts/eval-report.py` — `failure_taxonomy()` lane surfaces
  (`lane_evidence`, `lane_switches` lists built from run-log records,
  prefix-matched); `green_run_status()` + CLI `--lane` flag → `lane` /
  `fallback_carried`; new `lane-status` subcommand (D4 escalation).
- `scripts/test_eval_report.py` — seeded-fixture tests for AC 6, 8;
  doc-grep for AC 7.
- `.github/workflows/eval-behavioral.yml` — runner-job `env:` gains
  `DEEPSEEK_API_KEY` + `BEVAL_FALLBACK_ENABLED: "1"`; report job gains
  lane-status emission + the escalation/routing-review summary line.
- `.github/workflows/eval-per-change.yml` — same `env:` wiring on the
  `evals` matrix job (per-eval fallback covers the single-canary job).
- `scripts/test_eval_workflows.py` — replace the blunt
  "no DEEPSEEK_API_KEY anywhere" assertion (test
  `lane_and_nested_agent_override`, line ~122) with the scoped-intent
  assertion (secret only in `env:` as `${{ secrets.* }}`, never in a
  `run:` script); assert both fallback env vars present; keep every
  existing pin/lane assertion unchanged.
- `reference/eval-green-run-definition.md` — ONE added clause (RM-056
  amendment): the `lane` field, "fallback-carried (lane: fallback)"
  qualifying semantics, and the comparability note. Dated 2026-10-12.
- `skills/authoring-skills/references/eval-harness.md` — §(c) gains 2-3
  sentences: the CI lane may switch per run to the
  `deepseek/deepseek-flash` direct-key lane on log-proven degradation
  (RM-056), marked in the report; `-free`/zen selection semantics and
  `--model`-wins precedence unchanged. Minimal cite — no SKILL.md
  body changes.

## Scope

**Included**
- Runner-side trigger + switch + recording + ceilings + hermetic drill
  modes (runner/test file as the only runner-layer edits).
- Report surfaces: green-run `lane`/`fallback_carried`, failure-taxonomy
  lane lists, the `lane-status` escalation subcommand + its tests.
- Workflow env wiring (secret + opt-in flag) for both eval workflows +
  the summary escalation line.
- The green-run definition clause + the minimal harness-reference cite.
- Exit code 4 (fallback-ceiling stop) documented in the runner and
  asserted by tests; exit codes 0/1/2/3 unchanged.

**Excluded**
- Any changes to routing policy, model bindings, or catalog probes —
  `agents/*.md`, `reference/model-routing.md`, and
  `scripts/model-liveness-check.py` are untouched (RM-039 /
  `docs/ADRs/ADR-0013-model-routing-policy.md`'s domain; escalation to
  RM-040's review slot only).
- Any ROADMAP.md / roadmap-detail edits (ROADMAP is the migration
  pass's working product — never staged by this pass; roadmap update
  happens at merge per `reference/git-workflow.md`, by the owner's
  process).
- SKILL.md body changes (only the two reference-doc citations above).
- Consumer-repo propagation (dispatch_agent lane-fallback generation /
  nested-agent fallback regeneration for wrappers with non-empty agent
  maps; consumer projects follow at their own pace).
- New run-log schema fields (`log_run.py` / `schema.md` untouched) —
  marks ride `detail` prefixes; novel keys would be silently dropped by
  `build_record` (verified behavior).
- Mid-run lane health APIs, live catalog preflight as a switch
  predicate (the 2026-09-28 `opencode models` preflight stays advisory
  — RM-021 proved it unsafe as a gate).
- Auto-scaling/stretch goals: per-5xxx-value trigger classes beyond D1's
  table without an owner ruling (any candidate class routes through the
  change to RM-021's evidence base, not silent runner regex edits).
- Off-peak window enforcement at runtime (schedule design is
  ADR-0002/0013-family; the existing 10:30 UTC cron already sits in the
  DeepSeek 50%-price region).

## Schema / Type Impacts

None to the run-log schema or to any generated types — verified:
- `log_run.FIELD_TYPES`/`build_record` are untouched; lane marks ride
  `model` (existing str|null) + `detail` prefixes (existing str ≤512)
  + `eval_pass=None` annotations; novel per-record keys would be
  dropped by `build_record`, which is why the design never adds any.
- `green-run-status.json` gains additive fields only (`lane`,
  `fallback_carried`, and `lane-status.json`'s
  `routing_review` object read tolerantly elsewhere).
- No database, no migrations, no generated types in this repo.

## Verification

Every command the verify/build stage runs (from ci.yml's hermetic gate,
plus the plan-specific drills):

```
python3 skills/authoring-skills/scripts/test_runner.py
python3 scripts/test_eval_report.py
python3 scripts/test_eval_workflows.py
python3 scripts/test_quarantine.py
python3 skills/observing-runs/scripts/test_log.py
python3 skills/observing-runs/scripts/test_query.py
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

Hermetic drills (no model, no network; logs under .scratch, never repo
logs/; --no-quarantine always):

```
# positive drill: degradation proven -> switch -> marked green
python3 skills/authoring-skills/scripts/run_behavioral_eval.py \
  --skill writing-unit-tests --skills-root <drill fixture root> \
  --logs-dir .scratch/rm-056-design/drill \
  --stub-output :FALLBACK-DRILL: --no-quarantine
# then: exit 0; grep -c 'lane-degradation-evidence:' == 1;
#       grep -c 'lane-switch:' == 1; post-switch verdicts carry
#       deepseek/deepseek-flash; no repo logs/ touched.

# negative drill: external-directory class never switches
python3 skills/authoring-skills/scripts/run_behavioral_eval.py \
  --skill writing-unit-tests --skills-root <drill fixture root> \
  --logs-dir .scratch/rm-056-design/reject \
  --stub-output :EXTERNAL-REJECT: --no-quarantine
# then: non-zero exit; zero lane records.

# escalation fixture:
python3 scripts/eval-report.py lane-status \
  --logs-dir .scratch/rm-056-design/lane-fixture --print
```

Live smoke (manual, dated; only after the hermetic suite is green):

1. Primary-healthy: `gh workflow run eval-behavioral -f
   skills=authoring-skills -f full=false` → in the report summary,
   `Lane: primary` and the merged `failure-taxonomy.json` shows
   `lane_switches: []`.
2. Optional real-switch replay (as D6 procedure 2): a slowed canary run
   with `--model opencode-go/deepseek-v4.1-flash-typo` (guaranteed
   ProviderModelNotFoundError replay), `--logs-dir
   .scratch/rm-056-design/replay/`, asserting the three record shapes
   with real spend visible in the records.

## Open Questions

Non-blocking; each with a proposed default; none block the draft:

1. **Should `eval-per-change` carry the fallback at all?** A
   single-canary job can trip the per-eval path, cost ~one extra eval
   (~cents). *Proposed default: yes — wire both workflows; trimming
   per-change later is one env var.*
2. **Should a fallback-carried green run qualify unconditionally?** The
   strictest alternative reading is "informative, but
   disqualifying". *Proposed default: it qualifies with the mark (the
   owner ruling says "a fallback-carried green run records it as
   such" — recording is the mark, not a disqualification); flip
   requires editing the green-run definition clause before merge.*
3. **Ceiling value.** $3.00/run is ~4× the measured weekly fallback
   run; a monthly aggregate ceiling would need a stateful counter
   across runs. *Proposed default: per-run ceiling now; a monthly
   aggregate only if the owner wants hard monthly dollars — note for
   the RM-040 routing review.*
4. **`lane-status` retention horizon.** 30 days matches log retention;
   a longer horizon needs the 30-day prune/archive interplay. *Proposed
   default: 30 days; revisit at the RM-040 slot if the escalation
   horizon proves too short.*

## History

- 2026-10-12 — drafted by the designing-architecture pass (roadmap row
  RM-056, score 9, Now; owner-frozen policy dated 2026-10-11 carried in
  the body per RM-034). Sources read: `docs/roadmap-detail/RM-056.md`
  and RM-021.md, `reference/eval-green-run-definition.md`,
  `reference/model-routing.md`, `docs/ADRs/ADR-0013-go-first-model-policy.md`
  (+ superseded ADR-0002/0007 for the direct-key lane's measured
  economics and secret pattern), `skills/authoring-skills/references/eval-harness.md`,
  `skills/authoring-skills/scripts/run_behavioral_eval.py` (full read:
  lane constants, `assert_ci_free_model`, early-abort loop, `_redact`
  env list, sandbox env, stub modes, exit codes) + `test_runner.py`,
  `scripts/eval-report.py` + `test_eval_report.py` +
  `merge-eval-logs.py`, `scripts/ci-lane-overrides.py`,
  `.github/workflows/{eval-behavioral,eval-per-change,ci}.yml` +
  `scripts/test_eval_workflows.py`, `skills/observing-runs/scripts/log_run.py`
  + `references/schema.md` + `test_log.py` + `query_runs.py`
  (evidence for the build_record-drops-unknown-keys constraint),
  `reference/per-change-eval-sla.md`, ROADMAP RM-039/RM-040 rows +
  RM-040 detail, RM-034 detail (policy-in-body). Verified: the direct
  lane is already accepted by `assert_ci_free_model` and redacted
  (`_redact` env list) — the switch needs no new provider plumbing.
  UX consult: **no user-facing UI — council-ux consult skipped**
  (internal CI/eval logic; no screen, form, or flow changes). Design
  consult: explicitly skipped — no consult warranted; the row's policy
  is owner-frozen (2026-10-11) and every open design dimension had a
  defensible default drawn from RM-021's evidence base; a consult board
  would re-litigate frozen rulings, not resolve ambiguity.
  Consult outcome: skipped (policy frozen by owner directive,
  no feature-identity ambiguity).
- 2026-10-13 — implementation pass (branch `feat/rm-056-eval-fallback`,
  cut from the design tip `91a8684`). Owner approval 2026-10-12 per the
  implement dispatch; frontmatter `status` flipped `draft` → `approved`
  (RM-021 convention) and `revised` appended. Four gated commits, each
  green on its unit verifiers + the Layer-1 hermetic validators:
  1. runner fallback + hermetic drills — `run_behavioral_eval.py`,
     `test_runner.py` (AC 1-5, 9, 11);
  2. report surfaces + green-run clause — `scripts/eval-report.py`,
     `scripts/test_eval_report.py`,
     `reference/eval-green-run-definition.md` (AC 6-8);
  3. CI wiring — both eval workflows + `scripts/test_eval_workflows.py`
     (AC 10);
  4. harness-reference cite — `skills/authoring-skills/references/eval-harness.md`.
  AC 12 verified by the full offline suite green; AC 5's diff assertion
  verified in-pass (the change set is exactly Files to Modify; both
  workflows keep the same `opencode-go/deepseek-v4.1-flash` run-block
  pin). Rehearsal drills (hermetic, logs under `.scratch/rm-056-impl/`):
  `:FALLBACK-DRILL:` replays RM-021's model-resolution death class
  (3 terminal provider-classed records → one `lane-degradation-evidence:`
  → one `lane-switch:` → fallback verdicts carry
  `deepseek/deepseek-flash`; exit 0); `:EXTERNAL-REJECT:` replays the
  external-directory auto-reject class (zero lane records; exit 1);
  ceiling forced to `0.01` exits 4 with a `lane-fallback-ceiling:`
  record naming the deferred remainder.
  Deviation note (mechanical, proceeded with History): the owner-added
  clarification — "on a ceiling hit the run still emits its report and
  names the deferred remainder" — is NOT literal in the pre-approval
  plan body on the design branch. Implemented to intent: the ceiling
  record is written, the runner emits its report summary, and the record
  names the deferred remainder; AC 9 is unchanged.

### Follow-ups
- Live smoke 1 (primary-healthy `workflow_dispatch`, `Lane: primary`)
  and optional live smoke 2 (real-switch replay) are owner-run; not
  executed here per the dispatch's behavioral-evals budget constraint.
- AC 5's git-diff review assertion is verified in-pass (see History);
  a future reader can re-run `git diff <design-tip>...HEAD --name-only`.
- The routing-review escalation this feature emits lands in RM-040's
  monthly slot (2026-11-01) per D4; no ROADMAP.md edit is made by this
  pass (ROADMAP is the migration pass's working product — plan Excluded).
