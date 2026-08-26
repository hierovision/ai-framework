# Model Check + Right-Sizing — 2026-08-25

Full-sweep routing pass over all roles, run by the
`optimizing-model-routing` skill. Coverage: every skill → role; mutation:
role rows in model-routing.md (no agent free-default line changes).

## Sources

- Zen catalog (PAYG): `https://opencode.ai/zen/v1/models` — retrieved
  2026-08-25, live fetch, 64 entries
- Go catalog (flat-rate): `https://opencode.ai/zen/go/v1/models` —
  retrieved 2026-08-25, live fetch, 30 entries
- Artificial Analysis Intelligence Index v4.1.1 (leaderboard + model
  pages) — retrieved 2026-08-25, **independently reproduced** (AA runs
  its own published harness; index = 9 evals incl. Terminal-Bench v2.1,
  agentic tool-use, GDPval-AA). Reasoning-effort "max" variants scored.
- Prior recorded evidence (Thinkbench, MCPMark Verified, IFBench —
  2026-07-06 records in model-routing.md) — used as the multi-source
  context for incumbents.
- vals.ai — unreachable (404), not used.

## Current bindings (validated against live catalogs)

All currently bound IDs remain catalog-valid — **no stale bindings this
pass**. Agents (free defaults): build/design/council-architecture/
council-performance = `deepseek-v4-flash-free`; triage/council/
council-product/council-ux = `nemotron-3-ultra-free`; council-security =
`mimo-v2.5-free`. Grok family present in catalogs and auto-excluded
(user directive 2026-08-14).

## Per-role analysis

- **planner** — free: DeepSeek V4 Flash 0731 = AA 52 (strongest free
  generalist/coder; ties GLM-5.2-max 53, beats MiniMax-M3 45, K2.7-Code
  43) → stays. Go: **GLM-5.3 = AA 60** — the 2026-08-14 "until
  independently benched" caveat is now discharged; it ties Kimi K3 as
  the top open-weight score and is much faster (90 t/s, 29 s end-to-end
  vs K3's 35 t/s, 74 s) → stays, now evidence-backed. **The "hardest:
  gpt-5.6-luna" annotation is contradicted**: Luna (max) = AA 52, eight
  points BELOW glm-5.3 / kimi-k3 on the same Go tier; Luna's strengths
  are cost ($0.05/task) and speed (141 t/s), not frontier quality.
  Proposed: drop the annotation; hardest planner work escalates to Zen
  `claude-opus-5` (AA 63, top of index).
- **implementer / test-writer** — free: deepseek-v4-flash-free (52)
  stays. Go: kimi-k2.7-code = AA 43; **kimi-k3 = AA 60** (successor,
  same lab whose specialty is agentic coding; image-in capable). The
  17-point gap is far outside noise. K3 has no MCPMark run yet (K2.7's
  81.1 was the role-matched pick in July) → proposed move with the gap
  flagged (see Questionable). Zen: claude-sonnet-5 (max 55) stays.
- **triager** — free: nemotron-3-ultra-free (Nemotron 3 Ultra = AA 38;
  streaming caveat stands) stays — no better-validated free generalist.
  Go: hy3 = AA 42 — weak vs Go peers (glm-5.3 60, deepseek-v4-pro 53);
  the hy3 seat dates from the ling-era persona default → proposed
  **glm-5.3** (alt deepseek-v4-pro). Zen: gpt-5.4-mini / haiku-4-5 —
  gpt-5.4-mini does not appear in AA's visible top tier; **gpt-5.6-luna
  (max) = AA 52 at $0.05/task, 141 t/s** is the evidenced bulk-triage
  profile (large-volume summaries, cheap + fast) → proposed.
- **debugger / reviewer** — free deepseek (52) / Go glm-5.3 (60) / Zen
  sonnet-5 (55), gpt-5.4 → all unchanged; the glm-5.3 promotion caveat
  discharges as above.
- **vision-critic-fast** — Go minimax-m3 (AA 45; multimodal; UI-CSS
  judgment still unconfirmed — standing caveat). New multimodal Go
  options: **kimi-k3 (60, image-in confirmed on AA model page)** and
  **deepseek-v4-flash-vision-exp (51)**. No vision-quality bench
  (MMMU-Pro per-model, or the correcting-ui loop) separates them on the
  role's actual trait → no binding change; both recorded as candidates.
- **vision-critic-final** — gemini-3.1-pro stays (vision-quality seat;
  AA text index 48 is not the trait; no vision-arena data this pass).
- **council-member** — free mix (nemotron + mimo + deepseek families)
  unchanged — all valid. Go mix currently hy3 + mimo-v2.5 +
  deepseek-v4-flash (42/38/52) → proposed **kimi-k3 + glm-5.3 +
  deepseek-v4-flash** (60/60/52; three families: Kimi / Z.AI / DeepSeek;
  strictly stronger at equal diversity). Zen frontier mix unchanged.
- **skill-author** — free nemotron stays. Go minimax-m3 stays (the
  role-matched evidence — Thinkbench existing-code parity 0.999–1.000
  with GLM at 3.7× lower cost — still governs over the general index).
  `qwen3.8-max` (AA 58) replaces qwen3.7-max as the IF-escalation watch
  candidate, but no IFBench run for it exists yet → watch, not bind.
  Zen claude-sonnet-5 stays.
- **skill-reviewer** — free nemotron / Go glm-5.3 (now evidence-backed) /
  Zen claude-opus-5 (63, peak fable-5 62-with-fallback) → unchanged.

## Proposed bindings

| Role | Free | Go | Zen | Change |
|---|---|---|---|---|
| planner | deepseek-v4-flash-free | glm-5.3 (alt kimi-k3) | claude-opus-5 (peak fable-5) | drop "hardest: gpt-5.6-luna" annotation |
| implementer | deepseek-v4-flash-free | **kimi-k3** (alt kimi-k2.7-code) | claude-sonnet-5 | Go rebind |
| test-writer | deepseek-v4-flash-free | **kimi-k3** (alt kimi-k2.7-code) | claude-sonnet-5 | Go rebind |
| triager | nemotron-3-ultra-free | **glm-5.3** (alt deepseek-v4-pro) | **gpt-5.6-luna** (alt gpt-5.4-mini) | Go + Zen rebind |
| debugger | deepseek-v4-flash-free | glm-5.3 | claude-sonnet-5, gpt-5.4 | none (caveat discharged) |
| reviewer | deepseek-v4-flash-free | glm-5.3 | claude-sonnet-5, gpt-5.4 | none (caveat discharged) |
| vision-critic-fast | — | minimax-m3 | gemini-3-flash | none (candidates recorded) |
| vision-critic-final | — | — | gemini-3.1-pro | none |
| council-member | nemotron + mimo + deepseek (family mix) | **kimi-k3 + glm-5.3 + deepseek-v4-flash** | opus-5 + gemini-3.1-pro + gpt-5.6-sol | Go mix upgraded |
| skill-author | nemotron-3-ultra-free | minimax-m3 (watch qwen3.8-max IF) | claude-sonnet-5 | none |
| skill-reviewer | nemotron-3-ultra-free | glm-5.3 | claude-opus-5 | none (caveat discharged) |

No `agents/*.md` free-default line changes (all free picks retain).

## Questionable / uncertain

- **kimi-k3 lacks an MCPMark run** — the implementer/test-writer move
  rests on the AA general+agentic index (60 vs 43, independent), not the
  role's specific tool-orchestration bench. A K3 MCPMark score below
  K2.7's 81.1 would argue for keeping K2.7. *Resolve: MCPMark Verified
  run of K3.*
- **AA scores "max" reasoning-effort variants** — the opencode catalog
  IDs may default to a lower effort, so realized quality could differ
  from the benched figure for kimi-k3 / glm-5.3 / luna alike.
  *Resolve: spot-check a live invocation's effort behavior.*
- **gpt-5.6-luna demoted from "frontier-grade at flat rate"** (08-14
  claim) — AA max-effort 52 vs glm-5.3/kimi-k3 60 on the same tier. The
  08-14 note had no bench for luna; today's independent data contradicts
  the label. Luna remains excellent on cost/speed (its triager-Zen
  proposal here uses exactly those strengths).
- **New free-tier candidates unvalidated**: `muse-spark-1.2-contributor-
  free` (underlying Muse Spark 1.2 xhigh = AA 57 — potentially the
  strongest free generalist, but the "-contributor" variant's
  equivalence to the benched model is unverified), `x-preview-f-free`,
  `ox-alpha-free` (no AA entries), `big-pickle`, `laguna-s-2.1-free`,
  `nemotron-3.5-lightning-free`, `hy3-free`. The 08-14 prescribed
  head-to-head re-run is still pending. *Resolve: run the free-generalist
  head-to-head eval (Update procedure step 4).*
- **Vision seats**: kimi-k3 and deepseek-v4-flash-vision-exp are Go-tier
  multimodal candidates with no UI-judgment or MMMU-Pro evidence;
  deepseek's ID is explicitly experimental (`-exp`). The standing M3
  caveat (evaluate UI-CSS judgment in the correcting-ui loop) now
  applies to all three. *Resolve: vision-quality bench or the
  correcting-ui eval loop.*
- **Single-source decisions**: today's new numbers all come from one
  independent lab (AA). Independent > vendor, but no second independent
  source cross-checks glm-5.3's 60 / kimi-k3's 60. *Resolve: a second
  independent leaderboard covering them.*
- **deepseek-v4-pro on Go** (AA 53) — viable triager alt; not promoted
  to a primary seat because its Go build's parity with the benched 0813
  build is unconfirmed.
- **grok family** scores high on AA (grok-4.6 high = 61) — excluded by
  user directive regardless of score; recorded here so the exclusion is
  visibly applied, not overlooked.

## Applied

Applied 2026-08-25 — user approved the proposed table as-is. Changes
landed in `reference/model-routing.md` only (Routing update — 2026-08-25
section + role rows + status header); no `agents/*.md` changes (all free
defaults retain). Verifier:
`python3 skills/optimizing-model-routing/scripts/verify_rebind.py
--repo . --expect <generated>` — exit 0 (9 agent bindings checked,
3 forbidden ids absent, artifact + update marker verified). Branch:
`chore/model-rebind-2026-08-25` (commit + PR; user merges).
