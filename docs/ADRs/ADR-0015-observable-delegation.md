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
8. **Root routing + trust.** A delegate's milestone belongs to the ROOT of
   its parent chain: the server walks up (bounded) and follows a run-vehicle
   title marker, so depth-2 children reach the real orchestrator. A title
   marker is still a claim — trust is root-only (an existing root named by a
   title passes; this is a local-context boundary, not provenance), and an
   unresolvable chain drops the milestone visibly.
9. **Independent fallback companion.** A small always-loadable
   `delegation-sentinel` plugin (no-op server + TUI) renders the fallback line
   when the observer is absent, failed, disabled, disconnected, or its TUI is
   not running (presence marker `tui.json`). It reads the observer's plugin
   record and health record and never renders delegate detail; the observer
   cannot be relied on to draw its own absence banner.
10. **TUI config source.** 2.1.4 does not forward plugin options to the TUI
   part, so `DELEGATION_OBSERVER_ENABLED/STALL_SECONDS/HEALTH_FILE/
   STATUS_FILE` carry every TUI-relevant value end to end (options win when a
   host does forward them).

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
  values accept a documented env seam. Precedence is per key: a forwarded
  option wins, the env fills the gap, the shared contract is the default.
- A `thrash` warning clears on the next activity (`touch`); the durable signal
  is the single deduped milestone. Kept as a known limit, not hidden.
- Trust is root-only: a title naming any existing root passes (local-context
  boundary, not provenance).

## Evidence (2026-10-29, final round)

Live drills on isolated disposable managed services (ports 4099–4102;
isolated `XDG_CONFIG_HOME`/state/cache/tmp + `OPENCODE_DB`, TUI attached with
`--server`); all captures under `.scratch/rm-069/` (gitignored):

| Drill | What the capture proves | Path |
|---|---|---|
| D1 in-session | live `running: tool: sleep 25` row + child `parent_id` in the DB | `service-drill/final2/d1/{pane-running.txt,db.txt}` |
| D2 run-vehicle | attributable `sleep 20` running row, title marker, one synthetic, `WAKE success` 40 s after DONE | `service-drill/final2/d2/*` |
| D3 controls | steer queued on the same child id; interrupt → same child `idle_outcome=interrupted` | `service-drill/final2/d3/{steer.txt,pane-interrupt.txt,db.txt}` |
| D4-busy | 40 s tool call stays `running` at a 5 s drill threshold | `service-drill/final/busy/*` |
| D4-stall | quiet child warns at 5 s, fails at 2× | `service-drill/final/stall-pane.txt` |
| D4-loop | three identical calls → one `thrash` per child, deduped | `service-drill/final/{loop-pane.txt,loop2/,db.txt}` |
| D5 needs-input | waiting row + `needs-input` milestone naming the action | `drills/d5-pane.txt` |
| D6 absent | sentinel banner + terminal wake with no observer plugin | `d6/absent/{pane-absent.txt,pane-absent-fallback.txt,fallback/progress.log}` |
| D6 disabled | observer `! delegates unavailable` + sentinel disabled line (env) | `d6/disabled/pane-disabled.txt` |
| D6 TUI-failed | host `1 plugin failed` + sentinel `TUI is not running` | `d6/broken/pane-broken.txt` |
| nested depth-2 | grandchild milestone routed to the root through the vehicle marker | `service-drill/final2/nested/db.txt` |
| AC5 | no assistant turn between synthetics and the wake | `service-drill/final/db.txt`, `final2/d2/db.txt` |
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
- `plugins/delegation-sentinel/` — the always-loadable fallback banner.
- `docs/roadmap-detail/RM-069.md` — provenance and verification.
- RM-058 detail (`docs/roadmap-detail/RM-058.md`) — retained contracts.

## Amendment (2026-10-30) — discovery is not liveness

Post-apply defect on `main` (d13d504): the TUI strip listed historical child
sessions as `running: starting`, then flipped them all to
`stalled: quiet 245s`. Two causes, both in the implementation of Decision 3
and 4, not in the decision itself:

- `associateSessionInfo` accepted every `session.list()` entry with a
  `parent_id` or a `[delegate:…]` title and seeded
  `lastActivityAt = state.now()`, so quiet measured time since the *observer
  booted*; every bootstrapped row therefore carried an identical value.
- Nothing distinguished a session this process had evidence for from one the
  store merely remembered. `session.list()` returns every child the store has
  ever seen (274 in this repo's project, 272 idle for more than 10 minutes),
  so association alone produced a wall of false `running` rows and, later,
  false stall milestones.

Amends Decision 3 ("universal association") and Decision 4 ("progress is
event-driven"):

1. **Association is discovery; liveness needs evidence.** A row is `running`
   only when the host's live active map (`ctx.data.session.status`, `"idle" |
   "running"` on 2.1.4) says so or the session produced an event in this
   observer process. Everything else is `unknown` — a first-class status, not
   a soft `running`. The active map is *reconciled*, not accumulated: when
   the live map cannot be read at all, every discovered row is demoted to
   `unknown` and the banner says why; an id that disappears from an available
   map is denied the same way. A last-known `running` is never carried
   forward. Observed rows are untouched.
2. **Quiet comes from the session, never from the observer.** A discovered
   row's `lastActivityAt` is the store's real last event (`SessionInfo.time.
   updated`) where available and `null` otherwise; a `null` clock renders as
   `—` instead of claiming elapsed time. Two delegates with different last
   events therefore never share a quiet value by construction.
3. **The store outcome is terminal and outranks the live map.** The field is
   `SessionInfo.outcome` (`"succeeded" | "failed" | "interrupted"`), not a
   DB-column alias. A row carrying an outcome renders `completed`/`failed`,
   never `running`, emits no synthetic start/terminal milestone, and keeps the
   outcome across a map demotion. Completions observed live
   (`session.execution.*`) stay visible as `completed`; a completion that
   exists only in the store is history.
4. **Archived is final, for every row.** `time.archived` (bootstrap) and
   `session.archived` (live) hide the row; `markActive` and event promotion
   cannot revive it. Archive outranks the live map and observed provenance.
   `session.unarchived` is the only way back *from archived* — it does not
   make a row live again by itself: a row that is also terminal in the store
   stays collapsed history (stale) after unarchiving, because the store
   outcome is independent evidence. "Back in the strip" requires a live map
   entry or a real event, and never applies to a store-terminal row.
5. **History is collapsed, not reported.** A row that is archived, terminal in
   the store without being observed here, or (discovered) older than
   `staleGraceSeconds` is stale: never `running`, never a synthetic
   milestone, never clock-classified, collapsed into one
   `N stale delegates hidden` line and excluded from the focus/steer/
   interrupt picker. `delegation.history` (alt+g) is the explicit read-only
   path to focus one. `staleGraceSeconds` is an observer-owned display window
   (default 600 s) reached through the TUI env seam
   (`DELEGATION_OBSERVER_STALE_GRACE_SECONDS`); it is **not** part of
   `scripts/supervision_contract.json`, whose values are generated from the
   Python watchdog owners and carry no display window.
6. **Universal discovery is retained** for genuinely live delegates: a live
   active-map entry promotes the row, and the first real event promotes it
   *and refreshes the observation clock to the event/observation time*, so the
   next tick cannot read a 19 h-old store timestamp as quiet time. From there
   the documented stall/thrash/needs-input semantics apply unchanged, and
   `touch` clearing a warning also clears `unknown`.

Evidence: `docs/roadmap-detail/RM-069.md` → *The 2026-10-30 stale-row defect*.

## Amendment (2026-10-31) — attention wakes the parent once (RM-070)

Decision 5 sent every milestone with `resume:false` and kept the terminal wake
as the only prompt. The owner's 2026-10-31 challenge found the gap: a
`thrash`, `stall`, `needs-input` or `denied` milestone reached the parent's
inbox while the parent was idle, so the condition could burn work or deadlock
before the parent's next turn. This amendment narrows Decision 5 only. The
rest of ADR-0015 stands.

1. **Attention exception.** `thrash`, `stall`, `needs-input` and `denied`
   start exactly one parent turn per condition (same child, same kind, same
   target). Re-delivery of the same condition starts no second turn.
   `start`, `first-tool`, `resume`, `retry` and `terminal` remain
   `resume:false`; the RM-058 terminal wake remains the only terminal prompt.
2. **Bounded and visible.** `maxAttentionWakes` (default 3) caps attention
   turns per child per observer process. Beyond the cap the milestone is still
   queued as context (`resume:false`) and the drop is logged with its count
   (`attention wake dropped`, reason `cap` or `disabled`). `attentionWake`
   (default true) disables the exception entirely.
3. **Same gates, no new authority.** A wake uses the existing trusted-root and
   same-directory gate. An untrusted or unresolvable parent receives no wake
   and records the existing degradation. The plugin never auto-interrupts or
   cancels a child — the parent decides.
4. **Honest text.** A wake names the child, the condition and the task, says
   the parent may steer or interrupt, and never claims the child stopped. The
   parent is told to check the child's current state first.
5. **Configurable.** Options `attentionWake` / `maxAttentionWakes` and env
   `DELEGATION_OBSERVER_ATTENTION_WAKE` /
   `DELEGATION_OBSERVER_MAX_ATTENTION_WAKES`; a forwarded option wins over env,
   env wins over the shared default.
6. **Host vocabulary.** On the headless 2.1.4 server the tool name arrives in
   `session.tool.input.started` and the parsed input in
   `session.tool.input.ended`; `session.tool.called` carries no name and
   `session.message.content.updated` was not emitted. The reducer consumes the
   input events as well, so thrash detection works on the real host stream.

Evidence: `docs/roadmap-detail/RM-070.md` (unit, mutation and isolated live
drill).
