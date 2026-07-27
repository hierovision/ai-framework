# Model Routing

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

- Retrieved: 2026-07-03 (catalog/pricing); benchmark evidence added
  2026-07-06 (sources in "Benchmark evidence" below)
- **Catalog refresh: 2026-07-25** (both catalogs re-fetched; see "Catalog
  refresh" under Benchmark evidence) — `hy3-free` removed, new free + Go + Zen
  models, routing re-optimized: **free by default where a free model exists;
  Go flat-rate and Zen PAYG are escalation only** (per the established
  cost-conscious pattern).
- Review cadence: monthly, or when a deprecation notice lands
- Status: catalog + pricing current as of 2026-07-25; the escalation rows are
  **evidence-backed** (Benchmark evidence) and the `skill-author` /
  `skill-reviewer` / `vision-critic-*` rows are partly **empirically
  confirmed** by six authoring rounds in this repo. **Free generalist
  `ling-3.0-flash-free` validated 2026-07-26** via a clean, no-tool head-to-head
  eval (see "Free-tier caveats").

## Contents

- Roles → bindings
- Benchmark evidence (2026-07-06) + Catalog refresh (2026-07-25)
- Per-role benchmark rationale
- Provider notes (Free / Go / Zen)
- Vision capability notes
- Deprecation watch
- Free-tier fallback + council
- Update procedure

## Roles → bindings

Tiers: **Free default** (`opencode/*-free`, $0) → **Escalation — Go flat-rate**
(`opencode-go/`, uses the Go allotment) → **Escalation — Zen PAYG**
(`opencode/`, proprietary). The "Bench basis" column cites the most objective
signal available for the *escalation* pick (the free default is chosen for $0
cost, not benchmark rank — see Free-tier caveats).

| Role | Used by (loop stage) | Free default (`opencode/*-free`) | Escalation — Go flat-rate | Escalation — Zen PAYG | Bench basis (escalation) |
|---|---|---|---|---|---|
| `planner` | design, architecture | ling-3.0-flash-free | glm-5.2 | claude-opus-5 (peak: claude-fable-5) | Thinkbench autonomous loop 92%/0.976; SWE-bench Verified tier |
| `implementer` | implement (backend/frontend) | deepseek-v4-flash-free | kimi-k2.7-code (alt qwen3.7-plus) | claude-sonnet-5 (alt gpt-5.4) | MCPMark tool-use 81.1 (best of all); SWE-bench Verified |
| `triager` | triage, bulk edits, summaries | ling-3.0-flash-free (alt deepseek-v4-flash-free) | hy3 | gpt-5.4-mini / claude-haiku-4-5 | generalist reasoning (no free bench) |
| `test-writer` | unit/integration/e2e authoring | deepseek-v4-flash-free | kimi-k2.7-code (alt qwen3.7-plus) | claude-sonnet-5 | MCPMark + SWE-bench Verified |
| `debugger` | test-failure analysis | deepseek-v4-flash-free (alt ling-3.0-flash-free) | glm-5.2 | claude-sonnet-5, gpt-5.4 | Thinkbench + SWE-bench Verified |
| `reviewer` | code review | deepseek-v4-flash-free (alt ling-3.0-flash-free) | glm-5.2 | claude-sonnet-5, gpt-5.4 | SWE-bench Verified (defect catch) |
| `vision-critic-fast` | UI loop, routine passes | — (no free multimodal) | minimax-m3 (native multimodal) | gemini-3-flash (alt gpt-5.4-mini) | native image-in; vision bench (gemini) |
| `vision-critic-final` | UI loop, final review | — | — | gemini-3.1-pro (alt claude-sonnet-5) | vision quality (gemini-3.1-pro) |
| `council-member` | multi-perspective review | ling-3.0-flash-free + mimo-v2.5-free + deepseek-v4-flash-free (free, mix families) | hy3 + mimo-v2.5 + deepseek-v4-flash (Go, mix families) | claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol (frontier, max diversity) | family diversity + per-lens competence |
| `skill-author` | authoring new skills | ling-3.0-flash-free | minimax-m3 (alt glm-5.2, qwen3.7-max) | claude-sonnet-5 (qwen3.7-max is Go-only IF leader) | IFBench 79.1; Thinkbench existing-code parity |
| `skill-reviewer` | reviewing skill drafts | ling-3.0-flash-free (alt deepseek-v4-flash-free) | glm-5.2 | claude-opus-5 (peak: claude-fable-5) | SWE-bench Verified (highest reasoning) |

## Benchmark evidence (2026-07-06)

Sources: llm-stats SWE-bench Verified leaderboard; vals.ai (independent
verification); digitalapplied.com harness-variance analysis; thinkwright
Thinkbench autonomous-coding-loop test; Alibaba Qwen3.7 technical report
(IFBench); grahammiranda / codingfleet M3-vs-GLM comparisons.

**Read benchmarks as a tier filter, not a ranking.** Per digitalapplied
(2026-06-15): 99/100 SWE-bench Verified entries are self-reported, the set
is contamination-prone and saturated, and harness choice alone swings
scores 10–20 points. The most decision-relevant numbers here are the
independent autonomous-loop test and instruction-following (IFBench),
plus this repo's own six authoring rounds.

- **SWE-bench Verified (tier filter):** Fable 5 95.0 (independently
  confirmed, but export-suspended ~Jun 12, expected back ~Jul 1) ·
  GPT-5.5 88.7 · Opus 4.8 88.6 · Sonnet 5 85.2 · Gemini 3.1 Pro / DeepSeek
  V4 Pro 80.6 · MiniMax M3 80.5 · Qwen3.7 Max 80.4 · Kimi K2.6 80.2 ·
  Qwen3.6 Plus 78.8 · GLM 5.2 (no official Verified; ~62.1 SWE-bench Pro
  third-party).
- **Independent autonomous coding loop (Thinkbench, thinkwright):**
  GLM 5.2 92% full-pass / 0.976 mean; MiniMax M3 84% / 0.961. **Crucial
  nuance for us:** on *existing-code* tasks (bug fix, feature add,
  repair-to-green) both models score 0.999–1.000 — indistinguishable.
  GLM's edge is concentrated in *greenfield-from-empty-repo* builds.
  Skill authoring through the meta-skill is scaffolded/existing-code-like
  work, so M3's greenfield weakness barely applies.
- **Instruction-following (IFBench, the trait that most predicts
  authoring fidelity):** Qwen3.7 Max 79.1 (leads) · DeepSeek V4 Pro 77.0.
  GLM 5.2 empirically strong here — its "plain reading of the brief"
  tendency (vs M3 "adds more production-shaped machinery" on vague briefs,
  per thinkwright) is exactly the de-mirroring discipline our review
  rounds rewarded. Mitigated for M3 by our very detailed handoffs + the
  meta-skill's conciseness rule + the review pass.
- **Tool use (MCPMark Verified):** Kimi K2.7 Code 81.1 > Opus 4.8 76.4;
  K2.7 also ~30% more token-efficient. A strong `implementer` /
  `test-writer` escalation given heavy file/tool orchestration.
- **Multimodal:** MiniMax M3 is natively multimodal (image/video in) and
  on Go's flat rate — the only cheap open model that reads a screenshot
  without a bolt-on. Directly relevant to `vision-critic-fast` escalation.

### Catalog refresh — 2026-07-25 (this update)

Re-fetched both catalogs (Zen PAYG: `https://opencode.ai/zen/v1/models`;
Go flat-rate: `https://opencode.ai/zen/go/v1/models`). Material changes:

- **`opencode/hy3-free` removed from the catalog.** The triage/council
  "hy3 persona" default moves to **`opencode/ling-3.0-flash-free`**, chosen by
  a clean, no-tool head-to-head (2026-07-26) against the other free
  generalists (`nemotron-3-ultra-free`, `north-mini-code-free`,
  `laguna-s-2.1-free`): all four are competent and reliable in a no-tool
  clean-room; `ling` + `nemotron` tied for best output (10/10 on triage +
  planning); `laguna` relaxed a requirement; `ling` had the cleanest
  reliability across all invocation contexts. See Free-tier caveats.
- **Free tier still intact for most roles:** `mimo-v2.5-free` (devops/
  security) and `deepseek-v4-flash-free` (coding) remain valid free IDs, so
  they stay as the free defaults for those lenses.
- **New Zen frontier models:** `claude-opus-5`, `claude-fable-5` (peak; 95.0
  when last measured), `gpt-5.6-sol/terra/luna`, `gemini-3.6-flash`,
  `gemini-3.5-flash`, `gemini-3.5-flash-lite`. Escalation rows now use
  `claude-opus-5` (≥ opus-4-8 88.6) and `gpt-5.6-sol` (≥ gpt-5.5 88.7).
- **New Go models (escalation tier):** `kimi-k3` (successor to k2.7-code),
  `qwen3.7-max`, `qwen3.7-plus`, `grok-4.5`, and **`hy3` / `hy3-preview` are
  now Go flat-rate models** (usable as a Go-escalation generalist). Note
  **`qwen3.7-*` is Go-only** — bind it as a Go escalation, never as a Zen one.

### Free-tier caveats (read before relying on free defaults)

The free generalist (`ling-3.0-flash-free`) **was validated 2026-07-26** by a
clean, no-tool head-to-head eval (clean-room working dir; every tool + skill
permission denied) against `nemotron-3-ultra-free`, `north-mini-code-free`,
and `laguna-s-2.1-free`, on two persona tasks (backlog triage → ROADMAP;
architecture plan). Results: all four completed both tasks reliably (8/8
clean); all scored 10/10 on the triage rubric; on planning, `ling` and
`nemotron` scored 10, `north` 10 (slightly shallower), `laguna` 9 (introduced
a 5-min TTL cache that violates the "revoke immediately" requirement).
`nemotron` showed the strongest planning/architecture rigor (single-transaction
rotate, per-request `revoked_at` check, hash + index specifics) but exhibited
intermittent streaming errors under heavier/other agent contexts; `ling` had
**zero failures observed** across all probes and is the reliable default. So
`ling-3.0-flash-free` is the free generalist default; `nemotron-3-ultra-free`
is the strong alt when you need peak planning rigor. For risk-bearing tasks
you may still escalate to the Go or Zen tier.

**Rationale for the 2026-07-25 changes (this update):**
- **Free by default, escalate to Go/Zen** (restores the established
  cost-conscious pattern). The 2026-07-06 design had Go flat-rate as the
  default; this update returns the default to the free tier and makes Go and
  Zen *escalation only*, because defaulting to paid Go has direct financial
  consequences.
- `implementer` / `test-writer` escalation → **`kimi-k2.7-code`** (MCPMark
  tool-use 81.1, best of all models incl. Opus 4.8 at 76.4, ~30% more
  token-efficient) — the most objective escalation pick for an agent that
  orchestrates many file/tool calls. `qwen3.7-plus` remains a strong alt.
- `skill-author` escalation → **`minimax-m3`** (existing-code parity with GLM
  0.999–1.000, 3.7× cheaper) with `qwen3.7-max` (IFBench 79.1, Go-only) as the
  instruction-following escalation; `claude-sonnet-5` on Zen for proprietary
  IF strength.
- `council-member` frontier opt-in → **`claude-opus-5 + gemini-3.1-pro +
  gpt-5.6-sol`** (one model per vendor family) for maximum multi-perspective
  objectivity.

## Per-role benchmark rationale (escalation picks)

Each agent persona escalates to the model the objective evidence favours for
*its* task, not to a single flagship:

- **planner / design** — architecture + plan artifacts are largely
  *existing-code* work, where GLM 5.2's 92% Thinkbench full-pass (0.976
  mean) is the strongest documented open result; on existing-code it is
  statistically tied with M3 (0.999–1.000). Escalates to `claude-opus-5`
  (≥ 88.6 Verified) for hardest architecture.
- **implementer / test-writer** — heavy file + tool orchestration favours
  the best *tool-use* score: Kimi K2.7 Code at MCPMark 81.1 (above Opus 4.8
  76.4) and ~30% more token-efficient. Escalates to `claude-sonnet-5`
  (85.2 Verified) for cost/quality balance.
- **triager** — consolidation/ranking/summaries need a generalist; the free
  default is a free generalist, escalating to `hy3` (Go) or `gpt-5.4-mini` /
  `claude-haiku-4-5` (Zen, cheap) for very large/nuanced backlogs.
- **debugger / reviewer** — defect localization + root-cause benefits from
  GLM 5.2's 92% loop reasoning; escalates to Sonnet-5 / GPT-5.4.
- **vision-critic-fast** — must read screenshots cheaply; MiniMax M3 is the
  only natively-multimodal Go model. **Evaluate M3's UI-CSS judgment in the
  `correcting-ui` eval loop before trusting it** (its multimodal wins are on
  SVG-Bench / BrowseComp, not UI critique). `vision-critic-final` stays on
  Zen `gemini-3.1-pro` (strongest vision) for sign-off. No free multimodal
  exists, so vision defaults to the Go escalation (M3).
- **council-member** — objectivity comes from *family diversity*, not raw
  score: the free default mixes ling / mimo / deepseek (three families);
  the frontier opt-in mixes Anthropic / Google / OpenAI (Opus-5 / Gemini-3.1-
  pro / GPT-5.6) for maximal independent perspective.
- **skill-author** — scaffolded/existing-code authoring → MiniMax M3
  (existing-code parity 0.999–1.000 with GLM, 3.7× cheaper); IFBench leader
  `qwen3.7-max` (79.1, Go-only) is the instruction-following escalation.
- **skill-reviewer** — needs top reasoning; `glm-5.2` (Go escalation, 92%
  loop) is a competent cheap reviewer, escalating to `claude-opus-5` /
  `fable-5` (95.0) for peak skill-foundation review.

## Provider notes

- **Free tier** ($0): the `opencode/*-free` catalog entries (a subset of the
  Zen catalog). **This is the default tier** — used for every role where a
  free model exists. No financial consequence.
- **Go** ($10/mo flat): open models only. Config prefix `opencode-go/`.
  **Escalation tier** — used only when the free default is insufficient or
  unavailable (e.g. vision, peak coding). Limits: $12/5hr, $30/wk, $60/mo.
  `hy3` and `hy3-preview` are now Go flat-rate models (a strong Go
  escalation generalist).
- **Zen** (pay-as-you-go): full catalog including proprietary models.
  Config prefix `opencode/`. **Escalation tier** — the frontier opt-in
  (Opus-5, Fable-5, GPT-5.6, Gemini-3.1-pro) and the only source of
  vision-capable critics. **Note:** `qwen3.7-*` is Go-only — bind it as a Go
  escalation, never as a Zen one.
- Go can fall back to Zen balance when limits hit ("Use balance" in the
  console). The `AI_FRAMEWORK_FREE_TIER=1` toggle forces the free tier even
  when a Go/Zen key is present.

## Vision capability notes

The UI iteration loop **requires** a model that can read screenshots.
Tiered strategy (locked decision): cheap model per iteration pass, strong
model for final signoff. **No free multimodal model exists**, so
`vision-critic-fast` defaults to the Go escalation **MiniMax M3** (natively
multimodal, image + video in, on Go's flat rate). If M3's screenshot judgment
proves good enough for routine passes, the fast tier stays on the Go plan
instead of Zen billing — a material saving. **Not yet confirmed for UI-CSS
judgment specifically** (M3's multimodal wins are on SVG-Bench / BrowseComp,
not UI critique); evaluate in the `correcting-ui` eval loop before relying on
it. `vision-critic-final` stays Zen (`gemini-3.1-pro` / `claude-sonnet-5`)
for sign-off. Cheaper Zen vision alternatives for fast passes:
`gemini-3.5-flash` / `gemini-3.6-flash`.

## Deprecation watch (from Zen docs, 2026-07-03; refreshed 2026-07-25)

| Model | Deprecation date | Action |
|---|---|---|
| `hy3-free` (free tier) | 2026-07-25 (removed from catalog) | use `opencode/ling-3.0-flash-free` (free) or escalate |
| GPT 5.2/5.1/5 Codex variants | 2026-07-23 | avoid in new bindings |
| Kimi K2.5 | 2026-08-05 | use kimi-k2.7-code (or kimi-k3) |
| MiniMax M2.5 | 2026-08-05 | use minimax-m3 / m2.7 |
| Claude Opus 4.1 | 2026-08-05 | use opus-4-8 (or opus-5) |
| GLM 5 | 2026-05-14 (past) | use glm-5.2 |

New and safe to bind (2026-07-25): `claude-opus-5`, `claude-fable-5`,
`gpt-5.6-*`, `gemini-3.5/3.6-flash`, `kimi-k3`, `qwen3.7-max/plus`,
`grok-4.5`, `hy3` / `hy3-preview` (Go flat-rate), and the free roster
`ling-3.0-flash-free` (validated free generalist; `nemotron-3-ultra-free`,
  `north-mini-code-free`, `laguna-s-2.1-free` also competent — see caveats).

Known stale bindings in existing projects: none currently tracked. `pt`'s
`qwen3.6-plus` binding (`build` agent + `council-ux` subagent) was refreshed
to `qwen3.7-plus` as part of its skill-library adoption (2026-07-13).

## Free-tier fallback + council

Intent: the library **defaults to free models**; escalation (Go / Zen) is
opt-in per the routing table above. This section documents the free-tier
mode and the multi-model council that runs on free models for the two steps
where a single weak model is riskiest — **planning** and **review**. It never
alters the escalation rows. Status: protocol drafted 2026-07-14; models
re-verified 2026-07-25 (the `-free` IDs are separate catalog entries from
`deepseek-v4-flash` and `mimo-v2.5`, which remain the Go escalation rows).

### Free-model roster

| Role | Free model (catalog ID) | Maps to existing role row |
|---|---|---|
| `planner` / chairman / generalist | `opencode/ling-3.0-flash-free` | `planner` (glm-5.2 / claude-opus) |
| `implementer` / `test-writer` / `debugger` (coding) | `opencode/deepseek-v4-flash-free` | `implementer` (kimi-k2.7-code) |
| `devops` / CI / cloud / security | `opencode/mimo-v2.5-free` | `triager` (mimo-v2.5) |

### Activation + routing (free-tier mode)

- **Toggle:** `AI_FRAMEWORK_FREE_TIER=1` selects this mode. The escalation
  rows above remain the default-capable path; with the toggle on, every task
  uses a free model even when Go/Zen keys are present.
- **Single-task execution** uses the one mapped free model (no council) to
  conserve free quota:
  - planning / design → `opencode/ling-3.0-flash-free`
  - any coding (implement / test / debug) → `opencode/deepseek-v4-flash-free`
  - devops / CI / cloud / security → `opencode/mimo-v2.5-free`
- Skills reference **roles**, never these IDs (library convention). The
  binding of a role to a free model in free-tier mode happens in the
  harness/project config, not in skill bodies — this file is the single
  home of the IDs.

### Council structure (objectivity for planning & review)

Free models are individually weaker, so run **planning** and **review** as a
multi-model council and synthesize. The procedure and the agent-def sketches
live in `docs/FREE-TIER-COUNCIL.md` (a project drops those defs into
`.opencode/agents/`). Design:

- **Planning council** (producing a plan/spec via `designing-architecture`,
  `designing-cicd`, `deploying-with-supabase`, `deploying-to-azure-swa`,
  `securing-ci`):
  - A — `opencode/ling-3.0-flash-free`: primary planner.
  - B — `opencode/mimo-v2.5-free`: devops/security critique (CI safety, secrets,
    environments, migrate-before-deploy).
  - C — `opencode/deepseek-v4-flash-free`: coding-feasibility critique
    (realizable? are the ACs testable?).
  - Synthesis: A writes the final plan folding in B/C; **surface
    disagreements explicitly** (a finding one model overrides is named,
    not silenced).
- **Review council** (reviewing a diff/skill/workflow via `reviewing-code`,
  `skill-reviewer`):
  - A — `opencode/deepseek-v4-flash-free`: coding review.
  - B — `opencode/mimo-v2.5-free`: devops/security review.
  - C — `opencode/ling-3.0-flash-free`: plan/architecture coherence +
    synthesis.
  - Output: per-member findings + consensus verdict + unresolved
    disagreements flagged.

Mechanism: the orchestrator spawns subagents (Task tool) with `subagent_type`
bound to the free-council agent defs (each sets `model:` to the free ID), runs
them (parallel where possible), then synthesizes. See
`docs/FREE-TIER-COUNCIL.md` for the exact defs + a worked example.

### Guardrails

- Council only for **planning & review** (per above). Raw execution stays
  single-model to conserve free quota.
- Always surface disagreements; never let one model silently override
  another.
- Free-tier mode coexists with the escalation routing — the toggle selects
  between them; the escalation rows are not modified by enabling free-tier.

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
