# Council

The council protocol for the ai-framework library. Companion to
`reference/model-routing.md` (the `council-member` row) — that file is the
single home of the model IDs; this doc is the **procedure**.

The council runs on the **Go flat-rate lane** (`opencode-go/*`). It cannot run
on free models: the free tier rejects calls made from a nested Task subagent
(`OpenCode's free tier can only be used from within OpenCode`), so a free
council dies at step 0. This supersedes the 2026-09-13 free-tier council.

## Seats (one model family per seat)

| Seat | Go model | Family | Lens |
|---|---|---|---|
| `council` (chairman) | `opencode-go/kimi-k3` | Moonshot | synthesis |
| `council-architecture` | `opencode-go/glm-5.3-flash` | Zhipu | pattern alignment, tech debt, testability |
| `council-performance` | `opencode-go/qwen3.8-max` | Qwen | bottlenecks, N+1, caching, scaling |
| `council-security` | `opencode-go/deepseek-v4.1-flash` | DeepSeek | vulnerabilities, edge cases, data safety |
| `council-ux` | `opencode-go/minimax-m3` | MiniMax | end-user + developer experience |
| `council-product` | `opencode-go/mimo-v2.6-flash` | Xiaomi | requirements fit, scope, priority |

Frontier opt-in (user-requested only): `claude-opus-5-5` + `muse-spark-1.3` +
`kimi-k3`, one family per seat. Never upgrade models on your own.

## Procedure

1. Orchestrator extracts the question; if unclear, one clarifying question.
2. Spawn the seats in parallel via the Task tool (`subagent_type: "council-*"`),
   passing the question (2–3 sentences).
3. Collect all results. An **empty result is a failure, never a review** — do
   not synthesize over it; re-run the seat or mark the council degraded.
4. Verify each member's run header shows the intended `agent · model` line.
5. Synthesize: Common Ground · Tensions (name the disagreement) · Risk Register
   · Recommendation. Surface disagreements; never average them away.
6. STOP — discussion only; do not edit files or write code unless the user says
   "save this".

## Guardrails

- Council only for planning & review; raw execution stays single-model.
- `AI_FRAMEWORK_FREE_TIER=1` forces free models for the main session; the
  council must still run Go-bound, or be recorded as an explicit skip.
- A council on one model family is not a council — state it as degraded.

## Reasoning effort (`glm-5.3-flash`)

Z.AI accepts `reasoning_effort` only at `low` / `high` / `max` (default `max`)
with `thinking` enabled. Set it per model in opencode config:
`provider.opencode-go.models.glm-5.3-flash.options.reasoningEffort`. If the Go
path drops or rejects the control (opencode #49551, 2026-09-17), the seat runs
as-is at the default.
