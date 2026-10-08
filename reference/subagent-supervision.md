# Subagent dispatch & supervision protocol

Operational contract for long Task-delegated subagents. It exists because the
D2 dispatch (2026-09-28) authored 28 files correctly in ~5 minutes and then
spent 37 minutes inside three 11–13 minute opaque blocking eval calls —
invisible from outside, cancelled by the user who could not tell progress from
a hang. Promoted from `.scratch/skill-gap-analysis/SUBAGENT-PROTOCOL.md`
(2026-10-01); the watchdog now lives at `scripts/watch_agent.py`.

## Dispatch vehicles

- **In-session Task**: works when the parent session is on a nested-capable
  tier (Go / Zen / direct-key); a nested free-bound subagent is
  environment-dependent (CI rejects it) — see `reference/agent-teams.md`
  §Lane policy.
- **Run-vehicle**: `python3 scripts/dispatch_agent.py --agent <name>
  --prompt-file <file>` runs a top-level `opencode run`, prints the session id
  (resume with `--session`), validates the captured result against a declared
  contract, and emits exactly one `kind=agent` run-log record with agent +
  resolved model. Lane policy, topology bounds, question relay, and the full
  attribution contract: `reference/agent-teams.md`.
  - **Live visibility flags** (opt-in; mandatory-by-contract on any dispatch
    expected to exceed ~10 min): `--stream-out FILE` tees the stdout JSON
    event stream, `--stream-err FILE` tees stderr, `--heartbeat FILE` writes
    the dispatcher envelope and injects the §2 protocol block. A fresh
    dispatch truncates the targets; `--session` resume appends. The block
    is injected only on a fresh dispatch — a `--session` resume appends to
    the heartbeat without re-injecting it, so resumes do not accumulate
    copies. An unopenable target exits 2 before opencode launches (no
    session created).
  - **External grants**: `--allow-dirs PATH` (repeatable) grants opencode's
    `permission.external_directory` allow-map for one declared path,
    `<abs-path>/**`, least privilege. Without it behavior is unchanged.

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
- **Any brief whose work reaches outside the working directory must pass
  `--allow-dirs`** for each external path (least privilege; one flag per
  path). opencode's `external_directory` permission auto-rejects
  non-interactively: the turn terminates and `opencode run` exits 0 with no
  final text, which surfaces as an uninformative `empty result`. This is the
  two-architect incident of 2026-10-03 (`ses_efd9815fdffepLG4xeD2n3d6xS`,
  `ses_efd8a001dffePR1M6prjSgCrcL`). A denial now classifies as
  `permission denied: <tool> <command-or-path>` rather than `empty result`.

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

**Line ownership (run-vehicle).** The dispatcher owns the envelope — it
writes the `# progress:` header and `START` before launch and exactly one
terminal `DONE ok` / `BLOCKED <detail>` line on every outcome branch. The
subagent owns the body: `STEP` / `CALL begin|end` / `POLL` lines. The
injected prompt block names the absolute heartbeat path and cites this
section; the dispatcher never re-defines the protocol. Line format and the
parser regex live in `scripts/watch_agent.py`.

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

With the visibility flags the operator watches plain files live; the
watchdog remains the cross-check of heartbeat against opencode's own session
stream.

```
# launch (fresh truncates; --session resume appends)
python3 scripts/dispatch_agent.py --agent <name> --prompt-file <file> \
    --stream-out .scratch/dispatch/run.events.jsonl \
    --stream-err .scratch/dispatch/run.stderr.log \
    --heartbeat .scratch/dispatch/run.progress.log \
    --allow-dirs ../sibling-repo          # only if the brief reaches outside
# watch while it runs (two independent live channels)
tail -f .scratch/dispatch/run.events.jsonl
tail -f .scratch/dispatch/run.progress.log
```

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

## 5. Session-tree guard (pattern registry + abort authority)

The watchdog supervises one dispatched subagent; the **session-tree guard**
(`scripts/session_guard.py`) supervises the whole tree — the orchestrator's
workers and their workers (depth ≤ 2, `reference/agent-teams.md`) — and is
**mandatory by contract for any dispatch wave**, the same way live-visibility
flags are mandatory for runs expected to exceed ~10 minutes. Where the
watchdog flags, the guard escalates: flag → kill-child (surfaced) → **abort
the session**. A known failure pattern costs minutes, not an hour.

Launch forms:

```
# observe a live tree (read-only; no kill without explicit authority)
python3 scripts/session_guard.py --root <session-id> --watch 15 --json

# own the root process: abort is mechanical (process-group SIGTERM→SIGKILL)
python3 scripts/session_guard.py --root <id> --wrap -- opencode run ...
```

Pattern registry v1 (each detector grounded in an observed incident;
`--contract` enables RM-023 marker validation):

| Pattern | Signal | Action |
|---|---|---|
| `empty-result` | final result empty or missing its declared contract markers (RM-023) | flag |
| `permission-auto-reject` | `permission requested: external_directory … auto-rejecting` / `permission denied: …` — evidence names the denied path and hints `--allow-dirs` (the 2026-10-03 two-architect class) | flag |
| `dead-stream` | dispatched child with zero messages and zero parts (RM-026 class) | flag |
| `blocking-wait` | quiet gap > `--call-seconds` between session events (watchdog analysis) | kill-child |
| `stalled` | watchdog verdict STALLED/DEAD | kill-child |
| `identical-retry-loop` | ≥ `--retry-cap` (default 2) identical relaunches of the same agent + prompt digest after failed results within `--retry-window-min` (RM-024's bound, enforced) | **abort** |
| `wave-failure` | ≥ `--wave-ratio` (default 0.6) of one dispatch wave failing with a shared pattern (the 2026-10-07 reviewer-wave shape: 3 of 5 empty) | **abort** |
| `budget-exceeded` | tree wall clock > `--budget-minutes` (default 45; 0 disables) | **abort** |

`kill-child` is surfaced, not executed: an in-session Task child lives inside
the root process and has no separate pid (its kill is the root abort), while a
run-vehicle child is already bounded by `dispatch_agent.py --timeout`'s
process-group kill. The guard names the sessions to kill in its output.

**Abort contract.** An abort-class pattern fires → the guard writes exactly
one `ABORT` sentinel (JSON: `pattern`, `evidence`, `sessions`, `ts` UTC `Z`,
`root_session_id`; default `.scratch/session-guard/ABORT.<root-id>`) and emits
exactly one run-log record `kind=agent` / `outcome=stopped` with the pattern
in `detail`. The root process group dies only under kill authority: `--wrap`
(the guard owns the root) or `--kill-root --root-pid PID` (explicit, never a
`pgrep` guess — `opencode session` has no abort subcommand, only
`list`/`delete`). Exit codes: `0` clean, `2` warned (or abort warranted
without kill authority), `5` abort performed, `4` unknown.

Liveness is never reimplemented: the guard imports `watch_agent`'s
`analyze_session`/`verdict`, and its DB access is a `file:…?mode=ro` URI
(asserted by `scripts/test_session_guard.py`).
