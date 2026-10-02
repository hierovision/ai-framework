# OpenCode integration facts (dated, volatile)

Single home for the opencode CLI/plugin facts the library relies on. The
vendor API changes; re-verify against the linked docs before relying on any
line. Validated **2026-09-06**, except where a section carries its own date.

## Plugins / hooks

- opencode has **no `hooks` JSON key** in config
  (<https://opencode.ai/docs/config/>). Hooks are **TypeScript plugins**
  (<https://opencode.ai/docs/plugins/>).
- Plugin events include `session.created`, `session.deleted`, `session.idle`,
  `tool.execute.before`, `tool.execute.after`. There is **no**
  `SkillInvocationEnd` or `AgentSessionEnd` event, and no
  `${skill_name}`/`${tokens_in}` template variables.
- `session.idle` fires per session, not per skill, so it cannot attribute
  tokens, duration, or an outcome to a specific skill. Hook-based run logging
  is therefore aspirational until per-skill token attribution exists.

## `opencode run`

- `opencode run [message..]` accepts `--dir`, `--agent`, `--model/-m`,
  `--file/-f`, `--format` (<https://opencode.ai/docs/cli/#run-1>).
- There is **no `--skill` flag**. Resolve the skill from the installed layout
  and run from its directory: `opencode run --dir <dir> <prompt>`.

## Session store (read-only)

- `~/.local/share/opencode/opencode.db` is a SQLite DB with `session` and
  `part` tables. Open it read-only (`file:…?mode=ro`). `part.data` is JSON
  (`type`, `tool`, `state.input`/`state.status`); `session` carries `title`,
  `agent`, `cost`, `tokens_input`/`tokens_output`, `time_updated`, `parent_id`,
  `directory`. Dated 2026-10-01 — volatile, re-verify on touch;
  `scripts/watch_agent.py` degrades to heartbeat-only when the DB is absent or
  the schema changes.
- `session.model` is a **JSON blob** —
  `{"id":"nemotron-3-ultra-free","providerID":"opencode","variant":"default"}`
  on a probed `architect` run-vehicle session (2026-10-02). Resolve it to a
  display model as `<providerID>/<id>`; parse defensively (missing/odd blob →
  unknown, never a crash). `watch_agent.py` exposes it in `--json`.

## Agent dispatch (dated 2026-10-02)

- **`mode` semantics** (<https://opencode.ai/docs/agents/>, fetched
  2026-10-02): `primary` = selectable as the session agent, not offered to the
  Task tool; `subagent` = Task-only; `all` = both. opencode's default when
  `mode` is unspecified is `all`. `opencode agent list` annotates each entry
  `(primary)` / `(subagent)` / `(all)`; on 1.18.18 the five core personas were
  `(primary)` before the 2026-10-02 dispatch flip.
- **`permission.task`** (<https://opencode.ai/docs/permissions/>, fetched
  2026-10-02): matches the subagent type; object form with glob patterns where
  the **last matching rule wins**, so a `"*": "deny"` catch-all first plus
  explicit `"allow"` entries is the allow-list pattern. `deny` also removes
  the subagent from the Task tool's description.
- **Named dispatch honors the target's frontmatter `model`** (upstream #35126,
  fixed 2026-07-09): the target's binding — and its permission wrapper — travel
  with the agent, so an orchestrator need not restate either.
- **Free-tier nested calls are environment-dependent**: CI rejects a nested
  subagent bound to a free model (`OpenCode's free tier can only be used from
  within OpenCode` — `scripts/ci-lane-overrides.py`), and a free council died
  nested locally on 2026-10-01 (RM-017); but a Go-bound parent dispatched the
  free-bound `architect` in-session cleanly on 2026-10-02 (child session row
  `model={"id":"nemotron-3-ultra-free","providerID":"opencode",...}`). Route
  free-bound targets through the top-level run-vehicle
  (`scripts/dispatch_agent.py`) when the orchestrator is free-bound or
  headless.

## Model reasoning control (Go)

- `reasoning_effort` is an OpenAI-style parameter. Z.AI's API accepts it only at
  `low` / `high` / `max` (default `max`), with `thinking` enabled
  (<https://docs.z.ai/api-reference/llm/chat-completion>, fetched 2026-10-01).
  opencode sets it per model:
  `provider.opencode-go.models.<id>.options.reasoningEffort` or a variant
  (<https://opencode.ai/docs/models/>).
- The **Go** gateway has rejected or mangled it for some IDs:
  `invalid_request_error: native reasoning control reasoning_effort is not
  allowed` on `glm-5.3-flash` (6× in the host log, 2026-09-28). Upstream:
  opencode #49551 (2026-09-17) — the openai-compatible path drops it for
  `glm-*` IDs; #50818 (2026-09-23) — Go returns 400 for `max`/`minimal` on
  `mimo-v2.6-flash` while low/medium/high succeed. Dated 2026-10-01 — re-verify
  on touch. A fresh `opencode run -m opencode-go/glm-5.3-flash` routes clean
  (probed 2026-10-01), so the rejection is session/agent-option dependent: bind
  the model and set an allowed effort, or evaluate it as-is.

## Pointers

- `skills/observing-runs/SKILL.md`, `references/schema.md` — run logging.
- `skills/implementing-features/references/stacks/skills-library.md` — the
  implementation-time rule (never invent a flag/key; cite this file).
- `skills/authoring-skills/scripts/run_behavioral_eval.py` — consumes `--dir`.
