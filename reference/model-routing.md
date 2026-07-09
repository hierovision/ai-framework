# Model Routing

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

- Retrieved: 2026-07-03 (catalog/pricing); benchmark evidence added
  2026-07-06 (sources in "Benchmark evidence" below)
- Review cadence: monthly, or when a deprecation notice lands
- Status: catalog + pricing current; the `skill-author`, `skill-reviewer`,
  and `vision-critic-*` rows are now **evidence-backed** (2026-07-06) and
  partly **empirically confirmed** by six authoring rounds in this repo.
  Other rows remain seeded from positioning pending the Phase 5 harness.

## Contents

- Roles → bindings
- Benchmark evidence (2026-07-06)
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
| `vision-critic-fast` | UI loop, routine passes | minimax-m3 (natively multimodal — evaluate for UI screenshots) | gemini-3-flash, gpt-5.4-mini |
| `vision-critic-final` | UI loop, final review | — | gemini-3.1-pro, claude-sonnet-5 |
| `council-member` | multi-perspective review | glm-5.2 + minimax-m3 + qwen3.7-max (mix families) | mix: claude + gpt + gemini |
| `skill-author` | authoring new skills via `authoring-skills` | **minimax-m3 (default)**, glm-5.2 (escalation) | qwen3.7-max (instruction-following), claude-sonnet-5 |
| `skill-reviewer` | reviewing skill drafts, foundation work | — | **claude-opus-4-8 (default)**, claude-fable-5 (peak only) |

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
  `test-writer` candidate given heavy file/tool orchestration.
- **Multimodal:** MiniMax M3 is natively multimodal (image/video in) and
  on Go's flat rate — the only cheap open model that reads a screenshot
  without a bolt-on. Directly relevant to `vision-critic-fast` (may move
  routine UI-loop vision off Zen billing — evaluate before relying on it).

**Rationale for the changed rows:**
- `skill-author` → **minimax-m3 default.** Existing-code parity with GLM
  (0.999–1.000), 3.7× cheaper on Zen ($0.30/$1.20 vs $1.40/$4.40) and
  ~3.7× more requests per Go dollar-cap (~16k/mo vs ~4.3k/mo) — directly
  fixes the Go weekly-limit exhaustion. `glm-5.2` stays as the escalation
  for any skill where authoring quality wobbles (subtle/greenfield-ish);
  `qwen3.7-max` is the instruction-following escalation.
- `skill-reviewer` → **opus-4-8 default.** 88.6 Verified / 69.2 Pro —
  highest of any buyable model; Fable 5 (95.0) is 2× the price and
  export-suspended, so reserve it for peak architecture calls only. This
  confirms the user's cost-driven Fable-5→Opus-4.8 switch as correct.
- `skill-author` Zen escalation dropped **claude-sonnet-5**: at $3/$15 it
  is premium for *volume* scaffolded authoring and a *downgrade* from
  Opus 4.8 for review — it has no clear home in this two-role setup.

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
Tiered strategy (locked decision): cheap model per iteration pass, strong
model for final signoff. **Update 2026-07-06:** most Go open models are
weak/absent on vision, but **MiniMax M3 is natively multimodal** (image +
video in) and on Go's flat rate. If M3's screenshot judgment proves good
enough for routine `vision-critic-fast` passes, the fast tier can run on
the flat-rate Go plan instead of Zen billing — a material Phase 3 cost
saving. Not yet confirmed for UI-CSS judgment specifically (M3's
multimodal wins are on SVG-Bench / BrowseComp, not UI critique); evaluate
in the `correcting-ui` eval loop before relying on it. `vision-critic-final`
stays Zen (gemini-3.1-pro / claude-sonnet-5) for sign-off.

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
