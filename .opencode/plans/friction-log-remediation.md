---
slug: friction-log-remediation
title: Ingest and address the fpv friction log — lane contract, harness contract, quarantine UX, runner fixes
status: approved
created: 2026-10-09
related: []
---

# Plan: friction-log-remediation

## Goal / Approach

Every open friction from the `facilitating-product-vision` development pass
(`.scratch/fpv-impl/friction-log.md`) is either fixed in this repo or
rejected with a recorded reason — nothing stays silently open. The items
are documentation-contract defects (the eval lane truth, the
fixture-materialization/matcher contract), three small runner UX/behaviour
fixes, one persona-fit doctrine line, and two accepted observations. The
runner changes carry red-first hermetic tests; the doc changes carry grep
verifiers; the whole pass rides the offline gate. Commissioned by the user
(2026-10-09: "delegate the work to ingest and address the friction log in
this repo" — approval carried by this directive; the merge of the pass PR
remains user-gated).

## Ingest dispositions (RM-027 convention: valid → fixed/row; rest → reason)

| # | Friction | Disposition |
|---|---|---|
| 1 | session-guard child lifecycle | already fixed (RM-047/048; PR #105) |
| 2 | `default_model_tier` marker-doc staleness + local/CI lane divergence | FIX (docs + runner warning + precedence doc) |
| 3 | eval prompt ↔ fixture materialization ↔ matcher contract | FIX (documented contract reference; runner message split; eval-side already fixed in the skill) |
| 4 | pre-commit hook vs evals-first staging | FIX (authoring guidance: batch-to-green preferred; dated bypass allowed with record) |
| 4b | quarantine silently disables mid-iteration re-runs | FIX (authoring guidance + 0-selection diagnostics) |
| 4c | failed run-vehicle dispatch (persona-map fit; `--contract` omission) | FIX (agent-teams doctrine line; RM-044 items stay tracked) |
| 5 | runner stdout block-buffering | FIX (flush helper) |
| 6 | supervision ceremony overhead | REJECT (accepted supervision cost — no instruction would remove it; recorded here) |
| 7 | shared working tree across dispatches | REJECT (operational pattern, documented in briefs — recorded here) |

## Acceptance Criteria

1. **Lane truth restored (F2).** `skills/authoring-skills/SKILL.md`'s
   marker prose + the runner's header no longer claim CI is free-tier-only;
   they state the actual two-workflow pin
   (`opencode-go/deepseek-v4.1-flash` — `eval-behavioral.yml` /
   `eval-per-change.yml`), the precedence (`--model` beats the manifest
   marker; the marker is a manifest-local tier intent carried by five
   sibling skills). The runner prints a WARNING when both a manifest
   `default_model_tier` and an explicit `--model` are present and they
   disagree, naming both and stating the flag wins. — Verifier: new
   red-first hermetic case (marker+flag → warning present, selection
   proceeds on the flag); `rg -n "free.*tier" skills/authoring-skills/SKILL.md`
   shows the corrected statement, not the stale claim.
2. **Harness contract documented (F3).** New
   `skills/authoring-skills/references/eval-harness.md` (<100 lines, no TOC
   required) with four sections: (a) fixture materialization
   (source-layout destinations — prompts reference the materialized paths;
   artifacts are written at workdir-root-referenced paths; the
   `observing-runs` eval-1 precedent is the convention); (b) the artifact
   matcher's two surfaces and that a miss may mean file-not-found OR
   file-found-but-phrases-missing; (c) the lane/marker truth per AC1;
   (d) quarantine during iterate rounds (`--include-quarantine` meaning) +
   the 0-selection diagnostics. Cited from SKILL.md's eval sections.
   Eval-side item-3 fix is already delivered in the skill (D7/D9).
   — Verifier: file exists; `rg -n "eval-harness.md"
   skills/authoring-skills/SKILL.md` ≥ 1; `validate_skill.py --all` green.
3. **Matcher message split (F3e).** An artifact miss whose path matched at
   least one file but whose phrases missed reports `artifact phrases
   missing: [...] (file matched: <path>)`; a true no-match keeps the
   existing `no file matching '<glob>'` text. — Verifier: red-first
   hermetic cases for both shapes.
4. **0-selection diagnostics (F4b).** When an eval set selects zero (all
   quarantined / deferred / tier-excluded), the runner prints per-skill
   counts with the gate that excluded them and the flag that re-includes
   (`--include-quarantine` / `--include-deferred`). — Verifier: red-first
   hermetic case (all 4 quarantined → message names the gate + flag).
5. **Flush (F5).** The runner's per-eval status prints go through a
   flushed helper (`print(..., flush=True)`) so detached launches output
   progress immediately. — Verifier: helper unit case asserts the flush
   parameter is passed; existing runner suite stays green.
6. **Authoring guidance (F4/F4b).** SKILL.md's evals-Step 3 gains the
   batching-to-green guidance (commit the skill dir only when the validator
   is green; a dated `--no-verify` record is the honest fallback), and the
   fresh-agent step gains the iterate-round quarantine line. — Verifier:
   grep the two guidance lines.
7. **Persona-fit doctrine (F4c).** `reference/agent-teams.md` gains one
   line: external-repo read+draft briefs don't fit bash-restricted
   personas (multi-arg commands and redirects are denied; heartbeat writes
   fail) — check the target's permission map or use a judgment-led lane;
   dispatched consults carry `--contract`. — Verifier: grep.
8. **Delivery row + records.** ROADMAP row RM-050 (the pass's delivery,
   PR link backfilled at open); the friction log's dispositions are
   marked in-place; the offline gate block stays green. — Verifier:
   `python3 scripts/test_changed_files.py && ...` suite chain + the
   CONTRIBUTING gate commands; `rg -n "RM-050" docs/ROADMAP.md`.

## Files to Modify

- `skills/authoring-skills/SKILL.md` — corrected lane/marker prose (Step 5
  section + the runner-behaviour header reference), batching-to-green
  guidance (Step 3/Step 8 area), iterate-quarantine line (Step 6/7), and
  the `references/eval-harness.md` citations
- `skills/authoring-skills/references/eval-harness.md` — new; the
  documented harness contract (≤4 short sections)
- `scripts/run_behavioral_eval.py` — marker/--model conflict warning;
  artifact-miss message split; 0-selection diagnostics; flushed prints
- `scripts/test_runner.py` (or a focused new suite file) — red-first
  cases per ACs 1, 3, 4, 5
- `reference/agent-teams.md` — the persona-fit doctrine line
- `docs/ROADMAP.md` — RM-050 delivery row (source cell annotated with
  `plan friction-log-remediation (deleted at merge — git history)` per the
  ADR-0008 convention, plan staged on the branch)
- `.opencode/plans/friction-log-remediation.md` — staged on the branch
  (tracked); `.scratch/fpv-impl/friction-log.md` — dispositions marked
  (uncommitted scratch)

## Scope

**Included**

- All documented fixes above; the five sibling manifests carrying
  `default_model_tier: "free"` are AUDITED (the reference records their
  marker as tier-intent) but NOT edited
- Branch `fix/friction-log-remediation` → PR (merge user-gated)

**Excluded**

- Any fixture-materialization behaviour change in the runner (the
  workdir-materializes-at-source-layout shape stays; only the CONTRACT is
  documented — the alternative materialization design is a separate
  decision if it ever becomes a row)
- RM-044's tracked items (heartbeat format, injection conditionality,
  non-contract success classification) — separate rows, unchanged
- The session-guard quarantine reset flag design (`--reset-quarantine`) —
  documented path only (delete the skill's entries from
  `logs/quarantine.json` or `--include-quarantine`)
- Any consumer-repo changes (not required: no shadows exist; visibility is
  machine-global)

## Schema / Type Impacts

None.

## Verification

- `python3 scripts/test_runner.py` (and whatever suite file carries the
  new cases) — new cases red-first, then green
- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/check_typed_evals.py --base main`
- `python3 scripts/registry.py --check`
- the CONTRIBUTING.md offline gate block (docs-only PR still rides it)
- `./install.sh` + the consumer-set link check (no shadows — machine-global
  visibility re-verified after merge)
- the grep verifiers of ACs 1, 2, 6, 7

## Open Questions

- None with defaults needed — the one design-ish call (F2's marker
  disposition: keep the five siblings' markers as tier-intent, no edits)
  is decided in-line with the audit (their drivers are documented by their
  own notes).

## History

- 2026-10-09 — Commissioned by user directive ("delegate the work to
  ingest and address the friction log in this repo"), sequenced AFTER the
  consumer-set install verification (all four consuming repos resolve the
  skill through the machine-global link; no local shadows; pln excluded
  per directive). Plan written and executed by delegated dispatches on
  `fix/friction-log-remediation`; merge user-gated.
