# Three-layer eval gating (RM-003)

RM-003 shifts eval-based regression detection left from a weekly-only cadence
to a three-layer model: fast local hermetic checks, optional local advisory
feedback, and an un-bypassable per-change required check.

## Contents

- Topology
- Rationale
- Changed-files mapping classes
- Two-tier marker selection (pass 4)
- Typed-assertion enforcement (pass 5)
- Bypass semantics
- Layer 2 advisory command
- Rollback

## Topology

| Layer | Trigger | Scope | Runtime | Enforcement | Purpose |
|---|---|---|---|---|---|
| 1. Pre-commit | `git commit` (installed hook) | Hermetic validators: `validate_skill.py --all` + `scripts/verify.mjs` | ~14s | Advisory (bypassable with `--no-verify`) | Catch malformed skills/manifests before commit; 0 CI minutes |
| 2. Advisory pre-push | `git push` (optional, opt-in) | Single-skill behavioral eval for the changed skill | ~30-60s | Never blocks; labeled "courtesy-feedback-not-evidence" | Fast local feedback; quarantine state stays CI-owned |
| 3. Per-change PR check | `pull_request` / `push` to `main` | Skill change -> that skill's `default` canary; harness change -> fixed six-core set; one-eval-per-job matrix | <= 12 min target; 20 min ceiling; red in 2-3 min | Required check, un-bypassable | Regression detection per change |

Components:

- Layer 1: `scripts/install-hooks.sh` installs `.git/hooks/pre-commit`.
- Layer 2: documented command below (no committed script; intentionally
  developer-local).
- Layer 3: `.github/workflows/eval-per-change.yml`, plus
  `scripts/changed-files-to-skills.py` for the changed-skill mapping.
- Reports/dashboard: `scripts/eval-report.py` + the weekly
  `.github/workflows/eval-behavioral.yml` uploads.

## Rationale

Git hooks are bypassable (`--no-verify`); required PR checks are not. Layer 1
catches syntax/structure errors instantly at zero CI cost. Layer 2 gives
developers optional fast feedback without CI load. Layer 3 is the authoritative
gate that cannot be skipped. The weekly `eval-behavioral` run remains the
full-suite authority.

## Changed-files mapping classes

`scripts/changed-files-to-skills.py` maps changed paths to skills with
**first-match-wins** semantics and three classes:

- **evaluable** — `skills/<name>/**`, `reference/model-routing.md`,
  `agents/*.md`: run the owning skill's one `default` canary (fallback = first
  eval in file order).
- **harness** — `.github/workflows/**`, `scripts/**`, and any unmatched path:
  no owning behavioral eval, so run the fixed **six-core-default set**.
- **non_evaluable** — `docs/**`, `reference/**` (except `model-routing.md`),
  `.opencode/**`, top-level `README.md`/`LICENSE`/`.gitignore`, and `*.md`
  outside `skills/**` and `docs/**`: no behavioral surface, run 0 evals.

See the mapping table in `scripts/changed-files-to-skills.py`.

## Two-tier marker selection (pass 4)

- `"default": true` on exactly one eval per `evals.json` is that skill's
  per-change canary. Pass 4 marks `authoring-skills` and `observing-runs`;
  every other skill falls back to its first eval and is surfaced in
  `coverage-gaps.no_default_marker`.
- `"core": true` on the six core skills' default evals
  (`authoring-skills`, `designing-architecture`, `implementing-features`,
  `reviewing-code`, `triaging-requirements`, `writing-unit-tests`) is the
  harness-change set.
- The selected evals run as a **one-eval-per-job matrix** (`fail-fast: true`,
  `max-parallel` from the `EVAL_MAX_PARALLEL` repository variable, default 3).
  The aggregation/report job runs `needs: [evals]` + `if: always()`, so
  artifacts and SLA reporting survive a red leg.

## Typed-assertion enforcement (pass 5)

Every behavioral eval asserts through one of three closed channels — `action`
(a tool-event predicate over the `--format json` session stream), `artifact`
(a written file + key phrases), or `text` (a key phrase in the final response)
— selected by the nature rule (act → action; produces a file → artifact;
literally speech → text). The full schema lives in
`skills/authoring-skills/references/eval-assertions.md`.

- **Layer 1 (pre-commit)**: `validate_skill.py` + `scripts/verify.mjs` reject a
  malformed `expect` block and any eval carrying a `default`/`core` marker
  without one; `scripts/check_typed_evals.py --base HEAD` rejects a NEW or
  CHANGED eval without one.
- **Layer 3 (CI)**: `ci.yml` quality-gates runs
  `scripts/check_typed_evals.py --base <PR base / pre-push commit>`; the
  checkout fetches full history so the base ref resolves.
- **Migrate on touch**: any eval that fails, is touched, or is selected as a
  canary migrates to a typed `expect` block in the same change. Un-migrated
  evals are telemetered in `coverage-gaps.legacy_assertion_evals` /
  `legacy_assertion_count` (additive to the required arrays).

## Bypass semantics

| Layer | Bypass | Residual risk |
|---|---|---|
| 1 Pre-commit | `git commit --no-verify` | Caught by Layer 3 on the PR |
| 2 Pre-push | simply not run (opt-in) | Caught by Layer 3 on the PR |
| 3 PR check | branch protection required check; cannot be bypassed | none on the merge path |

## Layer 2 advisory command

Local, single-skill, **must not** touch quarantine state:

```bash
python3 skills/authoring-skills/scripts/run_behavioral_eval.py \
  --skill <changed-skill> \
  --model opencode/nemotron-3-ultra-free \
  --logs-dir .local-eval-logs \
  --no-quarantine
```

Output is **courtesy-feedback-not-evidence**: it never blocks a push and never
writes `logs/quarantine.json` (quarantine is CI-owned).

## Rollback

If the per-change workflow destabilizes:

1. Reduce `.github/workflows/eval-per-change.yml` to `workflow_dispatch` only
   (remove the `pull_request` and `push` triggers).
2. Revert the retry/quarantine changes in `run_behavioral_eval.py`.
3. The weekly `eval-behavioral.yml` remains the sole gate.
