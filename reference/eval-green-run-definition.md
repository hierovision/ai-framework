# Eval green-run definition (RM-003 AC10 / RM-021)

This is the canonical definition of a **steady-state green run** used by the
eval report dashboard (`green-run-status.json`) to qualify RM-003 AC4.

Amended 2026-10-03 (RM-021 acceptance): completion semantics moved to
final-verdict, depth updated, and recovered infra deaths recorded as lane-health
data rather than a disqualifier.

## Contents

- Definition
- First qualifying run
- Status artifact
- Relationship to RM-002's canary
- Sizing basis (resolved pass 3)

## Definition

A **steady-state green run** is a weekly `eval-behavioral` workflow run on
`main` that satisfies all four conditions:

1. **All included evals reach a final content verdict and all are PASS** — every
   eval's final record has `eval_pass=true`. Per-attempt annotations
   (`eval_pass=null`) are lane-health data, not content verdicts. A terminal
   infra failure (`outcome=error` with no final `eval_pass`) disqualifies the
   run because the signal is incomplete. Recovered infra deaths (an eval that
   had one or more `eval_pass=null` annotation records but ended with a final
   PASS/FAIL verdict) are recorded as `infra_retried` lane-health data, not a
   disqualifier (RM-021, 2026-10-03; `eval-report.py failure-taxonomy` reports
   `terminal_infra` and `recovered_infra` separately).
   (evals excluded by default — `deferred:true`, CI free-tier `go|zen`, or
   quarantined — are not "included" and therefore not required to pass).
2. **Zero quarantine flips** — no eval entered or left quarantine during the
   run (`logs/quarantine.json` unchanged across the run).
3. **Within the weekly SLA budget** — the run completes in `<= 120` minutes
   wall time. The weekly default-depth suite has 26 included evals; the monthly
   full suite has 110 included evals (see `reference/per-change-eval-sla.md`).
4. **On `main`** — the run is the scheduled weekly workflow on the `main`
   branch, not a PR, fork, or manual dispatch from a feature branch.

A run that fails any condition is a candidate, not a green run.

## First qualifying run

- Earliest candidate: the scheduled weekly run on **2026-09-21**.
- Subsequent candidates: `2026-09-28`, `2026-10-05`, ...
- RM-021 is satisfied by the weekly default-depth variant (26 evals) on the
  `opencode-go/deepseek-v4.1-flash` lane.
- The first qualifying run's run ID and artifact link are recorded in
  `green-run-status.json` via
  `scripts/eval-report.py green-run-status --record --run-id <id> --date <date>
  --duration-min <n> --all-pass --quarantine-flips 0 --depth default
  --infra-retried <n> --artifact-url <url>`.

## Status artifact

`green-run-status.json` is produced by
`scripts/eval-report.py green-run-status` and uploaded as a 30-day CI artifact.
Not-yet-achieved shape:

```json
{
  "achieved": false,
  "reason": "No steady-state green run observed as of <date>. ...",
  "candidate_runs": [],
  "definition": "reference/eval-green-run-definition.md"
}
```

Achieved shape adds `run_id`, `date`, `branch`, `duration_min`, `all_pass`,
`quarantine_flips`, `infra_retried`, `depth`, `artifact_url`, and `qualified_at`.

## Relationship to RM-002's canary

RM-002 verified the gate's **negative** path with a deliberately broken eval
canary (run `35108912831`, 2026-09-16): the job failed red and emitted an
`eval_pass=false` record. RM-003's green run is the **positive** counterpart:
the same gate, unmodified, passing the full included suite on `main`.

## Sizing basis (resolved pass 3)

The budget is `<= 120` min against the measured ~100s/eval: the full ~63-eval
suite is ~105 min worst case (run 35392700424 measured ~100s/eval; the prior
30s/eval estimate was imaginary). The ~105 min weekly duration is expected, not
a defect, and does not disqualify a green run. This resolves the earlier
sizing tension recorded in pass 2.

Updated counts (RM-021, 2026-10-03): weekly default-depth = 26 included evals;
monthly full suite = 110 included evals.
