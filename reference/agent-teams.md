# Agent teams — dispatch, lanes, and attribution

The contract for composing the framework's personas as delegated workers from
one orchestrating session: who may dispatch whom, which lane a delegation may
use, how questions travel back, and how every delegation is attributed.
Supervision mechanics live in `reference/subagent-supervision.md`; result
validity in `reference/delegated-result-contract.md`.

## Topology and bounds

- **Orchestrator → worker**: one orchestrating session dispatches workers via
  the Task tool (in-session) or the run-vehicle
  (`scripts/dispatch_agent.py`). Workers do not dispatch beyond the policy
  below.
- **Depth ≤ 2**: the orchestrator's workers may dispatch their own workers
  (architect → planner), but the chain stops there — a third nesting level is
  forbidden. The leaf side of the permission matrix enforces the stop.
- **Fan-out ≤ 6**: at most six parallel workers per dispatch wave (the council
  precedent: five lenses + chairman). Split larger sets into waves, and keep
  each Task to one checkpoint of ≤ ~10 minutes per
  `reference/subagent-supervision.md` §1.
- The only encoded dispatch rule is **leaf hygiene**: the planner, every
  `council-*` lens, and the single-shot roles (`reviewer`, `skill-reviewer`,
  `vision-critic-fast`, `vision-critic-final`) deny `task`, so a single-shot
  agent cannot recurse. Orchestrators and the loop workers (`test-writer`,
  `debugger`, `skill-author`) carry no `permission.task` allow-list
  (`reference/opencode-integration.md`).

## Composition

Composition is **judgment-led**: any dispatchable persona may spawn any other
within the bounds above. There is deliberately no per-persona allow-list — a
hard matrix is a design-time guess that forbids exactly the task-driven
composition (an implementer that needs `architect` after a contract-breaking
discovery, a curator that wants a `council` read). Typical compositions are
examples, not gates:

- an orchestrator → any worker (the general case);
- architect → planner or a council lens for design consults;
- implementer → `test-writer` / `debugger` / `council-*` / explore while
  building;
- a verifier that resists → `debugger`, then back to `implementer`;
- UI iteration → `vision-critic-fast` during the fix loop,
  `vision-critic-final` for sign-off;
- meta-loop → `skill-author`, then `skill-reviewer` (the author never grades
  itself);
- curator → architect / planner / implementer to route an item;
- leaves by role: planner, `council-*`, `reviewer`, `skill-reviewer`,
  `vision-critic-fast`, `vision-critic-final`.

The leaf deny is the one mechanically encoded exception.

## Lane policy

- A delegation runs on the lane the target's declared `model` resolves to;
  named dispatch honors the target's frontmatter `model`
  (`reference/opencode-integration.md`).
- **In-session Task works when the parent session is on a nested-capable
  tier — Go, Zen, or the direct-key lane.** Every framework persona is
  Go-bound by default (go-first policy, 2026-10-03 — plan
  go-first-model-bindings), so in-session dispatch is the normal path.
- **A nested free-bound subagent is environment-dependent.** CI rejects it
  (`OpenCode's free tier can only be used from within OpenCode` —
  `scripts/ci-lane-overrides.py` keeps the guard for free-bound consumer
  wrappers), and the 2026-10-01 free council died nested locally (RM-017 →
  council bound to Go). A free-bound target is a consumer-repo binding, not
  a framework persona: when the orchestrator is headless or the target is
  free-bound, do not rely on in-session dispatch.
- **Targets outside the nested-capable tiers route through the run-vehicle
  when in-session is not viable**: `python3 scripts/dispatch_agent.py
  --agent <name> --prompt-file <file>` runs a top-level `opencode run`
  session, prints the session id, captures the result, and emits the
  attribution record. `--model <id>` overrides the lane for that call;
  `--contract <name>` fails the dispatch non-zero when the result is empty
  or malformed (`reference/delegated-result-contract.md`). Add
  `--stream-out FILE`, `--stream-err FILE`, and `--heartbeat FILE` for live
  visibility (mandatory by contract for runs expected to exceed ~10 min) and
  `--allow-dirs PATH` (repeatable, least privilege) for any brief that
  reaches outside the working directory — see
  `reference/subagent-supervision.md` §Dispatch vehicles.
- While a delegated run is in flight, supervision follows RM-022
  (`scripts/watch_agent.py`): a stalled or blocking run is flagged within one
  poll. A dispatch wave runs under the session-tree guard
  (`scripts/session_guard.py`, `reference/subagent-supervision.md` §5) —
  mandatory by contract: it observes workers and workers' workers (depth ≤ 2),
  matches the known failure-pattern registry (empty results, permission
  auto-rejects, identical-retry loops, wave-majority failures, budget
  overrun), and holds abort authority — it fails the session fast instead of
  letting a broken wave burn one.

## Question relay

Two resume paths, one per lane; both preserve the worker's context instead of
restarting it:

- **Task path**: resume with the Task tool's `task_id`. RM-025 applies — the
  resume call MUST carry `description` (a `SchemaError(Missing key
  ["description"])` otherwise). Record the requirement at the call site.
- **Run-vehicle path**: the dispatch prints the session id; resume with
  `opencode run --session <id>` (`scripts/dispatch_agent.py --session <id>`).
  RM-022 supervision applies while it runs.

Never restart a relayed question in a fresh context while the prior session is
resumable — that discards the worker's state.

## Attribution

Every delegated run emits **exactly one** `kind=agent` run-log record with
non-null `agent` and `model` (schema owner:
`skills/observing-runs/scripts/log_run.py`; RM-001):

- **Run-vehicle (mechanical)**: `scripts/dispatch_agent.py` resolves the
  model from the finished **session row** (`session.model`, read-only through
  the watcher's reader), falling back to the declared binding when the DB is
  unavailable (explicit `--model`, else the target's frontmatter). The
  pre-run line labels the declared value `binding=`; completion prints the
  session-resolved `model=`, and the record uses the session-resolved value —
  so a consumer repo's project wrapper is never recorded as the framework's
  free binding. It sums tokens/cost from the event stream and emits the
  record itself.
- **In-session Task (convention)**: the orchestrator emits the record after
  collecting the result — agent = the dispatched subagent type, model = the
  child run's resolved model (the `model` blob on the child session row, or
  the binding shown in the run header), outcome per
  `reference/delegated-result-contract.md`. `python3 scripts/watch_agent.py
  --json` exposes the session `model` so this needs no raw DB reads by hand.

## Integration

- RM-022 — supervision: `reference/subagent-supervision.md` (heartbeat,
  bounded calls, watchdog); this document adds the run-vehicle dispatch form
  and the attribution line.
- RM-023 — delegated-result contract: `reference/delegated-result-contract.md`
  (empty or malformed = failed run, never clean).
- RM-024 — retry / vehicle-switch: a failed delegation is retried at most
  twice on the same vehicle, then switched or taken over inline.
- RM-025 — Task resume requires `description`: recorded at the call site in
  §Question relay.
