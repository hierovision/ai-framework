# Model Routing

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

## Core routing table

| Role | Free default (`opencode/*-free`) | Escalation — Go flat-rate (`opencode-go/`) | Escalation — Zen PAYG (`opencode/`) | Bench basis for escalation |
|---|---|---|---|---|
| `planner` | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt kimi-k3) | claude-opus-5 (peak: claude-fable-5) | AA Intelligence Index 60; Thinkbench autonomous loop 92%/0.976 |
| `implementer` | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 (alt gpt-5.4) | AA 60 vs K2.7 43; MCPMark 81.1 (K2.7 legacy) |
| `triager` | nemotron-3-ultra-free | glm-5.3 (alt deepseek-v4-pro) | gpt-5.6-luna (alt gpt-5.4-mini) | AA 60 / luna 52 at $0.05/task + 141 t/s |
| `test-writer` | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | AA 60; MCPMark + SWE-bench Verified |
| `debugger` | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | Thinkbench + SWE-bench Verified |
| `reviewer` | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | SWE-bench Verified (defect catch) |
| `vision-critic-fast` | — (no free multimodal) | minimax-m3 (native multimodal) | gemini-3-flash (alt gpt-5.4-mini) | native image-in; vision bench (gemini) |
| `vision-critic-final` | — | — | gemini-3.1-pro (alt claude-sonnet-5) | vision quality (gemini-3.1-pro) |
| `council-member` | nemotron-3-ultra-free + mimo-v2.5-free + deepseek-v4-flash-free | kimi-k3 + glm-5.3 + deepseek-v4-flash (Go, mix families) | claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol (frontier, max diversity) | family diversity + per-lens competence |
| `skill-author` | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | minimax-m3 (alt glm-5.2, qwen3.7-max) | claude-sonnet-5 (qwen3.7-max is Go-only IF leader) | IFBench 79.1; Thinkbench existing-code parity |
| `skill-reviewer` | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt glm-5.2) | claude-opus-5 (peak: claude-fable-5) | SWE-bench Verified (highest reasoning) |

## Routing update — 2026-08-25

Full-sweep pass via the `optimizing-model-routing` skill. All previously bound IDs remain catalog-valid (no stale bindings). Key changes:

- `implementer`/`test-writer` Go: kimi-k2.7-code → **kimi-k3** (AA 60 vs 43)
- `triager` Go: hy3 → **glm-5.3** (AA 60 vs 42); Zen: gpt-5.6-luna (AA 52 at $0.05/task, 141 t/s)
- `council-member` Go mix: hy3 + mimo-v2.5 + deepseek-v4-flash → **kimi-k3 + glm-5.3 + deepseek-v4-flash** (42/38/52 → 60/60/52)
- Free defaults and all `agents/*.md` bindings: **unchanged**
- Watch list: kimi-k3 and deepseek-v4-flash-vision-exp are Go-tier multimodal candidates for `vision-critic-fast`; qwen3.8-max (AA 58) replaces qwen3.7-max as skill-author IF escalation watch
- Grok family scores 61 on AA — hard-excluded (user directive 2026-08-14)

## Benchmark evidence principles

**Read benchmarks as a tier filter, not a ranking.** The most decision-relevant numbers are the independent autonomous-loop test (Thinkbench) and instruction-following (IFBench), plus this repo's own authoring rounds. Harness choice alone swings scores 10–20 points.

- SWE-bench Verified: directionally useful for tier filtering, not model ranking
- Thinkbench autonomous coding loop: GLM 5.2 92% full-pass / 0.976 mean; on existing-code tasks both GLM and M3 score 0.999–1.000 (indistinguishable)
- IFBench (instruction-following): Qwen3.7 Max 79.1 (leads); DeepSeek V4 Pro 77.0
- MCPMark Verified: Kimi K2.7 Code 81.1 > Opus 4.8 76.4; K2.7 ~30% more token-efficient
- Multimodal: MiniMax M3 is natively multimodal (image/video in) on Go's flat rate — the only cheap open model that reads a screenshot without a bolt-on

## Hard exclusions

Never bind, recommend, or escalate to these models in any tier, for any persona or workflow. This is a user directive, dated 2026-08-14.

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `grok-4.5` | Go, Zen | user directive (2026-08-14): grok family excluded from everything |
| `grok-4.6` | Zen | same |
| `grok-build-0.1` | Zen | same |

The exclusion supersedes any earlier mention. When a new grok-* ID appears in a catalog fetch, treat it as excluded automatically.

## Free-tier caveats (read before relying on free defaults)

The free generalist was validated 2026-07-26 by a clean, no-tool head-to-head eval. Since 2026-08-14 `ling-3.0-flash-free` is gone from the catalog, `nemotron-3-ultra-free` now holds the generalist seats — its streaming caveat is the standing reliability risk. For risk-bearing tasks you may still escalate to Go or Zen tier. Free by default; escalation is opt-in.

## Provider notes

- **Free tier** ($0): `opencode/*-free` catalog entries (subset of Zen catalog). Default tier — used for every role where a free model exists. No financial consequence.
- **Go** ($10/mo flat): Open models only. Config prefix `opencode-go/`. Escalation tier — used when the free default is insufficient or unavailable (vision, peak coding). Limits: $12/5hr, $30/wk, $60/mo. `hy3` and `hy3-preview` are now Go flat-rate models.
- **Zen** (pay-as-you-go): Full catalog including proprietary models. Config prefix `opencode/`. Escalation tier — frontier opt-in (Opus-5, Fable-5, GPT-5.6, Gemini-3.1-pro) and the only source of vision-capable critics. `qwen3.7-*` is Go-only — bind it as a Go escalation, never as a Zen one.
- Go can fall back to Zen balance when limits hit ("Use balance" in the console). `AI_FRAMEWORK_FREE_TIER=1` forces the free tier even when a Go/Zen key is present.

## Vision capability strategy

The UI iteration loop requires a model that can read screenshots. Tiered strategy (locked decision):

- **`vision-critic-fast`** (iteration passes): defaults to **MiniMax M3** on Go's flat rate (natively multimodal, cheapest option). If M3's screenshot judgment proves good enough for routine passes, the fast tier stays on Go instead of Zen billing — a material saving. **Not yet confirmed for UI-CSS judgment specifically** (M3's multimodal wins are on SVG-Bench / BrowseComp, not UI critique); evaluate in the `correcting-ui` eval loop before relying on it.
- **`vision-critic-final`** (sign-off): stays Zen (`gemini-3.1-pro` / `claude-sonnet-5`) for strongest vision quality.
- Cheaper Zen vision alternatives for fast passes: `gemini-3.5-flash` / `gemini-3.6-flash`; `gemini-3.7-flash` (newest, 2026-08-14) is the upgrade candidate — bench its vision judgment before switching.

**No free multimodal model exists**, so vision defaults to the Go escalation (M3).

## Update procedure

1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - Docs pages for pricing/deprecations
2. Update the core routing table and bench basis per-role rationale.
3. If a bound model is deprecated or beaten on price/quality, update the role row and note it in the commit message.
4. Bump the retrieval date at the top of the file.
5. When the Phase 5 eval harness exists: re-run role benchmarks before changing any binding, and record results alongside the change.

## Free-tier fallback + council

- **Toggle:** `AI_FRAMEWORK_FREE_TIER=1` selects free-tier mode. The escalation rows above remain the default-capable path; with the toggle on, every task uses a free model even when Go/Zen keys are present.
- Skills reference **roles**, never these IDs (library convention). The binding of a role to a free model in free-tier mode happens in the harness/project config, not in skill bodies — this file is the single home of the IDs.
- **Council** runs on free models for planning & review (per `docs/FREE-TIER-COUNCIL.md`). Planning council (A: nemotron-3-ultra-free, B: mimo-v2.5-free, C: deepseek-v4-flash-free) and review council (A: deepseek-v4-flash-free, B: mimo-v2.5-free, C: nemotron-3-ultra-free) synthesize findings with explicit disagreement surface.
- Council only for **planning & review** (per above). Raw execution stays single-model to conserve free quota.
- Always surface disagreements; never let one model silently override another.
- Free-tier mode coexists with the escalation routing — the toggle selects between them; the escalation rows are not modified by enabling free-tier.