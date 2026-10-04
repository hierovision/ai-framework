# Model Routing

**2026-10-03 pass (Go-first):** every role defaults to a live **Go flat-rate**
model (`opencode-go/`). Free use is an explicit opt-in — the environment
toggle `AI_FRAMEWORK_FREE_TIER=1` or a per-session model switch — and a last
resort, never a default. **`kimi-k3` is hard-excluded (user cost directive
2026-10-03: console-disabled, too expensive) and `gpt-6-luna` is hard-excluded
(3/3 CI canary failures on the 2026-09-29 eval-lane pass, plus
`/responses`-only), alongside `glm-5.3` / `glm-5.2` (cost, 2026-10-01).
Exclusions sit above all scores.** The user upgraded to **Go Plus ($40/mo)** —
same models and token prices, higher per-model allowances; spend is
re-evaluated at the next monthly review (2026-11-01, ADR-0013). The 2026-10-03
AA live pull refreshed the seat numbers (glm-5.3-flash 42, deepseek-v4.1-flash
39, MiMo-V2.6-Pro 46 — the new score leader).

Retrieval: catalogs, docs, and benchmark rows **retrieved and live-verified
2026-10-03** (AA leaderboard, `https://opencode.ai/zen/go/v1/models`,
`https://opencode.ai/zen/v1/models`). Liveness probe contract: `POST
https://opencode.ai/zen/go/v1/chat/completions` (`/zen/v1/*` for Zen),
**bare catalog IDs** (no lane prefix in the gateway request; config bindings
keep their `opencode-go/` prefix), `Authorization: Bearer $OPENCODE_API_KEY`,
`Content-Type: application/json`, the **required `x-opencode-session`
header**, body `{"model": M, "messages":[{"role":"user","content":"Reply with
exactly: OK"}], "max_tokens":16}`, **20s cap**. A candidate that cannot answer
within 20s is "not live for that check" — the timeout is never extended to
rescue it. The old `https://opencode.ai/api/*` endpoints 404 and are not used.

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

## Contents

Core routing table — Benchmark evidence principles — Hard exclusions —
Free opt-in — Provider notes — Vision capability strategy —
Update procedure — Council

## Core routing table

| Role | Default — Go flat-rate (`opencode-go/`) | Free opt-in (`AI_FRAMEWORK_FREE_TIER=1`) | Escalation — Zen PAYG (`opencode/` or `deepseek/` direct key) | Bench basis for default |
|---|---|---|---|---|
| `planner` / `architect` | glm-5.3-flash (alt kimi-k2.7-code) | nemotron-3-ultra-free | claude-opus-5-5 (alt gpt-5.6-sol) | KingBench 3 91.25 (independent, 2026-08-14) + AA 42 (2026-10-03); opus-5-5 58 (max) is the Zen opt-in leader |
| `implementer` | deepseek-v4.1-flash (alt kimi-k2.7-code — live on Go) | nemotron-3-ultra-free | deepseek/deepseek-flash (alt gpt-5.6-sol, gemini-3.8-flash) | AA 39 (2026-10-03 live pull), 209 t/s, tool calls + vision live-verified; repo-proven CI eval lane (3/3 probes) |
| `triager` / `curator` | glm-5.3-flash (alt kimi-k2.7-code) | nemotron-3-ultra-free | gpt-5.6-luna (alt glm-5.3-flash) | KingBench 91.25 + AA 42; generalist quality + reliability |
| `test-writer` | deepseek-v4.1-flash (alt kimi-k2.7-code) | nemotron-3-ultra-free | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 39 + tool-use probes; shared lane with `implementer` |
| `debugger` | mimo-v2.6-pro (alt glm-5.3-flash) | nemotron-3-ultra-free | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 46 = 2026-10-03 score leader ($0.13/task), live 1.83s; alt covers cost/context (glm-5.3-flash 1M context) |
| `reviewer` | mimo-v2.6-pro (alt glm-5.3-flash) | nemotron-3-ultra-free | deepseek/deepseek-flash (alt gpt-5.6-sol) | AA 46 (defect-catch, 2026-10-03 pull); score leader per the 2026-10-03 scores-over-diversity directive |
| `skill-reviewer` | mimo-v2.6-pro (alt glm-5.3-flash) | nemotron-3-ultra-free | claude-opus-5-5 | AA 46 (2026-10-03); highest reasoning among bound on the Zen opt-in |
| `skill-author` | minimax-m3 (alt qwen3.7-max) | nemotron-3-ultra-free | glm-5.3-flash (alt deepseek/deepseek-flash) | IFBench 82.9 — top eligible (AA-run, 2026-09-13) |
| `vision-critic-fast` | minimax-m3 (native multimodal) | — (no free multimodal) | gpt-5.4-mini (alt gemini-3.8-flash) | native image-in (hard gate); M3 native multimodal on the flat rate |
| `vision-critic-final` | deepseek-v4.1-flash (same model as the validated direct-key seat, on Go) | — | deepseek/deepseek-flash (alt gemini-3.8-flash) | live vision side-by-side 2026-09-18 (parity/better vs sonnet-5); first real-loop validating-ui cycle is the acceptance gate |
| `council-member` | qwen3.8-flash + gpt-5.6-luna + glm-5.3-flash + deepseek-v4.1-flash + minimax-m3 + mimo-v2.6-flash | — (free cannot serve a nested subagent; see Council) | claude-opus-5-5 + muse-spark-1.3 + gpt-5.6-sol | six families in six seats; per-seat basis in `agents/council.md`; family diversity is the objectivity mechanism, scores outrank it for non-council roles |

## Benchmark evidence principles

**Read benchmarks as a tier filter, not a ranking.** The most decision-relevant numbers are the independent autonomous-loop test (Thinkbench) and instruction-following (IFBench), plus this repo's own authoring rounds. Harness choice alone swings scores 10–20 points. Gaps ≤2–3 AA points are noise; **scores outrank family diversity** (user directive 2026-10-03) — diversity is a soft tie-breaker, except that council seats deliberately span families (Choice 10).

- AA Intelligence Index (Artificial Analysis, independent; **live pull 2026-10-03** — reasoning-config-specific rows, a tier filter, not a ranking): MiMo-V2.6-Pro 46, glm-5.3 (max) 45 (excluded — cost), qwen3.8-max 45 (cost), kimi-k3 44 (excluded — cost), glm-5.3-flash 42, gemini-3.8-flash 41, deepseek-v4.1-flash 39, gpt-5.6-luna 38, mimo-v2.6-flash 38, gpt-5.6-terra 38, deepseek-v4-pro 36, minimax-m3 29, kimi-k2.7-code 26, hy3 25, nemotron-3-ultra 23 (the free-tier baseline this policy removes as a default).
- **Liveness gate (user directive 2026-10-03):** a candidate must answer the trivial `Reply with exactly: OK` probe within 20s on its tier or it is "not live for that check"; never extend the timeout to rescue it (a 90s cap on 2026-10-03 produced a false "dead" reading for a model that answered in 2.3s on a healthy route). A chat-completions `ModelProtocolUnsupported` 400 is a protocol statement, not a death: GPT-5.6 Luna is served via `/zen/go/v1/responses` — the opencode runtime path is the verification vehicle (OQ9).
- Terminal-Bench v4.0 (Laude Institute/Stanford bench, independently run by AA, 2026-09-13): frontier agentic-terminal measurement; its leaders are peak-tier models excluded by the 2026-09-13 cost directive, so it currently ratifies rather than decides Zen rows.
- SWE-bench Verified: directionally useful for tier filtering, not model ranking.
- Thinkbench autonomous coding loop: GLM 5.2 92% full-pass / 0.976 mean; on existing-code tasks both GLM and M3 score 0.999–1.000 (indistinguishable).
- KingBench 3 (independent, 2026-08-14): GLM-5.3 91.25% — beats Fable 5 (82.5%), Opus 5 (77.5%), Kimi K3 (77.5%). Strongest independent reasoning signal for the GLM-5.3-Flash rows; single-benchmark, watch for Thinkbench/MCPMark reproduction.
- IFBench (instruction-following, independently run by AA, 2026-09-13): MiniMax-M3 82.9 — top *eligible* model (grok 4.3 at 83.3 is hard-excluded); former leader qwen3.7-max 79.1.
- MCPMark Verified: Kimi K2.7 Code 81.1 > Opus 4.8 76.4; K2.7 ~30% more token-efficient. K2.7-code is live on Go — the code-heavy implementer escalation.
- DeepSeek vendor docs (api-docs.deepseek.com, 2026-09-18): `deepseek-flash` is the canonical ID for **DeepSeek-V4.1-Flash**; legacy `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` are retired aliases served at Flash price. Vision ✓ (JPEG/PNG/GIF/WebP, ≤1024 tokens/image), tool calls ✓, JSON ✓, thinking + non-thinking modes, 1M context / 384K max output. Off-peak = half price; peak only 01:00–04:00 and 06:00–10:00 UTC Mon–Fri.
- Live vision side-by-side (2026-09-18, this repo, synthetic probes): DS V4.1-Flash vs claude-sonnet-5 on a UI-mock critique (both caught the planted color/hierarchy defects; DS additionally computed WCAG contrast ratios and exact hex values) and a chart-reading test (both exact values + correct average). Sonnet eliminated by user directive 2026-09-18.

## Hard exclusions

Never bind, recommend, or escalate to these models in any tier, for any
persona or workflow. **Exclusions sit above all scores:** a live probe or a
top benchmark result never overrides one — `kimi-k3` probes live (1.91s) and
scores AA 44, and it stays excluded.

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `grok-4.5` | Go, Zen | user directive (2026-08-14): grok family excluded from everything |
| `grok-4.6` | Zen | same |
| `grok-build-0.1` | Zen | same |
| `claude-fable-5` | Zen | user cost directive (2026-09-13): peak-tier pricing ($10/$50) — manual invocation only, never bound in any loop |
| `claude-fable-5-1` | Zen | same |
| `gpt-6-astra` | Zen | same |
| `claude-sonnet-5` (and all sonnet IDs) | Zen | user directive (2026-09-18): eliminated entirely in favor of deepseek/deepseek-flash; not bound in any role or alt list |
| `glm-5.3` | Go, Zen | user cost directive (2026-10-01): near-identical to GLM-5.3-Flash at ~9× cost ($1.40/$4.40 vs $0.15/$0.50 per 1M); never bound, any tier |
| `glm-5.2` | Go, Zen | same directive (2026-10-01) — same $1.40/$4.40 class |
| `kimi-k3` | Go, Zen | user cost directive (2026-10-03): console-disabled as too expensive (AA 44, $2.00/task); never bound, any tier |
| `gpt-6-luna` | Go, Zen | rejected on the 2026-09-29 eval-lane pass (3/3 CI canary failures) plus `/responses`-only protocol; excluded 2026-10-03 |

The grok exclusion supersedes any earlier mention. When a new grok-* ID appears
in a catalog fetch, treat it as excluded automatically. The cost directive
covers the whole peak pricing class — treat `gpt-5.5` / `gpt-5.5-pro` (and any
new $10/$50-tier ID) identically if ever proposed; the 2026-10-01 GLM directive
covers glm-5.3 / glm-5.2 and the 2026-10-03 directives cover kimi-k3 and
gpt-6-luna. These models may be invoked manually by the user for experiments;
they must never be bound by any role, agent, or loop in this repo.

## Free opt-in

Free models are **not a default**. The only two ways to run free are:

1. `AI_FRAMEWORK_FREE_TIER=1` — the explicit opt-in toggle (also the eval
   runner's free-tier mode); or
2. a per-session model switch to a `*-free` catalog ID.

The free generalist was validated 2026-07-26 by a clean, no-tool head-to-head
eval. `nemotron-3-ultra-free` now holds the generalist opt-in seat — its
streaming caveat is the standing reliability risk (AA 23 is the baseline this
policy removes as a default). All four free-family IDs re-verified live
2026-09-18. `big-pickle` is docs-listed free and routes live but is
**unbenched** — free-tier redundancy candidate only, stays unbound until
evaluated.

**Nested-subagent constraint:** the free tier cannot serve a nested Task
subagent (`OpenCode's free tier can only be used from within OpenCode`), so
free use never applies to the council or to any in-session dispatch whose
target is free-bound; a framework persona is Go-bound and does not hit this.

**Council seat policy (Go flat-rate, updated 2026-10-03):** one family per
seat — qwen3.8-flash (chairman, Qwen), gpt-5.6-luna (performance, OpenAI),
glm-5.3-flash (architecture, Zhipu), deepseek-v4.1-flash (security, DeepSeek),
minimax-m3 (ux, MiniMax), mimo-v2.6-flash (product, Xiaomi). Family diversity
is the seat-design mechanism; for non-council roles scores outrank diversity
(2026-10-03 directive). The changed seats (chairman, performance) were
seat-validated 2026-10-04 — 3/3 prompts each through the opencode path — as
were the `mimo-v2.6-pro` quality seats (context window 1M confirmed).

## Provider notes

- **Go / Go Plus** (flat-rate): the **default tier** for every role. Open models only. Config prefix `opencode-go/`. **Go $10/mo; Go Plus $40/mo** (user upgraded 2026-10-01) — same models and token prices, higher per-model usage. Each model has its own monthly dollar cap: 5-hour = 20% of it, weekly = 50%, monthly = 100% (opencode.ai/docs/go, fetched 2026-10-01). Go falls back to Zen balance ("Use balance") after limits. Catalog includes glm-5.3-flash, qwen3.8-flash, qwen3.8-max, deepseek-v4.1-flash, minimax-m3, mimo-v2.6-flash/pro, gpt-5.6-luna, kimi-k2.7-code, longcat-2.0 — with glm-5.3/glm-5.2, kimi-k3, and gpt-6-luna excluded by policy (see Hard exclusions; catalog presence never overrides).
- **Free tier** (opt-in only): `opencode/*-free` catalog entries that are docs-listed and live-verified. Selected only via `AI_FRAMEWORK_FREE_TIER=1` or an explicit per-session model switch — never a bound default. Catalog-vs-docs mismatches stand: `deepseek-v4-flash-free` and `muse-spark-1.2-contributor-free` are catalog-listed but NOT docs free-listed — excluded from candidacy (the 2026-09-02 failure pattern).
- **Zen** (pay-as-you-go): Full catalog including proprietary models. Config prefix `opencode/`. Workspace model-access toggles gate individual models — "Model is disabled" means a workspace toggle, not a gateway death (resolved 2026-09-18). `qwen3.7-*` is Go-only — bind it as a Go escalation, never as a Zen one. `muse-spark-1.3` (paid flagship, AA 48) routes live with no toggle.
- **CI eval lane (user directive 2026-09-29)**: behavioral evals in CI run on the **Go flat-rate** lane — **`opencode-go/deepseek-v4.1-flash`**, authenticated by the repo's `OPENCODE_API_KEY`. Chosen on measured evidence (3/3 probes pass, 34 s light / 168 s heavy; AA 39, $0.27/task; `mimo-v2.6-flash` measured 2× slower and was rejected on wall time). Depth policy: **weekly = default per skill (26 evals); monthly = full suite (111)**, six measured-weight shards; a full sharded run measured 59 min wall and ~$1.8 (allowance-equivalent). **Requires workspace region = Global** (set 2026-09-29).
  **Nested-subagent caveat (found 2026-09-29, superseded for this repo 2026-10-03):** a skill that spawns a free-tier-bound subagent dies in CI (the free tier rejects calls made outside the OpenCode client). `scripts/ci-lane-overrides.py` still emits `OPENCODE_CONFIG_CONTENT` for that case — now an empty agent map for this repo (every persona is Go-bound) and a working guard for consumer repos whose wrappers are free-bound. **Sandbox caveat (measured 2026-09-29):** the CI override adds `permission.external_directory {"/tmp/**": "allow", "~/.config/opencode/**": "allow"}` (ephemeral runner; unmatched paths keep the default so the checkout stays out of reach).
- **Direct-key lane** (user's own DeepSeek API key, approved 2026-09-18): config prefix `deepseek/`. Billed directly by DeepSeek to the user's own balance — check that balance separately from opencode. `deepseek/deepseek-flash` = V4.1-Flash (live-probed: text, vision, tool calls); `deepseek/deepseek-v4-pro` also routes live (AA 36, no vision). Off-peak half price during 01:00–04:00 and 06:00–10:00 UTC Mon–Fri. This lane is an explicit opt-in escalation only.
- Go can fall back to Zen balance when limits hit ("Use balance" in the console). `AI_FRAMEWORK_FREE_TIER=1` forces the free tier even when a Go/Zen key is present — the explicit free opt-in.

## Vision capability strategy

The UI iteration loop requires a model that can read screenshots. Tiered strategy (updated 2026-10-03):

- **`vision-critic-fast`** (iteration passes): defaults to **MiniMax M3** on Go's flat rate (natively multimodal). Zen fast passes: **gpt-5.4-mini** (alt **gemini-3.8-flash**, AA 41). **M3 is not yet confirmed for UI-CSS judgment specifically** (its multimodal wins are on SVG-Bench / BrowseComp, not UI critique); evaluate in the `correcting-ui` eval loop before relying on it.
- **`vision-critic-final`** (sign-off): defaults to **`opencode-go/deepseek-v4.1-flash`** — the same model as the validated direct-key `deepseek/deepseek-flash` seat (user directive 2026-09-18), now on the Go lane (2026-10-03). Basis: live-probed vision, vendor-documented image support, and a 2026-09-18 side-by-side against sonnet-5 showing parity-or-better on UI-mock critique and exact chart reading. **Acceptance gate:** the first real-page `validating-ui`/`correcting-ui` cycle validates the seat. Alt: **gemini-3.8-flash** (AA 41, natively multimodal); the direct-key lane remains the explicit fallback.

**No free multimodal model exists**, so vision binds the Go lane (M3 fast / DS final).

## Update procedure

0. Run the model-doctor canary first: `python3 scripts/model-liveness-check.py` (bound + documented IDs vs live catalogs, the docs free list, and the Go-first policy assertions — no `-free` bindings, no hard-excluded IDs, table/live consistency). Investigate any drift before the full pass — a red canary means the current bindings are already stale. Add `--probe` with `OPENCODE_API_KEY` set for the live trivial-prompt probe (20s cap, bare catalog IDs, `x-opencode-session` required; `/responses`-only IDs report protocol-unsupported, not death).
1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - Docs pages for pricing/deprecations — **`https://opencode.ai/docs/zen/#endpoints` is authoritative for free-tier availability** (the API catalog can list IDs that are not actually routable; see 2026-09-02 `deepseek-v4-flash-free` failure).
   - Check the workspace **Model access** toggles — a "Model is disabled" error is a workspace toggle, not a gateway death. Re-probe after any toggle change.
2. **Candidate gate — liveness (hard gate, before any evaluation or ranking):** catalog membership alone does not make a model a candidate. A model is a candidate **only if** it is BOTH catalog-listed **and** live-verified on its tier with the probe contract above (20s cap; never extended). Access restrictions fail the gate the same way errors do: a model routable only behind an explicit opt-in, consent gate, or region lock is **not live**. Never opt in on the user's behalf. Gates lift without notice, so every pass re-probes from scratch: a rehabilitated model re-enters candidacy on its own.
3. Update the core routing table and bench basis per-role rationale (ranking only over **live candidates** from step 2). The default column stays Go; a free model may be listed only in the opt-in column.
4. If a bound model is deprecated or beaten on price/quality, update the role row and note it in the commit message.
5. Bump the retrieval date at the top of the file.
6. Re-run the 3-prompt seat validation for any changed council/quality seat before recording it as settled; a failed seat re-opens its OQ and reverts to the recorded alt.

## Council

- **Council** runs on the Go lane for planning & review (per `agents/council.md`). The six seats bind one family each: qwen3.8-flash (Qwen), gpt-5.6-luna (OpenAI), glm-5.3-flash (Zhipu), deepseek-v4.1-flash (DeepSeek), minimax-m3 (MiniMax), mimo-v2.6-flash (Xiaomi). Reason: the free tier cannot serve a nested Task subagent; the 2026-09-13 free-council seats are retired. A Zen frontier council (claude-opus-5-5 + muse-spark-1.3 + gpt-5.6-sol) stays the explicit opt-in.
- Council only for **planning & review**. Raw execution stays single-model.
- Always surface disagreements; never let one model silently override another.
- The free opt-in (`AI_FRAMEWORK_FREE_TIER=1`) coexists with the council — the toggle selects the main session's tier; the council stays Go-bound or is recorded as an explicit skip.
