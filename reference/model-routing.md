# Model Routing

**2026-10-25 pass (Go-first):** every role defaults to a live **Go flat-rate**
model (`opencode-go/`). Free use is an explicit opt-in — the environment
toggle `AI_FRAMEWORK_FREE_TIER=1` or a per-session model switch — and a last
resort, never a default. Exclusions unchanged: **`kimi-k3`** (user cost
directive 2026-10-03: console-disabled, too expensive), **`gpt-6-luna`**
(3/3 CI canary failures 2026-09-29, `/responses`-only), **`glm-5.3` /
`glm-5.2`** (cost, 2026-10-01), the grok family, all sonnet IDs, and the peak
$10/$50 class. **Exclusions sit above all scores.** `kimi-k3.1-pro` is a
**distinct ID** from `kimi-k3` — live on Go, cheaper per token ($2/$10 vs
$3/$15), and not covered by the 2026-10-03 directive. The 2026-10-25 live
pull: Kimi K3.1 Pro (AA 55.1, TB4 67.2%) and Gemini 4 Argon (AA 52.6,
TB4 57.1%) are the new Go leaders; MiMo-V2.6-Pro 46.3; DeepSeek V4.1 Flash
1017 45.1 at $0.26/task; MiniMax M3.1 Flash 42.7; GLM-5.3-Flash 41.8;
MiniMax M3 29.2 (IFBench leader). Go Plus ($40/mo) remains the funding
basis; spend is reviewed 2026-11-01 (RM-040, ADR-0013).

Retrieval: catalogs, docs, runtime probes, and benchmark rows **retrieved
2026-10-25** (AA leaderboard + per-model AA evaluation pages;
`https://opencode.ai/zen/go/v1/models`; `https://opencode.ai/zen/v1/models`;
`https://opencode.ai/docs/zen/#endpoints`; `https://opencode.ai/docs/go/`;
`opencode models`; DeepSeek API docs). Liveness contract: the binding
vehicle is a **fresh `opencode run -m <provider>/<model> "Reply with exactly:
OK"`** (never `--continue`), 25s wall cap = ~4s CLI/server startup + the 20s
contract cap. A model must be in **opencode's runtime model registry**
(`opencode models`) as well as its tier catalog; a catalog-listed ID absent
from the registry fails with `ProviderModelNotFoundError` and is not
bindable. The chat-completions probe (`POST /zen/go/v1/chat/completions`,
`/zen/v1/*` for Zen, bare catalog IDs, required `x-opencode-session`, 20s
cap) remains the API-key path — the 2026-10-25 pass could not use it because
the stored `opencode` / `opencode-go` keys returned `api_key_expired`. A
candidate that cannot answer within the cap is "not live for that check" —
the timeout is never extended to rescue it. Access restrictions (opt-in,
consent, region) fail the gate the same way errors do. The old
`https://opencode.ai/api/*` endpoints 404 and are not used.

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

## Contents

Core routing table — Skill coverage — Benchmark evidence principles — Hard
exclusions — Free opt-in — Provider notes — Vision capability strategy —
Update procedure — Council

## Core routing table

| Role | Default — Go flat-rate (`opencode-go/`) | Free opt-in (`AI_FRAMEWORK_FREE_TIER=1`) | Escalation — Zen PAYG (`opencode/` or `deepseek/` direct key) | Bench basis for default |
|---|---|---|---|---|
| `planner` / `architect` | kimi-k3.1-pro (alt gemini-4-argon) | deepseek-v4.1-flash-free | gemini-4-argon (alt deepseek/deepseek-flash) | AA 55.1 + TB4 67.2% (AA independent, 2026-10-25); Gemini 4 Argon 52.6 / TB4 57.1% |
| `implementer` | deepseek-v4.1-flash (alt kimi-k3.1-pro — live on Go) | deepseek-v4.1-flash-free | deepseek/deepseek-flash (alt gemini-4-argon) | AA 45.1 (1017), $0.26/task, TB4 33.8%, CI lane 3/3; Kimi leads TB4 67.2% but $2.11/task and $60 Go Plus cap vs DeepSeek's $160 |
| `triager` / `curator` | kimi-k3.1-pro (alt glm-5.3-flash) | deepseek-v4.1-flash-free | gemini-4-argon (alt deepseek/deepseek-flash) | AA 55.1 generalist — the live Go leader |
| `test-writer` | deepseek-v4.1-flash (alt kimi-k3.1-pro) | deepseek-v4.1-flash-free | deepseek/deepseek-flash (alt gemini-4-argon) | AA 45.1 + FrontierCode 43.7%; shared lane with `implementer` |
| `debugger` | kimi-k3.1-pro (alt mimo-v2.6-pro) | deepseek-v4.1-flash-free | deepseek/deepseek-flash (alt gemini-4-argon) | TB4 67.2% (agent-loop leader) vs MiMo 34.8%; MiMo alt at $0.13/task |
| `reviewer` | mimo-v2.6-pro (alt kimi-k3.1-pro) | deepseek-v4.1-flash-free | gemini-4-argon (alt deepseek/deepseek-flash) | FrontierCode 45.4% (Kimi 47.1% within 2-pt noise) at $0.13/task |
| `skill-reviewer` | kimi-k3.1-pro (alt mimo-v2.6-pro) | deepseek-v4.1-flash-free | gemini-4-argon (alt deepseek/deepseek-flash) | AA 55.1; review reasoning |
| `skill-author` | minimax-m3 (alt minimax-m3.1-flash) | deepseek-v4.1-flash-free | minimax-m3 (alt deepseek/deepseek-flash) | IFBench 82.9% — top eligible (AA independent); M3.1 Flash AA 42.7 but IFBench unmeasured |
| `vision-critic-fast` | minimax-m3 (alt gemini-4-argon) | nemotron-3.5-super-vl-free | gemini-4-argon (alt deepseek/deepseek-flash) | native image gate; MMMU-Pro 78.6% (M3); Gemini 4 Argon unmeasured |
| `vision-critic-final` | deepseek-v4.1-flash (alt kimi-k3.1-pro) | nemotron-3.5-super-vl-free | deepseek/deepseek-flash (alt gemini-4-argon) | MMMU-Pro 80.6% + repo side-by-side 2026-09-18; Kimi MMMU 83.9% alt |
| `council-member` | qwen3.8-flash + gpt-5.6-luna + glm-5.3-flash + deepseek-v4.1-flash + minimax-m3.1-flash + mimo-v2.6-pro | — (free cannot serve a nested subagent; see Council) | gemini-4-argon + muse-spark-1.3 + deepseek/deepseek-flash | six families in six seats; within-family AA 29.2→42.7 (MiniMax), 37.9→46.3 (Xiaomi); per-seat basis in `agents/council.md` |

## Skill coverage

Every skill maps to one role. Mutation is role-level (the core table and
`agents/*.md`); this table is the coverage check that no skill hides behind
indirection.

| Role | Skills |
|---|---|
| `planner` / `architect` | designing-architecture; facilitating-product-vision; designing-cicd; deploying-to-azure-swa; deploying-with-supabase; securing-ci; modeling-threats; optimizing-model-routing |
| `implementer` | implementing-features; releasing-a-version; observing-runs |
| `triager` / `curator` | triaging-requirements; managing-github-issues; refining-issue-acceptance |
| `test-writer` | writing-unit-tests; writing-integration-tests; writing-e2e-tests |
| `debugger` | debugging-test-failures |
| `reviewer` | reviewing-code; reviewing-security; auditing-accessibility; auditing-supply-chain; validating-against-official-docs; handling-security-incidents |
| `skill-reviewer` | sourcing-external-skills; orchestrator skill verification (no standalone skill) |
| `skill-author` | authoring-skills |
| `vision-critic-fast` | capturing-ui-evidence; correcting-ui |
| `vision-critic-final` | validating-ui |
| `council-member` | council + council-architecture / council-performance / council-product / council-security / council-ux |

## Benchmark evidence principles

**Read benchmarks as a tier filter, not a ranking.** The most decision-relevant numbers on 2026-10-25 are the independent agent-loop benches (**Terminal-Bench 4.0**, **FrontierCode 1.1**) and instruction-following (**IFBench**), plus this repo's own probes. Harness choice alone swings scores 10–20 points (DeepSeek's vendor TB4 run claims 42.3 for 1017; AA's independent run scores it 33.8). Gaps ≤2–3 AA points are noise; **scores outrank family diversity** (user directive 2026-10-03) — diversity is a soft tie-breaker, except that council seats deliberately span families (Choice 10).

- AA Intelligence Index (Artificial Analysis, independent; **live pull 2026-10-25** — reasoning-config-specific rows, a tier filter, not a ranking): Kimi K3.1 Pro 55.1, Gemini 4 Argon 52.6, MiMo-V2.6-Pro 46.3, Qwen3.8 Max 45.4, DeepSeek V4.1 Flash 1017 45.1, Step 5 Preview 43.7, Claude Haiku 5.5 43.4, MiniMax M3.1 Flash 42.7, GLM-5.3-Flash 41.8, Qwen3.8 Flash (Next) 39.8 (the exact bound `qwen3.8-flash` ID has no separate AA row; identity conditional), MiMo-V2.6-Flash 37.9, GPT-5.6 Luna 37.3, MiniMax M3 29.2. A score above a binding never implies candidacy: Claude Opus 5.5 57.6 (not in the runtime registry), Sonnet 5.5 55.8 (excluded family), GPT-6 Astra 52.7 (peak class), GLM-5.3 44.8 (cost).
- **Terminal-Bench 4.0** (Laude Institute/Stanford; independently run by AA, 2026-10-25; pass@1 over 3 repeats, mini-swe-agent): Kimi K3.1 Pro 67.2% (leader), Gemini 4 Argon 57.1%, Muse Wonder 52.0%, Qwen3.8 Max 38.9%, MiMo-V2.6-Pro 34.8%, DeepSeek 1017 33.8%, GLM-5.3-Flash 32.8%, MiniMax M3.1 Flash 25.8%. This is the decisive bench for planner/debugger/implementer loop reasoning.
- **FrontierCode 1.1** (Cognition dataset; independently run by AA, 2026-10-25; 100 private tasks, 3 runs, Stirrup): Kimi K3.1 Pro 47.1%, MiMo-V2.6-Pro 45.4%, DeepSeek 1017 43.7%, Gemini 4 Argon 43.5%, GLM-5.3-Flash 41.0%, MiniMax M3.1 Flash 38.6%. The closest match to "would a maintainer merge this" review work.
- **MMMU-Pro** (independently run by AA): Kimi K3.1 Pro 83.9%, DeepSeek 1017 80.6%, MiniMax M3.1 Flash 79.1%, MiniMax M3 78.6%. Gemini 4 Argon is unmeasured; Gemini 3.8 Flash 84.2% is the family proxy. Academic multimodal reasoning, not UI-CSS judgment.
- **Liveness gate (user directive 2026-10-03):** a candidate must answer within the cap on its tier or it is "not live for that check"; never extend the timeout to rescue it. **2026-10-25 finding:** the runtime registry (`opencode models`) is part of the gate — 59 of 85 Zen catalog IDs return `ProviderModelNotFoundError` in opencode 1.19.4, including `claude-opus-5-5`, `gpt-5.6-sol`, `gemini-3.8-flash`, `gpt-5.6-luna`, and `gpt-5.4-mini`. Catalog membership without registry membership is not bindable. A chat-completions `ModelProtocolUnsupported` 400 is a protocol statement, not a death.
- SWE-bench Verified: directionally useful for tier filtering, not model ranking.
- Thinkbench autonomous coding loop (historical, 2026): GLM 5.2 92% full-pass / 0.976 mean; on existing-code tasks both GLM and M3 score 0.999–1.000. Superseded by TB4/FC for the 2026-10-25 decision.
- KingBench 3 (independent, 2026-08-14): GLM-5.3 91.25% — retained as background for the Zhipu family; not decisive in this pass.
- IFBench (instruction-following, independently run by AA; retrieved 2026-10-25): MiniMax-M3 **82.9%** — top *eligible* model (grok 4.3 at 83.3% and grok 4.20 at 82.9% are hard-excluded). Kimi K3.1 Pro, Gemini 4 Argon, M3.1 Flash, and DeepSeek 1017 have no IFBench row yet.
- MCPMark Verified (historical): Kimi K2.7 Code 81.1 > Opus 4.8 76.4; K2.7 ~30% more token-efficient. Retained as tool-use background; K2.7-code is live on Go but now rates AA 25.8 / TB4 3.4%, so it is no longer a default candidate.
- DeepSeek vendor docs (api-docs.deepseek.com, 2026-10-17): `deepseek-flash` is the canonical ID for **DeepSeek-V4.1-Flash-1017**; legacy `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` are retired aliases served at Flash price. Input text+image, tool calls ✓, JSON ✓, thinking + non-thinking, 1M context / 384K max output. Vendor self-reported: TB4 42.3 (prior 31.2), DeepSWE 77.0 (prior 74.2) — tier filter only. Off-peak = half price; peak 01:00–04:00 and 06:00–10:00 UTC Mon–Fri.
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
gpt-6-luna. **`kimi-k3.1-pro` is not `kimi-k3`**: it is a separate, live Go ID
at $2.00/$10.00 per 1M (cheaper than K3's $3.00/$15.00), and the 2026-10-03
cost directive does not name it. It is bound on the 2026-10-25 table with a
$60 Go Plus monthly cap; revisit at the 2026-11-01 spend review. These models
may be invoked manually by the user for experiments; they must never be bound
by any role, agent, or loop in this repo.

## Free opt-in

Free models are **not a default**. The only two ways to run free are:

1. `AI_FRAMEWORK_FREE_TIER=1` — the explicit opt-in toggle (also the eval
   runner's free-tier mode); or
2. a per-session model switch to a `*-free` catalog ID.

The free generalist seat moved on 2026-10-25 to **`deepseek-v4.1-flash-free`**
(AA 45.1 for the 1017 build, live 3.49s) — the strongest free generalist by a
wide margin and the same family as the Go implementer lane. `nemotron-3-ultra-free`
is **docs-listed but absent from the Zen catalog** (2026-10-25) and is retired
from the table; the catalog-vs-docs rule excludes it from candidacy. The free
tier now also has a **multimodal** model: `nemotron-3.5-super-vl-free` (native
image input, live, AA 26.5) fills the vision opt-in. `glm-5.3-flash-free`
(AA 41.8) and `mimo-v2.6-flash-free` (AA 37.9) are the redundant generalists.
`big-pickle`, `flint-40b-free`, and `beam-free` are live but **unbenched** —
redundancy candidates only, unbound until evaluated.

**Nested-subagent constraint:** the free tier cannot serve a nested Task
subagent (`OpenCode's free tier can only be used from within OpenCode`), so
free use never applies to the council or to any in-session dispatch whose
target is free-bound; a framework persona is Go-bound and does not hit this.

**Council seat policy (Go flat-rate, updated 2026-10-25):** one family per
seat — qwen3.8-flash (chairman, Qwen), gpt-5.6-luna (performance, OpenAI),
glm-5.3-flash (architecture, Zhipu), deepseek-v4.1-flash (security, DeepSeek),
minimax-m3.1-flash (ux, MiniMax), mimo-v2.6-pro (product, Xiaomi). Family
diversity is the seat-design mechanism; for non-council roles scores outrank
diversity (2026-10-03 directive). The 2026-10-25 within-family upgrades
(MiniMax, Xiaomi) passed the 3-prompt seat validation on 2026-10-25 (3/3 each;
the product seat had one transient 60s timeout, passed on retry). The
unchanged seats were validated 2026-10-04.

## Provider notes

- **Go / Go Plus** (flat-rate): the **default tier** for every role. Open models only. Config prefix `opencode-go/`. **Go $10/mo; Go Plus $40/mo** (user upgraded 2026-10-01) — same models and token prices, higher per-model usage. Each model has its own monthly dollar cap: 5-hour = 20% of it, weekly = 50%, monthly = 100% (opencode.ai/docs/go, fetched 2026-10-25). Go falls back to Zen balance ("Use balance") after limits. Catalog (38 IDs, 2026-10-25) includes kimi-k3.1-pro, gemini-4-argon, claude-haiku-5-5, step-5-preview, longcat-2.0, hy3/hy4-preview, glm-5.3-flash, qwen3.8-flash/max, qwen3.7-plus, deepseek-v4.1-flash/pro, minimax-m3/m3.1-flash, mimo-v2.6-flash/pro, gpt-5.6-luna, kimi-k2.7-code, muse-spark-1.2/1.3-contributor — with glm-5.3/glm-5.2, kimi-k3, gpt-6-luna, and grok-4.7 excluded by policy (see Hard exclusions; catalog presence never overrides). **Go monthly caps for the new leaders:** Kimi K3.1 Pro $60 (Go Plus), Gemini 4 Argon $120, DeepSeek V4.1 Flash $160, MiMo-V2.6-Pro $60, GLM-5.3-Flash $180, MiniMax M3.1 Flash $80.
- **Free tier** (opt-in only): `opencode/*-free` catalog entries that are docs-listed and live-verified. Selected only via `AI_FRAMEWORK_FREE_TIER=1` or an explicit per-session model switch — never a bound default. Catalog-vs-docs mismatches stand: `nemotron-3-ultra-free` is docs-listed but **absent from the 2026-10-25 Zen catalog** (retired from the table); `deepseek-v4-flash-free` and `muse-spark-1.2-contributor-free` are catalog-listed but NOT docs free-listed — excluded from candidacy (the 2026-09-02 failure pattern).
- **Zen** (pay-as-you-go): Full catalog including proprietary models. Config prefix `opencode/`. **Only 17 of the 85 catalog IDs are in opencode's runtime registry** (`opencode models`, 2026-10-25); the rest fail `ProviderModelNotFoundError` and are not bindable regardless of catalog presence. Workspace model-access toggles can also gate individual models — "Model is disabled" means a workspace toggle, not a gateway death (resolved 2026-09-18). `qwen3.7-*` is Go-only — bind it as a Go escalation, never as a Zen one. Live bindable Zen families: Google (`gemini-4-argon`), Meta (`muse-spark-1.3`, `muse-wonder-1.0`), Anthropic (`claude-haiku-5-5`), DeepSeek (`deepseek-v4.1-flash`), Zhipu (`glm-5.3-flash`), Qwen (`qwen3.8-flash`), MiniMax (`minimax-m3`), plus the free IDs. `kimi-k2.7-code` is in the Zen registry but its 2026-10-25 probe exceeded the cap (25s); it is not live for that check. `muse-wonder-1.0` scores AA 52.4 / TB4 52.0 but answered in 24.5s, over the 20s cap — excluded until re-probed.
- **CI eval lane (user directive 2026-09-29)**: behavioral evals in CI run on the **Go flat-rate** lane — **`opencode-go/deepseek-v4.1-flash`**, authenticated by the repo's `OPENCODE_API_KEY`. Chosen on measured evidence (3/3 probes pass, 34 s light / 168 s heavy; AA 45.1 for 1017, $0.26/task; `mimo-v2.6-flash` measured 2× slower and was rejected on wall time). Depth policy: **weekly = default per skill (26 evals); monthly = full suite (111)**, six measured-weight shards; a full sharded run measured 59 min wall and ~$1.8 (allowance-equivalent). **Requires workspace region = Global** (set 2026-09-29). The RM-056 fallback switches a log-proven-degraded run to the direct `deepseek/deepseek-flash` API and marks the lane in the eval report — never a silent re-bind.
  **Nested-subagent caveat (found 2026-09-29, superseded for this repo 2026-10-03):** a skill that spawns a free-tier-bound subagent dies in CI (the free tier rejects calls made outside the OpenCode client). `scripts/ci-lane-overrides.py` still emits a V2 config override for that case — now an empty `agents` map for this repo (every persona is Go-bound) and a working guard for consumer repos whose wrappers are free-bound. **Sandbox path (V2, 2026-10-29):** CI no longer uses `OPENCODE_CONFIG_CONTENT` (V2 ignores it for agents and permissions). The workflow generates an isolated `XDG_CONFIG_HOME` root with `ci-lane-overrides.py --xdg-root`: one catch-all `external_directory: "*"` deny, then explicit allow roots for `/tmp/**`, the runner temp, `~/.config/opencode/**`, and the generated config root (last match wins). Unlisted paths stay denied; the checkout is not an external root.
- **Direct-key lane** (user's own DeepSeek API key, approved 2026-09-18): config prefix `deepseek/`. Billed directly by DeepSeek to the user's own balance — check that balance separately from opencode. `deepseek/deepseek-flash` is **DeepSeek-V4.1-Flash-1017** (vendor docs 2026-10-17; live-probed 2026-10-25: text, vision, tool calls, 1M context, 2.98s). AA independently scores it 45.1, TB4 33.8%, FrontierCode 43.7%, $0.26/task, 169 t/s. `deepseek/deepseek-v4-pro` also routes live (AA 36.0, no vision). Off-peak half price during 01:00–04:00 and 06:00–10:00 UTC Mon–Fri. This lane is an explicit opt-in escalation only.
- Go can fall back to Zen balance when limits hit ("Use balance" in the console). `AI_FRAMEWORK_FREE_TIER=1` forces the free tier even when a Go/Zen key is present — the explicit free opt-in.

## Non-chat models (decision endpoints)

- **Jev 1.13** (`jev-1.13`, `jev-1.13-free`) — TypeSafe AI "System One"
  decision model; Zen-only (absent from the Go catalog, verified
  2026-10-25). Endpoint `https://opencode.ai/zen/v1/systemone` (typed
  questions → values + probabilities; no AI SDK package). $0.042/1M
  input, output free; free variant limited-time. **Never a role-binding
  candidate** — not a chat model; no routing pass may rank or bind it
  in any tier. Evaluated for advisory use 2026-10-03:
  `reference/jev-system-one-evaluation.md` (trigger-gated; ROADMAP
  RM-041).

## Vision capability strategy

The UI iteration loop requires a model that can read screenshots. Tiered strategy (updated 2026-10-25):

- **`vision-critic-fast`** (iteration passes): defaults to **MiniMax M3** on Go's flat rate (native image input, MMMU-Pro 78.6%, 103 t/s). Go alt: **gemini-4-argon** (native image/video/PDF input, AA 52.6, MMMU-Pro unmeasured; Gemini 3.8 Flash 84.2% is the family proxy). Zen fast passes: **gemini-4-argon** (alt deepseek/deepseek-flash). **M3 is still not confirmed for UI-CSS judgment specifically**; evaluate in the `correcting-ui` loop before relying on it.
- **`vision-critic-final`** (sign-off): defaults to **`opencode-go/deepseek-v4.1-flash`** — the same model as the validated direct-key `deepseek/deepseek-flash` seat (user directive 2026-09-18), now on the Go lane. Basis: MMMU-Pro 80.6%, live-probed vision, vendor-documented image support, and a 2026-09-18 side-by-side against sonnet-5 showing parity-or-better on UI-mock critique and exact chart reading. **Acceptance gate:** the first real-page `validating-ui`/`correcting-ui` cycle validates the seat. Alt: **kimi-k3.1-pro** (MMMU-Pro 83.9%, native image) and **gemini-4-argon**; the direct-key lane remains the explicit fallback.
- **Free opt-in:** **`nemotron-3.5-super-vl-free`** is a native image-input free model (live 2026-10-25, AA 26.5) — the free fallback for both seats, quality-caveated. It replaces the old "no free multimodal" statement.
- **No free model is quality-competitive for UI judgment**, so the paid seats stay Go-bound (M3 fast / DS final).

## Update procedure

0. Run the model-doctor canary first: `python3 scripts/model-liveness-check.py` (bound + documented IDs vs live catalogs, the docs free list, and the Go-first policy assertions — no `-free` bindings, no hard-excluded IDs, table/live consistency). Investigate any drift before the full pass — a red canary means the current bindings are already stale. Add `--probe` with `OPENCODE_API_KEY` set for the live trivial-prompt probe (20s cap, bare catalog IDs, `x-opencode-session` required; `/responses`-only IDs report protocol-unsupported, not death).
1. Fetch current catalogs and the runtime registry:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
   - **`opencode models`** — the bindable set. A catalog-listed ID absent from the registry fails with `ProviderModelNotFoundError` and is not a candidate (2026-10-25: 17 of 85 Zen IDs bindable).
   - Docs pages for pricing/deprecations — **`https://opencode.ai/docs/zen/#endpoints` is authoritative for free-tier availability** (the API catalog can list IDs that are not actually routable; see 2026-09-02 `deepseek-v4-flash-free` failure).
   - Check the workspace **Model access** toggles — a "Model is disabled" error is a workspace toggle, not a gateway death. Re-probe after any toggle change.
2. **Candidate gate — liveness (hard gate, before any evaluation or ranking):** catalog membership plus registry membership plus a live probe. A model is a candidate **only if** it is catalog-listed, **in the runtime registry**, and live-verified on its tier with the probe contract above (cap never extended). Access restrictions fail the gate the same way errors do: a model routable only behind an explicit opt-in, consent gate, or region lock is **not live**. Never opt in on the user's behalf. Gates lift without notice, so every pass re-probes from scratch: a rehabilitated model re-enters candidacy on its own.
3. Update the core routing table, the Skill coverage table, and the bench basis per-role rationale (ranking only over **live candidates** from step 2). The default column stays Go; a free model may be listed only in the opt-in column. A new skill must land in the coverage table in the same pass that routes it.
4. If a bound model is deprecated or beaten on price/quality, update the role row and note it in the commit message.
5. Bump the retrieval date at the top of the file.
6. Re-run the 3-prompt seat validation for any changed council/quality seat before recording it as settled; a failed seat re-opens its OQ and reverts to the recorded alt.

## Council

- **Council** runs on the Go lane for planning & review (per `agents/council.md`). The six seats bind one family each: qwen3.8-flash (Qwen), gpt-5.6-luna (OpenAI), glm-5.3-flash (Zhipu), deepseek-v4.1-flash (DeepSeek), minimax-m3.1-flash (MiniMax), mimo-v2.6-pro (Xiaomi). Reason: the free tier cannot serve a nested Task subagent; the 2026-09-13 free-council seats are retired. A Zen frontier council (**gemini-4-argon + muse-spark-1.3 + deepseek/deepseek-flash**) stays the explicit opt-in. `claude-opus-5-5` and `gpt-5.6-sol` are catalog-listed but **not in the runtime registry** (2026-10-25), so they are no longer bindable anywhere, including this opt-in.
- Council only for **planning & review**. Raw execution stays single-model.
- Always surface disagreements; never let one model silently override another.
- The free opt-in (`AI_FRAMEWORK_FREE_TIER=1`) coexists with the council — the toggle selects the main session's tier; the council stays Go-bound or is recorded as an explicit skip.
