---
slug: pr-14-council-review
title: Handoff — free-council review of PR #14 (rm-001/rm-002 OQ closure)
status: handoff
created: 2026-09-13
related: [rm-001, rm-002, "PR #14"]
---

# Handoff: free-council review of PR #14

Purpose: give a cold session everything needed to act on the free council's
review of PR #14 without re-deriving it. Read `.opencode/plans/rm-001.md` and
`rm-002.md` for the underlying OQs. This file is local-only (`.opencode/` is
git-ignored).

## What was reviewed

- **PR #14** — "chore: rm-001/rm-002 OQ closure" — https://github.com/hierovision/ai-framework/pull/14
- Branch `chore/rm-001-002-closure` → base `main`; 13 files, +206/−52; state OPEN.
- Claims: closes all 13 OQs across rm-001/rm-002; verification green
  (validate_skill, test_log, test_query, test_prune, test_runner).
- Change scope: JSONL null semantics (missing tokens/duration → null, never 0),
  fictional `hooks.opencode.json` superseded by a TypeScript plugin shape
  (`observe.plugin.js`) plus a `$comment`, eval runner switched from the
  invented `opencode run --skill` flag to `--dir`, new `skills-library` stack
  reference, and `deferred: true` on all evals in two suites.

Reproduce:

```bash
git fetch origin chore/rm-001-002-closure
git checkout chore/rm-001-002-closure
```

Changed files: `skills/authoring-skills/scripts/run_behavioral_eval.py`,
`skills/implementing-features/SKILL.md`,
`skills/implementing-features/references/stacks/skills-library.md` (new),
`skills/observing-runs/SKILL.md`,
`skills/observing-runs/references/hooks.opencode.json`,
`skills/observing-runs/references/observe.plugin.js` (new),
`skills/observing-runs/references/schema.md`,
`skills/observing-runs/scripts/log_run.py`, `query_runs.py`, `test_log.py`,
`test_query.py`, `skills/optimizing-model-routing/evals/evals.json`,
`skills/validating-against-official-docs/evals/evals.json`.

## Chairman verification (already run, green)

Run on the PR branch:

```bash
python3 -m py_compile skills/observing-runs/scripts/log_run.py \
  skills/observing-runs/scripts/query_runs.py \
  skills/authoring-skills/scripts/run_behavioral_eval.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 skills/observing-runs/scripts/test_log.py
python3 skills/observing-runs/scripts/test_query.py
python3 skills/observing-runs/scripts/test_prune.py
python3 skills/authoring-skills/scripts/test_runner.py
```

All exit 0. The PR's verification claim is credible. The council members could
not run these (bash denied); the chairman did.

## Council findings

Panels: security=mimo-v2.5-free, performance=nemotron-3-ultra-free,
ux=mimo-v2.5-free, product=nemotron-3-ultra-free, architecture=muse-spark.
**Architecture lens returned empty three times — unavailable, no findings
fabricated.** Re-run it on a different model if that lens is needed.

### Convergent (flagged by multiple lenses)

1. **`observe.plugin.js` is the weakest artifact.** It hardcodes
   `outcome:"success"`, swallows all errors in a bare `catch {}`, fires on
   every `session.idle` with no dedup/debounce, and emits a record with no
   `skill`/`model`/tokens/duration — it logs nothing analytically usable and
   can silently report failure as success. Flagged by security, performance,
   and ux independently. (Since hook emission is documented as aspirational
   and is not the default, this is currently dead code — severity is
   conditional on someone enabling it.)
2. **Claims vs evidence.** The new "<2% AND <200 tokens/run" overhead gate
   (`skill/observing-runs/SKILL.md`, `references/schema.md`) is asserted as a
   hard bound with no measurement path in the diff. Hook-based zero-token ROI
   is not delivered — explicitly aspirational.
3. **Null semantics are consistently propagated** across schema, `log_run.py`
   defaults, `query_runs.py` known-only aggregation, and tests (`gamma`
   fixture). Clean — no action.

### Single-lens

- **Security:** env forwarded wholesale to the `opencode` subprocess in
  `run_behavioral_eval.py` (no stdout guard for the model credential;
  trusted-subprocess reliance). Retention window keyed on `mtime`, not
  creation time (`query_runs.py` prune). `ensure_ascii=False` with validation
  only on `detail` length. Append-only/no-readback tests assert source strings,
  not runtime behavior (`test_log.py`).
- **Performance:** eval runner creates a temp dir, copies files, and spawns a
  cold `opencode` per eval (~63/night, no reuse). `aggregate` full-scans every
  daily file on every query. Plugin can spawn `python3` on every idle event.
- **UX:** `hooks.opencode.json` keeps a config-shaped filename for prose
  `$comment`; plugin reads as runnable rather than aspirational; `--list` hides
  deferred evals by default. The `skills-library.md` stack reference was called
  the strongest addition in the PR.
- **Product:** backward-compat — old records with literal `0` are treated as
  known by the new aggregator, skewing cost/latency until they age out (30-day
  retention); no migration/version/reader-side coercion. All 6 evals across two
  suites are deferred, so default CI coverage drops to zero for them. The
  "13 OQs closed" claim lacks a question→change traceability map.

## Risk register

| Risk | Severity |
|---|---|
| Plugin mistaken for a working default → silently wrong/missing telemetry, unbounded writes | Medium |
| Default CI coverage for two eval suites drops to zero | Medium |
| Old `0`-valued records skew aggregates (bounded by 30-day retention) | Medium |
| Overhead gate asserted, not measured | Medium |
| Credential forwarding (trusted subprocess), unicode injection, static-source tests, mtime retention, filename confusion | Low |

## Recommended fixes (four small changes)

1. **Self-qualify `observe.plugin.js`** — file-level comment (and/or rename to
   `observe.plugin.EXAMPLE.js`) stating: aspirational stub; convention-based
   `log_run.py --record` is the default; the plugin does not measure
   tokens/duration. Prevents it reading as production code.
2. **Mark the overhead gate's status** in `skills/observing-runs/SKILL.md` and
   `references/schema.md` — "provisional, measured on the RM-002 baseline" or
   "unverified" — rather than stating it as an established hard bound.
3. **Decide the `0 → null` backward-compat question** — either reader-side
   coercion in `query_runs.py` (treat legacy `0` as unknown) or an explicit
   note that pre-change records age out within the 30-day retention window.
4. **Surface deferred coverage where a runner user sees it** — the
   `--list` output or suite README should state that deferred evals are
   excluded by default, not only the SKILL.md prose.

Optional follow-ups (not blocking): plugin dedup/debounce, incremental
aggregation instead of full scan, per-eval session reuse in the runner, and a
question→change map for the "13 OQs closed" claim.

## Suggested next-session entry point

1. `git checkout chore/rm-001-002-closure` (or the PR's current head).
2. Apply fixes 1–4 above; keep them minimal and scoped to this PR.
3. Re-run the verification block from the "Chairman verification" section.
4. Commit to the PR branch (do not rewrite history) and push.
5. Re-run the architecture council lens (it failed here) to close the gap.

Notes: the council ran on free models (read-only: edit/bash/write denied). The
working tree was returned to `chore/gitignore-skill-playwright` after the
review; the review did not modify PR #14.

## Alignment check — roadmap / maturity / volatility layers (2026-09-13)

Appended after the review. The council findings above stand as the record; this
section checks the **recommended fixes** against `docs/ROADMAP.md`,
`docs/maturity-plan.md`, and `docs/CONCEPTS.md` Choice 6 (layer by rate of
change). Verdict: the risk findings are aligned; fixes 2 and 3 are not
layer-correct, fix 1 is incomplete, and the closure claim needs plan-contract
reconciliation before it is honest.

### Recommendation → framework mapping

| Rec | Roadmap / maturity anchor | Layer | Verdict |
|---|---|---|---|
| 1 self-qualify plugin | RM-001; Choice 1; maturity §8 | L3 reference | Partial — misses fabricated `outcome` |
| 2 overhead gate status | RM-001 AC6; RM-002 baseline; §8 | L4 fact in L1/L2 files | Misaligned |
| 3 `0->null` back-compat | RM-001 AC3; Choice 4 | L1 contract | Partial — needs owner + test |
| 4 deferred coverage | RM-002 AC4/AC8; RM-003; §7 | L2 | Aligned, under-resolved |
| optional perf follow-ups | maturity §8 | L2 | Premature — needs triggers |

### Findings

1. **Overhead gate is a volatile measured fact in slow files (high).**
   `skills/observing-runs/SKILL.md` and `references/schema.md` state
   `<2% AND <200 tokens/run` as a hard bound. Choice 6: "fast-changing content
   is never copied into slow-changing files — the slow files only point to it."
   The number depends on model/harness/token counts and has no recorded
   measurement in the diff. Maturity §8 calls this the "L4-on-paper" trap. Fix 2
   labels it provisional but leaves the number in `SKILL.md` (L2) and
   `schema.md` (L1).
2. **Plan body contradicts the closed null semantics (high).** `rm-001.md`
   lines 155–157 still list `tokens_in (int, default 0)`, `tokens_out (int,
   default 0)`, `duration_ms (int, default 0)`. The OQ2 closure, `schema.md`,
   `log_run.py`, and tests all say default `null`, never `0`. The same plan's
   Approach says `<1%` (line 32) while OQ5 says `<2%`. `plan-format.md` requires
   superseded content to be struck inline, not left contradicting. Convergent
   finding 3 checked schema/code/tests and reported "clean" — true at those
   layers, false at the plan contract the audit trail reads. This weakens the
   "13 OQs closed" claim.
3. **OpenCode CLI/plugin facts are duplicated across four slow files (high).**
   The "no `run --skill`" / "no `hooks` key, hooks are TS plugins" fact appears
   in `skills-library.md` (L3), `schema.md` (L1), `SKILL.md` (L2), and
   `hooks.opencode.json` `$comment`. Each is dated 2026-09-06, but a volatile
   vendor-API fact is supposed to have one home with pointers. The
   `skills-library.md` editing conventions are legitimate L3; the copied API
   claim is drift risk.
4. **Plugin fix misses the schema-honesty violation (medium).**
   `observe.plugin.js` hardcodes `"outcome":"success"` and swallows all errors.
   RM-001 OQ2 closed as "never fabricated"; `outcome` is required and Choice 1
   closes only on objective signals. Fix 1 self-qualifies the file but does not
   state that the plugin emits a fabricated outcome. Also reconcile `SKILL.md`
   "preferred" (hook emission) vs "remains the default" (convention).
5. **Deferred coverage is an RM-002 acceptance concern (medium).** Fix 4
   (surface in `--list`/README) is necessary but should also register the
   coverage gap against RM-003 ("coverage: which skills have eval records vs
   gaps"), not leave it as prose. Maturity §7 "eval suite blocks regressions" is
   partly unmet for the two deferred suites.
6. **No roadmap reconciliation (medium).** `ROADMAP.md` lines 25–26 still list
   RM-001/RM-002 as `next` though implementation landed 2026-08-30 and PR #14 is
   the closure. The next-session entry does not say to update ROADMAP status or
   tick the maturity-plan §7 exit criteria. RM-002 AC5 (live-dispatch regression)
   is manual, so RM-002 likely stays open; RM-001 can move to `done` on merge.
7. **Optional follow-ups harden aspirational/scale-absent paths (low).** Plugin
   dedup hardens code this doc calls dead; incremental aggregation and per-eval
   session reuse optimize a few-hundred-lines/day, weekly-cadence path. Keep
   them, each gated on a named trigger, per §8.

### Revised recommendation set

1. Fix 1 — add: the plugin also **fabricates `outcome:"success"`**; it is not
   schema-honest and must not be enabled as-is. Reconcile "preferred" vs
   "default".
2. Fix 2 — keep the qualitative guardrail in `SKILL.md`; move the numeric
   threshold + measurement method/date to the dated outer layer or the RM-002
   baseline artifact and reference it; mark `unverified` until measured.
3. Fix 3 — prefer reader-side legacy coercion in `query_runs.py` + a dated
   compatibility note in `schema.md` (the owner) + a test. Treat it as a Layer-1
   contract change and record it in `rm-001.md` History.
4. Fix 4 — keep `--list`/README visibility; add the RM-003 coverage-gap
   registration.
5. New — reconcile `rm-001.md`: strike `default 0` in Schema/Type Impacts
   (superseded 2026-09-06 → `null`) and align `<1%` vs `<2%`. Required for the
   closure claim.
6. New — single dated home for the OpenCode CLI/plugin facts; the other three
   files link to it.
7. New — after merge, update `ROADMAP.md` status and `maturity-plan.md` §7
   checkboxes; note RM-002 AC5 as the remaining manual gate.
8. Optional follow-ups — keep, each with a trigger; drop plugin dedup until the
   plugin is adopted.

### Doc conventions

- `status: handoff` is not in `plan-format.md`'s enum
  (`draft | approved | superseded`), and the slug mismatches the filename. As a
  git-ignored session artifact the home is correct (Choice 6 L4: decision
  trail); it should not present as a plan.
- The inline free-model IDs are an acceptable dated record of which lens ran on
  which model; the single-home rule binds `reference/model-routing.md`, not a
  dated handoff. No change.
- "Question→change map" is largely already satisfied: `rm-001.md`/`rm-002.md`
  each carry a "Closure decisions (2026-09-06)" block mapping every OQ to
  decision + status + file. Point at it rather than listing the map as missing.

Revised next-session entry: items 1–4 of the original section, plus fixes 5–7
above; re-run the chairman verification block, then the architecture council
lens.

## Implementation log (2026-09-13)

Applied the revised recommendation set on `chore/rm-001-002-closure`, synced
with main `f456e8b` (#16 + #17). Fix 7 (roadmap/maturity) is included and
takes effect on merge.

1. `observe.plugin.js` → `observe.plugin.EXAMPLE.js`; header states it
   fabricates `outcome:"success"`, is not schema-honest, and must not be
   enabled as-is. SKILL.md "preferred" → "aspirational, not the default".
2. Overhead number moved to new `reference/run-log-overhead.md`, marked
   `unverified`; SKILL.md / schema.md point to it.
3. Legacy `0` → unknown coercion in `query_runs.py` (`_as_known_int`); dated
   note in `schema.md`; `test_query.py` `delta` fixture (red → green).
4. `--list` surfaces deferred and CI-excluded counts (`run_behavioral_eval.py`;
   `test_runner.py` updated red → green); RM-003 acceptance registers the
   coverage gap.
5. `rm-001.md` plan body reconciled (`default 0` struck; `<1%` → `<2%`).
6. New `reference/opencode-integration.md` is the single dated home for the
   opencode CLI/plugin facts; SKILL.md, schema.md, hooks.opencode.json, and
   skills-library.md now point to it.
7. `ROADMAP.md` RM-001 → done, RM-002 → in-progress (AC5 manual); maturity
   plan §7 Observability criterion ticked.

Verification: `validate_skill.py --all`, `test_log.py`, `test_query.py`,
`test_prune.py`, `test_runner.py`, `py_compile` — all exit 0.

### Architecture lens (re-run 2026-09-14)

The seat failed in the original review because the running opencode process
had cached the pre-#17 binding `muse-spark-1.2-contributor-free` (disabled at
the gateway → `AI_APICallError: Model is disabled` → empty Task output). The
agent file on disk was already correct (`muse-spark-1.3-contributor-free`); the
process needed a restart to reload `agents/*.md`. After the restart the lens
ran and returned findings:

- Choice 6 honored: the volatile overhead budget and opencode facts now live
  in `reference/`; the slow files point rather than copy.
- Residual found and fixed: `schema.md` "Emission" still called hook-based
  emission "preferred" — reconciled to "aspirational, not the default".
- Residual found and fixed: `_as_known_int` had no sunset; added a removal
  date (~2026-10-06, when legacy `0` records age out of the 30-day window).
- Follow-up (not blocking): cross-skill relative links into `reference/`
  resolve in both the repo and the symlinked global install, but are
  depth-fragile and `validate_skill.py` does not check link targets — consider
  a link-existence check in verification.

Verification after the two fixes: same block, all exit 0.
