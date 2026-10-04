# ADR-0013: Go-first model policy — Go defaults, free opt-in, kimi-k3 and gpt-6-luna excluded

## Status: accepted 2026-10-03

## Context

The library's standing policy was free-first: every role defaulted to a free
model where one existed, with paid lanes as escalation only (ADR-0007's
premise; `docs/CONCEPTS.md` Choice 7c). Practice had already diverged — the CI
eval lane moved to the Go flat-rate lane on 2026-09-29 (recorded in
`reference/model-routing.md`, ADR-0002 left describing the retired direct-key
phase) — and consumer repos hand-pinned Go bindings to escape the free tier.

Free-first had become a reliability tax on the default path: 9 of 17 personas
were bound to `opencode/nemotron-3-ultra-free`, the model family behind the
observed dead sessions and dispatch failures; the free tier cannot serve a
nested Task subagent at all; and its AA baseline (Nemotron 3 Ultra 23) caps
quality on every design/implement/review pass. The 2026-10-03 live evidence
pull refreshed the seat numbers (MiMo-V2.6-Pro 46 — new score leader;
glm-5.3-flash 42; deepseek-v4.1-flash 39) and produced three user directives:
Go by default with free as an explicit last-resort opt-in; `kimi-k3` removed
(console-disabled as too expensive); objective scores outrank family
diversity outside the council's deliberate six-family design. `gpt-6-luna`
carried 3/3 CI canary failures on the 2026-09-29 eval-lane pass.

## Decision

1. **Every framework persona and workflow binds a live Go model by
   default** (`opencode-go/`); the per-role bindings live in
   `reference/model-routing.md` and `agents/*.md`.
2. **Free is an explicit opt-in** — `AI_FRAMEWORK_FREE_TIER=1` or a
   per-session model switch — and a last resort, never a default. No new
   rebinding mechanism is added.
3. **`kimi-k3` is hard-excluded** (user cost directive 2026-10-03:
   console-disabled, too expensive) and **`gpt-6-luna` is hard-excluded**
   (3/3 CI canary failures 2026-09-29 plus `/responses`-only), alongside the
   existing `glm-5.3` / `glm-5.2` cost exclusions and the peak-tier class.
   **Exclusions sit above all scores:** a live probe or a top benchmark
   result never overrides one.
4. **The CI eval lane stays on the Go flat-rate lane** (user directive
   2026-09-29, `opencode-go/deepseek-v4.1-flash`) — superseding ADR-0002's
   direct-key basis. The nested-agent CI override
   (`scripts/ci-lane-overrides.py`) becomes an empty agent map for this repo
   (superseding ADR-0007's free-first premise) while remaining a guard for
   consumer repos whose wrappers are still free-bound.
5. **Go Plus ($40/mo) is the funding basis**, re-evaluated at the next
   monthly review (2026-11-01) against spend vs per-model caps and whether
   free-lane viability warrants revisiting.
6. The **liveness gate is the 20s trivial probe** (bare catalog IDs,
   required `x-opencode-session`, timeout never extended); a
   chat-completions `ModelProtocolUnsupported` response is a protocol
   statement, not a death.

## Consequences

- The free-tier reliability tax leaves the default path; consumer repos can
  stop hand-pinning defaults.
- ADR-0002 and ADR-0007 are superseded by this decision (statuses updated in
  place; their audit trail stands).
- `scripts/model-liveness-check.py` enforces the policy (no bound `-free`
  ID, no bound excluded ID, table/Go-catalog consistency), with hermetic
  fixture-driven tests in `scripts/test_model_policy.py`.
- The kimi-k3 cost leak is closed; the Go Plus spend is visible and dated.

## Review trigger

**2026-11-01 (next monthly review):** Go Plus spend vs per-model caps and
whether free-lane viability warrants revisiting. Tracked as a roadmap row
(`docs/ROADMAP.md`).

## Sources

- User directives 2026-10-03: Go defaults with free as last resort; Go Plus
  upgrade; kimi-k3 disabled in the console as too expensive.
- `.opencode/plans/go-first-model-bindings.md` (approved plan; evidence basis
  and History).
- `reference/model-routing.md` (bindings, exclusions, probe contract),
  `docs/CONCEPTS.md` Choice 7c.
- ADR-0002 (superseded), ADR-0007 (superseded).
