# Model Check + Right-Sizing — 2026-08-30

## Sources

- Zen catalog (https://opencode.ai/zen/v1/models) — retrieved 2026-08-30 (live fetch)
- Go catalog (https://opencode.ai/zen/go/v1/models) — retrieved 2026-08-30 (live fetch)
- Artificial Analysis Intelligence Index v4.1.1 — retrieved 2026-08-06, independence status: **independently reproduced** (9 evals: GDPval-AA v2, τ³-Banking, Terminal-Bench v2.1, SciCode, HLE, GPQA Diamond, CritPt, AA-Omniscience, AA-LCR)
- Thinkbench autonomous coding loop — retrieved 2026-06-19, independence status: **independently reproduced** (thinkwright, 72 tasks, 3 trials/task, cache-aware cost)
- Ante harness Terminal-Bench 2.1 reproduction — retrieved 2026-08-09, independence status: **independently reproduced** (Antigma Labs, 445 trials, Harbor published)
- GLM-5.3 KingBench 3 — retrieved 2026-08-14, independence status: **independently reproduced** (fixed prompt set across Fable 5, Opus 5, Opus 4.8, Kimi K3, Qwen3.8 Max)
- MCPMark-Verified leaderboard (BenchLM) — retrieved 2026-08-29, independence status: **independently reproduced** (Kimi K2.7 Code 81.1%)
- DeepSeek V4 Flash 0731 vendor benchmarks — vendor self-reported (DeepSeek Harness, not independently reproduced except TB 2.1 by Ante)
- Kimi K3 technical report (arXiv:2607.24653v2) — vendor self-reported (MCPMark 94.5%, other agentic benches)

## Current bindings

| Role | Free default | Escalation — Go | Escalation — Zen | Agent binding (free) |
|---|---|---|---|---|
| planner | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt kimi-k3) | claude-opus-5 (peak: claude-fable-5) | design: deepseek-v4-flash-free |
| implementer | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 (alt gpt-5.4) | build: deepseek-v4-flash-free |
| triager | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt deepseek-v4-pro) | gpt-5.6-luna (alt gpt-5.4-mini) | triage: nemotron-3-ultra-free |
| test-writer | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | — |
| debugger | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | — |
| reviewer | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | — |
| vision-critic-fast | — | minimax-m3 | gemini-3-flash (alt gpt-5.4-mini) | — |
| vision-critic-final | — | — | gemini-3.1-pro (alt claude-sonnet-5) | — |
| council-member | nemotron-3-ultra-free + mimo-v2.5-free + deepseek-v4-flash-free | kimi-k3 + glm-5.3 + deepseek-v4-flash | claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol | council-arch: deepseek-v4-flash-free; council-sec: mimo-v2.5-free; council-perf: deepseek-v4-flash-free; council-ux: nemotron-3-ultra-free; council-prod: nemotron-3-ultra-free; council: nemotron-3-ultra-free |
| skill-author | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | minimax-m3 (alt glm-5.2, qwen3.7-max) | claude-sonnet-5 | — |
| skill-reviewer | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt glm-5.2) | claude-opus-5 | — |

## Per-role analysis

### planner (design, architecture)
**Dominant trait:** autonomous-loop reasoning on existing code
**Candidates considered:**
- deepseek-v4-flash-free (free): serves DeepSeek V4 Flash 0731 — AA 50, TB 2.1 82.7% (indep. Ante), DeepSWE 54.4, Toolathlon 70.3. Strong agentic coding model.
- nemotron-3-ultra-free (free alt): serves Nemotron 3 Ultra — AA 38.3. Lower intelligence index.
- glm-5.3 (Go): AA 60 (tied top open), KingBench 3 91.25% (indep., beats Fable 5 82.5%), TB 3.0 28.3%, DeepSWE 66.9%, Agentic rank #6 (96th %ile). Best independently verified reasoning.
- kimi-k3 (Go alt): AA 60, MCPMark 94.5% (vendor), GDPval 1686. Strong but MCPMark vendor-only.
- claude-opus-5 (Zen): AA 63 (top proprietary). Peak escalation.
- claude-fable-5 (Zen alt): AA 62.

**Why winner wins:** Free default stays deepseek-v4-flash-free — the 0731 build now has independent TB 2.1 verification (82.7%) and AA 50, making it the strongest free model for agentic planning work. Go escalation stays glm-5.3 — independent KingBench 3 (91.25%) and AA 60 confirm it as the strongest open reasoning model. Zen stays claude-opus-5 (AA 63) for peak.

### implementer (implement backend/frontend)
**Dominant trait:** tool + file orchestration
**Candidates considered:**
- deepseek-v4-flash-free (free): TB 2.1 82.7% (indep.), Toolathlon 70.3. Strong tool use.
- kimi-k3 (Go): MCPMark 94.5% (vendor), Toolathlon 76.5%, K2.7 81.1% (indep. BenchLM). Best tool-use evidence.
- kimi-k2.7-code (Go alt): MCPMark 81.1% (indep.), Toolathlon not current.
- claude-sonnet-5 (Zen): SWE-bench Verified 85.2. Cost/quality balance.
- gpt-5.4 (Zen alt): SWE-bench Verified ~88.7.

**Why winner wins:** Free default stays deepseek-v4-flash-free (independent TB 2.1 82.7%). Go escalation stays kimi-k3 — vendor MCPMark 94.5% and indep. K2.7 81.1% make it the tool-use leader. Zen stays claude-sonnet-5 for cost/quality.

### triager (triage, bulk edits, summaries)
**Dominant trait:** generalist quality + reliability
**Candidates considered:**
- nemotron-3-ultra-free (free): AA 38.3. Was validated in 2026-07-26 head-to-head (10/10 triage + planning). Streaming errors under load observed.
- deepseek-v4-flash-free (free alt): AA 50, TB 2.1 82.7% (indep.). Stronger on paper but not re-validated in head-to-head.
- glm-5.3 (Go): AA 60. Strongest open generalist.
- gpt-5.6-luna (Zen): AA ~52 (max), $0.05/task, 141 t/s. Cost/speed profile for bulk triage.
- gpt-5.4-mini (Zen alt): AA lower, cheaper.

**Why winner wins:** Free default stays nemotron-3-ultra-free — the 2026-07-26 clean-room head-to-head validated it (10/10 triage, 10/10 planning rigor). The prescribed re-run (Update procedure step 4) gates any free-seat change. Go stays glm-5.3 (AA 60). Zen stays gpt-5.6-luna for bulk-triage profile (cost/speed).

### test-writer (unit/integration/e2e authoring)
**Dominant trait:** tool + file orchestration (same as implementer)
**Candidates considered:** Same as implementer.
**Why winner wins:** Same rationale as implementer. Keep current.

### debugger (test-failure analysis)
**Dominant trait:** defect localization + loop reasoning
**Candidates considered:**
- deepseek-v4-flash-free (free): TB 2.1 82.7% (indep.), DeepSWE 54.4.
- nemotron-3-ultra-free (free alt): AA 38.3.
- glm-5.3 (Go): KingBench 3 91.25% (indep.), TB 3.0 28.3%, DeepSWE 66.9%. Thinkbench lineage (GLM-5.2 92% full-pass).
- glm-5.2 (Go alt): Thinkbench 92% full-pass / 0.976 mean (indep.). On existing-code tasks 0.999–1.000.
- claude-sonnet-5 / gpt-5.4 (Zen): SWE-bench Verified 85.2 / 88.7.

**Why winner wins:** Free stays deepseek-v4-flash-free (independent TB 2.1). Go stays glm-5.3 (KingBench 3 independent 91.25%, Thinkbench lineage). Zen stays claude-sonnet-5 / gpt-5.4.

### reviewer (code review)
**Dominant trait:** defect localization + loop reasoning (same as debugger)
**Why winner wins:** Same rationale as debugger. Keep current.

### vision-critic-fast (UI loop, routine passes)
**Dominant trait:** native multimodality (hard gate)
**Candidates considered:**
- minimax-m3 (Go): native multimodal (image/video in), on Go flat rate. Only cheap open model with native screenshot reading.
- gemini-3.7-flash (Zen): new flash, vision candidate — not yet benched for UI-CSS judgment.
- gemini-3-flash (Zen alt): cheaper flash.
- kimi-k3 (Go/Zen): native image input per AA, but not benched for UI critique.
- deepseek-v4-flash-vision-exp (Go): experimental, not benched.

**Why winner wins:** Go stays minimax-m3 — only natively multimodal model on Go flat rate. Zen stays gemini-3-flash (alt gpt-5.4-mini) with gemini-3.7-flash as upgrade candidate (bench before switching). **Caveat:** M3's UI-CSS judgment not confirmed in correcting-ui eval loop (multimodal wins on SVG-Bench/BrowseComp, not UI critique).

### vision-critic-final (UI loop, final review)
**Dominant trait:** vision quality
**Candidates considered:**
- gemini-3.1-pro (Zen): strongest vision quality per prior evidence.
- claude-sonnet-5 (Zen alt): strong vision.

**Why winner wins:** Keep gemini-3.1-pro for sign-off.

### council-member (multi-perspective review)
**Dominant trait:** family diversity (not raw score)
**Candidates considered:**
- Free: nemotron-3-ultra-free (NVIDIA) + mimo-v2.5-free (MiniMax) + deepseek-v4-flash-free (DeepSeek) = 3 families ✓
- Go: kimi-k3 (Moonshot) + glm-5.3 (Z.ai) + deepseek-v4-flash (DeepSeek) = 3 families ✓
- Zen: claude-opus-5 (Anthropic) + gemini-3.1-pro (Google) + gpt-5.6-sol (OpenAI) = 3 families ✓

**Why winner wins:** All tiers maintain three-family diversity. No change needed.

### skill-author (authoring new skills)
**Dominant trait:** instruction following
**Candidates considered:**
- nemotron-3-ultra-free (free): AA 38.3. Empirically confirmed by six authoring rounds in this repo.
- deepseek-v4-flash-free (free alt): AA 50. Stronger on paper but not empirically confirmed for skill authoring.
- minimax-m3 (Go): Thinkbench existing-code parity 0.999–1.000 with GLM-5.2, 3.7× cheaper. Value pick for scaffolded/existing-code work.
- qwen3.7-max (Go alt): IFBench 79.1 (leads), Go-only. IF escalation.
- qwen3.8-max (Go watch): successor to qwen3.7-max, watch for IF bench.
- claude-sonnet-5 (Zen): proprietary IF strength.

**Why winner wins:** Free stays nemotron-3-ultra-free (empirically confirmed by six authoring rounds). Go stays minimax-m3 (existing-code parity, cost). Zen stays claude-sonnet-5. qwen3.8-max on watch for IF escalation.

### skill-reviewer (reviewing skill drafts)
**Dominant trait:** top reasoning
**Candidates considered:**
- nemotron-3-ultra-free (free): AA 38.3. Empirically confirmed.
- deepseek-v4-flash-free (free alt): AA 50.
- glm-5.3 (Go): AA 60, KingBench 3 91.25% (indep.). Strongest Go reasoning.
- glm-5.2 (Go alt): Thinkbench 92% full-pass.
- claude-opus-5 (Zen): AA 63. Peak reasoning.

**Why winner wins:** Free stays nemotron-3-ultra-free (empirically confirmed). Go stays glm-5.3 (independent KingBench 3 91.25%, AA 60). Zen stays claude-opus-5.

## Proposed bindings

| Role | Proposed Free | Proposed Go | Proposed Zen | Changed? | Bench basis (escalation) |
|---|---|---|---|---|---|
| planner | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt kimi-k3) | claude-opus-5 (peak: claude-fable-5) | No | AA 60 (indep. 2026-08); KingBench 3 91.25% (indep.) |
| implementer | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 (alt gpt-5.4) | No | MCPMark K2.7 81.1% (indep.); K3 94.5% (vendor) |
| triager | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt deepseek-v4-pro) | gpt-5.6-luna (alt gpt-5.4-mini) | No | AA 60 / luna 52 at $0.05/task + 141 t/s (indep. 2026-08) |
| test-writer | deepseek-v4-flash-free | kimi-k3 (alt kimi-k2.7-code) | claude-sonnet-5 | No | MCPMark K2.7 81.1% (indep.) |
| debugger | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | No | KingBench 3 91.25% (indep.); Thinkbench 92% (indep.) |
| reviewer | deepseek-v4-flash-free (alt nemotron-3-ultra-free) | glm-5.3 (alt glm-5.2) | claude-sonnet-5, gpt-5.4 | No | KingBench 3 91.25% (indep.) |
| vision-critic-fast | — | minimax-m3 | gemini-3-flash (alt gpt-5.4-mini) | No | native image-in; vision bench (gemini) |
| vision-critic-final | — | — | gemini-3.1-pro (alt claude-sonnet-5) | No | vision quality (gemini-3.1-pro) |
| council-member | nemotron-3-ultra-free + mimo-v2.5-free + deepseek-v4-flash-free | kimi-k3 + glm-5.3 + deepseek-v4-flash | claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol | No | family diversity + per-lens competence |
| skill-author | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | minimax-m3 (alt glm-5.2, qwen3.8-max) | claude-sonnet-5 | No | Thinkbench existing-code parity 0.999–1.000; IFBench 79.1 (qwen3.7-max) |
| skill-reviewer | nemotron-3-ultra-free (alt deepseek-v4-flash-free) | glm-5.3 (alt glm-5.2) | claude-opus-5 | No | KingBench 3 91.25% (indep.); AA 60 |

**No bindings changed.** All current bindings remain catalog-valid and evidence-backed.

## Questionable / uncertain

1. **Free generalist re-validation pending** — The 2026-07-26 head-to-head that validated nemotron-3-ultra-free (and ling-3.0-flash-free, now removed) has not been re-run with the current free roster: `nemotron-3-ultra-free`, `deepseek-v4-flash-free`, `mimo-v2.5-free`, `ling-3.0-flash-fin-free`, `muse-spark-1.2-contributor-free`, `nemotron-3.5-lightning-free`, `laguna-s-2.1-free`. The Update procedure step 4 prescribes this re-run before any free-seat change. *Resolution: run the clean-room head-to-head eval on the current free roster.*

2. **`ling-3.0-flash-fin-free` vs `ling-3.0-flash-free`** — The catalog now has `ling-3.0-flash-fin-free` (different ID from the validated `ling-3.0-flash-free` removed 2026-08-14). No benchmark evidence for the `-fin` variant. *Resolution: include in the head-to-head re-run; do not bind until validated.*

3. **New free models unbenched** — `muse-spark-1.2-contributor-free`, `nemotron-3.5-lightning-free`, `big-pickle` (Zen, not free), `ox-alpha-free` (not in catalog) have no independent benchmark evidence. *Resolution: include in head-to-head re-run.*

4. **Kimi K3 MCPMark 94.5% is vendor-reported** — The 94.5% comes from Moonshot's technical report (arXiv:2607.24653v2). The independent verified score is Kimi K2.7 Code at 81.1% (BenchLM, 2026-08-29). *Resolution: await independent MCPMark Verified run for K3.*

5. **GLM-5.3 KingBench 3 91.25% is independent but single-benchmark** — Strong signal but only one independent coding benchmark. *Resolution: monitor for Thinkbench or MCPMark reproduction.*

6. **DeepSeek V4 Flash 0731 agent benchmarks mostly vendor-reported** — Only TB 2.1 82.7% is independently reproduced (Ante harness, 2026-08-09). DeepSWE 54.4, Toolathlon 70.3, etc. are DeepSeek Harness (unreleased). *Resolution: monitor for independent reproduction of agent suite.*

7. **MiniMax M3 UI-CSS judgment unconfirmed** — M3's multimodal wins are on SVG-Bench/BrowseComp, not UI critique. The `correcting-ui` eval loop has not validated it for screenshot-based CSS judgment. *Resolution: evaluate in correcting-ui eval loop before relying on it for vision-critic-fast.*

8. **Gemini-3.7-flash vision unbench** — New Zen flash model, candidate for vision-critic-fast upgrade. No vision-quality evidence yet. *Resolution: bench vision judgment before switching from gemini-3-flash.*

9. **Qwen3.8-max IFBench unbench** — Successor to qwen3.7-max (IFBench 79.1). No IFBench run published yet. *Resolution: watch for independent IFBench on qwen3.8-max.*

10. **Grok family hard-excluded** — `grok-4.5` (Go), `grok-4.6`, `grok-build-0.1` (Zen) are in catalogs but excluded by user directive (2026-08-14). AA scores 61 (grok-4.5) / 54 (grok-4.6 high) would otherwise be competitive. *Resolution: exclusion stands per user directive; do not add to any table/roster/watch.*

11. **Nemotron-3-ultra-free streaming reliability caveat** — Observed intermittent streaming errors under load (noted in model-routing.md Free-tier caveats). Carries into Questionable/Uncertain as a reliability risk for the free generalist seat. *Resolution: monitor in production; escalate to Go/Zen for risk-bearing tasks.*

12. **Catalog-vs-binding: `hy3-free` absent from free catalog** — The 2026-08-14 re-check noted `hy3-free` re-added, but 2026-08-30 catalog shows only `hy3`/`hy3-preview` on Go. No free `hy3-free` exists. *Resolution: already not bound; no action needed.*

## Applied

Not applied — awaiting approval.