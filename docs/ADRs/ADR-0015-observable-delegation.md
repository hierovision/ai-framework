# ADR-0015 — Observable delegation (event-driven subagent status + owner controls)

## Status

accepted 2026-10-29

## Context

RM-058 shipped concurrent owner turns and wake-on-completion, but deliberately
deferred live progress: its observer polls the durable surface every 30 s, and
the plan's Open Question left `session.idle`/plugin progress unimplemented.
The consequence is the original 2026-09-28 failure shape — a delegated child is
a black box until it ends; the owner either polls files or waits.

OpenCode V2 2.1.4 now exposes the missing surfaces (probed 2026-10-29; facts in
`reference/opencode-integration.md`):

- a server event stream (`ctx.event.subscribe()` / `GET /api/event`) with
  per-step, per-tool, permission, form, usage and execution events;
- a TUI plugin API (`@opencode/plugin/tui`) with slots, toasts, attention,
  keymap commands, dialogs and tabs;
- an explicit child hierarchy (`session_v2.parent_id`, `session.created`);
- synthetic messages (`ctx.session.synthetic`) that add **no model turn**;
- `GET /api/plugin`, which reports each plugin's `features` and `state`
  (`active` / `failed`).

## Decision

1. **One observer plugin, two parts.** `plugins/delegation-observer/` exports a
   server part (`server.ts`: association, reducer, synthetic milestones) and a
   TUI part (`tui.tsx`: strip, footer, panel, toasts, controls). The loader
   resolves `<dir>/server` and `<dir>/tui`; a `tui` entry sets
   `features.tui`. No `cli.json` switch is needed (verified).
2. **Background handles.** The run-vehicle orchestrator form is
   `dispatch_agent.py --detach` (pid/log/heartbeat/session file returned
   immediately; the child keeps writing durable surfaces, the wake still
   fires). An in-session `subagent` runs as a background tab while the parent
   model keeps its turn; the parent tool call itself is synchronous.
3. **Universal association without a registry.** In-session children map via
   `parent_id`; run-vehicle children carry the machine-readable title
   `[delegate:<orchestrator-session-id>] <agent>: <task>`, emitted by the
   shared adapter and set with `run --title`. Interactive dispatch joins the
   shared V2 service so the TUI's event stream owns the child; grant-driven and
   `--standalone` dispatches keep the durable contract.
4. **Progress is event-driven; polling is only the fallback.** The TUI renders
   from `ctx.data.listen` events and never reads heartbeat files. Quiet/stall
   is a local clock over event timestamps, not a file poll. The 30 s
   completion observer and the terminal wake are unchanged and remain the
   fallback for headless/standalone children and for degradation.
5. **Milestones are synthetic and bounded.** start / first-tool / needs-input /
   denied / stall / thrash / retry / resume / terminal. They are sent with
   `delivery:"steer", resume:false` (queued for the next turn, never starting
   one), and only the plugin instance owning the parent's location emits (a
   service activates the plugin once per location). Routine milestones are
   capped at one per delegate per 30 s and deduplicated; attention milestones
   fire once per distinct condition immediately; the terminal one fires
   exactly once. The terminal wake stays the only progress-path **prompt**.
6. **One supervision vocabulary.** Thresholds are generated from
   `watch_agent.py` / `observe_completion.py` into
   `scripts/supervision_contract.json`; the plugin's defaults are asserted
   equal to it. Busy never stalls; an open step gets the generation budget; a
   call in flight gets the blocking budget.
7. **Controls, with unchanged authority.** Focus/open, steer
   (`session.prompt` with `delivery: "steer"`) and interrupt
   (`session.interrupt`) act on the same session id. Tree abort stays the
   session guard's process-group authority; the TUI never gets kill power.
8. **Trust + visible degradation.** A title marker is a claim: before the
   first synthetic message the parent must resolve as a root session
   (`session.get`, no `parentID`), else the milestone is dropped and the drop
   is published. Absent/failed plugin, disconnected stream, disabled config,
   unassociated running *child* sessions (the root is excluded), or a
   server-side health failure produce a banner naming the
   watchdog/observer fallback. The system never claims visibility it does not
   have.

## What this supersedes (and what it does not)

Superseded from RM-058, exactly as its deferred half:

- the poll-observer choice for **interactive local** progress visibility (the
  30 s observer remains the headless fallback and the wake vehicle);
- the deferred `session.idle`/plugin-progress Open Question;
- the assumption that progress visibility requires the owner to tail files.

**Retained unchanged:** terminal wake (vehicle, quiescence gate, wake text,
exactly once), worktree-safe dispatch, per-class permission profiles, the
status-claim ownership rules, and the session guard's kill authority.

## Consequences

- A local delegate is visible within the first event (association is
  event-driven; the AC1 bound is 2 s), and the owner can act without a new
  session.
- Synthetic milestones add context but no turns; the 30 s routine cap bounds
  chatter while needs-input is never delayed.
- The plugin is a presentation/control plane, not a second liveness engine: a
  plugin bug degrades to the durable stack instead of blinding supervision.
- Headless/standalone children are deliberately outside the live view; their
  contract is the watchdog + wake, and the banner says so.
- Host adoption is a separate owner step (install peer deps, add the config
  entry, restart on a known port); this ADR records the shape, not the install.
- 2.1.4 does not forward plugin `options` to the TUI part; the interactive
  thresholds accept a documented env seam while the server uses the options.

## Evidence (2026-10-29)

Live drills on an isolated disposable managed service (`service set port 4099`,
isolated `XDG_CONFIG_HOME`/state/cache/tmp + `OPENCODE_DB`, TUI attached with
`--server`); all captures under `.scratch/rm-069/` (gitignored):

| Drill | What the capture proves | Path |
|---|---|---|
| D1 in-session | strip running→completed, two synthetic milestones, parent turn done | `drills/d1-pane.txt` |
| D2 run-vehicle | title-marker child in the strip, one synthetic, one wake 64 s after DONE | `service-drill/final/d2/*` |
| D3 controls | focus, steer queued on the same id (`delivery:"steer"`), interrupt | `drills/d3-running-pane.txt` |
| D4-busy | 40 s tool call stays `running` at a 5 s drill stall threshold | `service-drill/final/busy/*` |
| D4-stall | quiet child warns at 5 s, fails at 2× | `service-drill/final/stall-pane.txt` |
| D4-loop | three identical calls → one `thrash` per child, deduped | `service-drill/final/{loop-pane.txt,loop2/,db.txt}` |
| D5 needs-input | waiting row + `needs-input` milestone naming the action | `drills/d5-pane.txt` |
| AC5 | no assistant turn between synthetics and the wake | `service-drill/final/db.txt` |
| loader/degradation | loader line + initialized; broken plugin fails visibly | `drill-loader/stderr2.log`, `drill-degraded/stderr.log` |

AC6 wording was reconciled by the architect in the approved plan: routine
progress is capped at one synthetic message per delegate per 30 s; attention
states (needs-input, stall, thrash, terminal) emit immediately, once per
condition. The implementation and tests match that wording.

## References

- `reference/subagent-supervision.md` §7 — the operational contract.
- `reference/opencode-integration.md` — dated V2 API facts (events, TUI,
  synthetic, plugin entrypoints, options).
- `plugins/delegation-observer/README.md` — configuration, controls, install.
- `docs/roadmap-detail/RM-069.md` — provenance and verification.
- RM-058 detail (`docs/roadmap-detail/RM-058.md`) — retained contracts.
