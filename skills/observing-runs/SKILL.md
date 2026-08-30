---
name: observing-runs
description: Make every skill/agent/eval execution observable through a structured, queryable run log so the framework can answer "why did the agent do X, and did it regress?". Owns the canonical JSONL run-log schema (single source of truth), the log_run.py emission helper, and the query_runs.py aggregator/pruner. Use whenever the user says "log this run", "why did the agent do X", "what's our eval-pass rate / token cost / latency per skill", "set up run logging", or surfaces observability/ROI/drift needs — even without saying "observe". Not for feeding logs into the agent's own prompt (anti-pattern), per-sub-step tracing, or external telemetry services.
---

# Observing Runs

Turn skill/agent/eval execution into a structured, queryable signal
without bloating the agent's context. This skill owns the **run-log
schema** (the single source of truth), the emission helper
(`log_run.py`), and the aggregator/pruner (`query_runs.py`).

## ROI guardrail (deliberate, non-negotiable)

Logging is **strictly out-of-context at runtime**:

- Records are appended to a file on disk and are read ONLY **out-of-band**
  (humans via `query_runs.py`, CI via RM-002/RM-003, ROI/drift scripts via
  RM-009/RM-011). They are **never injected into the agent's own live
  prompt** for "self-awareness".
- Emission is **once per run, not per internal sub-step**. One JSONL line
  per run boundary; sub-step tracing is out of scope for v1.
- The query script is **opt-in** (run on demand), never per turn.
- `detail` is **failure-only and capped at 512 chars** — never raw prompt,
  output, or transcript.

This keeps logging cost <1% of a run's tokens (one `log_run.py` tool call
≈ 80–160 tokens vs thousands per task) and eliminable entirely via
hook-based emission.

## The contract

The schema is documented authoritatively in
[references/schema.md](references/schema.md) — it is the single source of
truth. Do **not** redefine field names in any writer or reader; import
`log_run.py` instead.

### Emitting a record

```bash
python3 skills/observing-runs/scripts/log_run.py --record '{
  "kind": "eval", "skill": "writing-unit-tests", "model": "go",
  "tokens_in": 812, "tokens_out": 305, "duration_ms": 142000,
  "outcome": "success", "eval_pass": true
}'
```

- `kind` and `outcome` are required; everything else defaults sensibly.
- `log_run.py` is **symlink-safe**: it resolves its own location via
  `realpath(argv[0])`, so a symlinked install
  (`~/.config/opencode/skills/observing-runs`) still resolves correctly.
- Append-only, non-blocking: one line written, no read-back.

### Querying aggregates

```bash
python3 skills/observing-runs/scripts/query_runs.py aggregate --logs-dir logs/
```

Reports per-skill token totals (cost/task), mean `duration_ms` (latency),
and eval-pass rate. See [references/schema.md](references/schema.md) for
the full field/consumer list.

### Pruning (retention)

```bash
python3 skills/observing-runs/scripts/query_runs.py prune --older-than 30d
python3 skills/observing-runs/scripts/query_runs.py prune --older-than 30d --archive
python3 skills/observing-runs/scripts/query_runs.py prune --older-than 30d --dry-run
```

Default window **30 days**; `--archive` gzips to `logs/archive/`; `--dry-run`
is a no-op. Aggregates persist (RM-003/009/011); raw lines don't.

## Hook-based emission (preferred, zero agent tokens)

A hook fires outside the agent's generation and costs the agent **zero
tokens**. Reference config: [references/hooks.opencode.json](references/hooks.opencode.json).
Verify the hook event model against current opencode docs before enabling
auto-instrumentation; fall back to convention-based logging if hooks are
unavailable.

## What gets logged (narrow event set)

- **Eval runs (RM-002):** one record per eval prompt — `kind=eval`,
  `skill`, `model`, `tokens_in/out`, `duration_ms`, `outcome`, `eval_pass`.
  ~63 evals/night → a few hundred lines/day at most.
- **Skill/agent invocations (convention/adoption-gated):** one record per
  run. NOT auto-wired into all 21 skills in v1.

Explicitly NOT logged: full prompts, full agent outputs, intermediate
tool-call transcripts, environment dumps, PII.

## Read path (logs are read, not write-only)

All consumers are out-of-band, on schedule or on demand — never per turn:

- **query_runs** — humans run it on demand (cost/task, latency, eval-pass rate).
- **RM-002** — the scheduled behavioral-eval workflow writes one `kind=eval`
  record per eval and uploads `logs/` as a 30-day artifact.
- **RM-003** — builds a per-skill report from the aggregates.
- **RM-009** — derives the 4 ROI numbers from token/duration fields.
- **RM-011** — the eval-pass-rate slope is the drift score.

## Anti-patterns (explicitly forbidden)

- **Do NOT feed run-log content back into the agent's context window.**
  It defeats the ROI guardrail and turns bounded telemetry into context bloat.
- **Do NOT log per internal sub-step** (one record per tool call). Emission
  is once per run only.
- **Do NOT capture raw prompt / output / tool-call transcripts.** `detail`
  is failure-only, capped 512 chars.
- **Do NOT keep logs forever.** Prune (default 30d); only rolled-up
  aggregates persist.
- **Do NOT send logs to any external service / database.** File-based only.
