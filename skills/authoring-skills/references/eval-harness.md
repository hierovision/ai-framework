# Eval harness contract — fixtures, matcher, lanes, quarantine

The contract the fresh-agent eval runner (`scripts/run_behavioral_eval.py`)
enforces on every skill's `evals/evals.json`. Schema and event-stream envelope
live in `references/eval-assertions.md`.

## (a) Fixture materialization & prompts

The runner copies each eval's `files[]` into a fresh temp workdir (the
`beval-*` prefix). Files land at their **source-layout paths** —
`evals/fixtures/lean-roadmap/foo.md` materializes under
`<workdir>/<skill>/evals/fixtures/lean-roadmap/foo.md`, mirroring the
repo. The workdir root is the repo root for the run. Prompts must
reference **materialized paths**: name the workdir root and the
materialized skill location explicitly. The `observing-runs` eval-1
precedent (`skills/observing-runs/evals/evals.json:8`) reads *"the
working dir has the skill at `skills/observing-runs/`"*. **The artifact
destination belongs to the prompt** — the matcher resolves
`expect.artifact[].path` under the run workdir root. Treat the
materialized fixture tree as INPUT-only (read, do not write). The
naive form *"the repo is at `fixtures/lean-roadmap/`"* without naming
the materialized skill location costs two full local rounds and the
CI lane correction (friction-log items 2 + 3, friction-log
2026-10-09).

## (b) The artifact matcher

`assert_artifact` (`run_behavioral_eval.py:412-452`) has **two
surfaces**, either satisfying one `expect.artifact` entry: (1) the
workdir filesystem via `glob.glob(target, recursive=True)` reading
each match and checking every phrase in `phrases[]` (whitespace-
normalized, case-insensitive); (2) `write`/`edit` tool events matched
via `fnmatch.fnmatchcase` on the `filePath` (`**/name` collapses to
`*`). Surface 1 is alive on the initial turn; surface 2 is the live
channel after the `finally`-cleanup at line ~742. A miss surfaces as
one of two distinct shapes (AC3, D2): when at least one file matched
the glob but none contained every phrase, the message reports
`artifact phrases missing: [...] (file matched: <path>)` — artifact
found, content missed vocabulary. When no file matched, the message
keeps `no file matching '<glob>'`. **Until D2's split lands, both
shapes funnel through the single legacy string** at
`run_behavioral_eval.py:451` — `artifact: no file matching <glob>
containing all phrases <phrases>` — so the wording alone mis-diagnoses
the predicate; check the actual file under the workdir before trusting
the message. `expect.artifact[]` count thresholds are **intent only**
(no `count` class — RM-003 pass 5). Per-eval `timeout` (default 240s,
env `BEVAL_TIMEOUT_SECONDS`) is the stall budget; `deferred: true`
excludes from default runs (re-include with `--include-deferred`).

## (c) Lane & tier precedence

Both eval workflows PIN the runner to a model via `--model`:
`.github/workflows/eval-behavioral.yml:163` (scheduled, weekly,
sharded) and `.github/workflows/eval-per-change.yml:283,286`
(per-change matrix, `core` + `default` modes). **Precedence: `--model`
WINS over a manifest's `default_model_tier`** — loader fallback
(`run_behavioral_eval.py:99`: `tier = data.get("default_model_tier",
"free")`); resolution at `:592` (`model or e["model_tier"]`) selects
the flag when present. Under a pinned CI lane, the marker is **inert**
— it only steers a manifest-only local invocation. The `--ci` flag
(auto-enabled by `CI=true` in the GitHub Actions env or
`AI_FRAMEWORK_FREE_TIER=1`) gates `assert_ci_free_model`
(`run_behavioral_eval.py:812`), which accepts three prefixes:
`*-free` (the $0 opencode tier), `opencode-go/*` (the Go flat-rate
tier), and `deepseek/*` (the legacy direct-key lane). Zen pay-as-you-go
(`opencode/*`, non-free) is never allowed in CI.

**Five-sibling manifest audit** (marker = tier-intent tag, not
steering; no manifest edits per plan scope). All five carry
`default_model_tier: "free"` at evals.json line 3: `auditing-supply-
chain`, `modeling-threats`, `handling-security-incidents` are silent
on tier intent; `reviewing-security`'s authoring round ran on the
legacy direct-key lane (marker is advisory, real lane was paid);
`sourcing-external-skills` notes `model-tier variation deferred,
harness pins one tier` (marker is a soft default, harness lanes
dominate).
## (d) Quarantine & selection diagnostics

An eval that fails **3 consecutive runs** moves to
`status=quarantined` in `logs/quarantine.json` (RM-003 AC9;
`scripts/quarantine.py:42`, threshold = 3). A success resets the
counter on a watching entry; a quarantined entry needs `rehab_runs`
(default 3) consecutive passes to rehabilitate. The list is CI-owned;
local Layer-2 advisory runs must pass `--no-quarantine` so they never
write to it. **Mid-iteration hazard**: after three consecutive
failures across development rounds, every default eval auto-quarantines
and the next launch is a silent no-op (exit 0, stdout `no evals
selected`). The authoring loop — where consecutive failures are
EXPECTED until the body converges — is the one workflow guaranteed to
trip this. Friction-log item-4b (2026-10-09, D8 launch, all four
default evals quarantined) is the worked example. Two honest paths
back: **`--include-quarantine`** re-includes deliberately re-tested
evals (`eval_pass` reflects the retry, not the quarantine state);
**per-skill manual reset** removes the skill's entries from
`logs/quarantine.json` (or `python3 scripts/quarantine.py clear
<skill>#<eval_id>`). A `--reset-quarantine` flag is documented as a
path, not implemented. D2's diagnostics message (AC4) prints per-skill
counts with the gate that excluded them and the flag that re-includes;
until D2 lands, the runner prints only the bare `no evals selected`
at line ~1308.
