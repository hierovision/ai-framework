# OpenCode integration facts (V2, dated, volatile)

Single home for the OpenCode V2 facts this library relies on. The vendor API
changes; re-verify against the linked docs before relying on any line.
**Validated 2026-10-26/27 against opencode `2.1.4`**; the canary evidence is
under `.scratch/v2-canary/`.

The migration cutover is atomic: there is no V1/V2 dual-run layer. The
previous release tag is the code rollback; the C5 backup is the data rollback.

## Binary, package, version

- Package: `@opencode/cli@2.1.4` (never the legacy V1 package, never `latest`).
- `opencode --version` prints `opencode v2.1.4` (the exact string is
  `opencode v2.1.4`).
- `opencode run` flags: `--agent`, `--model/-m` (`provider/model#variant`),
  `--session/-s`, `--continue/-c`, `--fork`, `--format <default|json>`,
  `--file/-f`, `--title`, `--thinking`, `--auto`, `--standalone`,
  `--server URL`.
- There is **no `--dir`**; the working directory is the child process `cwd`
  (and `PWD`). There is **no `--skill`** flag — resolve the skill from the
  installed layout and run from its directory.
- Log level is `OPENCODE_LOG_LEVEL=ERROR` in the environment. The eval lanes
  do not pass CLI log switches; post-smoke's loader probe is the one exception
  (global `--log-level info --print-logs` to capture the plugin startup line).
- Root `-m` / `--agent` were removed; emit only `run --agent` / `run --model`.

## Service and typed API

- `opencode service status` prints the service URL (JSON when running,
  `stopped` when not); `opencode service start|stop|restart` manage it.
- The service requires the `service.json` password; **use `opencode api`**
  (it authenticates) rather than raw HTTP unless a caller supplies an
  authenticated URL.
- Typed endpoints (validated 2026-10-27):
  - `GET /api/session/active` → `{"data": {<sid>: {"type": "busy"|"retry"}}}`
  - `GET /api/session/{id}` → `{"data": {id, model, cost, tokens, outcome,
    time{created,updated,idle}, title, location{directory}}}`
  - `POST /api/session/{id}/agent` body `{"agent": "<name>"}`
  - `POST /api/session/{id}/prompt` body `{"text": "<text>"}`
  - `POST /api/session/{id}/interrupt` → `{"interrupted": bool}`
  - `GET /api/session/{id}/log`
  - `GET /api/agent?directory=<dir>` → `{"data": [agent…]}`
  - `GET /api/info` → `{version, pid, urls, paths, capabilities}`
- The V1 status endpoint and the V1 client attach wake vehicle are gone. Wake uses
  the typed calls above; a 404 preflight defers with `unknown-session` instead
  of creating a ghost session.

## Session store (read-only)

- Path resolution: `OPENCODE_DB_PATH` (test override) > `OPENCODE_DB` >
  `opencode debug paths db` / the vendor location
  (`~/.local/share/opencode/opencode.db`).
- V2 reads/writes `session_v2`, `session_message`, `session_inbox`, `event`;
  V1 `session`/`message`/`part` are migration sources only.
- `session_v2` columns used here: `id`, `project_id`, `parent_id`, `title`,
  `directory`, `agent`, `model` (JSON `{providerID,id,variant}`), `cost`,
  `tokens_input`, `tokens_output`, `time_created`, `time_updated`,
  `time_idle`, `idle_outcome`.
- `session_message` columns: `id`, `session_id`, `type`
  (`user|assistant|system|synthetic|idle|compaction`), `seq`, `time_created`,
  `time_updated`, `data` (assistant content blocks: `reasoning`, `text`,
  `tool` with `name`/`state`; message-level `finish`).
- Completion/idleness: `session_v2.time_idle` + `idle_outcome` when present
  (migrated rows may carry NULL — degrade to the assistant-message terminal
  marker). `time_idle` is the idle clock, not a per-token clock.
- First V2 boot auto-migrates V1 sessions **one-way**. Migration is batched
  and resumable (`kv.migration.v1-v2` cursor); a truncated run leaves a
  lower-id tail unmigrated, which a later boot resumes. Never claim lossless
  migration without checking source-ID membership.
- DB access is read-only (`file:…?mode=ro`). The only mutating API calls are
  `session.interrupt`, `session.agent`, and `session.prompt`.

## JSON event stream

`opencode run --format json` emits newline-delimited JSON with top-level
`type` in `step_start`, `text`, `tool_use`, `step_finish`, `error`, and
`sessionID`; the `part` carries:

| part.type | fields |
|---|---|
| `step-start` | `snapshot` |
| `text` | `text`, `time{start,end}` |
| `tool` | `tool`, `id`, `state{status,input,output,error,metadata,time}` |
| `step-finish` | `reason`, `cost`, `tokens{input,output,reasoning,cache{read,write}}` |
| `reasoning` | `text` |

Tool vocabulary: `shell`, `read`, `edit`, `glob`, `grep`, `subagent`, `skill`.
V1 names (`bash`, `write`, `patch`, `task`) are aliases the eval harness
accepts for consumer manifests and logs. `filePath` is now `path`; the
`subagent` tool carries `agent` and `sessionID`.

## Permissions

- Config uses ordered `permissions` arrays of
  `{action, resource, effect}` (`effect` = `allow|deny|ask`). The **last
  matching rule wins** (proved live 2026-10-27: deny `*` then allow
  `<abs>/**` permits the read).
- Actions: `shell`, `edit`, `subagent`, `external_directory`, `skill`,
  `execute`, `read`, `question`.
- `external_directory` defaults to **allow**; the dispatcher emits a
  catch-all `deny` first and explicit `<abs-path>/**` `allow` rules after it.
  Per-agent `external_directory` is forbidden (the dispatcher owns grants).
- Non-interactive runs auto-reject an `ask`: the tool part is
  `state.status=error` with `state.error` containing "cannot ask the user for
  permission", and stderr carries
  `permission requested: <action> (<target>); auto-rejecting`. Classify it as
  `permission denied: <tool> <target>`, never `empty result`.
- Migration residual: cutover preflight fails closed unless the canary report
  shows zero missing sessions or a machine-readable classification
  (`docs/opencode-v2-migration-classification.json`) / dated owner acceptance
  matches the reported count.
- There is no `OPENCODE_PERMISSION` env var. `OPENCODE_CONFIG_CONTENT` /
  `OPENCODE_CONFIG` are recorded as config sources but do **not** activate an
  injected agent/grant under V2 2.1.4; the dispatcher writes a generated
  `opencode.jsonc` under a temporary `XDG_CONFIG_HOME` and links the agent
  corpus. Stop a stale service before changing the config root.
- `execute: deny` on every persona (Code Mode is not needed; it closes the
  policy-bypass class). Re-open only with a named task and a dated record.

## Agents

- Agent definitions live as markdown in the agent directory (`agents/*.md` in
  the repo/global layout, `.opencode/agents/*.md` for a project). The agent
  **ID is path-derived**; `name:` is ignored and must be absent.
- Frontmatter: `description`, `model`, `mode`, `hidden`, ordered
  `permissions`; `temperature` is tolerated by 2.1.4 (probe 2026-10-27) and is
  retained for the council lenses.
- Config-level agents use the top-level `agents` object; the title model is
  `agents.title.model = {providerID, model}`. `small_model` is a deprecated
  compatibility input that normalizes to it.
- `mode`: `primary` / `subagent` / `all` (default `all`). Nested subagents
  (the free tier is environment-dependent) use this `subagent` mode and the
  `subagent` tool.
- `opencode debug agents` returns an empty list in 2.1.4 for config-defined
  agents; the equivalent listing is `opencode api GET /api/agent` (service
  mode), and a live `run --agent <id>` is the existence proof.

## Plugins

- `@opencode/plugin@2.1.4` is the matching runtime package (the legacy V1
  plugin package is not a V2 contract).
- Shape: `Plugin.define({ id, async setup(ctx) { … return cleanup } })`;
  domain methods (`ctx.model.list()`, `ctx.session.compact({sessionID})`);
  an aborted `ctx.event.subscribe()` loop; cleanup returned from `setup`.
- A V1 default-function export is rejected ("must export a default definition
  with an id and an effect or setup function"); a
  `{id, setup: v1Function}` wrapper loads but is **not** functional (the V1
  event-hook return contract is not executed).
- `plugins/auto-compact-at-threshold/` is the canonical port: startup marker,
  threshold re-arm, compaction call, abort cleanup. The versioned config wires
  it as a **relative local path**: `plugins: ["./plugins/auto-compact-at-threshold"]`.
  A bare `"plugins/auto-compact-at-threshold"` is parsed as an npm package
  spec and fails with `NpmInstallFailedError`; a file path is rejected with
  "configured plugin path must be a directory" (measured 2026-10-29).
- **Options shape (probed 2026-10-29):** a string entry carries no options; an
  object entry `{ "package": "./plugins/<dir>", "options": { … } }` is
  accepted, and the loader forwards `options` to `setup(ctx)` as
  `ctx.options` **for the server part only** — the TUI part receives `{}` on
  2.1.4. A TUI value that must match the server needs an env/file source.
- **Plugin discovery (probed 2026-10-29):** the loader also scans the config
  root's `plugins/*` directories and loads a directory even when it is not
  listed in the `plugins` array. To make a plugin genuinely absent, remove its
  directory. A directory needs a resolvable `server` entrypoint even for a
  TUI-only companion (`{server: undefined}` is skipped); `tui` alone is not a
  loadable plugin. `features.tui` is set from the `<dir>/tui` entrypoint.
- 2.1.4's plugin context has **no log domain** (`ctx` carries
  `app/location/options/agent/.../session/shell`, no `log`/`logger`). The
  plugin writes its structured startup marker to `process.stderr`; run
  `opencode run --standalone --print-logs --log-level info` to capture the
  loader and marker on stderr. (`--print-logs`/`--log-level` exist as global
  flags; evals still use `OPENCODE_LOG_LEVEL=ERROR` and do not emit them.)
- **Plugin entrypoints (probed 2026-10-29, binary `Zg`).** A plugin directory
  resolves its parts as `<dir>/server` and `<dir>/tui` (and `<dir>/rpc`) via
  module resolution — no package `exports` map is consulted. A `tui` entry
  sets `features.tui: true` on the plugin record; the TUI host imports it.
  `GET /api/plugin` (`opencode api GET /api/plugin`) returns
  `{id, source, features, state}` with `state.status` `active` or `failed`
  (with `error`) — the honest source for a degradation banner.
- **TUI plugin context (same probe).** `@opencode/plugin@2.1.4`'s `./tui`
  export defines `Plugin.define({id, setup})` with `ctx.data.listen/on`,
  `ctx.data.session.{list,status,permission,form}`, `ctx.ui.slot`
  (`sidebar.content`, `home.footer.status`, `session.panel`, …),
  `ctx.ui.toast/attention/keymap/dialog/tabs/panel/router`,
  `ctx.client` (typed `session.prompt/interrupt`, `plugin.list`) and
  `ctx.storage`. JSX intrinsics are `box`/`text`/`span`/… from
  `@opentui/solid` (peer; `jsxImportSource` in the plugin `tsconfig.json`).
- **Server event stream + synthetic messages.** `ctx.event.subscribe()`
  yields `OpenCodeEvent` (`{id, created, type, data}`); the vocabulary used by
  the delegation observer is `session.created/renamed/status/step.*/tool.*/
  message.content.updated/usage.updated/execution.*`, `permission.asked/
  replied`, `form.created/replied/cancelled`. `ctx.session.synthetic({sessionID,
  text, description, metadata})` appends a synthetic message **without a model
  turn** (client counterpart: `POST /api/session/{id}/synthetic`).
- `runtime-probe.mjs` proves the module's `setup`/cleanup behavior, but it is
  not loader proof. `plugin list` does not enumerate local directories, so
  post-smoke also runs the real CLI with the versioned config and requires
  both the loader's `loading plugin` line for this directory and the
  `auto-compact-at-threshold initialized` marker. The marker must also carry
  the per-run token the probe passes as `OPENCODE_LOADER_PROBE_TOKEN` (the
  plugin echoes it as `extra.probe`), so a different plugin copy emitting the
  same static text cannot satisfy the check. Three pieces of evidence are
  required: config wiring, runtime probe, and loader log.
- **TUI context correction (probed 2026-10-29, live TUI).** The keymap is
  `ctx.keymap`, not `ctx.ui.keymap` (the latter is undefined and fails the TUI
  part at setup). A plugin command registered with `palette: true` / `slash`
  still does **not** appear in this build's ctrl+p palette or slash completion
  (both returned "No matching commands"), while `keymap.shortcuts(id)` resolves
  a declared `bind` — so bindings are the working control surface in 2.1.4.
  There is **no `--port` flag** on the TUI (`Unrecognized flag: --port`), so a
  standalone TUI exposes no server URL.
- **Event shapes that matter (generated 2.1.4 types).**
  `form.created.data = {form: FormInfo1}` (session id nested at
  `data.form.sessionID`); `permission.replied.data.reply` is
  `once|always|reject` (a rejection is a denial, not a resume);
  `session.step.ended.data` carries `finish`, `cost`, `tokens`;
  `session.tool.called.data` has **no tool name** (name/target come from
  `session.message.content.updated`).
- **Headless tool events (probed 2026-10-31, RM-070 drill).** On a raw
  `opencode serve` with no TUI attached, the server emitted
  `session.tool.input.started` (`{sessionID, assistantMessageID, id, name}`),
  `session.tool.input.ended` (`{..., text: "<input JSON>"}`), then
  `session.tool.called` (`{input}` with no `name`) and `session.tool.success`;
  it did **not** emit `session.message.content.updated`. The observer consumes
  the input pair, so tool labelling and thrash detection do not depend on a
  TUI client. This is the host path the live drill exercised.
- **Managed service probe (2026-10-29, extended).** `opencode service set port
  <n>` + `service start` works under an isolated `XDG_CONFIG_HOME` (writes
  `service.json` there; `OPENCODE_PASSWORD` is required by clients). A plugin
  wired in that config root loads in the service: `GET /api/plugin?directory=
  <work>` returns it with `features: {server: true, tui: true}` and
  `state: active`. The list is **location-scoped**: without the directory the
  same call returns `{"data": []}` for the service's own location, so a TUI
  must pass its location (`client.plugin.list({location:{directory}})`) or it
  falsely reads "not loaded". The service also activates a plugin **once per
  location** (work, home, repo), so a per-location side effect (a synthetic
  milestone) must be guarded by the instance's own location.
- **Synthetic messages (2026-10-29).** `session.synthetic` accepts
  `delivery: "steer"|"queue"` and `resume?: boolean`. With default
  `resume` a synthetic started a model turn; `{delivery:"steer",
  resume:false}` queues it for the next turn without generating. TUI plugin
  `options` are not forwarded to the TUI part by the 2.1.4 host (the server
  part receives them); use an explicit env seam if both parts need a value.
- **Delegation association marker (RM-069, 2026-10-29).** A run-vehicle child
  is identified by its session **title**
  `[delegate:<orchestrator-session-id>] <agent>: <task>`, set with `run
  --title` and read from `session.created.title` / `session.renamed.title` /
  `SessionInfo.title`. In-session Task children need no marker (`parentID`).
  This avoids a second registry and any write to the session store.

## Model reasoning control (Go)

- `reasoning_effort` is an OpenAI-style parameter; Z.AI accepts `low`/`high`/
  `max` with thinking enabled. opencode sets it per model
  (`provider.opencode-go.models.<id>.options.reasoningEffort`) or via a
  variant (`--model provider/model#variant`).
- The Go gateway has rejected/mangled it for some IDs (upstream #49551,
  #50818, dated 2026-10-01). Bind an allowed effort or run as-is; re-verify on
  touch.

## Pointers

- `scripts/opencode_v2.py` — the shared adapter (all facts above live there).
- `scripts/opencode_v2_canary.py` / `_consumer.py` / `_cutover.py` /
  `_post_smoke.py` — the operational gates.
- `skills/observing-runs/SKILL.md`, `references/schema.md` — run logging.
- `skills/implementing-features/references/stacks/skills-library.md` — the
  implementation-time rule (never invent a flag/key; cite this file).
- `skills/authoring-skills/scripts/run_behavioral_eval.py` — consumes `cwd`/
  `PWD`, `--standalone`, and per-run `OPENCODE_DB`/XDG isolation.

## Eval startup latency (2026-10-28, extended 2026-10-29)

CI run 40709127604's `validating-ui#1` job killed three attempts at 240 s with
zero JSON events and empty stderr. The same model/auth/runner produced the full
stream for `designing-architecture#1` (206 s) in the same run. A bounded
600 s isolated probe of `validating-ui#1` emitted a complete event stream and
passed in 53–406 s across two isolated probes (406 s inside the 240–600 s band); 60 s-bounded repetitions stalled, so the tail is startup/
provider latency, not an assertion or config defect. The eval now carries
`timeout: 600` (the existing per-eval manifest policy); assertions are
unchanged. `BEVAL_STARTUP_LOG=1` records the spawn command, per-run DB, log
level, and timeout in the CI job log for the next zero-event occurrence.

**2026-10-29 — measured residual, no timeout change.** The isolated
`ci-132` evidence (`.scratch/ci-132/*/run-2026-10-28.jsonl`) records the
same spread: `validating-ui#1` completed in 23.5 s and 57.9 s (assertion
misses), 53.2 s (pass), and 406.7 s (pass); `designing-architecture#1`
passed in 166.3 s; three 60 s-bounded repetitions recorded zero events
(`stability-1/2/3`). The per-change job ceiling is **20 minutes
(1200 s)** and the per-eval stall ceiling is 600 s; the 406.7 s tail sits
inside both. The variability is startup/provider-side (zero-event stalls
versus the same model/auth streaming normally), not an assertion or config
defect. No timeout was raised and no retry-until-green was added.

The runner now measures spawn → first non-empty stdout line
(`first_event=Nms`) in the `BEVAL_STARTUP_LOG=1` line and in a stall's
detail (`first stdout line: none` for a true zero-event stall). The
timeout path still kills the process group at the configured ceiling; the
instrumentation only records when the first stdout line arrived.
