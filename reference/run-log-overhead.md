# Run-log overhead budget (dated, provisional)

Status: **`unverified`** as of 2026-09-13 — no RM-002 baseline has been
recorded. Treat the numbers below as a target, not an established hard bound.

## Budget

Convention-based logging (`log_run.py --record`, one call per run) must stay:

- **< 2%** of the run's total tokens, and
- **< 200 tokens/run**.

One `log_run.py --record` call is roughly 80–160 tokens; a task is thousands.

## Measurement method

Measure on the RM-002 weekly behavioral-eval baseline: per run, compare the
`log_run.py` tool-call tokens against the run's total tokens. Record the
baseline date and result here when available.

## Disposition

If either bound is exceeded, mandate hook-based emission before broad
adoption. Hook emission is currently aspirational (see
`opencode-integration.md`) and cannot attribute tokens/duration, so the
convention-based call remains the default.

## History

- 2026-09-13: created. The number moved here from
  `skills/observing-runs/SKILL.md` and `references/schema.md` (Choice 6 — a
  volatile, measurement-dependent number does not belong in the slow
  skill/contract files). Still `unverified`.
