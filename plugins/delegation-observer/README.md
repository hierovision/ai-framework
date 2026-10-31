# Delegation observer (V2 plugin)

Makes every delegated subagent observable, steerable and non-blocking — with
no manual polling, no foreground black boxes and no dispatch that returns no
observable handle.

- **Server part** (`server.ts`): subscribes to the connected server's event
  stream, associates each child session with its orchestrator, reduces it, and
  appends rate-limited **synthetic** messages to the orchestrator. Routine and
  terminal milestones add no model turn; an attention condition starts exactly
  one bounded parent turn (RM-070).
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
| `staleGraceSeconds` | `600` | history window: a discovered row older than this collapses as stale |
| `attentionWake` | `true` | `thrash`/`stall`/`needs-input`/`denied` start one parent turn (RM-070) |
| `maxAttentionWakes` | `3` | attention turns per child per observer process |
| `healthFile` | `<location>/.scratch/delegation-observer/health.json` | shared degradation record |
| `statusFile` | — | opt-in observer snapshot read by `delegation.status` |
| `DELEGATION_OBSERVER_ENABLED` (env, TUI) | — | `0/false/no/off` disables the TUI part |
| `DELEGATION_OBSERVER_STALL_SECONDS` (env, TUI) | — | interactive threshold |
| `DELEGATION_OBSERVER_STALE_GRACE_SECONDS` (env, TUI) | — | history window (positive seconds) |
| `DELEGATION_OBSERVER_ATTENTION_WAKE` (env) | — | `0/false/no/off` disables attention wakes |
| `DELEGATION_OBSERVER_MAX_ATTENTION_WAKES` (env) | — | positive integer cap |
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

The **watchdog thresholds** (`stallSeconds`, `callSeconds`, `loopRepeats`,
`generationSeconds`, `milestoneMinIntervalSeconds`) are the shared supervision
contract (`scripts/supervision_contract.json`, generated from `watch_agent.py` /
`observe_completion.py`); `state.test.ts` fails if the TypeScript side drifts.
`staleGraceSeconds` is **not** part of that contract: it is an observer-owned
display window with no Python owner, so it lives here and in the plugin only.
The status panel prints the effective stall/call/loop/generation thresholds
and the effective stale grace.

## Liveness is evidence, not discovery

`session.list()` returns every child session the store has ever seen, so
association is **discovery only**. A row is `running` only when the host's live
active map says so or the session produced an event in this observer process;
everything else is `unknown`. Quiet comes from the session's real last event
(`time.updated`) and is never fabricated from the observer's own boot clock, so
two delegates with different last events never share a quiet value.

**Terminal and archived are final.** The store outcome is the real
`SessionInfo.outcome` field (`succeeded`/`failed`/`interrupted`); such a row
reads `completed`/`failed`, never `running`, emits no synthetic start/terminal
milestone, and keeps that outcome even when the live map says running.
`time.archived` and the `session.archived` event hide a row for good — the
live map and later events cannot revive it; `session.unarchived` is the only
way back from archived, but it does not by itself return a store-terminal row
to the live strip (that row stays collapsed history). A completion you watched
happen (`session.execution.*`) stays visible; one that only exists in the
store is history.

A row that is archived, terminal in the store but unobserved here, or
(discovered) older than `staleGraceSeconds` is **stale**: it never reads
`running`, never emits a synthetic milestone, is never clock-classified, is
excluded from the focus/steer/interrupt picker, and collapses into one
`N stale delegates hidden` line. The first real event promotes a discovered
row *and* resets the observation clock to that event's observation time, so an
old store timestamp can never be read as quiet time; from there the documented
stall/thrash/needs-input semantics take over.

Tool calls are labelled from `session.tool.input.started` (name) and
`session.tool.input.ended` (input JSON) as well as
`session.message.content.updated`: the headless 2.1.4 server emits the former
pair and may emit neither a name on `session.tool.called` nor content updates,
so thrash detection does not depend on a TUI being attached.

If the host cannot answer `session.list()`/`session.status()`, the live map is
unavailable: the banner says so and every discovered row is demoted to
`unknown` (stale if its last event is past the grace window) — a last-known
`running` is never carried forward. The same reconciliation denies any id that
disappears from an otherwise available map. Observed rows are untouched; their
own event clock owns them. Recovery re-promotes a discovered row as soon as the
map answers again.

## Milestones

| Kind | Class | When | Parent turn |
|---|---|---|---|
| start | routine | first association | no |
| first-tool | routine | first tool call of the child | no |
| resume | routine | after a permission/form reply | no |
| needs-input | attention | `permission.asked` / `form.created` (session id at `data.form.sessionID`) | **one wake** |
| denied | attention | `permission.replied` with `reply:"reject"` — a warning, never a resume | **one wake** |
| stall | attention | quiet beyond the applicable window (busy is never stalled) | **one wake** |
| thrash | attention | identical tool target ≥ `loopRepeats` (one count per call id) | **one wake** |
| retry | attention | vendor `retry` status, deduped per attempt | no (strip alert only) |
| terminal | exactly once | `session.execution.succeeded/failed/interrupted` | no (the RM-058 wake prompts) |

Every milestone is sent with `delivery: "steer"`. Routine and terminal
milestones carry `resume: false`: they are queued for the parent's next turn
and never start one. An attention milestone (`thrash`, `stall`, `needs-input`,
`denied`) carries `wake: true` and is sent with `resume: true`, starting
exactly one parent turn per condition (same child, same kind, same target).
`attentionWake` (default true) disables that exception; `maxAttentionWakes`
(default 3) caps it per child per process. Beyond the cap the milestone is
still queued as context with `resume:false` and the drop is logged with its
count (`attention wake dropped`). Retry stays strip-only. The wake text names
the child, condition and task and says the parent may steer or interrupt;
it never claims the child stopped. A managed service activates the plugin once
per location, so only the instance owning the parent session's directory
emits. Routine milestones are capped at one per delegate per
`milestoneMinIntervalSeconds` and deduplicated; attention milestones fire
immediately once per distinct condition; the terminal one fires exactly once
and bypasses the cap. Milestones are `synthetic` messages, so a wake costs one
parent turn and nothing else. The terminal **wake** (`DISPATCH WAKE …`,
`scripts/observe_completion.py`) is unchanged and remains the only terminal
prompt.

## Controls

| Command | Call |
|---|---|
| `delegation.focus` | `ui.tabs.focus(sessionID)` (falls back to navigation) |
| `delegation.steer` | `client.session.prompt({sessionID, text, delivery: "steer"})` |
| `delegation.interrupt` | `client.session.interrupt({sessionID})` |
| `delegation.history` | pick a collapsed (stale) row and `ui.tabs.focus` it — read-only |
| `delegation.panel` | `ui.panel.open("delegates")` |

Collapsed history is not a live target: steer/interrupt are disabled for stale
rows and the live picker excludes them. `delegation.history` is the explicit
path to inspect one (focus only).

Bindings in this 2.1.4 TUI: `alt+d` focus, `alt+s` steer, `alt+x` interrupt,
`alt+g` history, `alt+p` panel, `alt+h` health. Palette/slash entries are declared but this
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
- the live session status map (`session.list()`/`session.status()`) cannot be
  read — discovered delegates then have no liveness source and may be hidden
  as stale;
- running **child** sessions exist with no delegate association (the
  orchestrator/root is excluded; only an explicit `running`/`busy` counts);
- the server part reports synthetic-delivery or stream failure through the
  shared health record (`<location>/.scratch/delegation-observer/health.json`).

In every case the durable watchdog/observer — heartbeat, `watch_agent.py`,
`observe_completion.py` wake — remains authoritative. The plugin never claims
live visibility it does not have.

## Structure

`model.ts` owns every read, timer, command, decision **and** the plugin/slot
registration (`createDefinition(Plugin, views)`), and is exercised by
`model.test.ts` against a mock host — including the plugin record (active /
failed / missing / unreachable), the shared health record with its 1 s throttle,
one fake-timer interval tick, the status command's healthy and degraded
answers, and the registered slot disposers.

**Documented boundary:** `tui.tsx` cannot be imported by `node --test` (it is
JSX), so it is **live-drill-only**. It supplies three render callbacks
(`strip`, `footer`, `panel`) to `createDefinition`; the registration, the slot
names/order, the render invocation and the disposer chain are all asserted in
`model.test.ts` with stub views, and the callback bodies are exercised by the
documented live drill. No model or liveness behavior lives in `tui.tsx`; it
only decides presentation (heading, stale-collapse line, footer banner text,
threshold display).

The projections in `model.ts` are built by `projection(version, compute)`:
a plain `version()` read (not `createMemo`), because solid's server build —
what `node --test` imports — freezes a memo at construction and would hide
every post-construction update. The read is what makes the client re-render,
and `model.test.ts` asserts it directly (a reactive effect cannot run under the
server build).

## Tests

```
node --test state.test.ts tui.test.ts server.test.ts model.test.ts   # 127 tests
node ../delegation-sentinel/sentinel.test.ts           # 5 tests
tsc -p . --noEmit
node mutation-check.mjs                                # 43 break/restore proofs
```

`mutation-check.mjs` is the checked-in evidence behind every liveness guard:
it removes one guard at a time, requires the named test to fail, restores that
file byte-for-byte (and byte-compares the restore), and fails if a mutation
survives, fails for the wrong test, or a restored file differs from its
original. It runs in CI with the offline suites.

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
  `session.tool.called/success/failed`, `session.tool.input.started/ended`,
  `session.message.content.updated`, `session.usage.updated`,
  `permission.asked/replied`, `form.created/replied/cancelled`,
  `session.execution.succeeded/failed/interrupted`.

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
