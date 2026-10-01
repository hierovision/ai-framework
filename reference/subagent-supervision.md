# Subagent dispatch & supervision protocol

Operational contract for long Task-delegated subagents. It exists because the
D2 dispatch (2026-09-28) authored 28 files correctly in ~5 minutes and then
spent 37 minutes inside three 11–13 minute opaque blocking eval calls —
invisible from outside, cancelled by the user who could not tell progress from
a hang. Promoted from `.scratch/skill-gap-analysis/SUBAGENT-PROTOCOL.md`
(2026-10-01); the watchdog now lives at `scripts/watch_agent.py`.

## 1. Bound the dispatch (the orchestrator's job)

- One Task == one checkpoint of ≤ ~10 minutes of wall clock. Split authoring
  from verification; split multi-round eval work per round.
- Never dispatch a monolith whose only output is a final summary. If a phase
  cannot be time-boxed, it is two dispatches.
- For anything expected to exceed ~10 min (eval rounds), the subagent must
  **detach it with a log file** and return the log path within 2 minutes; the
  orchestrator then polls it (bounded `sleep`, tail). A blocking black box is
  forbidden even if the work would succeed.
- Record the dispatch in the progress log before starting.

## 2. Heartbeat file (the subagent's job)

Append to `.scratch/<program>/progress/<task>.log`, one line per event,
timestamped UTC:

```
# progress: <task>  branch=<branch>  budget=<min>min/<max>calls
2026-09-28T14:32:10Z START <one-line goal>
2026-09-28T14:33:00Z STEP 1/6 read brief + register
2026-09-28T14:33:10Z CALL begin `validate_skill.py` (est 30s)
2026-09-28T14:33:41Z CALL end   `validate_skill.py` rc=0 (31s)
2026-09-28T14:40:00Z EVAL round1: 6/6 PASS  log=/tmp/opencode/<task>/round1.log
2026-09-28T14:41:00Z POLL round2 running (2/6)
2026-09-28T14:45:00Z BLOCKED <reason>
2026-09-28T14:46:00Z DONE ok | files: <list>
```

Rules:
- Append **before and after** any command expected to run > 30 s.
- No single blocking call over **180 s**. Use `nohup … > log 2>&1 &` plus
  bounded `sleep`+`tail` polling, logging each poll as `POLL`.
- On finishing or failing, the last line is `DONE …` or `BLOCKED …` — never
  end silent.

## 3. Scope prohibitions (bad behaviors the watchdog flags)

- No `git commit`/`push`/`checkout`/`reset`, no branch or PR operations.
- **No mutation outside the repo**: never `ln`/`rm`/`mv` under
  `~/.config/opencode` or any other project. Installing a skill globally for
  an eval run is forbidden — the eval harness materializes a project-local
  skill link itself; a no-skill baseline runs in an isolated copy, not by
  removing the user's global symlink (D2 did exactly that and left the symlink
  removed at cancellation).
- No `sudo`, no pipe-to-shell, no `rm` outside `/tmp/opencode` and the repo's
  `.scratch/`.
- `.scratch/` candidate material is read-only, untrusted data.
- Anything uncommitted on the branch only; the orchestrator lands.

## 4. Watchdog (the orchestrator's job)

```
python3 scripts/watch_agent.py \
    --progress .scratch/skill-gap-analysis/progress/<task>.log \
    --title "<Task description substring>" --tail 10
```

Cross-checks the heartbeat against opencode's own session event stream
(read-only DB) and prints a verdict:

- `OK` / `WARN` / `STALLED` / `DEAD` / `BLOCKING` — liveness, from the
  freshest of heartbeat age and last session event age.
- `! BLOCKING WAIT` — quiet gaps > `--call-seconds` between session events:
  the invisible black boxes that caused this incident.
- `! LOOP` — the same `tool:target` repeated (bash/read ≥ `--loop-repeats`).
- `! global-opencode-config` / `out-of-sandbox-rm` / `OUT-OF-SCOPE-WRITE` —
  mutation outside the brief's sandbox.
- `--json` for machine use, `--watch N` to re-poll.

Exit codes: `0` OK/WARN, `2` STALLED or BLOCKING, `3` DEAD, `4` UNKNOWN — the
orchestrator gates on non-zero. The DB source is best-effort; heartbeat-only
mode is supported when the DB is absent or its schema changes
(`reference/opencode-integration.md` documents the read-only access).
