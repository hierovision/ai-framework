# Model Routing

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

- Retrieved: 2026-07-03 from https://opencode.ai/docs/zen/ and
  https://opencode.ai/docs/go/
- Review cadence: monthly, or when a deprecation notice lands
- Status: **seeded from published pricing/positioning — not yet
  empirically validated.** Phase 5 eval harness will benchmark role
  bindings (pass rate / tokens / latency) and update this table.

## Contents

- Roles → bindings
- Provider notes (Zen vs Go)
- Vision capability notes
- Deprecation watch
- Update procedure

## Roles → bindings

| Role | Used by (loop stage) | Go default (flat-rate) | Zen escalation (PAYG) |
|---|---|---|---|
| `planner` | design, architecture | glm-5.2 | claude-opus-4-8, gpt-5.5 |
| `implementer` | implement (backend/frontend) | kimi-k2.7-code, qwen3.7-plus | claude-sonnet-5, gpt-5.4 |
| `triager` | triage, bulk edits, summaries | deepseek-v4-flash, mimo-v2.5 | gpt-5.4-mini, claude-haiku-4-5 |
| `test-writer` | unit/integration/e2e authoring | kimi-k2.7-code, qwen3.7-plus | claude-sonnet-5 |
| `debugger` | test-failure analysis | glm-5.2, deepseek-v4-pro | claude-sonnet-5, gpt-5.4 |
| `reviewer` | code review | glm-5.2 | claude-sonnet-5, gpt-5.4 |
| `vision-critic-fast` | UI loop, routine passes | — (open models weak on vision) | gemini-3-flash, gpt-5.4-mini |
| `vision-critic-final` | UI loop, final review | — | gemini-3.1-pro, claude-sonnet-5 |
| `council-member` | multi-perspective review | glm-5.2 + minimax-m3 + qwen3.7-max (mix families) | mix: claude + gpt + gemini |
| `skill-author` | authoring new skills via `authoring-skills` | glm-5.2 (validate first — see PLAN.md) | claude-sonnet-5 |
| `skill-reviewer` | reviewing skill drafts, foundation work | — | claude-fable-5, claude-opus-4-8 |

## Provider notes

- **Go** ($10/mo flat): open models only. Limits: $12/5hr, $30/wk, $60/mo.
  Config prefix `opencode-go/`. Default here first — marginal cost is zero
  within limits.
- **Zen** (pay-as-you-go): full catalog including proprietary models.
  Config prefix `opencode/`. Escalation path and only source of
  vision-capable critics.
- Go can fall back to Zen balance when limits hit ("Use balance" in the
  console).

## Vision capability notes

The UI iteration loop **requires** a model that can read screenshots.
As of 2026-07-03, Go's open models are weak or absent on vision — budget
the vision-critic roles through Zen. Tiered strategy (locked decision):
cheap model per iteration pass, strong model for final signoff.

## Deprecation watch (from Zen docs, 2026-07-03)

| Model | Deprecation date | Action |
|---|---|---|
| GPT 5.2/5.1/5 Codex variants | 2026-07-23 | avoid in new bindings |
| Kimi K2.5 | 2026-08-05 | use kimi-k2.7-code |
| MiniMax M2.5 | 2026-08-05 | use minimax-m3 / m2.7 |
| Claude Opus 4.1 | 2026-08-05 | use opus-4-8 |
| GLM 5 | 2026-05-14 (past) | use glm-5.2 |

Known stale bindings in existing projects: `pt` uses `qwen3.6-plus`
(still served, but `qwen3.7-plus` is newer and cheaper — refresh during
Phase 4 migration).

## Update procedure

1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - Docs pages for pricing/deprecations
2. Update tables above; bump the retrieved date.
3. If a bound model is deprecated or beaten on price/quality, update the
   role row and note it in the commit message.
4. When the Phase 5 eval harness exists: re-run role benchmarks before
   changing any binding, and record results alongside the change.
