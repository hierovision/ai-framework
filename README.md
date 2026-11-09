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

Requires **OpenCode V2 `2.2.6`** (package `@opencode/cli@2.2.6`; exact pin,
no `latest`, no caret range). `opencode --version` prints `opencode v2.2.6`.
Install/upgrade with the supported command (`opencode upgrade <target> --method
yarn` for a new version; `yarn global add @opencode/cli@2.2.6` for the
same-version migration, because `opencode upgrade` skips an already-installed
version); the config root is `~/.config/opencode`. The reviewed config is
staged with `python3 scripts/stage_opencode_config.py --backup`. The canary
and pin check are the pre-merge gates; see ADR-0017. Never hand-edit a pin
seam.

The yarn-global install retains the V1 `opencode-ai` package, so **both
packages publish an `opencode` bin**: Yarn links the V2 binary as `opencode2`
and may leave the default `opencode` pointing at V1. Run
`python3 scripts/opencode_upgrade.py upgrade --to <pin> --apply
--drain-acknowledged` (with the pinned version) from a normal terminal with all
sessions closed; it reuses the installed V2 package (no Yarn reinstall),
atomically repairs the default `opencode` shadow to that package binary, and
verifies `opencode --version` + `opencode debug paths config` before the smoke.
A predecessor `upgrade-<pin>-verify.json` is preserved before new evidence is
written: an unverified one as
`upgrade-<pin>-verify.json.failed-<UTC stamp>`, a verified one as
`upgrade-<pin>-verify.json.previous-<UTC stamp>`. A failed verification records
`verified: false` with the exact manual rollback guidance — never an automatic
rollback (ADR-0017).
For a V1 previous default, rollback uses the actual
`~/.config/opencode.v1-backup-*` tree, not the V2-era pre-apply snapshot.
SQLite backups are written mode 0600. Existing backups created before this fix
may still be group/world-readable; the owner runs once from the repo root after
merge:
`chmod 600 ~/.config/opencode.v1-backup-*/opencode.db
"$PWD"/.scratch/opencode-v2/pre-upgrade-*/opencode.db 2>/dev/null`.

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
