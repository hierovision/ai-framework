# Delegation observer (V2 plugin)

Makes every delegated subagent observable, steerable and non-blocking — with
no manual polling, no foreground black boxes and no dispatch that returns no
observable handle.

- **Server part** (`server.ts`): subscribes to the connected server's event
  stream, associates each child session with its orchestrator, reduces it, and
  appends rate-limited **synthetic** messages to the orchestrator (no model
  turn).
- **TUI part** (`tui.tsx`): a persistent sidebar strip + footer count, toasts
  and attention alerts, and the focus / steer / interrupt controls. It renders
  from the same event stream; it never reads heartbeat files.

Contract: `reference/subagent-supervision.md` (§7), decision record
`docs/ADRs/ADR-0015-observable-delegation.md`. RM-058's terminal wake,
worktree safety, permission profiles and status-claim rules are **unchanged**
and remain the fallback.

## Association (no side registry)

| Vehicle | Association |
|---|---|
| in-session `subagent` | `session_v2.parent_id` (`session.created` / `session.list()`) |
| run-vehicle (`dispatch_agent.py`) | title prefix `[delegate:<orchestrator-session-id>] <agent>: <task>` (`--title`) |

The marker is emitted by the shared V2 adapter (`scripts/opencode_v2.py`) and
truncated to 160 characters (`delegationTitle`); newlines are collapsed. A
standalone/headless child has no interactive parent and is intentionally not
associated: the durable watchdog/observer remains its contract.

## Configuration

Plugin options live under the plugin entry's options object:

```jsonc
"plugins": [
  { "package": "./plugins/delegation-observer",
    "options": { "delegationObserver": { "enabled": true } } }
]
```

| Option | Default | Meaning |
|---|---|---|
| `enabled` | `true` | disables both parts; the TUI shows the disabled banner |
| `stallSeconds` | `240` | quiet window before `warning` |
| `callSeconds` | `300` | quiet window for a tool call in flight |
| `loopRepeats` | `3` | identical tool targets (one count per call id) that flag thrash |
| `generationSeconds` | `600` | quiet budget inside an open assistant step |
| `milestoneMinIntervalSeconds` | `30` | routine synthetic-milestone cap per delegate |
| `staleGraceSeconds` | `600` | age after which a discovered-only session collapses as stale |
| `healthFile` | `<location>/.scratch/delegation-observer/health.json` | shared degradation record |
| `statusFile` | — | opt-in observer snapshot read by `delegation.status` |
| `DELEGATION_OBSERVER_ENABLED` (env, TUI) | — | `0/false/no/off` disables the TUI part |
| `DELEGATION_OBSERVER_STALL_SECONDS` (env, TUI) | — | interactive threshold |
| `DELEGATION_OBSERVER_HEALTH_FILE` (env, TUI) | — | must match the server's `healthFile` |
| `DELEGATION_OBSERVER_STATUS_FILE` (env, TUI) | — | fallback snapshot path |

The 2.1.4 host does not forward plugin entry options to the TUI part, so the
env source is the end-to-end channel for the TUI; options still win where a
host forwards them. The observer TUI writes a presence marker
(`<location>/.scratch/delegation-observer/tui.json`) for the sentinel.

**Sentinel companion.** `plugins/delegation-sentinel/` is an always-loadable
TUI-only fallback: it renders one line when this plugin is absent, failed,
disabled, disconnected, or its TUI is not running. It never shows delegate
detail.

The numeric defaults are the **shared supervision contract**
(`scripts/supervision_contract.json`, generated from `watch_agent.py` /
`observe_completion.py`); `state.test.ts` fails if the TypeScript side drifts.
The status panel prints the effective values.

## Liveness is evidence, not discovery

`session.list()` returns every child session the store has ever seen, so
association is **discovery only**. A row is `running` only when the host's live
active map says so or the session produced an event in this observer process;
everything else is `unknown`. Quiet comes from the session's real last event
(`time.updated`) and is never fabricated from the observer's own boot clock, so
two delegates with different last events never share a quiet value.

A discovered row that is terminal in the store, archived, or older than
`staleGraceSeconds` is **stale**: it never reads `running`, never emits a
synthetic milestone, and the strip collapses all of them into one
`N stale delegates hidden` line. The same holds for the clock classifier — a
row with no observed event has no observation clock, so it is never classified
stalled. The first real event promotes the row and the documented
stall/thrash/needs-input semantics take over from there. Current-session
completions (`session.execution.*`) stay visible as `completed`/`failed`.

## Milestones

| Kind | Class | When |
|---|---|---|
| start | routine | first association |
| first-tool | routine | first tool call of the child |
| resume | routine | after a permission/form reply |
| needs-input | attention | `permission.asked` / `form.created` (session id at `data.form.sessionID`) |
| denied | attention | `permission.replied` with `reply:"reject"` — a warning, never a resume |
| stall | attention | quiet beyond the applicable window (busy is never stalled) |
| thrash | attention | identical tool target ≥ `loopRepeats` (one count per call id) |
| retry | attention | vendor `retry` status, deduped per attempt |
| terminal | exactly once | `session.execution.succeeded/failed/interrupted` |

Every milestone is sent with `delivery: "steer"` and `resume: false`: it is
queued for the parent's next turn and never starts one. A managed service
activates the plugin once per location, so only the instance owning the
parent session's directory emits. Routine milestones are capped at one per
delegate per `milestoneMinIntervalSeconds` and deduplicated; attention milestones fire
immediately once per distinct condition; the terminal one fires exactly once
and bypasses the cap. Milestones are `synthetic` messages — they add no model
turn. The terminal **wake** (`DISPATCH WAKE …`, `scripts/observe_completion.py`)
is unchanged and remains the only progress-path prompt.

## Controls

| Command | Call |
|---|---|
| `delegation.focus` | `ui.tabs.focus(sessionID)` (falls back to navigation) |
| `delegation.steer` | `client.session.prompt({sessionID, text, delivery: "steer"})` |
| `delegation.interrupt` | `client.session.interrupt({sessionID})` |
| `delegation.panel` | `ui.panel.open("delegates")` |

Bindings in this 2.1.4 TUI: `alt+d` focus, `alt+s` steer, `alt+x` interrupt,
`alt+p` panel, `alt+h` health. Palette/slash entries are declared but this
build does not surface plugin commands there (probed 2026-10-29); bindings are
the working surface.

The run-vehicle orchestrator form is `dispatch_agent.py --detach` (pid, log,
heartbeat and session file returned immediately; the child keeps writing them).

Interrupt is a typed request on the **same** session id. It is not the session
guard's kill authority: process-group abort stays guard-owned
(`scripts/session_guard.py`, `reference/subagent-supervision.md` §5). The
guard's `--interrupt` CLI is the same typed call for an owner-initiated stop.

## Degradation (never silent)

The strip shows a warning (and the footer shows `! delegates unavailable`)
when:

- the plugin is not loaded, or the server record is `failed`;
- the event stream is disconnected/unavailable;
- the observer is disabled by configuration;
- running **child** sessions exist with no delegate association (the
  orchestrator/root is excluded);
- the server part reports synthetic-delivery or stream failure through the
  shared health record (`<location>/.scratch/delegation-observer/health.json`).

In every case the durable watchdog/observer — heartbeat, `watch_agent.py`,
`observe_completion.py` wake — remains authoritative. The plugin never claims
live visibility it does not have.

## V2 API dependencies (verified against 2.1.4, 2026-10-29)

- Loader: `<plugin-dir>/server` and `<plugin-dir>/tui` entrypoints (binary
  `Zg` resolves `server`, `tui`, `rpc`); a relative config path is required.
- Server: `Plugin.define`, `ctx.event.subscribe()`, `ctx.session.list()`,
  `ctx.session.synthetic({sessionID, text, description, metadata})`.
- TUI: `@opencode/plugin/tui`, `ctx.data.listen`, `ctx.ui.slot`
  (`sidebar.content`, `home.footer.status`, `session.panel`),
  `ctx.ui.toast/attention/keymap/dialog/tabs/panel`, `ctx.client.session.*`,
  `ctx.client.plugin.list`.
- Event vocabulary used: `session.created`, `session.renamed`,
  `session.status`, `session.step.started/ended/failed`,
  `session.tool.called/success/failed`, `session.message.content.updated`,
  `session.usage.updated`, `permission.asked/replied`, `form.created/replied/
  cancelled`, `session.execution.succeeded/failed/interrupted`.

## Install / apply (owner step — deliberately not performed here)

1. From the merged branch: `npm install` in this directory. `@opencode/plugin`
   2.1.4, `solid-js` 1.9.12 and `@opentui/core`/`solid` 0.6.8 are declared as
   exact **peer** dependencies (the host provides the versions; npm
   materializes them locally so the loader and typecheck resolve). The
   `typecheck` script (`tsc -p . --noEmit`) is the type-level proof against
   2.1.4.
2. Add `./plugins/delegation-sentinel` alongside it (the fallback banner).
3. Add `{ "package": "./plugins/delegation-observer" }` to the versioned V2
   config `plugins` array (keep the auto-compaction entry).
4. Restart the service/TUI on a known port
   (`OPENCODE_WAKE_URL=http://127.0.0.1:4096 opencode --port 4096`) so the
   terminal wake and the event stream share one server.
5. Verify: the plugin loader log line, `GET /api/plugin` shows
   `features.tui: true`, and the sidebar strip appears on the next delegation.
