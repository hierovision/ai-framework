# Model Routing

Catalogs, docs free list, and liveness probes: retrieved and live-verified 2026-09-13.

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

## Core routing table

| Role | Free default (`opencode/*-free`) | Escalation — Go flat-rate (`opencode-go/`) | Escalation — Zen PAYG (`opencode/`) | Bench basis for escalation |
|---|---|---|---|---|
| `planner` | nemotron-3-ultra-free | glm-5.3 (alt kimi-k3) | claude-opus-5 | AA II v4.3: opus-5 51, glm-5.3 45 (top open); KingBench 91.25 |
| `implementer` | nemotron-3-ultra-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | MCPMark 81.1 (K2.7 alt); AA 44 |
| `triager` | nemotron-3-ultra-free | glm-5.3 (alt kimi-k3) | gpt-5.6-luna (alt glm-5.3-flash) | AA v4.3: luna 38 at $0.18/task + 120 t/s; glm-5.3-flash 42 |
| `test-writer` | nemotron-3-ultra-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | MCPMark + SWE-bench Verified |
| `debugger` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | claude-sonnet-5 | Thinkbench + SWE-bench Verified |
| `reviewer` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | claude-sonnet-5 | SWE-bench Verified (defect catch) |
| `vision-critic-fast` | — (no free multimodal) | minimax-m3 (native multimodal) | gpt-5.4-mini (alt gemini-3.8-flash) | native image-in (hard gate); AA 41 (gemini-3.8-flash) |
| `vision-critic-final` | — | — | claude-sonnet-5 (alt claude-opus-5) | sign-off vision quality at sonnet pricing; AA 38 / 51 |
| `council-member` | nemotron-3-ultra-free + mimo-v2.5-free + muse-spark-1.3-contributor-free + ling-3.0-flash-fin-free | kimi-k3 + glm-5.3 + deepseek-v4.1-flash | claude-opus-5 + gemini-3.8-flash + kimi-k3 | per-lens quality first, family diversity soft goal (AA 44/45/40; 51/41/44) |
| `skill-author` | nemotron-3-ultra-free | minimax-m3 (alt glm-5.2, qwen3.7-max) | claude-sonnet-5 | IFBench 82.9 — top eligible (AA-run, 2026-09-13) |
| `skill-reviewer` | nemotron-3-ultra-free | glm-5.3 (alt glm-5.2) | claude-opus-5 | AA II v4.3 51 — highest reasoning among bound |

## Benchmark evidence principles

**Read benchmarks as a tier filter, not a ranking.** The most decision-relevant numbers are the independent autonomous-loop test (Thinkbench) and instruction-following (IFBench), plus this repo's own authoring rounds. Harness choice alone swings scores 10–20 points.

- AA Intelligence Index v4.3 (Artificial Analysis, independent; rescaled from v4.2 — old-scale scores such as "AA 60" are not comparable). Readings 2026-09-13 for bound models: claude-opus-5 51, glm-5.3 45 (top open weights), kimi-k3 44, glm-5.3-flash 42, gemini-3.8-flash 41, deepseek-v4.1-flash 40, gpt-5.6-luna 38, claude-sonnet-5 38, glm-5.2 34, minimax-m3 30, kimi-k2.7-code 26
- Terminal-Bench v4.0 (Laude Institute/Stanford bench, independently run by AA, 2026-09-13): frontier agentic-terminal measurement; its leaders are peak-tier models excluded by the 2026-09-13 cost directive, so it currently ratifies rather than decides Zen rows
- SWE-bench Verified: directionally useful for tier filtering, not model ranking
- Thinkbench autonomous coding loop: GLM 5.2 92% full-pass / 0.976 mean; on existing-code tasks both GLM and M3 score 0.999–1.000 (indistinguishable)
- KingBench 3 (independent, 2026-08-14): GLM-5.3 91.25% — beats Fable 5 (82.5%), Opus 5 (77.5%), Kimi K3 (77.5%). Strongest independent reasoning signal for the GLM-5.3 Go rows; single-benchmark, watch for Thinkbench/MCPMark reproduction
- IFBench (instruction-following, independently run by AA, 2026-09-13): MiniMax-M3 82.9 — top *eligible* model (grok 4.3 at 83.3 is hard-excluded); former leader qwen3.7-max 79.1
- MCPMark Verified: Kimi K2.7 Code 81.1 > Opus 4.8 76.4; K2.7 ~30% more token-efficient
- Multimodal: MiniMax M3 is natively multimodal (image/video in) on Go's flat rate — the only cheap open model that reads a screenshot without a bolt-on. DeepSeek V4.1-Flash is vision-capable per DeepSeek's own docs (2026-09-13: images alongside text, JPEG/PNG/GIF/WebP, ≤1024 tokens/image); its vision *judgment* is unbenched — bench before it takes any vision seat

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

The grok exclusion supersedes any earlier mention. When a new grok-* ID appears in a catalog fetch, treat it as excluded automatically. The cost directive covers the whole peak pricing class — treat gpt-5.5 / gpt-5.5-pro (and any new $10/$50-tier ID) identically if ever proposed. These models may be invoked manually by the user for experiments; they must never be bound by any role, agent, or loop in this repo.

## Free-tier caveats (read before relying on free defaults)

The free generalist was validated 2026-07-26 by a clean, no-tool head-to-head eval. Since 2026-08-14 `ling-3.0-flash-free` is gone from the catalog, `nemotron-3-ultra-free` now holds the generalist seats — its streaming caveat is the standing reliability risk. For risk-bearing tasks you may still escalate to Go or Zen tier. Free by default; escalation is opt-in.

**Council seat policy (user directive, 2026-09-13):** family diversity is a **soft goal** — attempted each pass, but per-model quality outranks diversity for its own sake. Free-family readings on AA II v4.3 (2026-09-13): ling ~25 (partial index), nemotron-3-ultra 23, mimo-v2.5 22 (one-point ties break toward diversity); nemotron-3.5-lightning-free scores 14 — confirmed weak, stays unbound. muse-spark-1.3-contributor-free is not separately benched (same-family flagship muse-spark-1.3 scores 48; the free variant runs contributor terms). Seat validations: architecture seat (muse-spark) passed 2026-09-04; product seat (ling-fin) passed 2026-09-13 (3-prompt checklist + cross-family convergence). Free council seats: nemotron×2 (chairman, performance), mimo×2 (security, ux), muse-spark-1.3 (architecture), ling-fin (product) — four families in six seats, largest family share 2/6.

## Provider notes

- **Free tier** ($0): `opencode/*-free` catalog entries (subset of Zen catalog) **that are docs-listed and live-verified**. Default tier — used for every role where a live free model exists. No financial consequence.
- **Go** ($10/mo flat): Open models only. Config prefix `opencode-go/`. Escalation tier — used when the free default is insufficient or unavailable (vision, peak coding). Limits: $12/5hr, $30/wk, $60/mo. `hy3` and `hy3-preview` are now Go flat-rate models. New on Go 2026-09-13: `deepseek-v4.1-flash` (AA II 40, live-verified). DeepSeek's own docs (2026-09-13): the legacy `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` names are retired upstream aliases served by V4.1-Flash at Flash price — prefer the canonical `deepseek-v4.1-flash` ID. DeepSeek continues to offer V4 Pro on its own API, but here it is not live: opencode serves it only behind a China-hosted explicit opt-in.
- **Zen** (pay-as-you-go): Full catalog including proprietary models. Config prefix `opencode/`. Escalation tier — frontier opt-in (claude-opus-5; the peak pricing class — astra, fable, gpt-5.5-class — is excluded by the 2026-09-13 cost directive, manual invocation only). `qwen3.7-*` is Go-only — bind it as a Go escalation, never as a Zen one.
- Go can fall back to Zen balance when limits hit ("Use balance" in the console). `AI_FRAMEWORK_FREE_TIER=1` forces the free tier even when a Go/Zen key is present.

## Vision capability strategy

The UI iteration loop requires a model that can read screenshots. Tiered strategy (locked decision):

- **`vision-critic-fast`** (iteration passes): defaults to **MiniMax M3** on Go's flat rate (natively multimodal, cheapest option). Zen fast passes: **gpt-5.4-mini** (alt **gemini-3.8-flash**, AA 41). As of 2026-09-13 `gemini-3-flash`, `gemini-3.1-pro`, `gemini-3.5-flash(-lite)`, and `gemini-3.6-flash` are all disabled at the gateway; `gemini-3.7-flash` and `gemini-3.8-flash` are the live gemini vision options. **M3 is not yet confirmed for UI-CSS judgment specifically** (its multimodal wins are on SVG-Bench / BrowseComp, not UI critique); evaluate in the `correcting-ui` eval loop before relying on it.
- **`vision-critic-final`** (sign-off): **claude-sonnet-5** (alt **claude-opus-5**) — strongest live vision quality below the excluded peak tier (user cost directive, 2026-09-13).
- **`deepseek-v4.1-flash`** (Go flat rate) is the named bench-first successor for the fast seat: vision-capable per DeepSeek's docs (2026-09-13; JPEG/PNG/GIF/WebP, ≤1024 tokens/image) and AA II 40, but unbenched on UI vision judgment — bench it in the `correcting-ui` loop before it takes the seat. The `deepseek-v4-flash-vision-exp` alias it replaces is retired upstream.

**No free multimodal model exists**, so vision defaults to the Go escalation (M3).

## Update procedure

0. Run the model-doctor canary first: `python3 scripts/model-liveness-check.py` (bound + documented IDs vs live catalogs and the docs free list). Investigate any drift before the full pass — a red canary means the current bindings are already stale.

1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - Docs pages for pricing/deprecations — **`https://opencode.ai/docs/zen/#endpoints` is authoritative for free-tier availability** (the API catalog can list IDs that are not actually routable; see 2026-09-02 `deepseek-v4-flash-free` failure).
2. **Candidate gate — liveness (hard gate, before any evaluation or ranking):** catalog membership alone does not make a model a candidate. A model is a candidate **only if** it is BOTH catalog-listed **and** live-verified: for free tier, docs-listed at `https://opencode.ai/docs/zen/#endpoints` **and** actually routes in a live opencode session (minimal probe: select the agent bound to that model and verify clean routing — no error and no opt-in, consent, or region gate); for Go/Zen, actually routes in a live session on its tier. Cross-check catalog vs docs; any divergence → Questionable/Uncertain and the ID is excluded from ranking/evaluation. Non-live IDs never enter benchmark comparison or ranking at any score. Access restrictions fail the gate the same way errors do: a model routable only behind an explicit opt-in, consent gate, or region lock (e.g. geo-hosted serving requiring user opt-in) is **not live**. Never opt in on the user's behalf — that would enroll them in the gated serving and its data terms without consent. Exclude the ID, name the gate in Questionable/Uncertain, and move on. Gates lift without notice, so every pass re-probes from scratch: a rehabilitated model re-enters candidacy on its own, with no record to reconcile.
2b. **Go/Zen escalation gate:** for any model added to a Go or Zen escalation row, run a live routing probe (select an agent bound to that model on its tier, invoke with a trivial prompt, confirm clean routing with no error and no opt-in/consent gate). Record the probe result in the commit message and PR description. Non-live escalation IDs are excluded from the row.
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