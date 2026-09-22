# Per-change eval SLA + quota guardrail (RM-003 AC8, AC11)

SLA and cost model for the Layer 3 per-change eval workflow
(`.github/workflows/eval-per-change.yml`). Pass 4 re-derives the math from the
**measured ~100s per fresh-agent eval** (first live per-change run, PR #23,
run 35392700424 — 12 evals exceeded the old 20 min ceiling); the prior 30s/eval
figure was imaginary and is superseded.

## Contents

- SLA budget
- Selection and `--limit`
- Matrix execution
- Stall headroom
- Quota model
- Guardrail
- Three-layer cost
- Concurrency evidence
- Trade-offs

## SLA budget

Marker-selected math: a skill change runs that skill's one `default` canary
(fallback: first eval in file order); a harness change runs the fixed six-core
set. Stalls add up to **2×240s worst case per eval** (one 240s stall + one
bounded retry).

| Scenario | Max skills | Max evals | Target wall time | Job timeout |
|---|---|---|---|---|
| Single skill change | 1 | 1 | ~2 min | <= 5 min | 20 min |
| Two skill changes | 2 | 2 | ~3-4 min | <= 12 min | 20 min |
| Harness change (repo-root `scripts/`, `.github/workflows/`) | 6 (core set) | <= 6 | ~10-11 min | <= 12 min | 20 min |
| Docs-only / non-evaluable | 0 | 0 | ~0s | n/a | exits early |

The workflow keeps a single static `timeout-minutes: 20` for the matrix. The
CI summary reports elapsed against the scenario target:
`Per-change eval: 5m 12s, target <=12m / ceiling 20m`.

## Selection and `--limit`

The workflow selects the eval set deterministically via the runner's two-tier
marker flags:

- skill change: `--default --skill <skill>` (that skill's `"default": true`
  canary; fallback = first eval in file order).
- harness change: `--core --skill <skill>` for each of the fixed six core
  skills (their `"core": true` default evals).

Both selected paths **ignore `--limit`**; `--limit` is retained for manual
sharding only. There is no relevance list and no alphabetical fallback — a
harness change is the fixed six-core set.

## Matrix execution

Selected evals run as a **one-eval-per-job matrix** (`strategy.matrix.include`
from the plan job's selection JSON) with:

- `fail-fast: false` **during the shakedown phase** (2026-09-21: one run reports
  all legs' results instead of one red per run); flip to `true` after two
  consecutive fully-green CI runs — tracked follow-up. When enabled, a red eval
  cancels in-flight siblings and surfaces in
  **2-3 min**.
- `max-parallel` configurable via the repository variable
  `EVAL_MAX_PARALLEL` (default **3**; raise only after a clean live CI run).

The aggregation/report job runs `needs: [evals]` + `if: always()`, so the
eval-report and coverage-gap artifacts plus SLA reporting survive a red leg.
Each matrix leg uploads its `logs/` as `eval-logs-<skill>`; the report job
downloads them (`merge-multiple: true`) and aggregates.

## Stall headroom

Every `opencode` invocation is bounded by `BEVAL_TIMEOUT_SECONDS` (default
240s) with a process-group kill and a synthetic transient failure (AC9). A
stalled eval therefore costs at most 2×240s before it is classified; the 20 min
job ceiling absorbs a stall on the small selected set.

## Quota model

`scripts/eval-report.py quota-projection` writes `quota-projection.json`
(also uploaded by the weekly workflow). Pass-4 counts:

```json
{
  "weekly_run_min": 128.6,
  "weekly_min_used": 514.4,
  "per_change_run_min": 7,
  "per_change_min_used": 105,
  "prs_per_month_assumed": 15,
  "projected_monthly": 619.4,
  "guardrail_limit": 1800,
  "updated": "2026-09-19"
}
```

- `weekly_run_min` = included evals x ~100s (`WEEKLY_MIN_PER_EVAL = 1.67`).
  The current CI-included count is 77 (deferred + go/zen excluded).
- `weekly_min_used` = `weekly_run_min` x 4 weeks.
- `per_change_run_min` = 7 (blended 1-2 skill / <=6 harness evals).
- `per_change_min_used` = 7 x 15 assumed PRs/month.
- `projected_monthly` = sum of the two monthly buckets (~619 min, well under
  the 1,800 guardrail).

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
| 3. Per-change PR check | GitHub Actions | ~2-11 min/PR (marker-selected) | n/a |
| Weekly full suite | GitHub Actions | ~129 min/week (77 evals) | n/a |

## Concurrency evidence

The 2026-09-19 6-parallel free-tier eval-session probe completed with **zero
429/rejections** — the matrix premise holds. `max-parallel` starts at 3 and is
raised only after a clean live CI run.

**Gateway caveat (2026-09-19)**: four model families stalled simultaneously
while the direct-key deepseek lane answered clean in 2.6s, so the stall lives
in the shared gateway, not any model. The stall machinery (AC9) is the correct
CI response; eval-model A/B is unanswerable mid-window and is out of scope.

## Trade-offs

- Layer 1 and Layer 2 shift latency to the developer machine to save CI
  minutes; both are advisory and bypassable.
- Layer 3 is the enforcement gate and cannot be bypassed (unlike `git commit
  --no-verify`).
- Per-change is a fast high-signal tripwire, not a shallow copy of the weekly
  gate: non-default evals only ever ran weekly, so their regression window is
  unchanged from RM-002. Skills without a `default` marker are surfaced in
  `coverage-gaps.no_default_marker` and fall back to their first eval.
- **Known tension (recorded pass 4)**: the plan's weekly estimate assumed ~63
  evals; the current CI-included count is 77, so at the measured ~100s/eval
  the full suite is ~129 min, above the 120 min weekly ceiling. The weekly
  workflow keeps `timeout-minutes: 120` per AC10. Re-baseline the ceiling or
  shard the weekly suite before a full run can qualify as green.
