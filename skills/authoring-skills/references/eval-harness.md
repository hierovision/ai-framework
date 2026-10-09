# Eval harness contract — fixtures, matcher, lanes, quarantine

The contract the fresh-agent eval runner (`scripts/run_behavioral_eval.py`)
enforces on every skill's `evals/evals.json`. Schema and event-stream envelope
live in `references/eval-assertions.md`.

## (a) Fixture materialization & prompts

The runner copies each eval's `files[]` into a fresh temp workdir (the
`beval-*` prefix) at their **source-layout paths** — an
`evals/fixtures/<name>/foo.md` fixture materializes under
`<workdir>/<skill>/evals/fixtures/<name>/foo.md` (workdir root = repo
root). Prompts must name both the workdir root and the materialized skill
location explicitly: the `observing-runs` eval-1 precedent
(`skills/observing-runs/evals/evals.json:8`) reads *"the working dir has
the skill at `skills/observing-runs/`"*. **The artifact destination
belongs to the prompt** (the matcher resolves `expect.artifact[].path`
under the workdir root); treat the fixture tree as INPUT-only. A prompt
naming only `fixtures/lean-roadmap/` costs two local rounds.

## (b) The artifact matcher

`assert_artifact` (`run_behavioral_eval.py:418-483`) has **two surfaces**,
either satisfying one `expect.artifact` entry: (1) the workdir filesystem
via `glob.glob(target, recursive=True)` reading each match and checking
every phrase in `phrases[]` (whitespace-normalized, case-insensitive);
(2) `write`/`edit` tool events matched via `fnmatch.fnmatchcase` on the
`filePath` (`**/name` collapses to `*`). Surface 1 is alive on the initial
turn; surface 2 is the live channel after the `finally`-cleanup at line
~742. A miss surfaces as one of two shapes (AC3, D2): when a file matched
the glob but none contained every phrase, the message reports `artifact
phrases missing: [...] (file matched: <path>)` — artifact found, content
missed vocabulary. When no file matched, the legacy lump at
`run_behavioral_eval.py:480-482` keeps `no file matching '<glob>'`.
`expect.artifact[]` count thresholds are **intent only** (no `count`
class — RM-003 pass 5). Per-eval `timeout` (default 240s, env
`BEVAL_TIMEOUT_SECONDS`) is the stall budget; `deferred: true` excludes
from default runs (re-include with `--include-deferred`).

## (c) Lane & tier precedence

Both eval workflows PIN the runner via `--model`:
`.github/workflows/eval-behavioral.yml:163` (scheduled, weekly, sharded)
and `.github/workflows/eval-per-change.yml:283,286` (per-change matrix,
`core` + `default`). Scheduled-CI lane as of 2026-10-09: both pin
`--model opencode-go/deepseek-v4.1-flash` (go-first flat-rate policy);
re-verify against the workflow files when touching this contract.
**Precedence: `--model` WINS over a manifest's `default_model_tier`** —
loader fallback (`run_behavioral_eval.py:99`: `tier =
data.get("default_model_tier", "free")`); resolution at
`:622/:674/:708/:749` (`model or e["model_tier"]`) selects the flag when
present. Under a pinned CI lane the marker is **inert** — it only steers a
manifest-only local invocation.

The **tier-conflict warning** (a declared manifest tier disagreeing with
`--model`) fires only OUTSIDE `--ci` mode (`run_behavioral_eval.py:1266`
returns empty under `ci_mode` or no flag) and only for a tier actually
DECLARED (per-eval or top-level `default_model_tier`; the loader's `"free"`
fallback at `:99` is not a declaration, `:115-116`).

The `--ci` flag (auto-enabled by `CI=true` or `AI_FRAMEWORK_FREE_TIER=1`)
gates `assert_ci_free_model` (`run_behavioral_eval.py:842`), which accepts
three prefixes: `*-free` (the $0 opencode tier), `opencode-go/*` (the Go
flat-rate tier), and `deepseek/*` (the legacy direct-key lane). Zen
pay-as-you-go (`opencode/*`, non-free) is never allowed in CI.

**Five-sibling manifest audit** (marker = tier-intent tag, not steering;
no manifest edits per plan scope). All five carry `default_model_tier:
"free"` at evals.json line 3: `auditing-supply-chain`, `modeling-threats`,
`handling-security-incidents` are silent on tier intent;
`reviewing-security`'s authoring round ran on the legacy direct-key lane
(marker is advisory, real lane was paid); `sourcing-external-skills` notes
`model-tier variation deferred, harness pins one tier` (marker is a soft
default, harness lanes dominate).

## (d) Quarantine & selection diagnostics

An eval that fails **3 consecutive runs** moves to `status=quarantined` in
`logs/quarantine.json` (RM-003 AC9; `scripts/quarantine.py:42`, threshold =
3). A success resets the counter on a watching entry; a quarantined entry
needs `rehab_runs` (default 3) consecutive passes to rehabilitate. The list
is CI-owned; local Layer-2 advisory runs must pass `--no-quarantine` so
they never write to it. **Mid-iteration hazard**: after three consecutive
failures across rounds, every default eval auto-quarantines and the next
launch is a silent no-op (exit 0, stdout `no evals selected`). The
authoring loop — failures EXPECTED until the body converges — is the one
workflow guaranteed to trip this. Friction-log item-4b (2026-10-09, D8
launch, all four default evals quarantined) is the worked example. Two
honest paths back: **`--include-quarantine`** re-includes deliberately
re-tested evals (`eval_pass` reflects the retry,
not the quarantine state); **per-skill manual reset** removes the skill's
entries from `logs/quarantine.json` (or `python3 scripts/quarantine.py
clear <skill>#<eval_id>`). A `--reset-quarantine` flag is documented as a
path, not implemented. The shipped diagnostics
(`run_behavioral_eval.py:1443-1453`, AC4/D2) print per-skill counts with
the gate that excluded them and the flag that re-includes —
`no evals selected for <skill>: N quarantined (re-include with
--include-quarantine), ...`; the bare message is only the fallback when no
gate accounts for the empty selection (`:1454`).
