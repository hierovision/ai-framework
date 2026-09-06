# Stack: skills-library (implementation-time concerns)

Read this when Step 3 detects the project is this skills/agents
Python+Node library itself (repo-root `skills/*/SKILL.md`,
`scripts/*.py` helpers, `evals/evals.json`, no app framework, no DB).
This file is implementation-time — the editing conventions you apply
when changing code under an approved plan.

If the project declares a different stack, do not read this file.

## Contents

- Python helper discipline
- JSONL schema discipline
- Verification commands
- Where this stack trips an implement pass

## Python helper discipline

- Every `scripts/*.py` with a run-as-main gate resolves its own path
  via `os.path.realpath(sys.argv[0])` so a symlinked install
  (`~/.config/opencode/skills/<name>` → repo) still resolves. Test the
  gate via a symlink, not just a direct invocation.
- Syntax-check Python with `python3 -m py_compile`, never `bash -n`
  (`bash -n` cannot parse Python; two plans recorded this deviation).
- Scripts are executed, not just read: run each bundled script and its
  test directly during verification.

## JSONL schema discipline

- The schema owner is the single source of truth
  (`../observing-runs/references/schema.md` for run logs). Import the
  owner module (`log_run`); never redefine field names in a reader.
- Missing != zero: unknown `tokens_in/out` and `duration_ms` are
  `None`, never fabricated as 0. Aggregations sum known components
  only and divide by known-count (None when none known).
- File-based only: no external service or DB. Run telemetry under
  `logs/` stays git-ignored; raw lines prune, aggregates persist.

## Verification commands

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
  (library rule; every touched skill must pass).
- Per-script tests (`test_log.py`, `test_query.py`, `test_prune.py`,
  `test_runner.py`) exit 0; `python3 -m py_compile` on touched scripts.
- Structural workflow checks parse YAML with `d.get(True)` for the
  `on:` key (YAML 1.1 parses `on` as boolean True, not the string).

## Where this stack trips an implement pass

- **Hand-rolling a second schema** instead of importing the owner.
  Duplicated field names drift; the plan's Schema section names the
  owner — import it.
- **`bash -n` on a `.py` file to get verification green.** It checks
  nothing; use `py_compile`.
- **Inventing `--skill` for `opencode run`.** The CLI has no such flag
  (see https://opencode.ai/docs/cli/#run-1); use `--dir` + installed
  skills, and cite the doc.
- **Inventing a `hooks` JSON key.** Hooks are TypeScript plugins (see
  https://opencode.ai/docs/plugins/); the JSON snippet shape is not
  real. Ship the plugin file, not the imagined key.
