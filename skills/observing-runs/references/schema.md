# Run-log schema (single source of truth)

This document is the **canonical, authoritative definition** of the
run-log JSONL contract owned by the `observing-runs` skill. Every writer
(`log_run.py`) and every reader (`query_runs.py`, the RM-002 eval runner,
RM-009 ROI / RM-011 drift scripts) MUST conform to it. Do not redefine
field names elsewhere.

## Storage

- One file per **UTC day**: `logs/run-<YYYY-MM-DD>.jsonl` (repo root).
- Git-ignored (see repo `.gitignore` → `logs/`). Telemetry is never committed.
- `logs/` may be overridden via `OBSERVE_LOG_DIR` (CI uses this).
- One **JSON object per line**; each line is one *run* (not one sub-step).
- Append-only. Records are never edited in place and the log is never
  read back into an agent's live prompt (ROI guardrail — see SKILL.md).

## Fields

| field | type | required | default | notes |
|---|---|---|---|---|
| `ts` | string (ISO-8601 UTC) | auto | now | correlation metadata |
| `run_id` | string (uuid) | auto | uuid4 | correlation metadata |
| `kind` | enum `skill`\|`agent`\|`eval` | **yes** | — | event type |
| `skill` | string \| null | no | null | attribution / slice |
| `agent` | string \| null | no | null | attribution / slice |
| `model` | string \| null | no | null | attribution / slice |
| `tokens_in` | int \| null | no | null | cost / ROI (RM-009); null when unknown, never 0-by-default |
| `tokens_out` | int \| null | no | null | cost / ROI (RM-009); null when unknown, never 0-by-default |
| `duration_ms` | int \| null | no | null | speed / latency; null when unknown, never 0-by-default |
| `outcome` | enum `success`\|`failure`\|`error`\|`stopped` | **yes** | — | quality / regression |
| `eval_pass` | bool \| null | no | null | eval-kind pass/fail (drift) |
| `detail` | string \| null | no | null | **failure-only**, capped 512 chars |

`required` = must be present in the caller's record (no safe default).
`auto` = filled by `log_run.py` when absent. All twelve keys are present
in every written line.

### Legacy `0` compatibility (2026-09-13)

Writers before 2026-09-06 defaulted unknown `tokens_in`/`tokens_out`/
`duration_ms` to literal `0`. Writers now emit `null` (missing != zero). The
aggregator (`query_runs.py`) treats a literal `0` in these three fields as
unknown, because under the old default `0` carried no information; legacy
records therefore cannot skew cost/latency aggregates. A genuine `0` is not a
supported value for these fields — emit `null` when unknown. Verifier:
`test_query.py` `delta` fixture. **Sunset:** legacy records age out of the
30-day retention window by ~2026-10-06; the reader-side coercion can be
removed after that date.

### `detail` discipline

`detail` is **optional, failure-only, and capped at 512 characters**. It
carries a short error/reason string (e.g. why a run failed). It is
**never** raw prompt text, raw agent output, or a tool-call transcript.
Full I/O is never logged (privacy + noise + cost).

## Example lines

```jsonl
{"ts":"2026-08-28T06:00:00Z","run_id":"c1f2...","kind":"eval","skill":"writing-unit-tests","agent":null,"model":"go","tokens_in":812,"tokens_out":305,"duration_ms":142000,"outcome":"success","eval_pass":true,"detail":null}
{"ts":"2026-08-28T06:03:11Z","run_id":"a9b0...","kind":"eval","skill":"writing-unit-tests","agent":null,"model":"go","tokens_in":790,"tokens_out":298,"duration_ms":139000,"outcome":"failure","eval_pass":false,"detail":"expected_behavior[3] missing: agent did not route RLS to integration"}
{"ts":"2026-08-28T09:15:02Z","run_id":"d4e5...","kind":"skill","skill":"triaging-requirements","agent":null,"model":"zen","tokens_in":1205,"tokens_out":540,"duration_ms":88000,"outcome":"success","eval_pass":null,"detail":null}
```

## Emission (the convention)

Emit **one record per run**, from the run boundary (a skill/agent call
or an eval prompt) — not from inside the run per tool call. Two ways:

1. **Hook-based (aspirational, not the default):** an opencode hook fires
   outside the agent's generation and calls `log_run.py` with the measured
   fields, but the example cannot attribute skill/model/tokens/duration and
   is not schema-honest. Dated facts:
   [../../../reference/opencode-integration.md](../../../reference/opencode-integration.md).
2. **Convention-based (the default):** the caller measures what it can and
   invokes `log_run.py --record '<json>'`. Adds ~80–160 tokens/run —
   bounded but non-zero. Prefer hook emission only once it can attribute a
   real run.

`log_run.py` accepts caller-supplied `tokens_in/out` and `duration_ms`
(the caller measures what the runtime exposes); fields default to `null`
when unknown and are **never fabricated** (missing != zero).
`query_runs.py` sums known components only; cost/task divides by runs with
known tokens (None when none known).

Overhead budget (dated, provisional): convention-based logging targets
<2% AND <200 tokens/run. This is **`unverified`** until measured on the
RM-002 baseline — it is a target, not an established bound. The number and
method live in
[../../../reference/run-log-overhead.md](../../../reference/run-log-overhead.md).

## Out-of-band consumers (logs are read, not write-only)

Logs have a concrete read path — all out-of-band, on schedule or on
demand, never per agent turn:

- **Humans:** `query_runs.py aggregate` (cost/task, latency, eval-pass rate).
- **CI (RM-002):** the scheduled behavioral-eval workflow writes one
  `kind=eval` record per eval and uploads `logs/` as a 30-day artifact.
- **Report (RM-003):** builds a per-skill report from aggregates.
- **ROI (RM-009):** derives the 4 ROI numbers from token/duration fields.
- **Drift (RM-011):** the eval-pass-rate slope is the drift score.

## Retention

- Local: `query_runs.py prune --older-than 30d` deletes daily files older
  than the window (override `--older-than` / `OBSERVE_RETENTION_DAYS`);
  `--archive` gzips them to `logs/archive/` instead of deleting;
  `--dry-run` is a no-op. Default window **30 days**.
- CI: run logs are a workflow artifact with `retention-days: 30`
  (RM-002); artifacts auto-expire, so CI is never the long-term store.
- Aggregates persist, raw lines don't: once a daily file is pruned, the
  rolled-up summary survives in the RM-003/009/011 report, not the source.

## Hooks snippet

The dated opencode CLI/plugin facts (no `hooks` JSON key; hooks are
TypeScript plugins; `opencode run` has no `--skill`) live in one place:
[../../../reference/opencode-integration.md](../../../reference/opencode-integration.md).
[hooks.opencode.json](hooks.opencode.json) records the superseded fictional
snippet; the aspirational run-boundary example is
[observe.plugin.EXAMPLE.js](observe.plugin.EXAMPLE.js) — not schema-honest and
not enabled by default. Convention-based logging remains the default.
