# Model Routing

Catalogs, docs free list, and liveness probes: retrieved and live-verified 2026-09-18.
2026-09-18 pass notes: Zen workspace model-access toggles were the cause of the
2026-09-18-morning "Model is disabled" errors (claude-opus-5, claude-sonnet-5,
gpt-5.6-sol, gpt-5.6-luna, big-pickle were then enabled by the user and
re-verified live). DeepSeek V4.1-Flash entered candidacy through the user's
direct DeepSeek API key (new `deepseek/` provider lane, approved 2026-09-18).
Claude Sonnet 5 eliminated entirely by user directive (2026-09-18) after a live
side-by-side vision evaluation showed DeepSeek V4.1-Flash at parity or better.

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

## Core routing table

| Role | Free default (`opencode/*-free`) | Escalation — Go flat-rate (`opencode-go/`) | Escalation — Zen PAYG (`opencode/` or `deepseek/` direct key) | Bench basis for escalation |
|---|---|---|---|---|
| `planner` | nemotron-3-ultra-free | glm-5.3 (alt kimi-k3) | claude-opus-5 (alt gpt-5.6-sol) | AA II: opus-5 51, sol 47 (max); KingBench 91.25 for glm-5.3 |
| `implementer` | nemotron-3-ultra-free | kimi-k3 (alt kimi-k2.7-code — live on Go, Zen upstream broken) | deepseek/deepseek-flash (alt gpt-5.6-sol, gemini-3.8-flash) | AA 40, tool calls + vision live-verified; sol 47 (max) |
| `triager` | nemotron-3-ultra-free | glm-5.3 (alt kimi-k3) | gpt-5.6-luna (alt glm-5.3-flash) | AA 38 @ $0.18/task, 120 t/s |
| `test-writer` | nemotron-3-ultra-free | kimi-k3 (alt kimi-k2.7-code) | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 40 + tool-use probes |
| `debugger` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 40, 1M context |
| `reviewer` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 40 (defect catch) |
| `vision-critic-fast` | — (no free multimodal) | minimax-m3 (native multimodal) | gpt-5.4-mini (alt gemini-3.8-flash) | native image-in (hard gate); AA 41 (gemini-3.8-flash) |
| `vision-critic-final` | — | — | deepseek/deepseek-flash (alt gemini-3.8-flash) | live vision side-by-side 2026-09-18 (parity/better vs sonnet-5 on UI + chart probes); AA 40; first real-loop validating-ui cycle is the acceptance gate |
| `council-member` | nemotron-3-ultra-free + mimo-v2.5-free + muse-spark-1.3-contributor-free + ling-3.0-flash-fin-free | kimi-k3 + glm-5.3 + qwen3.8-max | claude-opus-5 + muse-spark-1.3 + kimi-k3 | per-lens quality first, family diversity soft goal (AA 44/45/45 Go; 51/48/44 Zen); qwen3.8-max live-probe clean 2026-09-18 |
| `skill-author` | nemotron-3-ultra-free | minimax-m3 (alt glm-5.2, qwen3.7-max) | glm-5.3-flash (alt deepseek/deepseek-flash) | IFBench 82.9 — top eligible (AA-run, 2026-09-13); Zen pick by user cost decision 2026-09-18 (8× cheaper than sol) |
| `skill-reviewer` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | claude-opus-5 | AA II 51 — highest reasoning among bound |

## Benchmark evidence principles

**Read benchmarks as a tier filter, not a ranking.** The most decision-relevant numbers are the independent autonomous-loop test (Thinkbench) and instruction-following (IFBench), plus this repo's own authoring rounds. Harness choice alone swings scores 10–20 points.

- AA Intelligence Index (Artificial Analysis, independent; retrieved 2026-09-18, same scale as the 2026-09-13 v4.3 readings — bound-model values unchanged): claude-opus-5 (max) 51, muse-spark-1.3 (max) 48, gpt-5.6-sol 47 (max) / 44 (xhigh), qwen3.8-max 45, glm-5.3 45, kimi-k3 44, gpt-5.6-terra 42 (max, disabled at workspace), glm-5.3-flash 42, gemini-3.8-flash 41, deepseek-v4.1-flash 40 ($0.27/task, 208 t/s), gpt-5.6-luna 38, claude-sonnet-5 38 (eliminated 2026-09-18), deepseek-v4-pro 36 ($0.67/task, 75 t/s), minimax-m3 30, kimi-k2.7-code 26, nemotron-3-ultra 23, ling-3.0-flash-fin 23, mimo-v2.5 22. big-pickle has no AA reading (unbenched).
- Terminal-Bench v4.0 (Laude Institute/Stanford bench, independently run by AA, 2026-09-13): frontier agentic-terminal measurement; its leaders are peak-tier models excluded by the 2026-09-13 cost directive, so it currently ratifies rather than decides Zen rows
- SWE-bench Verified: directionally useful for tier filtering, not model ranking
- Thinkbench autonomous coding loop: GLM 5.2 92% full-pass / 0.976 mean; on existing-code tasks both GLM and M3 score 0.999–1.000 (indistinguishable)
- KingBench 3 (independent, 2026-08-14): GLM-5.3 91.25% — beats Fable 5 (82.5%), Opus 5 (77.5%), Kimi K3 (77.5%). Strongest independent reasoning signal for the GLM-5.3 Go rows; single-benchmark, watch for Thinkbench/MCPMark reproduction
- IFBench (instruction-following, independently run by AA, 2026-09-13): MiniMax-M3 82.9 — top *eligible* model (grok 4.3 at 83.3 is hard-excluded); former leader qwen3.7-max 79.1
- MCPMark Verified: Kimi K2.7 Code 81.1 > Opus 4.8 76.4; K2.7 ~30% more token-efficient. K2.7-code is live on Go (2026-09-18) — the Zen upstream serving returns NOT_FOUND; use the Go tier for K2.7 tool-use evals
- DeepSeek vendor docs (api-docs.deepseek.com, 2026-09-18): `deepseek-flash` is the canonical ID for **DeepSeek-V4.1-Flash**; legacy `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` are retired aliases served at Flash price. Vision ✓ (JPEG/PNG/GIF/WebP, ≤1024 tokens/image), tool calls ✓, JSON ✓, thinking + non-thinking modes, 1M context / 384K max output. Off-peak = half price; peak only 01:00–04:00 and 06:00–10:00 UTC Mon–Fri — for a US Eastern user this means the entire working day is off-peak. V4 Pro continues past 2026-09-14 "until further notice" (revocable — treat any V4 Pro binding as temporary).
- Live vision side-by-side (2026-09-18, this repo, synthetic probes): DS V4.1-Flash vs claude-sonnet-5 on a UI-mock critique (both caught the planted color/hierarchy defects; DS additionally computed WCAG contrast ratios and exact hex values) and a chart-reading test (both exact values + correct average). DS at parity or better. Sonnet eliminated by user directive 2026-09-18.

## Hard exclusions

Never bind, recommend, or escalate to these models in any tier, for any persona or workflow. This is a user directive, dated 2026-08-14.

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `grok-4.5` | Go, Zen | user directive (2026-08-14): grok family excluded from everything |
| `grok-4.6` | Zen | same |
| `grok-build-0.1` | Zen | same |
| `claude-fable-5` | Zen | user cost directive (2026-09-13): peak-tier pricing ($10/$50) — manual invocation only, never bound in any loop |
| `claude-fable-5-1` | Zen | same |
| `gpt-6-astra` | Zen | same |
| `claude-sonnet-5` (and all sonnet IDs) | Zen | user directive (2026-09-18): eliminated entirely in favor of deepseek/deepseek-flash; not bound in any role or alt list |

The grok exclusion supersedes any earlier mention. When a new grok-* ID appears in a catalog fetch, treat it as excluded automatically. The cost directive covers the whole peak pricing class — treat gpt-5.5 / gpt-5.5-pro (and any new $10/$50-tier ID) identically if ever proposed. These models may be invoked manually by the user for experiments; they must never be bound by any role, agent, or loop in this repo.

## Free-tier caveats (read before relying on free defaults)

The free generalist was validated 2026-07-26 by a clean, no-tool head-to-head eval. Since 2026-08-14 `ling-3.0-flash-free` is gone from the catalog, `nemotron-3-ultra-free` now holds the generalist seats — its streaming caveat is the standing reliability risk. For risk-bearing tasks you may still escalate to Go, Zen, or the direct-key tier. Free by default; escalation is opt-in. All four free-family IDs re-verified live 2026-09-18. `big-pickle` is docs-listed free and routes live (enabled 2026-09-18) but is **unbenched** — free-tier redundancy candidate only, stays unbound until evaluated.

**Council seat policy (user directive, 2026-09-13):** family diversity is a **soft goal** — attempted each pass, but per-model quality outranks diversity for its own sake. Free-family readings on AA II v4.3 (2026-09-13): ling ~25 (partial index), nemotron-3-ultra 23, mimo-v2.5 22 (one-point ties break toward diversity); nemotron-3.5-lightning-free scores 14 — confirmed weak, stays unbound. muse-spark-1.3-contributor-free is not separately benched (same-family flagship muse-spark-1.3 scores 48; the free variant runs contributor terms). Seat validations: architecture seat (muse-spark) passed 2026-09-04; product seat (ling-fin) passed 2026-09-13 (3-prompt checklist + cross-family convergence). Free council seats: nemotron×2 (chairman, performance), mimo×2 (security, ux), muse-spark-1.3 (architecture), ling-fin (product) — four families in six seats, largest family share 2/6.

## Provider notes

- **Free tier** ($0): `opencode/*-free` catalog entries (subset of Zen catalog) **that are docs-listed and live-verified**. Default tier — used for every role where a live free model exists. No financial consequence. Catalog-vs-docs mismatches stand: `deepseek-v4-flash-free` and `muse-spark-1.2-contributor-free` are catalog-listed but NOT docs free-listed — excluded from candidacy (the 2026-09-02 failure pattern).
- **Go** ($10/mo flat): Open models only. Config prefix `opencode-go/`. Escalation tier — used when the free default is insufficient or unavailable (vision, peak coding). Limits: $12/5hr, $30/wk, $60/mo. `hy3` and `hy3-preview` are Go flat-rate models. `kimi-k2.7-code` confirmed live on Go — **user directive (2026-09-18): Go-only; the broken Zen upstream is no longer probed or tracked** (Go's "Use balance" Zen fallback covers credit exhaustion). New on Go 2026-09-18: `qwen3.8-max` (AA 45, live-probed clean) and `qwen3.8-flash`.
- **Zen** (pay-as-you-go): Full catalog including proprietary models. Config prefix `opencode/`. Workspace model-access toggles gate individual models — "Model is disabled" means a workspace toggle, not a gateway death (resolved 2026-09-18 by enabling opus-5, sonnet-5, sol, luna, big-pickle). `qwen3.7-*` is Go-only — bind it as a Go escalation, never as a Zen one. `muse-spark-1.3` (paid flagship, AA 48) routes live with no toggle — distinct from the contributor-free variant and its training-terms caveat.
- **Direct-key lane** (user's own DeepSeek API key, approved 2026-09-18): config prefix `deepseek/`. Billed directly by DeepSeek to the user's own balance — check that balance separately from opencode. `deepseek/deepseek-flash` = V4.1-Flash (live-probed: text, vision, tool calls). `deepseek/deepseek-v4-pro` also routes live (AA 36, no vision). Off-peak half price during 01:00–04:00 and 06:00–10:00 UTC Mon–Fri; all other hours (i.e. the full ET working day) off-peak.
- Go can fall back to Zen balance when limits hit ("Use balance" in the console). `AI_FRAMEWORK_FREE_TIER=1` forces the free tier even when a Go/Zen key is present.

## Vision capability strategy

The UI iteration loop requires a model that can read screenshots. Tiered strategy (updated 2026-09-18):

- **`vision-critic-fast`** (iteration passes): defaults to **MiniMax M3** on Go's flat rate (natively multimodal, cheapest option). Zen fast passes: **gpt-5.4-mini** (alt **gemini-3.8-flash**, AA 41). As of 2026-09-13 `gemini-3-flash`, `gemini-3.1-pro`, `gemini-3.5-flash(-lite)`, and `gemini-3.6-flash` are disabled at the gateway; **gemini-3.8-flash is the gemini vision option** — user directive (2026-09-18): `gemini-3.7-flash` is superseded by 3.8-flash and no longer considered (toggle never flipped, no candidate value). **M3 is not yet confirmed for UI-CSS judgment specifically** (its multimodal wins are on SVG-Bench / BrowseComp, not UI critique); evaluate in the `correcting-ui` eval loop before relying on it.
- **`vision-critic-final`** (sign-off): **deepseek/deepseek-flash** via the direct-key lane (user directive 2026-09-18, eliminating claude-sonnet-5 entirely). Basis: live-probed vision (image probe described correctly), vendor-documented image support, and a 2026-09-18 side-by-side against sonnet-5 showing parity-or-better on UI-mock critique (including computed WCAG contrast ratios) and exact chart reading. **Acceptance gate:** the first real-page `validating-ui`/`correcting-ui` cycle validates the seat. Alt: **gemini-3.8-flash** (AA 41, natively multimodal).
- **`deepseek-v4.1-flash` on opencode's own tiers** is China-gated (2026-09-18) — **user directive (2026-09-18): opencode-tier DeepSeek (`opencode-go/deepseek-*`, `opencode/deepseek-*`) is no longer tracked or probed in future passes; DeepSeek escalation lives exclusively on the direct-key lane.**

**No free multimodal model exists**, so vision defaults to the Go escalation (M3).

## Update procedure

0. Run the model-doctor canary first: `python3 scripts/model-liveness-check.py` (bound + documented IDs vs live catalogs and the docs free list). Investigate any drift before the full pass — a red canary means the current bindings are already stale.
1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - Docs pages for pricing/deprecations — **`https://opencode.ai/docs/zen/#endpoints` is authoritative for free-tier availability** (the API catalog can list IDs that are not actually routable; see 2026-09-02 `deepseek-v4-flash-free` failure).
   - Check the workspace **Model access** toggles (docs: "Admins can enable or disable specific models… requests made to a disabled model will return an error") — a "Model is disabled" error is a workspace toggle, not a gateway death. Re-probe after any toggle change.
2. **Candidate gate — liveness (hard gate, before any evaluation or ranking):** catalog membership alone does not make a model a candidate. A model is a candidate **only if** it is BOTH catalog-listed **and** live-verified: for free tier, docs-listed at `https://opencode.ai/docs/zen/#endpoints` **and** actually routes in a live opencode session (minimal probe: select the agent bound to that model and verify clean routing — no error and no opt-in, consent, or region gate); for Go/Zen/direct-key, actually routes in a live session on its tier. Cross-check catalog vs docs; any divergence → Questionable/Uncertain and the ID is excluded from ranking/evaluation. Non-live IDs never enter benchmark comparison or ranking at any score. Access restrictions fail the gate the same way errors do: a model routable only behind an explicit opt-in, consent gate, or region lock (e.g. geo-hosted serving requiring user opt-in) is **not live**. Never opt in on the user's behalf — that would enroll them in the gated serving and its data terms without consent. Exclude the ID, name the gate in Questionable/Uncertain, and move on. Gates lift without notice, so every pass re-probes from scratch: a rehabilitated model re-enters candidacy on its own, with no record to reconcile.
2b. **Go/Zen/direct-key escalation gate:** for any model added to an escalation row, run a live routing probe (select an agent bound to that model on its tier, invoke with a trivial prompt, confirm clean routing with no error and no opt-in/consent gate). Record the probe result in the commit message and PR description. Non-live escalation IDs are excluded from the row.
3. Update the core routing table and bench basis per-role rationale (ranking only over **live candidates** from step 2).
4. If a bound model is deprecated or beaten on price/quality, update the role row and note it in the commit message.
5. Bump the retrieval date at the top of the file.
6. When the Phase 5 eval harness exists: re-run role benchmarks before changing any binding, and record results alongside the change.

## Free-tier fallback + council

- **Toggle:** `AI_FRAMEWORK_FREE_TIER=1` selects free-tier mode. The escalation rows above remain the default-capable path; with the toggle on, every task uses a free model even when Go/Zen keys are present.
- Skills reference **roles**, never these IDs (library convention). The binding of a role to a free model in free-tier mode happens in the harness/project config, not in skill bodies — this file is the single home of the IDs.
- **Council** runs on free models for planning & review (per `docs/FREE-TIER-COUNCIL.md`). The 5 council lenses bind to: security=mimo-v2.5-free, performance=nemotron-3-ultra-free, ux=mimo-v2.5-free, architecture=muse-spark-1.3-contributor-free, product=ling-3.0-flash-fin-free. Chairman binds to nemotron-3-ultra-free. Family diversity (soft goal, user directive 2026-09-13): nemotron×2, mimo×2, muse-spark×1, ling×1 — four families in six seats.
- Council only for **planning & review** (per above). Raw execution stays single-model to conserve free quota.
- Always surface disagreements; never let one model silently override another.
- Free-tier mode coexists with the escalation routing — the toggle selects between them; the escalation rows are not modified by enabling free-tier.
