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
| `loopRepeats` | `3` | identical `tool:target` repetitions that flag thrash |
| `generationSeconds` | `600` | quiet budget inside an open assistant step |
| `milestoneMinIntervalSeconds` | `30` | routine synthetic-milestone cap per delegate |

The numeric defaults are the **shared supervision contract**
(`scripts/supervision_contract.json`, generated from `watch_agent.py` /
`observe_completion.py`); `state.test.ts` fails if the TypeScript side drifts.
The status panel prints the effective values.

## Milestones

| Kind | Class | When |
|---|---|---|
| start | routine | first association |
| first-tool | routine | first tool call of the child |
| resume | routine | after a permission/form reply |
| needs-input | attention | `permission.asked` / `form.created` |
| stall | attention | quiet beyond the applicable window (busy is never stalled) |
| thrash | attention | identical `tool:target` ≥ `loopRepeats` |
| terminal | exactly once | `session.execution.succeeded/failed/interrupted` |

Routine milestones are capped at one per delegate per
`milestoneMinIntervalSeconds` and deduplicated; attention milestones fire
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
- running sessions exist with no delegate association (no live visibility).

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

1. From the merged branch: `npm install --omit=dev` in this directory — the
   runtime deps (`@opencode/plugin`, `solid-js`, `@opentui/core`,
   `@opentui/solid`, `@opencode/theme`) must resolve at load. The package's
   `typecheck` script (`tsc -p . --noEmit`) is the type-level proof against
   the 2.1.4 API; it needs a dev install of TypeScript.
2. Add `{ "package": "./plugins/delegation-observer" }` to the versioned V2
   config `plugins` array (keep the auto-compaction entry).
3. Restart the service/TUI on a known port
   (`OPENCODE_WAKE_URL=http://127.0.0.1:4096 opencode --port 4096`) so the
   terminal wake and the event stream share one server.
4. Verify: the plugin loader log line, `GET /api/plugin` shows
   `features.tui: true`, and the sidebar strip appears on the next delegation.
