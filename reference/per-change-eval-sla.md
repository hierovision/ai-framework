# Per-change eval SLA + quota guardrail (RM-003 AC8, AC11)

SLA and cost model for the Layer 3 per-change eval workflow
(`.github/workflows/eval-per-change.yml`).

## Contents

- SLA budget
- Timeout and `--limit` derivation
- Quota model
- Guardrail
- Three-layer cost
- Trade-offs

## SLA budget

| Scenario | Max skills | Max evals | Target wall time | Job timeout |
|---|---|---|---|---|
| Single skill change | 1 | ~6 | <= 5 min | 10 min |
| 2-3 skills changed | 2-3 | ~12-18 | <= 12 min | 20 min |
| Fallback smoke (ambiguous / no match) | <= 10 | <= 30 (3 per skill) | <= 15 min | 25 min |
| Docs-only / non-evaluable | 0 | 0 | ~0s | exits early |

The workflow sets a single `timeout-minutes: 20` cap (AC8). The report/summary
step records actual elapsed time against the 20-minute budget in the CI job
summary: `Per-change eval: <m>m <s>s (budget 20m)`.

## Timeout and `--limit` derivation

GitHub Actions evaluates `timeout-minutes` at job start, so the cap is static
(20 min) rather than computed from the skill count. The eval **count** is
bounded dynamically in the run step:

- changed skills present: `--limit = min(changed_skill_count * 6, 18)`
  (max 3 skills -> 18 evals).
- smoke class: `--limit 30` (bounded smoke subset).
- non-evaluable class: no eval invocation (0 evals).

## Quota model

`scripts/eval-report.py quota-projection` writes `quota-projection.json`
(also uploaded by the weekly workflow):

```json
{
  "weekly_run_min": 38.0,
  "weekly_min_used": 152.0,
  "per_change_run_min": 9,
  "per_change_min_used": 45,
  "prs_per_month_assumed": 5,
  "projected_monthly": 197.0,
  "guardrail_limit": 1800,
  "updated": "2026-09-18"
}
```

- `weekly_run_min` = included evals x 30s.
- `weekly_min_used` = `weekly_run_min` x 4 weeks.
- `per_change_min_used` = 9 min x 5 assumed PRs/month.
- `projected_monthly` = sum of the two monthly buckets.

## Guardrail

The per-change workflow reads `quota-projection.json` at start and fails fast
when `projected_monthly > 1800` (90% of GitHub Free's 2,000 min/month cap):

```
Quota guardrail: projected monthly minutes <n> would exceed 1800
```

The 1,800 limit is the 90% guardrail; the absolute cap is 2,000.

## Three-layer cost

| Layer | Where | CI minutes | Local time |
|---|---|---|---|
| 1. Pre-commit hook | developer machine | 0 | ~14s/commit |
| 2. Advisory pre-push | developer machine (opt-in) | 0 | ~30-60s/push |
| 3. Per-change PR check | GitHub Actions | <= 20 min/PR | n/a |
| Weekly full suite | GitHub Actions | ~32 min/week | n/a |

## Trade-offs

- Layer 1 and Layer 2 shift latency to the developer machine to save CI
  minutes; both are advisory and bypassable.
- Layer 3 is the enforcement gate and cannot be bypassed (unlike `git commit
  --no-verify`).
- The per-change cap (`--limit 18`) may under-run a skill with more than 6
  evals when 3 skills change; the weekly suite remains the full-coverage gate.
