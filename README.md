# ai-framework

A portable, versioned library of agent skills for engineering work,
following the [Agent Skills](https://opencode.ai/docs/skills/) specification
and [Anthropic's authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

Two feedback loops anchor the library:

1. **Core engineering loop** — feature work verified by tests
   (unit, integration, e2e).
2. **UI iteration loop** — visual refinement verified by Playwright
   screenshots and computed CSS.

See [PLAN.md](PLAN.md) for the full design, research foundation, and build
phases.

## Install

Symlinks every skill into `~/.config/opencode/skills/` so all projects
discover them globally:

```bash
./install.sh
```

Re-run after adding new skills. `git pull` alone updates the content of
already-linked skills. Remove links with:

```bash
./install.sh --uninstall
```

Per-project overrides: a skill of the same name in a project's
`.opencode/skills/` takes precedence there. Gate experimental skills with
[skill permissions](https://opencode.ai/docs/skills/#configure-permissions)
in `opencode.json`.

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
