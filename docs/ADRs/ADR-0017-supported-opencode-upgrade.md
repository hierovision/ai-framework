# ADR-0017: Supported OpenCode install/upgrade path

## Status

accepted 2026-11-02

## Context

ADR-0014 introduced a versioned V2 install behind a wrapper to keep the
one-time V1→V2 cutover atomic: `~/.yarn/bin/opencode` → a versioned wrapper
that selected a versioned binary and `XDG_CONFIG_HOME`. ADR-0016 then built a
standardized upgrade pipeline on that layout. The 2026-11-02 2.2.5 upgrade
showed the cost: the layout is not one of OpenCode's supported install
methods, so `opencode upgrade` cannot see or update it; the orchestrator,
canary invocation, cutover, link switch, and custom DB rollback existed partly
to compensate for the custom installer. The owner directed the correction:
follow the supported path and keep only the safety net that catches real
regressions.

OpenCode's supported upgrade command is `opencode upgrade [target] --method
<curl|npm|pnpm|bun|yarn|vp|brew|winget>`; the supported config root is the
ambient `~/.config/opencode` (or `XDG_CONFIG_HOME`). The user selected the
**yarn global** method and to keep the V1 package shadowed for the retention
window.

## Decision

1. **Supported binary and config.** Live install is yarn-global
   `@opencode/cli`; `opencode upgrade <target> --method yarn` is the live
   upgrade for a new version. The **same-version** migration uses the
   official `yarn global add @opencode/cli@<pin>` because `opencode upgrade`
   skips an already-installed version. The config root is
   `~/.config/opencode`. The custom versioned wrapper/binary dirs are
   retired.
2. **One-time config migration.** `scripts/stage_opencode_config.py` moves the
   reviewed V2 config (agents, plugins, `opencode.jsonc`, `cli.json`,
   `service.json`) to `~/.config/opencode`, backs up the V1 tree as
   `opencode.v1-backup-<timestamp>`, and re-links skills/agents/reference via
   `install.sh`. It refuses while OpenCode/supervision processes are live.
3. **V1 retention.** `opencode-ai@1.19.4` stays installed in the yarn global
   but shadowed by the V2 bin. The V1 config backup plus a pre-migration DB
   backup are the full restore. V1 removal is deferred until the retention
   window ends.
4. **Thin safety net.** The canary remains a **pre-merge** gate: C1–C8 +
   migration, plugin typechecks/tests, and a short debug-TUI setup smoke.
   `VERSION_PIN` remains the single version source; `check --pins-only`
   verifies the docs/CI/plugin seams; `prepare` updates them. The live
   `scripts/opencode_upgrade.py upgrade --apply` backs up the DB/config, runs
   the official command, repairs the default package-bin shadow, and
   post-smokes (`--version`, config root, `/api/info`, agents, plugin loader,
   observer API). It does not manage a custom DB rollback.
5. **Rollback.** V2→V2: `opencode upgrade <previous> --method yarn` plus the
   pre-upgrade DB/config backup. V1: reinstall the shadowed V1 bin and restore
   the V1 config/DB backups. Both are documented and drilled; there is no
   automatic link/DB rollback. The only automatic filesystem action is the
   package-bin shadow repair described in the 2026-11-09 amendment.
6. **Retirements.** `opencode_v2_cutover.py` and its test are retired; the
   versioned wrapper/directory layout is retired; ADR-0016's custom
   install/apply standard is superseded by this ADR. ADR-0014 remains the
   historical one-time cutover record.
7. **Drift detection.** The weekly issue-first workflow stays; its issue text
   points at `opencode upgrade <target> --method yarn`.

## Consequences

- A routine upgrade is one supported command, with a pre-merge canary and a
  post-upgrade smoke — not a custom installer pipeline.
- The TUI/plugin compatibility gate still catches the class of break that
  `opencode upgrade` cannot: the 2.2.x OpenTUI change and the 2.2.5
  TUI-context location difference.
- The V1 rollback is a manual full restore during the retention window, not a
  one-link switch.
- The repo no longer owns a binary installation format; it owns only the
  config corpus, the pin checks, and the canary.

## 2026-11-09 amendment — package-bin shadow and truthful failure

The 2.2.6 install exposed the yarn-global dual-bin collision: the retained V1
`opencode-ai` package and the V2 `@opencode/cli` package both publish an
`opencode` bin. Yarn linked the V2 package as `opencode2` but left the default
`opencode` on V1, so the orchestrator's post-install smoke measured the stale
V1 shim.

Repairing the default link to the installed V2 package is an **explicit
supported action**. `scripts/opencode_upgrade.py upgrade --to <pin> --apply
--drain-acknowledged` resolves the installed target (`opencode2` first, then
the package `bin/opencode.exe`), atomically replaces `~/.yarn/bin/opencode`
with that package binary (preferring a relative `opencode2` target), and
verifies `opencode --version` and `opencode debug paths config` against
`~/.config/opencode` before the smoke. When the target package is already
installed, the apply skips the official install and only repairs and verifies.

Failed verification is **not an automatic rollback**. The target package and
the repaired default stay in place; the artifact records `verified: false`,
`rolled_back: false`, the failing stage, the target package version/path,
default-link evidence, and the exact manual rollback command, while upgrade
state stays `prepared`. The pre-upgrade package/config/DB backup plus that
manual command remain the rollback.

## Sources

- Owner directive 2026-11-02 (supported path; yarn global; V1 shadowed; thin
  pipeline).
- `.opencode/plans/supported-opencode-upgrade.md` (approved plan; retired at
  merge).
- `opencode upgrade --help` (2.2.5) and the V2 CLI docs install/upgrade
  methods.
- ADR-0014 (one-time cutover, historical); ADR-0016 (superseded).
- `docs/roadmap-detail/RM-071.md` (correction amendment).
