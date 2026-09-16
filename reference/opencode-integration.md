# OpenCode integration facts (dated, volatile)

Single home for the opencode CLI/plugin facts the library relies on. The
vendor API changes; re-verify against the linked docs before relying on any
line. Everything below was validated **2026-09-06**.

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

## Pointers

- `skills/observing-runs/SKILL.md`, `references/schema.md` — run logging.
- `skills/implementing-features/references/stacks/skills-library.md` — the
  implementation-time rule (never invent a flag/key; cite this file).
- `skills/authoring-skills/scripts/run_behavioral_eval.py` — consumes `--dir`.
