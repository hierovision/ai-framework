---
slug: standardized-opencode-upgrade
title: Standardize OpenCode upgrades — one orchestrator, canary gate, prepared pin bump, drained apply
status: approved
created: 2026-11-02
revised: []
related: [opencode-v2-upgrade]
---

# Plan: standardized-opencode-upgrade

## Goal / Approach

**Goal.** Make an OpenCode version upgrade one repeatable, mostly automated
operation: detect the target, prove it with the canary, update every pin
consistently, and perform a drained atomic switch that verifies itself and
rolls back on failure. The 2.2.5 upgrade (PR #140) is the first end-to-end
exercise.

**Approach.** Add `scripts/opencode_upgrade.py` as the single entry point over
the existing adapter (`opencode_v2.py`), canary, cutover, and post-smoke. The
orchestrator owns:

- **status/check** — pinned vs live vs latest (npm registry), plus an offline
  pin-consistency gate over every active version seam.
- **plan** — resolve the target, read `@opencode/plugin@<target>` peer
  requirements, and report the compatibility delta (for 2.2.x: OpenTUI 0.7 at
  2.2.0 and 0.8 at 2.2.3+) before any write.
- **prepare** — bump the pin in the adapter, cutover, CI, README, reference,
  and plugin package/lockfile roots; append a dated ADR amendment. Idempotent;
  `--dry-run` writes nothing.
- **canary** — install the candidate into `.scratch/v2-<version>-prefix`, run
  the full existing canary against it, and typecheck/test the three plugins
  against the target `@opencode/plugin` + OpenTUI in a scratch copy. The copy
  sits at `.scratch/plugin-compat-<version>/plugins/<name>` with a `scripts`
  symlink beside it, so the observer's `../../scripts/...` contract lookup
  still resolves. Fail closed with a "manual migration required" report when
  source changes are needed.
- **apply** — the only human-gated step: drained TTY preflight, reuse the
  cutover's atomic switch, then post-switch verification (version, `/api/info`,
  agent count, plugin loader). Any failure automatically restores the previous
  wrapper link and the pre-upgrade DB and reports `ROLLED BACK`.
- **rollback** — delegate to the cutover manifest rollback.

The end-to-end path is `upgrade --to X` = `check → plan → canary → prepare`,
stopping before `apply` with the exact command. `--apply` continues when the
terminal is drained; otherwise it prints why and exits without switching.

The standard is binding through a new ADR-0016, an RM-071 roadmap row/detail,
an `AGENTS.md` rule ("version changes go through the orchestrator"), and the
operator section in `reference/opencode-integration.md`.

### Smoothing additions (same PR)

These remove the friction this upgrade actually hit:

1. **`status --explain` / `doctor`** — print the install topology
   (`~/.yarn/bin/opencode` → versioned wrapper → binary, config root, V1
   rollback package), pinned/live/latest, the last canary/apply stage, and the
   exact next command. This answers "was it npm or yarn?" without reading
   symlinks.
2. **`plan` release notes + matrix** — fetch the public GitHub releases
   between current and target, extract the `Breaking changes` sections, and
   print a CLI/plugin/OpenTUI/solid-js compatibility matrix with one action
   per row.
3. **One source of truth** — `opencode_v2.VERSION_PIN` is authoritative: the
   cutover imports it, CI exports `OPENCODE_VERSION` from the adapter, and
   `check --pins-only` enforces the remaining docs/plugin seams. No duplicate
   version constants.
4. **Resumable upgrade state** — `.scratch/opencode-v2/upgrade-state.json`
   records the target and the last successful stage (`checked → planned →
   canaried → prepared → applied`); `upgrade --resume` continues across the
   session boundary, and `status` shows the stage.
5. **Drain UX** — `apply` lists busy sessions from `GET /api/session/active`,
   supports `--wait-for-drain [--timeout]`, and `--stop-service` stops the
   shared service once the sessions are closed.
6. **`prepare --open-pr`** — commit/push/open a PR with a generated body
   (canary gate table, release notes, compatibility matrix, apply command);
   `gh` runs with `GH_CONFIG_DIR=$HOME/.config/gh` so the wrapper's
   `XDG_CONFIG_HOME` cannot hide the login.
7. **Hygiene** — `upgrade prune --keep N` removes old scratch prefixes/canary/
   compat dirs; `prepare` prints a lockfile delta summary (target entries +
   transitive count) so review focuses on the semantic change.
8. **Commit-visible canary gate** — the generated ADR amendment carries the
   gate table/residual; `check --pr` fails a pin change whose amendment is
   missing or names another version. Pre-commit and CI run
   `check --pins-only`.

## Acceptance Criteria

1. **Offline pin gate.** `python3 scripts/opencode_upgrade.py check --pins-only`
   exits 0 on a consistent tree and 1 naming every stale seam; a unit test
   mutates each seam in a temp copy and asserts the failure. Verifier:
   `python3 scripts/test_opencode_upgrade.py`.
2. **Remote check.** `status` prints pinned/live/latest and `check --remote`
   exits 1 when the registry has a newer `@opencode/cli`, 0 when equal. Verifier:
   unit test with a fake `npm` binary; live `status` output.
3. **Plan compatibility.** `plan --to 2.2.5` prints the target, the required
   `@opencode/plugin`/OpenTUI versions, the seams to change, and the next
   commands; `plan --to 2.2.0` reports OpenTUI 0.7; `plan --to 2.1.4` reports
   "current". Verifier: unit test with a fake peer-deps payload.
4. **Prepare is safe.** `prepare --to 2.2.5 --dry-run` prints the diff and
   leaves `git status` unchanged; a second real `prepare` is a no-op
   (`git diff --exit-code`). Verifier: temp-copy test.
5. **Prepare updates every seam.** After `prepare --to 2.2.5`,
   `check --pins-only` passes, the plugin package.json and lockfile roots pin
   `@opencode/plugin@2.2.5` + OpenTUI `0.8.1`, and the ADR carries a dated
   amendment. Verifier: temp-copy test + `check --pins-only`.
6. **Canary automation.** `canary --to 2.2.5` installs into
   `.scratch/v2-2.2.5-prefix`, invokes the full canary with
   `--version 2.2.5`, and writes evidence under `.scratch/v2-canary-2.2.5/`;
   a failing gate exits non-zero and names the gate. Verifier: unit test with
   a fake canary process; live run for 2.2.5.
7. **Plugin compatibility gate.** `canary` typechecks/tests the three plugins
   against the target `@opencode/plugin`/OpenTUI in a scratch copy; a failing
   typecheck stops with "manual migration required" and does not prepare or
   switch. Verifier: unit test with a fake plugin; live 2.2.5 evidence
   (131 + 5 + 11 tests).
8. **Apply refuses unsafe states.** `apply` exits 2 without a TTY, with a live
   OpenCode process, with current == target, or with a missing candidate; the
   wrapper link is unchanged. Verifier: temp-HOME test using the existing
   cutover process seam.
9. **Apply verifies and auto-rolls back.** After the switch, `apply` checks the
   binary version, `/api/info`, the agent count, and the plugin loader; a forced
   probe failure restores the original link and pre-upgrade DB and exits
   non-zero with `ROLLED BACK`. Verifier: temp-HOME test with a fake binary
   that fails one probe.
10. **Rollback.** `rollback --manifest` restores the previous link and DB;
    the test asserts the link target and a `session` row. Verifier: temp-HOME
    test.
11. **CI and drift detection.** `ci.yml` runs `test_opencode_upgrade.py` and
    `check --pins-only`; a scheduled workflow runs `check --remote` weekly and
    opens one idempotent issue when a newer version exists. Verifier: workflow
    lint + `test_eval_workflows.py`-style parsing test.
12. **The 2.2.5 exercise.** The branch's `status`, `plan`, and `canary` run
    live on 2.2.5; the owner runs `apply` from a normal terminal and the
    post-switch verification passes; evidence paths are recorded in
    RM-071/ADR-0016. Verifier: command outputs + `.scratch` artifacts.
13. **Docs and gates.** ADR-0016, the ADR index row, RM-071 row/detail,
    reference/README/AGENTS updates, and plan retirement land on the branch;
    `check_v2_config` (+`--baseline main`), `check_v2_surfaces`, the offline
    suites, and pre-commit are green. Verifier: the repo's CI command list.
14. **Operator visibility.** `status --explain` (and `doctor`) prints the
    install topology, pinned/live/latest, the last canary/apply stage, and the
    next command; the resumable state survives a simulated canary failure and
    `upgrade --resume` skips completed stages. Verifier: temp-HOME test with
    fake binaries and a state file.
15. **Release intelligence.** `plan` includes the target's breaking-change
    notes and a compatibility matrix (CLI/plugin/OpenTUI/solid-js) with one
    action per row. Verifier: fixture test with a captured GitHub-releases
    payload.
16. **Single source + PR gate.** The cutover imports `VERSION_PIN`; the CI
    workflow exports `OPENCODE_VERSION` from the adapter (no hardcoded pin);
    `check --pins-only` passes; `check --pr` fails a pin change whose ADR
    amendment is missing or names another version. Verifier: temp-copy test +
    workflow parsing test.
17. **Drain + PR automation.** `apply` lists busy sessions, `--wait-for-drain`
    exits when the fake process/session lists empty, `--stop-service` invokes
    the stop; `prepare --open-pr` generates the PR body and invokes `gh` with
    `GH_CONFIG_DIR=$HOME/.config/gh`. Verifier: temp-HOME test with fake
    `opencode`/`gh` binaries.
18. **Hygiene.** `upgrade prune --keep N` removes old scratch prefixes/canary/
    compat dirs and keeps the last N; `prepare` prints a lockfile delta
    summary (target entries + transitive count). Verifier: scratch-tree test.

## Files to Modify

- `scripts/opencode_upgrade.py` — new orchestrator: `status`, `check` (offline
  seams + remote registry), `plan`, `prepare`, `canary`, `apply`, `rollback`,
  `upgrade`; `--json` on every command.
- `scripts/test_opencode_upgrade.py` — new hermetic suite (fake npm/opencode
  binaries, temp HOME/copies, seam mutation, apply/auto-rollback).
- `scripts/opencode_v2_canary.py` — add `--version` (default `VERSION_PIN`),
  use it in C1 install/assert and tighten C2 to the exact version.
- `scripts/test_opencode_v2_canary.py` — cover the version override and exact
  C2 assertion.
- `scripts/opencode_v2_cutover.py` — reuse `check_drain`/`version_of`; no
  switch-behavior change (the orchestrator owns post-switch verification).
- `scripts/opencode_v2_post_smoke.py` — expose the existing loader/agent
  checks for the apply verifier if a small refactor is needed; otherwise
  import them unchanged.
- `.github/workflows/ci.yml` — add `test_opencode_upgrade.py` and
  `opencode_upgrade.py check --pins-only`.
- `.github/workflows/opencode-version-check.yml` — new weekly/dry-run
  scheduled check; opens one labeled issue for a newer version.
- `reference/opencode-integration.md` — replace the manual upgrade section
  with the orchestrator's standard path and the automation boundary.
- `README.md` — one-line upgrade command/link next to the pinned requirement.
- `AGENTS.md` — rule: version/pin changes go through the orchestrator; never
  hand-edit a single seam.
- `docs/ADRs/ADR-0016-opencode-upgrade-process.md` — new binding decision.
- `docs/ADRs/ADR-0014-opencode-v2-upgrade.md` — `prepare` appends the dated
  pin amendment (generated text, reviewed in the PR).
- `docs/ADRs/README.md` — index row for ADR-0016.
- `docs/ROADMAP.md` — RM-071 row, horizon strip, priority order, counters.
- `docs/roadmap-detail/RM-071.md` — new provenance/delivery evidence.
- `docs/roadmap-detail/RM-067.md` — pointer from the original cutover to the
  standard + RM-071.
- `plugins/*/package.json` + `package-lock.json` — updated by `prepare` (not
  hand-edited); the plan lists them so the implementer expects the generated
  diff.
- `plugins/*/README.md` — `prepare` updates the exact dependency statements
  (or `check --pins-only` flags them as stale).
- `.opencode/plans/standardized-opencode-upgrade.md` — retired before merge
  per ADR-0008/AGENTS rule 4; essence lives in ADR-0016/RM-071/reference.

## Scope

**Included**

- The orchestrator and its hermetic tests.
- Offline seam checking and the remote version check.
- Canary automation + plugin compatibility typecheck/tests.
- Drained apply with post-switch verification and automatic rollback.
- Weekly drift detection.
- ADR-0016, RM-071, reference/README/AGENTS updates.
- The first end-to-end 2.2.5 exercise (live canary now; live apply by the owner
  after the session closes).

**Excluded**

- Automatic source migration when a future `@opencode/plugin` API break needs
  code changes. The orchestrator stops with a manual-migration report; the
  fix is a separate plan/PR.
- Automatic merge, deploy, or an update without an owner-run apply.
- Upgrading the V1 `opencode-ai` rollback package.
- Consumer-repo (Paragon) upgrade automation beyond the existing
  `opencode_v2_consumer.py` readiness artifact.
- Windows support.
- A new `upgrading-opencode` skill (Open Question; proposed default is no skill
  until the process has run twice).

## Schema / Type Impacts

None for the database or generated types.

New machine-readable contracts:

- `opencode_upgrade.py check --json`:
  `{pinned, live, latest, update_available, seams: [{path, ok, detail}]}`.
- `opencode_upgrade.py plan --json`: target, required plugin/OpenTUI versions,
  seam changes, canary/apply command argv.
- Apply verification artifact under
  `.scratch/opencode-v2/upgrade-<version>-verify.json`:
  `{version, checks: {binary, service, agents, loader}, rolled_back}`.
- The cutover manifest schema is unchanged; the orchestrator writes the verify
  artifact separately and uses the manifest path for rollback.

## Verification

```markdown
- python3 scripts/test_opencode_upgrade.py
- python3 scripts/opencode_upgrade.py check --pins-only
- python3 scripts/test_opencode_v2_canary.py
- python3 scripts/test_opencode_v2_cutover.py
- python3 scripts/test_opencode_v2_post_smoke.py
- python3 scripts/test_opencode_v2_consumer.py
- python3 scripts/check_v2_config.py
- python3 scripts/check_v2_config.py --baseline main
- python3 scripts/check_v2_surfaces.py
- python3 scripts/test_v2_config.py
- python3 scripts/test_v2_surface_contract.py
- python3 scripts/test_eval_workflows.py
- python3 scripts/supervision_contract.py --check
- python3 scripts/test_supervision_contract.py
- node --test plugins/auto-compact-at-threshold/test.mjs
- npm ci --prefix plugins/delegation-observer --no-audit --no-fund
- node --test plugins/delegation-observer/*.test.ts plugins/delegation-sentinel/sentinel.test.ts
- node plugins/delegation-observer/mutation-check.mjs
- bash -n install.sh
- python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

Live exercise (the test-out):

```sh
python3 scripts/opencode_upgrade.py status
python3 scripts/opencode_upgrade.py plan --to 2.2.5
python3 scripts/opencode_upgrade.py canary --to 2.2.5
# after exiting the TUI, from a normal terminal:
opencode service stop
python3 scripts/opencode_upgrade.py apply --to 2.2.5
opencode --version   # opencode v2.2.5
```

## Open Questions

1. **PR vehicle.** Continue on `chore/opencode-v2-2.2.5` and retitle PR #140
   to the standard (proposed default), or keep #140 as the pin-only PR and
   stack a new `feat/standardized-opencode-upgrade` PR? Default: expand #140,
   because the 2.2.5 upgrade is the first exercise and the live apply should
   use the standard.
2. **Skill.** Add `skills/upgrading-opencode` now, or keep the standard in
   ADR-0016 + reference + the script and add a skill after two successful
   runs? Default: no new skill now (avoids the skill-eval/registry surface
   until the workflow proves stable).
3. **Scheduled drift check.** Include
   `.github/workflows/opencode-version-check.yml` now (proposed default), or
   defer it to a follow-up? Default: include it; it is the "automated as much
   as possible" detection half.
4. **Auto-rollback scope.** On a post-switch verification failure, restore
   both the wrapper link and the pre-upgrade DB (proposed default), or restore
   the link only and leave the new DB for inspection? Default: both; the
   pre-upgrade DB is the data rollback and the failed DB is preserved.
5. **Roadmap.** Add RM-071 and its detail file (proposed default), or treat
   this as a chore with no roadmap row? Default: add RM-071 so the standard
   has a tracked delivery/evidence home.
6. **Scheduled automation depth.** Open one labeled issue with the exact
   upgrade command (proposed default), or also open a draft PR with the pin
   bump + release notes? A draft PR needs branch-push permissions and the
   canary still stays owner-run. Default: issue first; draft PR only after
   the canary can run in CI.

## History

- 2026-11-02 — initial draft from the 2.2.5 upgrade investigation (PR #140,
  canary evidence `.scratch/v2-canary-2.2.5/`, plugin compatibility run).
- 2026-11-02 — added the smoothing layer (operator visibility, release notes/
  matrix, single source, resumable state, drain UX, `--open-pr`, hygiene,
  commit-visible canary gate) and the scheduled-automation open question.
- 2026-11-02 — approved by the owner: all eight smoothing items, issue-first
  scheduled check, expand PR #140, no new skill yet.
