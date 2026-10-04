# Council

The council protocol for the ai-framework library. Companion to
`reference/model-routing.md` (the `council-member` row) — that file is the
single home of the model IDs; this doc is the **procedure**.

The council runs on the **Go flat-rate lane** (`opencode-go/*`). It cannot run
on free models: the free tier rejects calls made from a nested Task subagent
(`OpenCode's free tier can only be used from within OpenCode`), so a free
council dies at step 0. This supersedes the 2026-09-13 free-tier council. Every
framework persona is Go-bound by default (go-first policy, 2026-10-03); the
council's six-family seat table is that policy's deliberate diversity form.
Dispatch lanes, composition bounds, and the run-vehicle dispatch path are
defined in `reference/agent-teams.md` §Lane policy; this document remains the
council procedure.

## Seats (one model family per seat)

| Seat | Go model | Family | Lens |
|---|---|---|---|
| `council` (chairman) | `opencode-go/qwen3.8-flash` | Qwen | synthesis |
| `council-architecture` | `opencode-go/glm-5.3-flash` | Zhipu | pattern alignment, tech debt, testability |
| `council-performance` | `opencode-go/gpt-5.6-luna` | OpenAI | bottlenecks, N+1, caching, scaling |
| `council-security` | `opencode-go/deepseek-v4.1-flash` | DeepSeek | vulnerabilities, edge cases, data safety |
| `council-ux` | `opencode-go/minimax-m3` | MiniMax | end-user + developer experience |
| `council-product` | `opencode-go/mimo-v2.6-flash` | Xiaomi | requirements fit, scope, priority |

Frontier opt-in (user-requested only): `claude-opus-5-5` + `muse-spark-1.3` +
`gpt-5.6-sol`, one family per seat. Never upgrade models on your own.

## Procedure

1. Orchestrator extracts the question; if unclear, one clarifying question.
2. Spawn the seats in parallel via the Task tool (`subagent_type: "council-*"`),
   passing the question (2–3 sentences).
3. Collect all results. Validate each against
   `reference/delegated-result-contract.md` (`council-lens`): an **empty or
   malformed** result is a **failed run**, never clean — do not synthesize over
   it. A **transient** failure is retried; a **deterministic** one is retried
   once, then the vehicle is switched or the work taken over inline; the
   outcome is **recorded**.
4. Verify each member's run header shows the intended `agent · model` line.
5. Synthesize: Common Ground · Tensions (name the disagreement) · Risk Register
   · Recommendation. Surface disagreements; never average them away.
6. STOP — discussion only; do not edit files or write code unless the user says
   "save this".

## Guardrails

- Council only for planning & review; raw execution stays single-model.
- `AI_FRAMEWORK_FREE_TIER=1` forces free models for the main session (the
  explicit free opt-in); the council must still run Go-bound, or be recorded
  as an explicit skip.
- A council on one model family is not a council — state it as degraded.

## Reasoning effort (`glm-5.3-flash`)

Z.AI accepts `reasoning_effort` only at `low` / `high` / `max` (default `max`)
with `thinking` enabled. Set it per model in opencode config:
`provider.opencode-go.models.glm-5.3-flash.options.reasoningEffort`. If the Go
path drops or rejects the control (opencode #49551, 2026-09-17), the seat runs
as-is at the default.
