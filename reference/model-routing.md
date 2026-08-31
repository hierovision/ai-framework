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
- Status: catalog + pricing current as of 2026-07-25; **catalog re-checked
  2026-08-30** (see "Catalog re-check — 2026-08-30"): both catalogs live-fetched
  2026-08-30; `ling-3.0-flash-free` and `north-mini-code-free` remain removed
  from the free roster (rebound to `nemotron-3-ultra-free`); `hy3-free` is
  absent from the free catalog (only `hy3`/`hy3-preview` on Go); new candidates
  confirmed (`glm-5.3`, `qwen3.8-max`, `gpt-5.6-luna` on Go; `gemini-3.7-flash`
  on Zen; `ling-3.0-flash-fin-free`, `muse-spark-1.2-contributor-free`,
  `nemotron-3.5-lightning-free`, `laguna-s-2.1-free`, `big-pickle` on free).
  The escalation rows remain **evidence-backed** (Benchmark evidence) and the
  `skill-author` / `skill-reviewer` / `vision-critic-*` rows remain partly
  **empirically confirmed** by six authoring rounds in this repo.
  **`deepseek-v4-flash-free` confirmed 2026-08-30** — independent Ante harness
  reproduces Terminal-Bench 2.1 82.7% (2026-08-09), AA Intelligence Index 50.
- **Routing re-optimized 2026-08-30** (see "Routing update — 2026-08-30"
  under the bindings table and `model-check-2026-08-30.md`): full-sweep pass;
  all bindings catalog-valid and evidence-backed; **no binding changes**.
  Independent evidence reinforced: KingBench 3 91.25% (GLM-5.3, indep.),
  AA 60 (Kimi K3, GLM-5.3), Ante TB 2.1 82.7% (DeepSeek V4 Flash 0731),
  MCPMark Verified 81.1% (Kimi K2.7 Code). Free generalist re-validation
  (head-to-head per Update procedure step 4) still pending.

## Contents

- Roles → bindings
- Benchmark evidence (2026-07-06) + Catalog refresh (2026-07-25)
- Official-release refresh (2026-08-02) + Catalog re-check (2026-08-14)
- Hard exclusions
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
| `planner` | design, architecture | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt kimi-k3) | claude-opus-5 (peak: claude-fable-5) | AA Intelligence Index 60 (indep. 2026-08-25); Thinkbench autonomous loop 92%/0.976 |
| `implementer` | implement (backend/frontend) | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 (alt gpt-5.4) | AA Intelligence Index 60 vs K2.7 43 (indep. 2026-08-25); MCPMark 81.1 (K2.7 legacy) |
| `triager` | triage, bulk edits, summaries | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt deepseek-v4-pro) | gpt-5.6-luna (alt gpt-5.4-mini) | AA 60 / luna 52 at $0.05/task + 141 t/s (indep. 2026-08-25) |
| `test-writer` | unit/integration/e2e authoring | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | AA 60 (indep. 2026-08-25); MCPMark + SWE-bench Verified |
| `debugger` | test-failure analysis | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | Thinkbench + SWE-bench Verified |
| `reviewer` | code review | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | SWE-bench Verified (defect catch) |
| `vision-critic-fast` | UI loop, routine passes | — (no free multimodal) | minimax-m3 (native multimodal) | gemini-3-flash (alt gpt-5.4-mini) | native image-in; vision bench (gemini) |
| `vision-critic-final` | UI loop, final review | — | — | gemini-3.1-pro (alt claude-sonnet-5) | vision quality (gemini-3.1-pro) |
| `council-member` | multi-perspective review | nemotron-3-ultra-free + mimo-v2.5-free + deepseek-v4-flash-free (free, mix families) | kimi-k3 + glm-5.3 + deepseek-v4-flash (Go, mix families) | claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol (frontier, max diversity) | family diversity + per-lens competence |
| `skill-author` | authoring new skills | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | minimax-m3 (alt glm-5.2, qwen3.7-max) | claude-sonnet-5 (qwen3.7-max is Go-only IF leader) | IFBench 79.1; Thinkbench existing-code parity |
| `skill-reviewer` | reviewing skill drafts | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt glm-5.2) | claude-opus-5 (peak: claude-fable-5) | SWE-bench Verified (highest reasoning) |

### Routing update — 2026-08-25

Full-sweep pass via the `optimizing-model-routing` skill; evidence and
per-role analysis in [model-check-2026-08-25.md](model-check-2026-08-25.md).
All previously bound IDs remain catalog-valid (no stale bindings).
New evidence: Artificial Analysis Intelligence Index v4.1.1 (independent
harness, retrieved 2026-08-25).

- `implementer` / `test-writer` Go: kimi-k2.7-code → **kimi-k3** (AA 60
  vs 43; K2.7 stays alt pending a K3 MCPMark run).
- `triager` Go: hy3 → **glm-5.3** (AA 60 vs 42 — hy3 held the seat from
  the ling-era persona default with no bench behind it); Zen: gpt-5.4-mini
  / claude-haiku-4-5 → **gpt-5.6-luna** (AA 52 at $0.05/task, 141 t/s —
  the bulk-triage profile; gpt-5.4-mini stays alt).
- `council-member` Go mix: hy3 + mimo-v2.5 + deepseek-v4-flash →
  **kimi-k3 + glm-5.3 + deepseek-v4-flash** (42/38/52 → 60/60/52; three
  families preserved).
- `planner` Go: glm-5.3 confirmed — its 2026-08-14 "until independently
  benched" caveat is discharged (AA 60); alt moves glm-5.2 → kimi-k3. The
  "hardest: gpt-5.6-luna" annotation is **dropped** (AA 52, below its
  Go-tier peers; luna's strengths are cost/speed, now reflected in the
  triager Zen seat). Hardest planner work escalates to Zen claude-opus-5.
- Free defaults and all `agents/*.md` bindings: **unchanged** — the
  prescribed free-generalist head-to-head re-run (new candidates
  muse-spark-1.2-contributor-free, x-preview-f-free, ox-alpha-free,
  big-pickle, nemotron-3.5-lightning-free, hy3-free, laguna-s-2.1-free)
  is still pending and gates any free-seat change.
- Watch list: kimi-k3 and deepseek-v4-flash-vision-exp are Go-tier
  multimodal candidates for `vision-critic-fast` (no vision-quality
  evidence yet — bench before switching); qwen3.8-max (AA 58) replaces
  qwen3.7-max as the skill-author IF-escalation watch.
- Grok family scores 61 on AA — still hard-excluded (user directive
  2026-08-14); recorded so the exclusion is visibly applied, not
  overlooked.

### Routing update — 2026-08-30

Full-sweep pass via the `optimizing-model-routing` skill; evidence and
per-role analysis in [model-check-2026-08-30.md](model-check-2026-08-30.md).
All previously bound IDs remain catalog-valid (no stale bindings).
Live catalog fetch 2026-08-30; independent evidence reinforced:
Artificial Analysis Intelligence Index v4.1.1 (retrieved 2026-08-06);
KingBench 3 91.25% (GLM-5.3, independent); Ante harness Terminal-Bench
2.1 82.7% (DeepSeek V4 Flash 0731, independent, 2026-08-09);
MCPMark Verified 81.1% (Kimi K2.7 Code, BenchLM, 2026-08-29).
**No binding changes** — all current bindings remain optimal per
objective evidence. Free generalist re-validation (head-to-head per
Update procedure step 4) still pending for current free roster.
Watch list updates: `gemini-3.7-flash` (vision-critic-fast candidate,
bench before switching); `qwen3.8-max` (skill-author IF watch);
`deepseek-v4-flash-vision-exp` (Go multimodal candidate, bench before
switching). Grok family remains hard-excluded (user directive 2026-08-14).

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
  `qwen3.7-max`, `qwen3.7-plus`, `grok-4.5` (later **hard-excluded** — see
  Hard exclusions), and **`hy3` / `hy3-preview` are
  now Go flat-rate models** (usable as a Go-escalation generalist). Note
  **`qwen3.7-*` is Go-only** — bind it as a Go escalation, never as a Zen one.

### Official-release refresh — 2026-08-02 (this update)

DeepSeek shipped the official V4-Flash release (`DeepSeek-V4-Flash-0731`,
public beta, 2026-07-31), superseding the preview with a **re-post-trained
checkpoint** (same 284B / 13B-active architecture) aimed squarely at
agentic/tool-orchestration work. The free catalog ID
`deepseek-v4-flash-free` serves this build (assumption: the opencode free
endpoint points the ID at the current official model). **The free tier's
coding model is now also its strongest engineering-reasoning model**, so the
free default for the `planner` (design) role moves from
`ling-3.0-flash-free` to `deepseek-v4-flash-free` (ling stays as the
reliability alt), and the `council-architecture` lens moves to it too. See
Per-role rationale.

Agentic benchmarks (vendor-stated — DeepSeek harness, minimal mode, max
effort; no independent reproduction as of 2026-07-31; the GLM-5.2 / Opus-4.8
columns are DeepSeek-harness figures, so read the cross-model rows as
directional, not settled):

| Benchmark | Flash-0731 | Flash-preview | Pro-preview | GLM-5.2 | Opus-4.8 |
|---|---|---|---|---|---|
| Terminal Bench 2.1 | 82.7 | 61.8 | 72.1 | 81.0 | 85.0 |
| DeepSWE | 54.4 | 7.3 | 12.8 | 46.2 | 58.0 |
| Toolathlon-Verified | 70.3 | 49.7 | 55.9 | 59.9 | 76.2 |
| DSBench-FullStack | 68.7 | 37.0 | 41.8 | 61.8 | 71.6 |
| DSBench-Hard | 59.6 | 25.8 | 31.1 | 54.5 | 71.7 |
| NL2Repo | 54.2 | 39.4 | 38.5 | 48.9 | 69.7 |
| Cybergym | 76.7 | 38.7 | 52.7 | — | 83.1 |
| AutomationBench Public | 25.1 | 10.8 | 12.8 | 12.9 | 27.2 |

Preview-era engineering / reasoning (official technical report, Max mode):
SWE-bench Verified 79.0 (Pro-Max 80.6) · LiveCodeBench 91.6 · GPQA Diamond
88.1 · MMLU-Pro 86.4. Semi-independent: Artificial Analysis Intelligence
Index ≈ 50 (median 17) for 0731 — directional corroboration of general
strength, not of the specific agent scores above.

Read with the standing caveat (benchmarks are a tier filter, not a ranking):
the controlled within-family jump (preview → official) and the preview
report's engineering scores are the solid signal; the GLM-5.2 comparisons
are cross-harness and directional only.

### Catalog re-check — 2026-08-14 (this update)

Re-fetched both catalogs (`https://opencode.ai/zen/v1/models` and
`https://opencode.ai/zen/go/v1/models`; full audit in
`reference/catalog-check-2026-08-14.md`). Material changes:

- **`ling-3.0-flash-free` removed from the catalog** (absent from Zen and
  Go on 2026-08-14). This was the validated free generalist (2026-07-26
  head-to-head) holding the `triager`, `skill-author`, `skill-reviewer`
  defaults, the `planner` no-tool alt, and the council chairman / UX /
  product seats. All those seats rebind to **`nemotron-3-ultra-free`**
  (catalog-verified, prior validation: 10/10 planning rigor in the 07-26
  eval; caveat: intermittent streaming errors observed under load — see
  Free-tier caveats). `north-mini-code-free` (named as a validated alt) is
  also gone. Re-run the head-to-head (Update procedure step 4) before any
  further free-generalist changes; `nemotron-3.5-lightning-free`,
  `muse-spark-1.2`, `big-pickle`, and `hy3-free` are the new candidates.
- **`hy3-free` is back in the Zen catalog** (the 07-25 removal record is
  stale; re-added by 08-14). Not rebound — the seat went to nemotron —
  but it belongs in the re-validation pool as the pre-ling generalist.
- **New Go models:** `glm-5.3` (successor to glm-5.2 — planner / debugger /
  reviewer escalation moves to it; glm-5.2 stays as the alt until 5.3 is
  independently benched), `qwen3.8-max` (successor to qwen3.7-max — watch
  for the skill-author IF escalation), **`gpt-5.6-luna`** (frontier-grade
  generalist now on the flat rate — the strongest Go option for hardest
  planner/reviewer work), `mimo-v2.5-pro`, `mimo-v2-pro`, `mimo-v2-omni`.
- **New Zen models:** `gemini-3.7-flash` (vision-critic-fast candidate —
  bench before switching), `gpt-5.4-pro`, `gpt-5.5-pro`, `gpt-5.3-codex`;
  `glm-5.2/5.1/5` and `deepseek-v4-pro` are now also on Zen. `grok-4.6` /
  `grok-build-0.1` are **hard-excluded** — see Hard exclusions.
- **GLM is no longer Go-only:** glm-5.2/5.1/5 now also appear on Zen (the
  07-25 "Go escalation" framing still holds for the escalation row, but Zen
  binding is now technically possible if ever needed).

### Catalog re-check — 2026-08-30 (this update)

Re-fetched both catalogs (`https://opencode.ai/zen/v1/models` and
`https://opencode.ai/zen/go/v1/models`; live fetch 2026-08-30). Material
changes:

- **`ling-3.0-flash-free` remains removed** from the catalog (absent from
  Zen and Go on 2026-08-30). The validated free generalist is gone;
  `nemotron-3-ultra-free` continues to hold the generalist seats.
- **`north-mini-code-free` remains removed** from the catalog.
- **`hy3-free` is absent from the free catalog** — only `hy3` and
  `hy3-preview` exist on Go flat-rate. The 2026-08-14 "re-added" note is
  stale; no free `hy3-free` exists as of 2026-08-30.
- **Free tier new/present IDs:** `ling-3.0-flash-fin-free` (different ID
  from removed `ling-3.0-flash-free`), `muse-spark-1.2-contributor-free`,
  `nemotron-3.5-lightning-free`, `laguna-s-2.1-free`, `big-pickle`
  (Zen, not free). None independently benched; head-to-head re-run
  (Update procedure step 4) required before binding.
- **Go tier confirmed:** `glm-5.3`, `qwen3.8-max`, `gpt-5.6-luna`,
  `kimi-k3`, `deepseek-v4-flash-vision-exp`, `hy3`, `hy3-preview`,
  `mimo-v2.5-pro`, `mimo-v2-pro`, `mimo-v2-omni` all catalog-verified.
- **Zen tier confirmed:** `gemini-3.7-flash`, `gpt-5.4-pro`, `gpt-5.5-pro`,
  `gpt-5.3-codex`, `glm-5.2/5.1/5`, `deepseek-v4-pro`, `grok-4.6`,
  `grok-build-0.1` (hard-excluded) all catalog-verified.
- **Grok family** (`grok-4.5` Go, `grok-4.6` Zen, `grok-build-0.1` Zen)
  present in catalogs but **hard-excluded** per user directive 2026-08-14.

### Hard exclusions

Never bind, recommend, or escalate to these models in any tier, for any
persona or workflow. This is a user directive, dated 2026-08-14.

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `grok-4.5` | Go, Zen | user directive (2026-08-14): grok family excluded from everything |
| `grok-4.6` | Zen | same |
| `grok-build-0.1` | Zen | same |

The exclusion supersedes any earlier mention (e.g. the 07-25 "New Go
models" record above is historical only). When a new grok-* ID appears in a
catalog fetch, treat it as excluded automatically — do not add it to any
table, roster, or watch list.

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
`ling-3.0-flash-free` was the free generalist default, with
`nemotron-3-ultra-free` the strong alt for peak planning rigor. **Since
2026-08-14** `ling-3.0-flash-free` is gone from the catalog, so
`nemotron-3-ultra-free` now holds the generalist seats — its streaming
caveat is the standing reliability risk, and re-validating it (plus
`nemotron-3.5-lightning-free`, `hy3-free`, `muse-spark-1.2`, `big-pickle`)
via the head-to-head eval is the prescribed next step (Update procedure
step 4). For risk-bearing tasks
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
  (≥ 88.6 Verified) for hardest architecture. **Free default (2026-08-02,**
  **superseded 2026-08-14 on the alt only):** `deepseek-v4-flash-free` — the
  0731 official build was re-post-trained for
  agentic work and now matches/exceeds GLM-5.2 on DeepSeek-harness agent
  benchmarks (Terminal Bench 2.1 82.7 vs 81.0, DeepSWE 54.4 vs 46.2), and
  planning in practice is tool-heavy (codebase research, grepping, artifact
  writes) — exactly the 0731 gains' home turf. `nemotron-3-ultra-free` now
  holds the no-tool generalist alt (ling was removed 2026-08-14); re-run the
  2026-07-26 head-to-head before any further switch (see Update procedure
  step 4). **Go escalation (2026-08-14):** `glm-5.3` (successor to 5.2),
  with `gpt-5.6-luna` — frontier-grade at flat rate — for the hardest
  architecture.
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
  score: the free default mixes nemotron / mimo / deepseek (three families;
  ling's seat passed to nemotron on 2026-08-14 after ling was removed from
  the catalog);
  the frontier opt-in mixes Anthropic / Google / OpenAI (Opus-5 / Gemini-3.1-
  pro / GPT-5.6) for maximal independent perspective. The
  `council-architecture` lens (engineering analysis: patterns, tech debt,
  testability) moved to `deepseek-v4-flash-free` on 2026-08-02 — the
  strongest free engineering-reasoning model — rebalancing the default
  council to 2 ling / 2 deepseek / 1 mimo while keeping all three families
  represented. (Since 2026-08-14 the 2 ling seats are nemotron: council =
  3 nemotron / 2 deepseek / 1 mimo — three families still represented.)
- **skill-author** — scaffolded/existing-code authoring → MiniMax M3
  (existing-code parity 0.999–1.000 with GLM, 3.7× cheaper); IFBench leader
  `qwen3.7-max` (79.1, Go-only) is the instruction-following escalation
  (watch `qwen3.8-max`, its Go successor, for the next bench round).
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
`gemini-3.5-flash` / `gemini-3.6-flash`; `gemini-3.7-flash` (newest flash,
2026-08-14) is the upgrade candidate — bench its vision judgment before
switching.

## Deprecation watch (from Zen docs, 2026-07-03; refreshed 2026-07-25; re-checked 2026-08-30)

| Model | Deprecation date | Action |
|---|---|---|
| `hy3-free` (free tier) | **absent from free catalog 2026-08-30** (only `hy3`/`hy3-preview` on Go) | do not bind; re-validate if re-added |
| `ling-3.0-flash-free` (free tier) | **2026-08-14 (removed from catalog)** | use `nemotron-3-ultra-free` (free) or escalate |
| `north-mini-code-free` (free tier) | **2026-08-14 (removed from catalog)** | use `nemotron-3-ultra-free` (free) or escalate |
| GPT 5.2/5.1/5 Codex variants | 2026-07-23 | avoid in new bindings |
| Kimi K2.5 | 2026-08-05 (due; still listed 2026-08-30) | use kimi-k2.7-code (or kimi-k3) |
| MiniMax M2.5 | 2026-08-05 (due; still listed 2026-08-30) | use minimax-m3 / m2.7 |
| Claude Opus 4.1 | 2026-08-05 (past) | use opus-4-8 (or opus-5) |
| GLM 5 | 2026-05-14 (past) | use glm-5.2 (or glm-5.3) |

New and safe to bind (2026-07-25; refreshed 2026-08-30): `claude-opus-5`,
`claude-fable-5`, `gpt-5.6-*` (`gpt-5.6-luna` also on Go flat-rate),
`gemini-3.5/3.6-flash` (and `gemini-3.7-flash`, newest), `kimi-k3`,
`qwen3.7-max/plus` (Go-only), `qwen3.8-max` (Go, watch for benches), `hy3` /
`hy3-preview` (Go flat-rate), `glm-5.3` (Go), and the free roster
`nemotron-3-ultra-free` (current free generalist; `nemotron-3.5-lightning-free`,
  `muse-spark-1.2-contributor-free`, `ling-3.0-flash-fin-free`, `big-pickle`,
  `laguna-s-2.1-free` also in the catalog — see caveats; validate before
  binding). **Grok family is hard-excluded** — see Hard exclusions.

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
`deepseek-v4-flash` and `mimo-v2.5`, which remain the Go escalation rows);
free roster re-verified 2026-08-30 (ling removed → nemotron holds the
generalist seats; `ling-3.0-flash-fin-free`, `muse-spark-1.2-contributor-free`,
`nemotron-3.5-lightning-free`, `laguna-s-2.1-free` also present).

### Free-model roster

| Role | Free model (catalog ID) | Maps to existing role row |
|---|---|---|
| `planner` (single-task) | `opencode/deepseek-v4-flash-free` (alt `opencode/nemotron-3-ultra-free`) | `planner` (glm-5.3 / claude-opus) |
| `chairman` / council planner seat | `opencode/nemotron-3-ultra-free` | `planner` (glm-5.3 / claude-opus) |
| `implementer` / `test-writer` / `debugger` (coding) | `opencode/deepseek-v4-flash-free` | `implementer` (kimi-k2.7-code) |
| `devops` / CI / cloud / security | `opencode/mimo-v2.5-free` | `triager` (mimo-v2.5) |

### Activation + routing (free-tier mode)

- **Toggle:** `AI_FRAMEWORK_FREE_TIER=1` selects this mode. The escalation
  rows above remain the default-capable path; with the toggle on, every task
  uses a free model even when Go/Zen keys are present.
- **Single-task execution** uses the one mapped free model (no council) to
  conserve free quota:
  - planning / design → `opencode/deepseek-v4-flash-free` (nemotron alt for
    no-tool generalist planning)
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
  - A — `opencode/nemotron-3-ultra-free`: primary planner (kept off
    deepseek for family diversity even though single-task planning defaults
    to deepseek — the council optimizes diversity over single-model peak;
    ling held this seat until its 2026-08-14 catalog removal).
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
  - C — `opencode/nemotron-3-ultra-free`: plan/architecture coherence +
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
