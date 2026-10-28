# ai-framework

A portable, versioned library of agent skills for engineering work,
following the [Agent Skills](https://opencode.ai/docs/skills/) specification
and [Anthropic's authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

Two feedback loops anchor the library:

1. **Core engineering loop** — feature work verified by tests
   (unit, integration, e2e).
2. **UI iteration loop** — visual refinement verified by Playwright
   screenshots and computed CSS.

## Install

Symlinks every skill into `~/.config/opencode/skills/` and every agent
into `~/.config/opencode/agents/` so all projects discover them globally:

```bash
./install.sh
```

Requires **OpenCode V2 `2.1.4`** (package `@opencode/cli@2.1.4`; exact pin,
no `latest`, no caret range). `opencode --version` prints `opencode v2.1.4`.

Re-run after adding new skills or agents. `git pull` alone updates the
content of already-linked skills/agents. Agent files are validated on
install: the ID is **path-derived**, so a legacy `name:` frontmatter key is
rejected, and `description` + `model` are required. Permissions use the V2
ordered `permissions` array (`shell`, `subagent`, `edit`, `execute`), never
the V1 `permission` map. Remove links with:

```bash
./install.sh --uninstall
```

Per-project overrides: a skill of the same name in a project's
`.opencode/skills/` takes precedence there. Gate experimental skills with
[skill permissions](https://opencode.ai/docs/skills/#configure-permissions)
in `opencode.json`.

Install the library as a set: some skills reference sibling skills'
contract files (e.g. `implementing-features` consumes
`designing-architecture`'s plan format via a relative sibling path).
`install.sh` links everything, so this is only a concern if you cherry-pick.

## Layout

```
skills/       One directory per skill (SKILL.md + references/ + scripts/ + evals/)
agents/       Thin agent templates — copy into a project's .opencode/agents/
              and bind to current model IDs
reference/    Volatile, dated facts: model routing, loop diagrams
docs/         Maintainer guides (adding a stack, authoring workflow)
```

## Principles

- Skills carry the knowledge; agents are thin, per-project model bindings.
- Loops close on objective signals (test exit codes, screenshots, computed
  CSS) — never on "looks done."
- Generic workflows + pluggable stack references.
- Volatile facts (model IDs, pricing) are quarantined in `reference/` with
  retrieved-on dates.
- Every skill ships with evals.
