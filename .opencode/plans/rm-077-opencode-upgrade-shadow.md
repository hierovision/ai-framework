---
slug: rm-077-opencode-upgrade-shadow
title: Preserve the V2 default binary and truthful verification across supported OpenCode upgrades
status: approved
created: 2026-11-09
revised: [2026-11-09]
related: [RM-071, RM-067]
---

# Plan: rm-077-opencode-upgrade-shadow

## Goal / Approach

**Goal:** every supported OpenCode upgrade leaves the default `opencode`
command resolving to the installed target V2 package, verifies that target
rather than a stale V1 shim, and records failure or success truthfully without
claiming an automatic rollback that did not occur.

**Observed failure.** On 2026-11-09, `@opencode/cli@2.2.6` installed
successfully and `opencode2 --version` returned `opencode v2.2.6`, but
`python3 scripts/opencode_upgrade.py upgrade --to 2.2.6 --apply
--drain-acknowledged` reported:

```text
verify binary: FAIL 1.19.4
verify api: FAIL
verify plugin: FAIL loader did not load ...
verify observer: FAIL api unavailable
```

An explicit 2.2.6 probe then passed: `opencode2 debug paths config` returned
`~/.config/opencode`, the service returned `"version":"2.2.6"`, 24 agent IDs
were present, and the plugin loader probe loaded
`auto-compact-at-threshold`. The release and canary were healthy; the default
command was not.

**Root cause, one sentence:** Yarn-global retains both `@opencode/cli` and
`opencode-ai`; both publish an `opencode` bin, Yarn links `opencode2` to V2 but
`opencode` to V1, and the upgrade orchestrator assumes its post-install `PATH`
lookup still resolves V2.

Contributing defects:

1. `scripts/opencode_upgrade.py::apply_supported()` does not reassert the V2
   shadow after the official Yarn install and before `post_upgrade_smoke()`.
   The smoke therefore measures `opencode-ai@1.19.4`.
2. The failure path writes `rolled_back=True` and stage `rolled-back`, although
   it neither restores the previous package nor restores the DB/config. The
   artifact misstates what happened.
3. `status` sees the broken default as an unsupported install and recommends
   re-running `stage_opencode_config.py --backup`, even when the V2 config is
   already staged and the 2.2.6 package plus `opencode2` binary are present.
4. The `target == VERSION_PIN` fast path returns `already current` without
   re-verifying an application whose prior apply failed.
5. `test_apply_requires_consent_and_post_smoke_failure` mocks the official
   install and smoke independently; no test models Yarn mutating the default
   bin link between those steps.
6. `reference/opencode-integration.md` still describes a versioned wrapper
   selecting `XDG_CONFIG_HOME`, contradicting ADR-0017 and the supported path.

**Approach.** Keep ADR-0017's supported installation model. Do not remove the
retained V1 package, add a custom wrapper, or hand-edit a pin seam. Add a
deterministic package-binary resolver and atomic default-link repair inside the
upgrade orchestrator:

- Resolve the installed V2 target in this order: the Yarn-managed
  `$HOME/.yarn/bin/opencode2` if it reports the exact target, then
  `$HOME/.config/yarn/global/node_modules/@opencode/cli/bin/opencode.exe`.
  Refuse if neither reports the target.
- Atomically replace `$HOME/.yarn/bin/opencode` with a symlink to the resolved
  package binary (prefer the relative `opencode2` target), using a temporary
  link in the same directory plus `os.replace`. This is a package-bin shadow,
  not a versioned wrapper.
- Verify both `opencode --version` and
  `opencode debug paths config` resolve to the target and
  `$HOME/.config/opencode` before any smoke.
- In `apply_supported()`, skip the official install when the target package is
  already installed, repair the shadow, then run the smoke with the repaired
  executable explicitly. This makes the current 2.2.6 recovery idempotent and
  avoids another Yarn operation resetting the link.
- When the target is already installed but the default is V1, `upgrade
  --to <pin> --apply --drain-acknowledged` repairs and verifies without
  reinstalling.
- On smoke failure, leave the installed target and repaired default in place
  (ADR-0017 has no automatic package/DB rollback), write `verified: false`,
  `rolled_back: false`, a named `failure_stage`, link/package evidence, and the
  exact manual rollback command. Leave upgrade state at `prepared`; never claim
  `rolled-back`.
- Extend `status`/`doctor` with target-package, default-link, and shadow state.
  A broken shadow reports the exact repair-and-verify command. Existing config
  staging is not recommended when the root is already supported.

The current host repair is part of acceptance: after this fix merges, the owner
runs the idempotent apply once on 2.2.6 with no package reinstall, which repairs
the default link and replaces the false failure artifact with passing evidence.

## Acceptance Criteria

1. **Yarn relink is reproduced hermetically.** A fixture has a V2
   `opencode2`, a V1 `opencode`, and an official-install stub that rewrites the
   default link to V1. `apply_supported()` exits 0 only after repairing the
   link to V2 and running the smoke against V2. — Verifier:
   `python3 scripts/test_opencode_upgrade.py` includes and passes
   `test_apply_repairs_yarn_relink_before_smoke`.

2. **The repaired binary is the one verified.** The smoke receives an explicit
   executable/link resolved after repair and asserts its exact version; it does
   not rely on a possibly stale `PATH`/`shutil.which` cache. — Verifier: the
   same test records the smoke argument and fails if it resolves V1; the live
   check is
   `readlink -f "$(command -v opencode)"` ending at the 2.2.6 package binary.

3. **Already-installed target recovery is idempotent through the CLI.** With
   the target package installed and the default link wrong, `upgrade --to <pin>
   --apply --drain-acknowledged` does not stop at the unsupported-topology
   guard, skips the official install, repairs the shadow, verifies, and records
   `applied`. — Verifier:
   `test_upgrade_repairs_when_default_is_v1` drives `upgrade()` end-to-end and
   asserts the official-install stub was not called and the smoke ran once;
   `test_apply_reuses_installed_target_and_repairs_default` covers the inner
   apply path.

4. **A failed apply is truthful.** A forced smoke failure produces an artifact
   with `verified: false`, `rolled_back: false`, the named failure stage, the
   target package version/path, default-link evidence, and the backup path; the
   upgrade state remains `prepared`. — Verifier:
   `test_apply_failure_is_not_reported_as_rolled_back` exits non-zero and
   asserts every field.

5. **Link repair fails closed.** Missing/mismatched target binaries or a
   config-root mismatch fail before smoke, leave a coherent diagnostic, and
   never link an unverified executable or report success. — Verifier:
   `test_shadow_repair_refuses_missing_or_wrong_target` and
   `test_shadow_repair_requires_supported_config_root` pass.

6. **Status and doctor diagnose the shadow.** With 2.2.6 installed but the
   default at 1.19.4, `status` reports `target_installed: 2.2.6`,
   `default_version: 1.19.4`, `shadow_ok: false`, and the exact repair command;
   `doctor` exits non-zero. It does not recommend re-staging a supported
   config. — Verifier:
   `test_status_detects_shadow_mismatch_and_next_repair` and
   `test_doctor_fails_on_shadow_mismatch` pass.

7. **There is no false rollback claim.** Code, tests, README, reference, and
   RM-071 detail no longer describe automatic link/DB rollback for supported
   applies; they name the package/config/DB backup and manual rollback command
   under ADR-0017. — Verifier:
   `rg -n "rolled-back|rolled_back|automatic rollback" scripts
   docs/roadmap-detail/RM-071.md reference/opencode-integration.md` shows only
   truthful compatibility fields/tests; the new failure test is green.

8. **Corrective path is documented and executable.** README and the dated
   ADR-0017 amendment state the Yarn bin collision, the authoritative
   `opencode`/`opencode2` distinction, the automatic shadow repair, and the
   owner recovery command for an already-installed target. —
   Verifier: `test_upgrade_docs_describe_supported_shadow` asserts the required
   terms and commands in README, reference, and ADR-0017;
   `python3 scripts/opencode_upgrade.py check --pins-only` and
   `python3 scripts/opencode_upgrade.py doctor` pass on the repaired host;
   `node scripts/verify.mjs` exits 0.

9. **Current 2.2.6 installation is repaired without reinstall.** After the
   code lands, the owner runs the new idempotent apply from a normal terminal
   with all sessions closed. It must not invoke Yarn. Required final evidence:
   `opencode --version` → `opencode v2.2.6`;
   `opencode2 --version` → `opencode v2.2.6`;
   `opencode debug paths config` → `$HOME/.config/opencode`;
   `/api/info` → `"version":"2.2.6"`;
   `upgrade-2.2.6-verify.json` has every check true and `verified: true`;
   `upgrade-state.json` is `applied`; a real standalone run returns `OK`. —
   Verifier: exact commands in Verification, plus preservation of the failed
   artifact under a dated `.failed-*` name and the
   `pre-upgrade-20261109T122006Z` backup.

10. **No weakening or scope drift.** No canary gate, post-smoke check, pin
    seam, or assertion is deleted or relaxed; the retained V1 package and no
    custom wrapper topology remain. — Verifier: `git diff main --
    scripts/test_*.py` contains no deleted test/assertion or skip; full suite
    below is green.

## Files to Modify

- `scripts/opencode_upgrade.py` — add target-binary resolution, atomic
  package-bin shadow repair, explicit-binary smoke invocation, idempotent
  already-installed recovery, truthful failure artifact/state handling, and
  `status`/`doctor` shadow fields and next command.
- `scripts/test_opencode_upgrade.py` — add the Yarn-relink, no-reinstall,
  shadow-repair failure, truthful-failure, status, and doctor tests; update the
  existing apply-failure expectation from false `rolled_back` to
  `verified: false`.
- `README.md` — document the Yarn dual-bin collision and that the supported
  orchestrator repairs the default `opencode` shadow.
- `reference/opencode-integration.md` — replace the stale versioned-wrapper
  paragraph with the supported yarn-global topology, `opencode`/`opencode2`
  distinction, shadow repair, and truthful failure/rollback semantics.
- `docs/ADRs/ADR-0017-supported-opencode-upgrade.md` — dated 2026-11-09
  amendment: package-bin shadow is an explicit supported action; apply repairs
  it before smoke; failed verification is not an automatic rollback.
- `docs/roadmap-detail/RM-071.md` — record the 2.2.6 shadow defect and point at
  RM-077.
- `docs/ROADMAP.md` — add the RM-077 Now row with evidence links and its
  horizon/counters; close it in the delivering PR.
- `docs/roadmap-detail/RM-077.md` — new provenance/evidence file for this
  defect and delivery.
- `.opencode/plans/rm-077-opencode-upgrade-shadow.md` — this plan; retire it in
  the delivering PR after the essence lands in ADR-0017/reference/RM-077.

No change is needed in `.github/workflows/ci.yml`: `test_opencode_upgrade.py`
and `check --pins-only` already run in `quality-gates`.

## Scope

### Included

- Correcting the supported upgrade's default-binary shadow, verification
  target, idempotent recovery, state/artifact truthfulness, and diagnostics.
- Hermetic tests that model Yarn mutating the link between install and smoke.
- Correcting ADR/reference/README/RM-071 documentation and adding RM-077.
- Repairing the current 2.2.6 host install without reinstalling the package.

### Excluded

- Removing or upgrading the retained V1 `opencode-ai@1.19.4` package.
- Reintroducing the retired versioned wrapper, custom `XDG_CONFIG_HOME`
  selector, cutover, or automatic link/DB rollback.
- Re-staging all agents/plugins or upgrading the deployed plugin package pins
  as part of every V2→V2 upgrade. The current 2.2.5 plugin packages loaded and
  passed the real 2.2.6 loader probe; a future incompatibility is canary-gated.
  Deployed-plugin version refresh is a separate follow-up if needed.
- Any session-DB migration, model/policy change, or unrelated upgrade CLI
  redesign.
- Running Yarn or the real install during tests.

## Schema / Type Impacts

No database or generated-type change.

The upgrade verification artifact (`upgrade-<version>-verify.json`) and
`upgrade-state.json` are local wire formats consumed by `status`/`doctor`:

- Add `verified`, `failure_stage`, `target_package`,
  `default_link`, and `default_version` fields.
- Keep `rolled_back` for reading older artifacts but write it as `false` on
  failure; `verified` is the authoritative result.
- Keep upgrade state at the last completed stage on failure; do not write a
  `rolled-back` stage for an apply that performed no restore.

The host filesystem contract is explicit:

- Retained package: `$HOME/.config/yarn/global/node_modules/opencode-ai/`.
- Target package: `$HOME/.config/yarn/global/node_modules/@opencode/cli/`.
- Yarn links: `$HOME/.yarn/bin/opencode2` (V2) and
  `$HOME/.yarn/bin/opencode` (must be repaired to V2).
- Supported config root: `$HOME/.config/opencode`.

## Verification

Hermetic:

```bash
python3 scripts/test_opencode_upgrade.py
python3 scripts/test_opencode_v2_post_smoke.py
python3 scripts/test_stage_opencode_config.py
python3 scripts/opencode_upgrade.py check --pins-only
python3 scripts/check_v2_config.py --baseline main
python3 scripts/check_v2_surfaces.py
node scripts/verify.mjs
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/check_roadmap_verbatim.py
```

The targeted suite must prove the red-first Yarn-relink case: remove the
shadow-repair call and
`test_apply_repairs_yarn_relink_before_smoke` must fail with V1 in the smoke;
restore it and the suite passes.

Live repair after the branch merges, owner-run from a normal terminal with all
sessions closed:

```bash
cd /home/hierovision/repos/ai-framework || exit 1

python3 scripts/opencode_upgrade.py status
python3 scripts/opencode_upgrade.py upgrade --to 2.2.6 --apply \
  --drain-acknowledged --stop-service
python3 scripts/opencode_upgrade.py status
python3 scripts/opencode_upgrade.py doctor
```

Expected: the apply reuses the installed 2.2.6 package, performs no Yarn
install, repairs `~/.yarn/bin/opencode`, and writes passing
`upgrade-2.2.6-verify.json`. Then:

```bash
opencode --version
opencode2 --version
opencode debug paths config
opencode service restart
opencode api get /api/info
opencode run --standalone --model opencode-go/deepseek-v4.1-flash \
  --format json "Reply OK"
```

Expected: both version commands print `opencode v2.2.6`; config root is
`$HOME/.config/opencode`; `/api/info` contains `"version":"2.2.6"`; the run
returns `OK`.

## Open Questions

1. **Should every V2→V2 upgrade also refresh deployed plugin package pins?**
   Proposed default: no in this fix; the supported path treats config staging
   as one-time, and the real 2.2.6 loader already passed with the deployed
   2.2.5 plugin packages. Record a follow-up only if a future canary shows a
   runtime incompatibility.
2. **Should the repair command be a separate `repair` subcommand?**
   Proposed default: no. Make `upgrade --to <pin> --apply` idempotent and have
   `status`/`doctor` print that one command, keeping one owner workflow.

## History

- 2026-11-09 — initial design pass after the live 2.2.6 apply. Investigated the
  actual failed artifact, global Yarn package/bin topology, explicit 2.2.6
  service/agent/plugin probes, orchestrator code, and test seams. The release
  and canary are healthy; the supported upgrade's V1/V2 bin shadow and failure
  bookkeeping are defective. UX consult skipped: no user-facing UI. No matching
  stack reference for this Python/Node tooling repo; planned generically.
- 2026-11-09 — owner approved the plan with both proposed defaults: deployed
  plugin-pin refresh is deferred unless a future canary fails, and the existing
  `upgrade --apply` path becomes idempotent rather than gaining a separate
  repair subcommand. Handoff is to a fresh implementer; the live 2.2.6 repair
  remains owner-run after review and merge.
- 2026-11-09 — implemented on `feat/rm-077-opencode-upgrade-shadow` (isolated
  worktree, based on main `f1a9443`). AC→verifier: AC1/AC2
  `test_apply_repairs_yarn_relink_before_smoke`; AC3
  `test_apply_reuses_installed_target_and_repairs_default` +
  `test_upgrade_repairs_when_default_is_v1`; AC4
  `test_apply_failure_is_not_reported_as_rolled_back`; AC5
  `test_shadow_repair_refuses_missing_or_wrong_target` +
  `test_shadow_repair_requires_supported_config_root`; AC6
  `test_status_detects_shadow_mismatch_and_next_repair` +
  `test_doctor_fails_on_shadow_mismatch`; AC8
  `test_upgrade_docs_describe_supported_shadow`; AC7/AC10 by the docs edits +
  `rg` sweep and the full suite. Red-first: with `repair_default_link` removed,
  `test_apply_repairs_yarn_relink_before_smoke` failed because the smoke
  recorded `version: 1.19.4` (V1); restoring the call is green. Interpretation
  note: the repaired default link is verified by the smoke's first two checks
  (`binary`, `config-root`) before the API/agent/plugin probes; the resolver
  and target-config check still fail closed before touching the link. Full
  verification: `test_opencode_upgrade.py` 21/21, `test_opencode_v2_post_smoke.py`
  10/10, `test_stage_opencode_config.py` 2/2, `check --pins-only` 20/20,
  `check_v2_config --baseline main` 17 agents, `check_v2_surfaces` clean,
  `verify.mjs` 29 manifests, `validate_skill --all` clean,
  `check_roadmap_verbatim` clean. No contract-breaking deviation. No scope
  creep. The 2.2.6 host repair remains owner-run post-merge (no live Yarn,
  package, config, or DB mutation in this pass).

### Follow-ups

- Deployed plugin-package refresh on a future V2→V2 upgrade remains deferred
  unless a canary shows a runtime incompatibility (plan Open Question 1).
- The shadow repair is exposed only through idempotent `upgrade --apply`; no
  separate `repair` subcommand (plan Open Question 2).
