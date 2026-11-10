# ADR-0016: Standardized OpenCode upgrades — one orchestrator, canary gate, prepared pin bump, drained apply

## Status

superseded by [ADR-0017](ADR-0017-supported-opencode-upgrade.md) 2026-11-02

> **Superseded 2026-11-02.** The custom versioned install/apply pipeline this
> decision standardized was retired in favor of the supported
> `@opencode/cli` + `opencode upgrade --method yarn` path. The canary,
> pin-check, release-matrix, and post-smoke essentials carry forward.

## Context

ADR-0014 pinned the OpenCode V2 integration and added a one-time, drained
V1→V2 cutover. The 2026-11-02 move from `2.1.4` to `2.2.5` exposed the
recurring-workflow gap: the pin lived in a dozen seams, the release and
plugin-compatibility analysis was done by hand, the canary had to be invoked
with a long scratch arg vector, the prepare step touched code, CI, docs,
plugin peers, lockfiles, and an ADR amendment, and the live switch could only
run after every session drained. The upgrade also split across sessions, so a
later session had to rediscover what had already passed.

The owner directed (2026-11-02) that the upgrade process become smooth and
automated as far as the architecture allows, using the 2.2.5 upgrade as the
first exercise. The irreducible human gate is the live switch: it needs a
drained process set and a TTY, and it cannot run from inside the session it
must replace.

## Decision

1. **One entry point.** `scripts/opencode_upgrade.py` is the only supported
   upgrade path. Its subcommands are `status`, `doctor`, `check`, `plan`,
   `prepare`, `canary`, `apply`, `rollback`, `prune`, and `upgrade`.
2. **One source of truth.** `opencode_v2.VERSION_PIN` is authoritative. The
   cutover imports it; CI exports `OPENCODE_VERSION` from the adapter instead
   of duplicating a literal; `check --pins-only` enforces the remaining
   README/reference/plugin seams. A pin change without a consistent seam set
   fails CI.
3. **Pipeline.** `upgrade --to <version>` runs `check → plan → canary →
   prepare` and stops before `apply`. `--apply` continues when the owner is
   on a drained TTY. `--resume` reads
   `.scratch/opencode-v2/upgrade-state.json` and skips completed stages.
4. **Canary is the gate.** `canary --to <version>` installs the candidate in
   `.scratch/v2-<version>-prefix`, runs C1–C8 plus the migration rehearsal
   against the V1 rollback binary as the C1 "default", and typechecks/tests
   all three plugins against the target `@opencode/plugin` and OpenTUI in a
   scratch copy. A failing gate stops the pipeline; a plugin source change
   that typecheck cannot absorb is reported as a manual migration, never
   forced. The canary stops the C2/C7 scratch services it started in a
   `finally` block, so a candidate service cannot leak into the live drain
   gate or masquerade as the live version.
5. **Release intelligence is automatic.** `plan` reads the target plugin's
   peer dependencies and the public GitHub releases between the current and
   target versions, prints the CLI/plugin/OpenTUI/solid-js matrix and the
   breaking-change sections, and lists the seams that will change. No write
   happens before the canary.
6. **Prepare is atomic and idempotent.** `prepare` bumps the adapter pin, the
   docs/README/reference/plugin READMEs, the plugin package.json peer and
   dependency roots, refreshes lockfiles, and appends the dated ADR
   amendment with the canary table and residual. `--dry-run` writes nothing;
   a second run is a no-op. `--open-pr` commits/pushes and opens the PR with
   a generated body; `gh` explicitly uses `GH_CONFIG_DIR=$HOME/.config/gh`
   because the V2 wrapper's `XDG_CONFIG_HOME` otherwise hides the login.
7. **Apply is drained, verified, and reversible.** `apply` requires
   `--drain-acknowledged` and a TTY, reuses the cutover's atomic
   link/DB backup/staging, then verifies the binary version, service
   `/api/info`, the 17-agent corpus, and the plugin loader. Any failure
   restores the previous wrapper link and the pre-upgrade DB, preserves the
   failed DB, and reports `ROLLED BACK`. `--wait-for-drain` and
   `--stop-service` smooth the only human step.
8. **Drift detection is scheduled and issue-first.** CI runs
   `test_opencode_upgrade.py` and `check --pins-only`. A weekly workflow runs
   `check --remote` and opens/updates one issue with the exact `upgrade`
   command. It never pushes a branch or performs the upgrade; the draft-PR
   bot stays a future option until the canary can run in CI.
9. **Evidence has a home.** Canary/plugin evidence lives under
   `.scratch/v2-canary-<version>/`; the apply verification artifact lives
   under `.scratch/opencode-v2/upgrade-<version>-verify.json`; the ADR
   amendment is the commit-visible summary. `check --pr` fails a pin change
   whose amendment is missing or names another version. *(Superseded by
   ADR-0017: `check --pr` is a local/manual release gate; CI runs only
   `check --pins-only` and the hermetic suite.)*
10. **Hygiene.** `prune --keep N` removes old scratch prefixes, canary roots,
    and plugin-compat copies while preserving the current pin and the last N
    versions. `prepare` prints a lockfile delta summary so review focuses on
    the semantic change rather than transitive patch churn.

## Consequences

- A routine upgrade is one command through `prepare` plus one owner-run
  `apply`; the canary, compatibility matrix, pin bump, lockfiles, and PR body
  are automated.
- A failed canary or post-switch verification cannot leave the live command
  on an unverified version: the switch rolls back link and DB.
- The one remaining manual gate is deliberate: the owner must close sessions
  and run `apply` from a normal terminal. The drain wait and service stop
  reduce that step to a single command.
- Future `@opencode/plugin` API breaks still need a separate source-migration
  plan; the orchestrator detects and stops rather than attempting it.
- The V1 rollback package and the versioned wrapper topology stay untouched;
  consumer-repo upgrades remain governed by `opencode_v2_consumer.py`.

## Sources

- Owner directive 2026-11-02 (standardize the upgrade process; smooth and
  automated as far as possible).
- `.opencode/plans/standardized-opencode-upgrade.md` (approved plan; retired
  per ADR-0008/AGENTS rule 4).
- 2.2.5 canary evidence `.scratch/v2-canary-2.2.5/` (C1–C8 PASS, migration
  residual 0) and the plugin compatibility run (131 + 5 + 11 tests).
- ADR-0014 (pin policy and the one-time cutover).
- `docs/roadmap-detail/RM-071.md` (delivery and test-out record).
