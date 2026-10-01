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
