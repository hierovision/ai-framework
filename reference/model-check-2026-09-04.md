# Model Check + Right-Sizing — 2026-09-04

Scoped pass: Go-tier escalation liveness (resolves the 2026-09-03 open item)
+ `omen-alpha` candidate evaluation. No free-tier or Zen rows analyzed; no
agent bindings changed.

## Sources
- Go catalog (flat-rate): `https://opencode.ai/zen/go/v1/models` — retrieved 2026-09-04 (live fetch)
- Zen catalog (PAYG): `https://opencode.ai/zen/v1/models` — retrieved 2026-09-04 (live fetch)
- Docs: `https://opencode.ai/docs/zen/#endpoints` — retrieved 2026-09-04 (authoritative for free-tier; `omen-alpha` absent from endpoints and pricing tables)
- Live routing probes (opencode session, Go tier, trivial prompt) — 2026-09-04

## Current bindings (probed rows)
- `council-member` Go: kimi-k3 + glm-5.3 + deepseek-v4-flash
- `triager` Go: glm-5.3 (alt deepseek-v4-pro)

## Per-role analysis
- Probe results (Go tier, 2026-09-04): `kimi-k3` LIVE; `glm-5.3` LIVE; `minimax-m3` LIVE; `omen-alpha` LIVE; `deepseek-v4-flash` FAILS ("only available hosted in China and requires explicit opt in"); `deepseek-v4-pro` FAILS (same).
- `council-member` (Go): deepseek-v4-flash fails the liveness hard gate → cannot hold the seat at any score. Replacement ranked over live candidates only: `minimax-m3` (MiniMax — a third distinct family vs kimi/GLM; natively multimodal; AA-tier open model already referenced in this repo's routing). Result: kimi-k3 + glm-5.3 + minimax-m3 — families Moonshot / Z.ai / MiniMax, diversity preserved (3 of 3).
- `triager` (Go alt): deepseek-v4-pro fails the same gate → replaced with `kimi-k3` (probe-verified live; AA 60).
- `omen-alpha`: passes the liveness gate (LIVE on Go) but no benchmark evidence of any tier exists — not independent, not cross-checked, not even vendor self-reported; absent from the docs endpoints/pricing tables (stealth/preview listing). No objective basis to rank it for any role; its model family is undisclosed, so it cannot be counted as a distinct family for council diversity either.

## Proposed bindings
- `council-member` Go: kimi-k3 + glm-5.3 + deepseek-v4-flash → **kimi-k3 + glm-5.3 + minimax-m3** (changed — liveness gate; families Moonshot / Z.ai / MiniMax)
- `triager` Go alt: deepseek-v4-pro → **kimi-k3** (changed — liveness gate; probe-verified live)
- `omen-alpha`: **Watch list only — do not bind** (live but unbenched and undocumented)
- All other rows and all `agents/*.md` bindings: unchanged

## Questionable / uncertain
- `omen-alpha` — live on Go but zero published benchmark evidence and no docs listing; also an undisclosed family, so it provides no countable council-diversity value. Resolution: independent benchmark publication or vendor disclosure of identity/family; re-evaluate at the next catalog check.
- deepseek **Zen** (PAYG, `opencode/deepseek-v4-flash` / `-pro`) variants unprobed — out of scope; no Zen row currently binds deepseek. Resolution: probe before any future Zen binding of these IDs (the Go failure may or may not extend to Zen hosting).
- `muse-spark-1.2-contributor-free` head-to-head eval still open (carried from 2026-09-03; next full routing pass).

## Applied
- `reference/model-routing.md`: `council-member` Go mix → kimi-k3 + glm-5.3 + minimax-m3; `triager` Go alt → kimi-k3; `### Routing update — 2026-09-04` appended with all probe results.
- `agents/council.md`: stale Go escalation example (hy3 + mimo-v2.5 + deepseek-v4-flash) → kimi-k3 + glm-5.3 + minimax-m3.
- `docs/FREE-TIER-COUNCIL.md`: Go-escalation reference note updated off deepseek-v4-flash.
- `docs/CONCEPTS.md`: stale council family mix (nemotron / mimo / deepseek) → nemotron / mimo / muse-spark.
- Verifier: OK (6 agent bindings unchanged and matching; no forbidden IDs in agents/).
