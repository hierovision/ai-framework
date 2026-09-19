# Eval green-run definition (RM-003 AC10)

This is the canonical definition of a **steady-state green run** used by the
eval report dashboard (`green-run-status.json`) to qualify RM-003 AC4.

## Contents

- Definition
- First qualifying run
- Status artifact
- Relationship to RM-002's canary
- Sizing basis (resolved pass 3)

## Definition

A **steady-state green run** is a weekly `eval-behavioral` workflow run on
`main` that satisfies all four conditions:

1. **All included evals pass** — every `kind=eval` record has `eval_pass=true`
   (evals excluded by default — `deferred:true`, CI free-tier `go|zen`, or
   quarantined — are not "included" and therefore not required to pass).
2. **Zero quarantine flips** — no eval entered or left quarantine during the
   run (`logs/quarantine.json` unchanged across the run).
3. **Within the weekly SLA budget** — the run completes in `<= 120` minutes
   wall time (the full ~63-eval suite at the measured ~100s/eval is ~105 min;
   see `reference/per-change-eval-sla.md`).
4. **On `main`** — the run is the scheduled weekly workflow on the `main`
   branch, not a PR, fork, or manual dispatch from a feature branch.

A run that fails any condition is a candidate, not a green run.

## First qualifying run

- Earliest candidate: the scheduled weekly run on **2026-09-21**.
- Subsequent candidates: `2026-09-28`, `2026-10-05`, ...
- The first qualifying run's run ID and artifact link are recorded in
  `green-run-status.json` via
  `scripts/eval-report.py green-run-status --record --run-id <id> --date <date>
  --duration-min <n> --all-pass --quarantine-flips 0 --artifact-url <url>`.

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
`quarantine_flips`, `artifact_url`, and `qualified_at`.

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
