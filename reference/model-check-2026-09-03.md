# Model Check + Right-Sizing — 2026-09-03

## Sources
- Zen catalog (PAYG): `https://opencode.ai/zen/v1/models` — retrieved 2026-09-03 (live fetch)
- Go catalog (flat-rate): `https://opencode.ai/zen/go/v1/models` — retrieved 2026-09-03 (live fetch)
- Docs free list: `https://opencode.ai/docs/zen/#endpoints` — retrieved 2026-09-03 (authoritative for free-tier)

## Current bindings
- `planner`: free=nemotron-3-ultra-free, Go=glm-5.3, Zen=claude-opus-5
- `implementer`: free=nemotron-3-ultra-free, Go=kimi-k3, Zen=claude-sonnet-5
- `triager`: free=nemotron-3-ultra-free, Go=glm-5.3, Zen=gpt-5.6-luna
- `test-writer`: free=nemotron-3-ultra-free, Go=kimi-k3, Zen=claude-sonnet-5
- `debugger`: free=nemotron-3-ultra-free, Go=glm-5.3, Zen=claude-sonnet-5/gpt-5.4
- `reviewer`: free=nemotron-3-ultra-free, Go=glm-5.3, Zen=claude-sonnet-5/gpt-5.4
- `vision-critic-fast`: free=none, Go=minimax-m3, Zen=gemini-3-flash
- `vision-critic-final`: free=none, Go=none, Zen=gemini-3.1-pro
- `council-member`: free=nemotron-3-ultra-free+mimo-v2.5-free+muse-spark-1.2-contributor-free, Go=kimi-k3+glm-5.3+deepseek-v4-flash, Zen=claude-opus-5+gemini-3.1-pro+gpt-5.6-sol
- `skill-author`: free=nemotron-3-ultra-free, Go=minimax-m3, Zen=claude-sonnet-5
- `skill-reviewer`: free=nemotron-3-ultra-free, Go=glm-5.3, Zen=claude-opus-5

Agent bindings (free defaults):
- `agents/council.md`: opencode/nemotron-3-ultra-free
- `agents/council-security.md`: opencode/mimo-v2.5-free
- `agents/council-performance.md`: opencode/nemotron-3-ultra-free
- `agents/council-ux.md`: opencode/mimo-v2.5-free
- `agents/council-architecture.md`: opencode/muse-spark-1.2-contributor-free
- `agents/council-product.md`: opencode/nemotron-3-ultra-free

## Per-role analysis
- `council-member` (free): Rebalanced to 3 families across 5 seats. `council-architecture` moved from nemotron to muse-spark-1.2-contributor-free (diversity seat; architecture lens most sensitive to family-level pattern bias). `council-ux` moved from nemotron to mimo-v2.5-free (validated security lens strength). Result: nemotron×3 (chairman, performance, product), mimo×2 (security, ux), muse-spark×1 (architecture). This is the best achievable 3-family split with current free model set.
- `council-member` (Go): `deepseek-v4-flash` in escalation row requires live Go-tier probe before next routing pass. If unverified, replace with `kimi-k3` (verified Go).
- `council` fallback: Removed `general` subagent fallback in `agents/council.md`; degraded council now aborts with explicit error.
- Free models docs-verified: mimo-v2.5-free, ling-3.0-flash-fin-free, nemotron-3-ultra-free, nemotron-3.5-lightning-free, big-pickle, muse-spark-1.3-contributor-free, muse-spark-1.2-contributor-free. `deepseek-v4-flash-free` in Zen catalog API but NOT in docs free list → NOT routable.

## Proposed bindings
- `council-member` free: nemotron-3-ultra-free + mimo-v2.5-free + muse-spark-1.2-contributor-free (unchanged — reflects current agent bindings)
- `council-architecture` free: nemotron-3-ultra-free → muse-spark-1.2-contributor-free (changed — diversity seat)
- `council-ux` free: nemotron-3-ultra-free → mimo-v2.5-free (changed — rebalance)
- `council-security` free: mimo-v2.5-free (unchanged)
- `council-performance` free: nemotron-3-ultra-free (unchanged)
- `council-product` free: nemotron-3-ultra-free (unchanged)
- `council` chairman free: nemotron-3-ultra-free (unchanged)

## Questionable / uncertain
- `muse-spark-1.2-contributor-free` lacks head-to-head eval (only catalog+docs liveness) — schedule eval for next routing pass (2026-10)
- `deepseek-v4-flash` Go-tier routability unverified — probe required before next pass
- `muse-spark-1.3-contributor-free` available as alternative third family if 1.2 shows regression
- Known monoculture risk: 3/5 free council seats on nemotron-3-ultra-free — accept until 4th free family validated

## Applied
- Updated `agents/council-architecture.md` model binding to `opencode/muse-spark-1.2-contributor-free`
- Updated `agents/council-ux.md` model binding to `opencode/mimo-v2.5-free`
- Updated `agents/council.md` table and removed `general` fallback
- Updated `reference/model-routing.md` with Routing update 2026-09-03, Free-tier caveats monoculture note, Update procedure Go/Zen gate
- Updated `docs/FREE-TIER-COUNCIL.md` model table to current state (snapshot, not changelog)
- Marked `reference/catalog-check-2026-08-14.md` as superseded
- Added Go-tier verification probe to `skills/optimizing-model-routing/SKILL.md` Step 3
- Verifier: OK (all bindings match, no forbidden IDs, artifact + update marker present)