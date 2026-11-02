---
slug: supported-opencode-upgrade
title: Adopt the supported OpenCode install/upgrade path and retire the custom versioned pipeline
status: approved
created: 2026-11-02
revised: []
related: [standardized-opencode-upgrade, opencode-v2-upgrade]
---

# Plan: supported-opencode-upgrade

## Goal / Approach

**Goal.** Move the live install to the supported `@opencode/cli` + `opencode
upgrade --method yarn` path with the default `~/.config/opencode` root, and
shrink the custom pipeline to the parts that catch real regressions: the
canary and the pin/docs/CI check. The 2.2.5 install is migrated in place
(same version), then the next release is tested through the official path.

**Approach.** The current versioned wrapper/binary/config root is a one-time
V1→V2 cutover artifact, not a supported install method. `opencode upgrade`
cannot manage it. The migration:

1. Backs up the V1 `~/.config/opencode`, the versioned 2.2.5 config, and the
   DB.
2. Stages the reviewed V2 config (agents, plugins, `opencode.jsonc`,
   `cli.json`, `service.json`) into `~/.config/opencode`, preserving the
   `skills`/`reference` links.
3. Installs `@opencode/cli@2.2.5` into the yarn global with the official
   method; the `~/.yarn/bin/opencode` custom wrapper is replaced by the
   package bin.
4. Verifies `which opencode`, `opencode debug paths config`, `--version`,
   `/api/info`, the TUI observer/sentinel, and the plugin loader.
5. Retires the versioned cutover/apply machinery; the live upgrade command is
   `opencode upgrade <target> --method yarn` with a pre-upgrade DB/config
   backup and a post-upgrade smoke.

The V1 `opencode-ai@1.19.4` yarn package stays installed but shadowed for the
retention window; the V1 config backup plus the pre-migration DB backup are
the full restore. The V2→V2 rollback is `opencode upgrade <previous>
--method yarn` plus the DB restore.

## Acceptance Criteria

1. **Supported topology.** `which opencode` resolves to the yarn-global
   `@opencode/cli` bin (not `~/.local/lib/opencode/*/opencode-wrapper`);
   `opencode debug paths config` is `~/.config/opencode`; `opencode
   --version` is 2.2.5. Verifier: live commands after the migration.
2. **Config migration.** The V2 agents/plugins/`opencode.jsonc`/`cli.json`/
   `service.json` are in `~/.config/opencode`; the V1 config is backed up; the
   `install.sh` skills/reference links still resolve. Verifier: `ls`, `opencode
   debug config`, `check_v2_config.py`.
3. **Official upgrade works.** `opencode upgrade 2.2.5 --method yarn`
   reinstalls the same version cleanly; the next target installs through the
   same command. `opencode upgrade --help` remains the documented path.
   Verifier: live same-version run + the next-version run.
4. **Rollback is documented and drilled.** V1 package/config/DB restore steps
   are recorded; the V1 package remains installed but shadowed. Verifier: a
   restore drill in a temp HOME plus the written procedure.
5. **Thin pipeline.** `opencode_v2_cutover.py` and the custom apply/rollback/
   versioned-dir logic are removed or reduced to historical notes;
   `opencode_upgrade.py` keeps `status`, `check`, `plan`, `canary`, `prepare`,
   `prune`, and a thin `upgrade` that calls the official command. Verifier:
   file/API review + tests.
6. **Canary remains the gate.** C1 checks the candidate and the current
   official default; C2–C5/C7–C8 + migration + plugin typechecks/tests stay;
   C6 (V1 rollback) stays optional against the shadowed V1 package. A short
   debug-TUI smoke asserts the observer/sentinel `stage=setup` completion.
   Verifier: `test_opencode_v2_canary.py` + a live candidate run.
7. **Pin/docs/CI consistency.** `VERSION_PIN` remains the single source; CI
   installs the pin via npm (official); `check --pins-only` passes; README/
   reference/ADR/AGENTS are updated. Verifier: `check --pins-only`, the
   existing v2/config/workflow gates.
8. **Decision record.** ADR-0017 (supported install/upgrade) is accepted;
   ADR-0016's custom install/apply standard is superseded/amended; RM-071 is
   amended or a new RM-072 records the correction; the plan retires at merge.
   Verifier: ADR index, ROADMAP, check_roadmap_verbatim.
9. **The 2.2.5 migration is tested end-to-end.** The live same-version
   migration passes; the next official upgrade passes; evidence is recorded.
   Verifier: live commands + `.scratch` evidence.
10. **No custom installer maintenance.** After the migration, the documented
    live upgrade is one official command; the only custom pre-merge gate is
    the canary + pin check.

## Files to Modify

- `scripts/opencode_upgrade.py` — shrink: `status`/`check`/`plan`/`canary`/
  `prepare`/`prune`/`upgrade`; remove `apply`, `rollback`, `cutover_ns`, the
  versioned-dir/source-prefix/target-clear logic; `upgrade` runs
  `opencode upgrade <target> --method yarn` after a DB/config backup and a
  post-smoke.
- `scripts/opencode_v2_cutover.py` — retire (delete or reduce to a historical
  note); remove the custom upgrade mode and link/DB rollback.
- `scripts/opencode_v2_canary.py` — C1 accepts the current official default;
  C6 optional against the shadowed V1 package; add the debug-TUI setup smoke;
  keep the scratch install/canary.
- `scripts/opencode_v2_post_smoke.py` — add an observer/sentinel API/TUI
  check; reuse in the post-upgrade smoke.
- `scripts/stage_opencode_config.py` — new: stage the reviewed V2 config into
  `~/.config/opencode` with a V1 backup, preserving skills/reference; used by
  the migration and `install.sh`.
- `install.sh` — stage the V2 config or point at the stage script.
- `scripts/test_opencode_upgrade.py` — thin-script and migration tests; remove
  the cutover/apply/rollback cases.
- `scripts/test_opencode_v2_canary.py` — new C1 default semantics, TUI smoke,
  optional C6.
- `scripts/test_opencode_v2_cutover.py` — retire with the script.
- `.github/workflows/ci.yml` — add the stage/migration smoke and the retained
  tests; remove the cutover test.
- `.github/workflows/opencode-version-check.yml` — keep; update the issue text
  to the official command.
- `reference/opencode-integration.md` — supported install/upgrade facts;
  remove the custom versioned wrapper/cutover standard.
- `README.md` — one supported install/upgrade line.
- `AGENTS.md` — rule 7: use `opencode upgrade` + the canary gate; never
  reintroduce a custom wrapper.
- `docs/ADRs/ADR-0017-supported-opencode-upgrade.md` — new accepted decision.
- `docs/ADRs/ADR-0016-opencode-upgrade-process.md` — superseded/amended.
- `docs/ADRs/README.md` — index.
- `docs/ROADMAP.md` + `docs/roadmap-detail/RM-071.md` — amendment or RM-072.
- `.opencode/plans/supported-opencode-upgrade.md` — retire at merge.

## Scope

**Included**

- The live 2.2.5 migration to the yarn-global official binary + default
  config root.
- The V1 config/DB backup and the shadowed V1 package.
- The thin orchestrator/canary/pin-check reduction.
- The debug-TUI observer/sentinel smoke and the sentinel location/health fix.
- ADR-0017, ADR-0016 supersession, RM-071/RM-072, reference/README/AGENTS.
- Same-version migration + next-version official upgrade tests.

**Excluded**

- Removing the V1 package (retention window).
- Auto-merge/deploy, consumer-repo upgrades, Windows.
- A new skill.
- Automatic TUI interaction beyond the setup smoke.

## Schema / Type Impacts

No DB/schema changes. The config root moves from the versioned root to
`~/.config/opencode`; `service.json`/`cli.json` are copied. The DB backup is
a pre-migration SQLite copy. The pin/plugin package contracts stay.

## Verification

```markdown
- python3 scripts/test_opencode_upgrade.py
- python3 scripts/test_opencode_v2_canary.py
- python3 scripts/test_opencode_v2_post_smoke.py
- python3 scripts/opencode_upgrade.py check --pins-only
- python3 scripts/check_v2_config.py
- python3 scripts/check_v2_config.py --baseline main
- python3 scripts/check_v2_surfaces.py
- python3 scripts/test_v2_config.py
- python3 scripts/test_v2_surface_contract.py
- python3 scripts/test_eval_workflows.py
- python3 scripts/check_roadmap_verbatim.py
- python3 -m yamllint -c .yamllint.yaml .github/workflows/
- bash -n install.sh
```

Live migration/upgrade:

```sh
# owner-run, separate terminal, TUI closed
opencode service stop
# backup V1 config + versioned 2.2.5 config + DB
python3 scripts/stage_opencode_config.py --backup
opencode upgrade 2.2.5 --method yarn
which opencode
opencode debug paths config     # ~/.config/opencode
opencode --version              # 2.2.5
# start the TUI; verify observer/sentinel + plugin loader
# then the next release:
opencode upgrade latest --method yarn
```

## Open Questions

1. **PR vehicle.** Rework #140 into this migration (proposed default) or
   stack a new PR? Default: rework #140; the custom orchestrator commits stay
   in branch history, the final diff is the supported path.
2. **Live migration window.** The owner runs the same-version migration after
   the PR is reviewed; the PR can stage the script/config tests. Default:
   owner-run after approval.
3. **C6 V1 rollback drill.** Keep it against the shadowed V1 package
   (proposed default) or retire it with the V1 retention? Default: keep it
   optional until the retention window ends.
4. **RM-071 vs RM-072.** Amend RM-071 with the supported-path correction
   (proposed default) or add RM-072? Default: amend RM-071 and its detail.

## History

- 2026-11-02 — initial draft from the supported-path review; owner chose yarn
  global, V1 shadowed, and the thin canary + pin-check pipeline.
