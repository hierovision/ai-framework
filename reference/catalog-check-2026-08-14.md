# Catalog Check + Model Right-Sizing — 2026-08-14

> **SUPERSEDED by 2026-09-03 remediation** — see `reference/model-routing.md` Routing update 2026-09-03. This file contains stale data (e.g., `deepseek-v4-flash-free` marked as ✓) and should not be used for routing decisions.

Validation of `reference/model-routing.md` + the `agents/*.md` bindings and
`docs/FREE-TIER-COUNCIL.md` against the **official opencode catalogs**,
followed by a right-sizing evaluation per persona/workflow.

## Sources (retrieved 2026-08-14)

- Zen catalog (PAYG): `https://opencode.ai/zen/v1/models` — 62 models
- Go catalog (flat-rate): `https://opencode.ai/zen/go/v1/models` — 26 models
- Docs: `https://opencode.ai/docs/models` (confirms `opencode/` = Zen prefix
  convention; no pricing table on the page — pricing claims below rest on
  the 2026-07-25 catalog/pricing fetch recorded in model-routing.md)

The catalog JSON carries IDs only (no pricing/metadata), so this check
covers **membership**, not price deltas.

## Part 1 — Validation vs official catalogs

### Adheres — referenced IDs still in catalog

| ID | Zen | Go |
|---|---|---|
| deepseek-v4-flash / deepseek-v4-flash-free / deepseek-v4-pro | ✓ | flash, pro ✓ |
| mimo-v2.5-free / mimo-v2.5 | ✓ free | ✓ |
| nemotron-3-ultra-free, laguna-s-2.1-free | ✓ | — |
| glm-5.2, glm-5.1, glm-5 | ✓ | ✓ |
| kimi-k2.7-code, kimi-k3, kimi-k2.6 | ✓ | ✓ |
| qwen3.7-max, qwen3.7-plus (Go-only claim **confirmed**) | — | ✓ |
| minimax-m3, minimax-m2.7, minimax-m2.5 | ✓ | ✓ |
| hy3, hy3-preview (Go flat-rate ✓) | — | ✓ |
| grok-4.5 | ✓ | ✓ |
| gpt-5.6-sol/terra/luna, gpt-5.5, gpt-5.4, gpt-5.4-mini | ✓ | luna ✓ |
| claude-opus-5, claude-fable-5, claude-sonnet-5, claude-haiku-4-5, claude-opus-4-8 | ✓ | — |
| gemini-3.1-pro, gemini-3.6-flash, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3-flash | ✓ | — |

All escalation rows (Go + Zen) and the deepseek/mimo free bindings check out.
`claude-opus-4-1` is absent — consistent with the deprecation-watch row.

### Gaps — referenced IDs NOT in any official catalog

1. **`ling-3.0-flash-free` — GONE from both catalogs.** The validated
   free generalist (2026-07-26 head-to-head winner, "reliable default") no
   longer exists. It is bound by **four agents** (`triage.md`, `council.md`
   chairman, `council-ux.md`, `council-product.md`) and is the free
   default/alt for `planner`, `triager`, `council-member`,
   `skill-author`, `skill-reviewer`, the council planner seat, and the
   review-council C seat in model-routing.md + FREE-TIER-COUNCIL.md.
   Impact: **the free-tier generalist strategy has no backing model**.
2. **`north-mini-code-free` — GONE** (named as a validated alt generalist
   in the 07-25/07-26 notes).

Fix (doc-backed by Update procedure step 4): rebind the ling seats to a
catalog-verified free model and re-run the head-to-head eval. Immediate
stand-in with prior validation: `nemotron-3-ultra-free` (10/10 planning in
the 07-26 eval; caveat: intermittent streaming errors observed). New
unvalidated free IDs available for the re-run: `nemotron-3.5-lightning-free`,
`muse-spark-1.2`, `big-pickle`. `hy3-free` is back in the catalog — see
outdated item 3 — and was the pre-ling generalist, so it belongs in the
re-validation pool too.

### Outdated — doc claims vs current catalog

| Doc claim | Catalog today | Fix |
|---|---|---|
| "`hy3-free` removed from the catalog 2026-07-25" (notes + Deprecation watch) | **Present** in Zen catalog | Record re-appearance with date; re-validate before use, or strike the removal row |
| "`gpt-5.6-*` are Zen models" (07-25 note) | **`gpt-5.6-luna` is also on Go flat-rate** | Note luna as Go-escalation-eligible (frontier at flat rate — major right-sizing option) |
| GLM is a Go escalation; no newer GLM listed | **`glm-5.3` on Go only** (new); glm-5.2/5.1/5 also on Zen now | Add glm-5.3 row; widen planner/reviewer options |
| Deprecation watch rows for kimi-k2.5 / minimax-m2.5 (due 2026-08-05) | Still listed in both catalogs (not yet removed) | Refresh watch dates/status |
| Zen frontier list (07-25) | New: `gemini-3.7-flash`, `grok-4.6`, `grok-build-0.1`, `gpt-5.4-pro`, `gpt-5.5-pro`, `gpt-5.3-codex`, `deepseek-v4-pro` (Zen) | Add to inventory; candidates below |

### New models available (not yet in routing doc)

- **Free:** `nemotron-3.5-lightning-free`, `muse-spark-1.2`, `big-pickle`
  (quality unvalidated)
- **Go:** `glm-5.3`, `qwen3.8-max` (successor to qwen3.7-max), `gpt-5.6-luna`,
  `mimo-v2.5-pro`, `mimo-v2-pro`, `mimo-v2-omni`
- **Zen:** `gemini-3.7-flash`, `grok-4.6`, `grok-build-0.1`, `gpt-5.4-pro`,
  `gpt-5.5-pro`, `gpt-5.3-codex`, `glm-5.2/5.1/5` (Zen availability is new),
  `deepseek-v4-pro` (Zen availability is new)

## Part 2 — Right-sizing evaluation per persona/workflow

Legend: ✓ keep · ⚠ needs fix (bound ID gone) · → recommended change.

| Persona / workflow | Free | Go (escalation) | Zen (escalation) | Verdict |
|---|---|---|---|---|
| **design (planner)** — architecture, tool-heavy planning | deepseek-v4-flash-free ✓ | glm-5.2 → **glm-5.3**; hardest → **gpt-5.6-luna** (frontier at flat rate) | claude-opus-5 ✓ | → |
| **build (implementer)** — heavy file/tool orchestration | deepseek-v4-flash-free ✓ | kimi-k2.7-code ✓ (watch kimi-k3 as successor) | claude-sonnet-5 ✓ | ✓ |
| **triage (triager)** — generalist summaries | **ling ⚠ → nemotron-3-ultra-free** (validated; streaming caveat) or deepseek | hy3 ✓ | gpt-5.4-mini / claude-haiku-4-5 ✓ | → |
| **test-writer** | deepseek-v4-flash-free ✓ | kimi-k2.7-code ✓ | claude-sonnet-5 ✓ | ✓ |
| **debugger** — root-cause reasoning | deepseek-v4-flash-free ✓ | glm-5.2 → **glm-5.3** | claude-sonnet-5 / gpt-5.4 ✓ | → |
| **reviewer** — defect catch | deepseek-v4-flash-free ✓ | glm-5.2 → **glm-5.3** or gpt-5.6-luna | claude-sonnet-5 ✓ | → |
| **vision-critic-fast** — screenshot per-pass | — (no free multimodal) | minimax-m3 ✓ | gemini-3.6-flash → **gemini-3.7-flash** (newest flash; bench before switch) | → |
| **vision-critic-final** — sign-off | — | — | gemini-3.1-pro ✓ | ✓ |
| **council chairman + lenses** | chairman/ux/product **ling ⚠ → nemotron family**; security mimo-v2.5-free ✓; architecture/performance deepseek ✓ | opt-in hy3 + mimo-v2.5 + deepseek-v4-flash ✓ | opt-in claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol ✓ | → |
| **skill-author** — existing-code authoring | **ling ⚠ → nemotron-3-ultra-free** | minimax-m3 ✓ (IF leader qwen3.7-max → watch **qwen3.8-max**) | claude-sonnet-5 ✓ | → |
| **skill-reviewer** — skill-foundation review | **ling alt ⚠ → nemotron** | glm-5.2 → **glm-5.3** | claude-opus-5 ✓ | → |

Diversity check after the proposed moves: council = deepseek ×2
(architecture, performance) + mimo ×1 (security) + nemotron ×3 (chairman,
ux, product) — **three families preserved**, so the council objectivity
principle survives the ling removal.

### Watch list (unvalidated, do not bind yet)

- `glm-5.3`, `qwen3.8-max`, `gpt-5.6-luna` (Go) — successors/upgrades;
  verify benches before switching escalation rows
- `nemotron-3.5-lightning-free`, `muse-spark-1.2`, `big-pickle` (free) —
  candidates for the re-run head-to-head
- `hy3-free` — back in catalog; re-validate before resurrecting

> **Hard exclusion (user directive, 2026-08-14):** the entire grok family
> (`grok-4.5`, `grok-4.6`, `grok-build-0.1`) is excluded from all bindings,
> escalations, and watch lists. Recorded in `reference/model-routing.md`
> under "Hard exclusions"; the grok rows in the tables above and in the
> new-model inventory are catalog facts only, not candidates.

> **Status: fixes applied 2026-08-14.** Ling-bound agents rebind to
> `nemotron-3-ultra-free` (triage, council chairman, council-ux,
> council-product); `reference/model-routing.md` and
> `docs/FREE-TIER-COUNCIL.md` updated (roster, deprecation watch, hy3-free
> re-appearance, glm-5.3 / gpt-5.6-luna / gemini-3.7-flash / qwen3.8-max
> rows); `docs/CURRICULUM.md` stale escalation rows fixed. The head-to-head
> re-run (Update procedure step 4) remains open work.

## Confidence

- **High** for membership: every ID above was checked directly against the
  two official endpoints fetched today (2026-08-14).
- **Medium** for "why ling/north disappeared" — the catalog does not say
  (rename? removal?); a re-fetch in a few days or the opencode changelog
  would confirm. Until then the remediation (rebind + re-run eval) is the
  same either way.
- **Low** for new-model quality — all new IDs are unvalidated; the routing
  doc's own Update procedure (step 4) requires re-running role benchmarks
  before binding, which is exactly the prescribed next step.

## Proposed remediation order

1. Rebind the four ling-bound agents (`triage`, `council` chairman,
   `council-ux`, `council-product`) + free-tier doc rows to
   `nemotron-3-ultra-free` (emergency: current bindings 404).
2. Update model-routing.md: deprecation-watch rows (ling, north-mini-code),
   hy3-free re-appearance, glm-5.3 / qwen3.8-max / gpt-5.6-luna Go rows,
   gemini-3.7-flash vision candidate, new-model inventory.
3. Schedule the head-to-head eval (Update procedure step 4) covering
   nemotron-3-ultra-free / nemotron-3.5-lightning-free / hy3-free /
   deepseek-v4-flash-free before finalizing the free generalist seat.
