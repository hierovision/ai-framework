# Three-layer eval gating (RM-003)

RM-003 shifts eval-based regression detection left from a weekly-only cadence
to a three-layer model: fast local hermetic checks, optional local advisory
feedback, and an un-bypassable per-change required check.

## Contents

- Topology
- Rationale
- Changed-files mapping classes
- Bypass semantics
- Layer 2 advisory command
- Rollback

## Topology

| Layer | Trigger | Scope | Runtime | Enforcement | Purpose |
|---|---|---|---|---|---|
| 1. Pre-commit | `git commit` (installed hook) | Hermetic validators: `validate_skill.py --all` + `scripts/verify.mjs` | ~14s | Advisory (bypassable with `--no-verify`) | Catch malformed skills/manifests before commit; 0 CI minutes |
| 2. Advisory pre-push | `git push` (optional, opt-in) | Single-skill behavioral eval for the changed skill | ~30-60s | Never blocks; labeled "courtesy-feedback-not-evidence" | Fast local feedback; quarantine state stays CI-owned |
| 3. Per-change PR check | `pull_request` / `push` to `main` | Changed skills' evals via the mapping table | <= 20 min | Required check, un-bypassable | Regression detection per change |

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
  `agents/*.md`: run the owning skill's evals.
- **smoke** — `.github/workflows/**`, `scripts/**`, and any unmatched path:
  no owning behavioral eval, so run the bounded smoke subset.
- **non_evaluable** — `docs/**`, `reference/**` (except `model-routing.md`),
  `.opencode/**`, top-level `README.md`/`LICENSE`/`.gitignore`, and `*.md`
  outside `skills/**` and `docs/**`: no behavioral surface, run 0 evals.

See the mapping table in `scripts/changed-files-to-skills.py`.

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
