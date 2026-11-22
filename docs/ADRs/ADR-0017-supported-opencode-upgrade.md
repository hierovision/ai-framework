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
default-link evidence, and the exact manual rollback guidance, while upgrade
state stays `prepared`. Every apply failure — including a command timeout or
spawn error — writes that named artifact. A predecessor artifact is archived
before overwrite (`.failed-<stamp>` unverified, `.previous-<stamp>` verified).
For a V1 previous default the rollback points at the actual
`~/.config/opencode.v1-backup-*` tree, not the V2-era pre-apply snapshot; SQLite
backups are written mode 0600. The pre-upgrade package/config/DB snapshot plus
that manual guidance remain the rollback.

## 2026-11-10 amendment — migration resume before smoke

A completed `kv.migration.v1-v2` row is not a permanent lossless claim. Vendor
behavior on 2.2.6: once the row is `{"phase":"completed"}`, a later service
start does not import V1 sessions created below that cursor. The live DB had
17 such subagent sessions (V1 `session` 2216, V2 `session_v2` 2251, cursor
completed), so the canary's previous single `run` rehearsal left them
unmigrated and misreported 52 pre-existing source `session_v2` rows as
target-only phantoms.

The canary migration gate and the explicit owner-run
`upgrade --to <pin> --apply --drain-acknowledged` now re-arm
`{"phase":"sessions"}` with no cursor on a scratch copy / the real DB
respectively, start an isolated V2 service (scratch) or the repaired default
service (apply), poll until `{"phase":"completed"}` with a bounded timeout,
and verify every source V1 ID plus the pre-existing V2 baseline. The canary
excludes source `session_v2` baseline rows from target-only accounting. A
timeout, missing source row, or missing baseline row is a truthful failure
(`verified: false`, named stage, counts in the artifact); there is no
residual/owner-acceptance path for these rows. Apply stops a service it
started on any failure, including a post-smoke failure or exception, and
leaves it running only when the post-smoke succeeds; the canary stops its
scratch service in a `finally`.

## 2026-11-20 amendment — verify-only recovery and external state

A failed post-smoke after a completed backup/install/migration previously cost
a full re-apply (the 2.8 GB backup plus the migration rehearsal) even when
only a smoke check was wrong. The 2.2.7 apply hit exactly that: `/api/agent`
can return its first response before a location finishes loading, so a
single-shot agent assertion failed a healthy install. `verify --to <pin>` is
the narrow recovery action:

- It runs the **full** post-smoke (binary, config root, API, agents, plugin
  loader, observer) against the explicit repaired default
  (`--default-bin`, `--link`, then `~/.yarn/bin/opencode`).
- It does **not** back up, install, or migrate, and it does not require
  `--drain-acknowledged`. It reads `service status` first: when stopped it
  starts the service, runs the smoke, and stops **only the service it
  started**; when already running it leaves it running. An unreadable status
  is a refusal, because verify never relies on the CLI's implicit service
  auto-start.
- It is eligible only when the artifact carries a completed smoke (non-empty
  `checks`) and the failed stage is one of `binary`, `config-root`, `api`,
  `agents`, `plugin`, `observer`. A shadow repair's `config-root` failure has
  empty `checks`, and `exception:smoke` is not a completed check, so both are
  refused.
- It archives the prior artifact under the existing
  `.failed-<stamp>` / `.previous-<stamp>` convention, writes `verified: true`,
  and advances state to `applied`.
- It refuses, naming the full
  `upgrade --to <pin> --apply --drain-acknowledged` command, for any other
  failure stage — install, shadow, and migration failures still need the full
  apply. Its already-verified fast path also refuses (rc 2) when the live
  default or shadow no longer matches the target.

Upgrade state and evidence now live under
`$XDG_STATE_HOME/opencode-upgrade` (default
`~/.local/state/opencode-upgrade`): `upgrade-state.json`,
`upgrade-<pin>-verify.json`, and `v2-canary-<pin>/`. The repo `.scratch`
state/canary/verify artifacts are read as a fallback and imported on the first
write, so `status`, `check --pr`, and `verify` survive `rm -rf .scratch` and
resolve identically from a fresh worktree. Pre-upgrade DB/config/package
snapshots stay under `.scratch/opencode-v2/pre-upgrade-*` and are cited by
absolute path in the artifact. `status` never reports `up to date` while the
pinned artifact is `verified: false` or state is `prepared`; `up to date`
requires the pinned artifact to be `verified: true` regardless of the state
file. A post-smoke failure names `verify --to <pin>`, any other failure names
the full apply command. `prune --keep N` also bounds the state-dir
`v2-canary-*` evidence (the current pin is always kept). The canary C7 and
post-smoke agent checks share one bounded `wait_for` helper that records
`polls` and timeout evidence. There is no automatic rollback and no
auto-apply change.

The `--channel patch`, `--auto`, `--auto-merge`, and detached-supervisor lanes
are **not** delivered by this amendment; they remain open plan items.

## 2026-11-20 amendment — patch channel and opt-in auto-merge

`upgrade --channel patch` resolves the newest `X.Y.Z` inside the pinned `X.Y`
and never a minor or major. An explicit `--to` wins; when no newer patch
exists the command exits 0 with an `already current` / `no newer patch`
message and does not run the plan or canary.

`upgrade --to <patch> --auto` composes the existing gates rather than
bypassing them: plan → canary → prepare (clean lockfiles, local four suites +
pins) → `check --pr` → PR. On a clean tracked tree it creates or switches to
`chore/opencode-<target>` from `main` before the plan; an unrelated branch or
dirty checkout is refused before any plan/commit/push, and `--dry-run` never
switches. `--auto --resume` from `main` requires recorded state for the
target. With `--auto-merge` it additionally enables
`gh pr merge --auto --squash` only when **all** of these hold: the target is a
patch inside the pinned `X.Y`; the Phase 1 manifest is present and
`machine_diff` is true for the full PR diff (generated writes plus any
branch-commit/staged path); the canary passes; the tracked tree is clean; and
the PR base is `main` with main ancestry. The upgrade branch is the current
checkout — "main" means PR base/ancestry, never a literal current branch.

Refusals leave the PR open, print the reason, and record the decision in
`.scratch/opencode-v2/auto-merge-<pin>.json`; minor/major targets and
non-machine diffs always stop at PR ready. Auto-merge is opt-in, never a
default. Rollback remains manual (no automatic rollback change), and the
detached supervisor/resume/`last-run.md` lanes are not part of this
amendment.

## 2026-11-20 amendment — detached apply, resume, and the run summary

`upgrade --to <pin> --apply --detach --drain-acknowledged` starts a detached
supervisor in a new session (`start_new_session=True`, stdio to
`supervisor-<pin>.log`) and returns immediately with the log and
`supervisor.json` paths. The record carries pid, target, phase, log, and
started/updated. The child waits up to 600 s for the **TUI** to exit
(`tui_processes()` filters the opencode family and excludes `serve`/
`--service` and supervision processes); on timeout it records `timeout` and
performs no service stop, backup, install, or migration. After the TUI exits,
the child confirms the merged `main` `VERSION_PIN` equals the target
(`pin-check` on mismatch) and that the local `scripts/` and `agents/` trees
match `origin/main` with no uncommitted changes in those paths (`tree-check`
on divergence; an unresolvable `origin/main` fails closed). Only then does it
stop the service and run the existing apply directly (`apply_supported`, not
the whole upgrade pipeline). Phases: `waiting-tui`, `timeout`, `pin-check`,
`tree-check`, `stopping-service`, `applying`, `done`/`failed`. It never passes
`--force`.

The auto lane uses the same supervisor: after a successful auto-merge with
`--drain-acknowledged` it spawns the detached child; without the drain
acknowledgment it stops at merged and prints the exact apply command. A
refused, closed, or timed-out merge never spawns.

`upgrade --to <pin> --apply --resume --drain-acknowledged` resumes from the
prior artifact: it reuses the recorded backup/DB snapshot, does not create a
new backup, and does not reinstall an already-installed target; it resumes at
shadow/migration/smoke. A smoke-only failure delegates to `verify` (no
backup/install/migration). With no prior artifact or usable backup it falls
back to the full apply. `status` reads `supervisor.json`, checks pid liveness,
and names the exact next action per phase; after apply/verify/auto completion
`last-run.md` records target, source/target versions, result, checks, artifact,
backup, merge commit, and next step.

Rollback remains manual. This amendment does not add automatic rollback, an
auto-rollback on a failed smoke, or a `rollback` command.

## 2026-11-21 amendment — refresh the live plugin corpus

The 2.2.7 host exposed a split between the reviewed repo plugin corpus and
the live config copy: the repo plugins were 2.2.7, but
`~/.config/opencode/plugins/` still held 2.2.5. The observer's TUI component
did not register, so the panel showed the sentinel fallback and delegates were
invisible; the completion observer's wake was also deferred by a local-service
401 (fixed separately by using the authenticated `opencode api` CLI for a
local wake URL).

The supported apply now refreshes the live corpus after shadow repair and
before migration: the three reviewed plugins are copied to a verified staging
tree, operator-added plugin entries are preserved, the old `plugins/` is
renamed to `plugins.v1-backup-<stamp>` inside the config root, and the staged
tree is swapped in. A failed copy or version/peer check
records `failure_stage: plugin-refresh` and leaves the target installed with
manual rollback guidance. The post-smoke adds a `plugin-versions` check: every
reviewed corpus plugin (`auto-compact-at-threshold`, `delegation-observer`,
`delegation-sentinel`) `package.json` version (and non-null
`@opencode/plugin` peer) must equal the target.

The manual repair is `python3 scripts/stage_opencode_config.py
--plugins-only` with the TUI closed and service stopped; it does not move the
config or DB. It is not a new installer and does not change the supported
`opencode upgrade` path.

## Sources

- Owner directive 2026-11-02 (supported path; yarn global; V1 shadowed; thin
  pipeline).
- `.opencode/plans/supported-opencode-upgrade.md` (approved plan; retired at
  merge).
- `opencode upgrade --help` (2.2.5) and the V2 CLI docs install/upgrade
  methods.
- ADR-0014 (one-time cutover, historical); ADR-0016 (superseded).
- `docs/roadmap-detail/RM-071.md` (correction amendment).
