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
- Log level is `OPENCODE_LOG_LEVEL=ERROR` in the environment. The V1-era CLI
  log switches are not used by this repo.
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
  threshold re-arm, compaction call, abort cleanup.

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
