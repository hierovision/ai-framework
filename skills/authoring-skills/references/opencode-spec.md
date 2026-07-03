# opencode Agent Skills Spec (working notes)

Source: https://opencode.ai/docs/skills/ — retrieved 2026-07-03.
Cross-compatible with the Agent Skills spec
(https://anthropics-skills.mintlify.app/spec/overview).

## Contents

- File placement and discovery
- Frontmatter fields
- Name validation
- Description constraints
- How skills surface to agents
- Permissions
- Troubleshooting

## File placement and discovery

One folder per skill, containing `SKILL.md` (exact case). opencode searches:

| Location | Scope |
|---|---|
| `.opencode/skills/<name>/SKILL.md` | project |
| `~/.config/opencode/skills/<name>/SKILL.md` | global (this library's install target) |
| `.claude/skills/<name>/SKILL.md` | project, Claude-compatible |
| `~/.claude/skills/<name>/SKILL.md` | global, Claude-compatible |
| `.agents/skills/<name>/SKILL.md` | project, agent-compatible |
| `~/.agents/skills/<name>/SKILL.md` | global, agent-compatible |

Project-local discovery walks up from the working directory to the git
worktree root. Skill names must be unique across all locations; a
project-local skill of the same name shadows the global one — this is the
library's supported override mechanism.

## Frontmatter fields

Only these are recognized (unknown fields are ignored):

| Field | Required | Notes |
|---|---|---|
| `name` | yes | see validation below |
| `description` | yes | 1–1024 chars |
| `license` | no | |
| `compatibility` | no | |
| `metadata` | no | string-to-string map |

## Name validation

- 1–64 chars, regex `^[a-z0-9]+(-[a-z0-9]+)*$`
- No leading/trailing hyphen, no `--`
- **Must match the containing directory name**
- Claude-side additional rules: no XML tags; avoid reserved words
  ("anthropic", "claude") for cross-platform portability

## Description constraints

- 1–1024 characters, non-empty, no XML tags
- Specific enough for the agent to choose correctly among all installed
  skills (see anthropic-best-practices.md → "Writing the description")

## How skills surface to agents

Skill name + description are listed in the native `skill` tool's
description under `<available_skills>`. The agent loads the body on demand
via `skill({ name: "..." })`. Relative paths inside a skill (references/,
scripts/) resolve against the skill's own directory.

## Permissions

Pattern-based gating in `opencode.json`:

```json
{
  "permission": {
    "skill": {
      "*": "allow",
      "experimental-*": "ask",
      "internal-*": "deny"
    }
  }
}
```

`allow` loads immediately; `ask` prompts the user; `deny` hides the skill
entirely. Per-agent overrides go in agent frontmatter (`permission.skill`)
or under `agent.<name>.permission.skill` in `opencode.json`. Disable the
skill tool for an agent with `tools: { skill: false }`.

## Troubleshooting

Skill not appearing:

1. `SKILL.md` spelled in all caps?
2. Frontmatter has both `name` and `description`?
3. `name` matches directory and passes the regex?
4. Name unique across all discovery locations?
5. Not hidden by a `deny` permission?
6. For this library: symlink present in `~/.config/opencode/skills/`
   (re-run `./install.sh`)?
