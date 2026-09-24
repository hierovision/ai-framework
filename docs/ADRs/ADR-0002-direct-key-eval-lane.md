# ADR-0002: CI behavioral evals run on the direct-key DeepSeek lane

## Status: accepted 2026-09-18

## Context

RM-002/RM-003 wire behavioral evals into CI (`eval-behavioral.yml`,
`eval-per-change.yml`). The eval runner drives a fresh agent per eval through
opencode, which needs a model lane. Free gateway lanes suffered
availability problems (a 24h outage was later the deciding evidence for the
2026-09-21 amendment, ADR-0007), and canary pass-rates on free lanes were
unstable enough to blur regression signal from lane noise.

## Decision

Behavioral evals in CI run on the direct-key DeepSeek lane
(`deepseek/deepseek-flash`, provider prefix `deepseek/`), driven by a
`DEEPSEEK_API_KEY` secret. The key is redacted from persisted event streams
at persistence time (`***`). Measured budget: ~$0.68 per weekly off-peak run.

## Consequences

- CI eval signal is stable and attributable to the evals, not the lane.
- The key is a long-lived secret scoped to the eval workflows; redaction and
  the public-repo artifact caveat are the compensating controls
  (`eval-behavioral.yml` artifact comments).
- Weekly cron parked at 10:30 UTC (off-peak) to hold the measured budget
  (amended 2026-09-21, ADR-0007).

## Sources

- PR #20 (commit `a4216d7`); user directive 2026-09-18
- `reference/model-routing.md` (provider notes, budget measurement)
- `docs/ROADMAP.md` RM-002/RM-003 acceptance cells
