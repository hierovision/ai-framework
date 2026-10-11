---
slug: rm-052-053-vision-roadmap-schema
title: Vision contract split (RM-052) + roadmap Now/Next/Later schema upgrade (RM-053)
status: draft
created: 2026-10-11
revised: []
related:
  - paragon-consumer ADR-0007 (counterpart, consumer repo)
sources:
  - .scratch/rm-052-053-design/handoff-roadmap-structure.md (paragon handoff 2026-10-09, §A/§B)
  - docs/ROADMAP.md rows RM-052/RM-053 (fired 2026-10-09)
  - verified live 2026-10-11: producttalk.org/product-roadmaps (Torres); atlassian.com/agile/product-management/roadmaps
---

# Plan: rm-052-053-vision-roadmap-schema

## Goal / Approach

One sentence: the vision document carries strategy only (no operational
slice tables) and `ROADMAP.md` becomes the operational backlog under a
Now/Next/Later, confidence-gated item schema — so the two skill
contracts (`facilitating-product-vision`, `triaging-requirements`) stop
duplicating their artifacts and future sessions emit the right shapes.

Strategy (separable halves, executed as two gate-pass-sized commits):

1. **RM-053 (triaging-requirements)** — `references/roadmap-format.md`
   adopts the first-class item-row schema
   `ID | Title | Outcome | Horizon | Category | Impact | Urgency |
   Score | Status | Success measure | Blocked-by | Sources | Notes`,
   the no-AC / confidence-gated-detail rules, and the removal of the
   "ADR-gated extension excluded from v1" language; `SKILL.md`
   schema/section descriptions + merge table follow.
2. **RM-052 (facilitating-product-vision)** —
   `references/artifact-format.md` drops the fixed `## Slices`
   section, makes Outcome Themes strategy-only, moves the
   column-label literals to the roadmap contract, defers (never
   duplicates) the roadmap-row contract to `roadmap-format.md`;
   `SKILL.md` steps 3/5 updated (items only as roadmap rows, ACs NOT
   emitted); `references/consumer-session.md` guidance updated.

The docs/ROADMAP.md migration itself is NOT in scope (see Excluded).
Eval suites for both skills are updated (typed assertions per
ADR-0003, honest-limits discipline kept).

### Design decision D1 — acceptance-contract mapping (the open
design question, resolved here)

This repo's roadmap rows have doubled as verification contracts: the
open-row `Acceptance` cell carries the full evidence bar (RM-021,
RM-045). Under the new schema, open rows carry `Success measure` +
`Notes`, NOT full AC prose. The mapping:

- **What moves to the plan artifact** (authored at plan time by
  `designing-architecture`): the detailed evidence bar — the full
  observable-behavior + verifier criteria, edge cases, and the
  verification commands. This is content the old `Acceptance` cell
  carried beyond one outcome line: dispatched-agent checklists,
  review requirements, driver-by-driver evidence mechanics.
- **What compresses into `Success measure`** (new column, one line,
  testable, outcome-phrased): the *outcome lock* of the old Acceptance
  cell — the first observable outcome a reviewer would check, phrased
  as "what must be true" (e.g. RM-052's would become "no stale
  Slices/column-literal language remains; evals updated and recorded
  honestly"). Not a build-time AC; it is the deferred-success
  boundary the row promises. If a row has no defensible one-line
  outcome, detail does not belong in the row — cite a trigger and let
  the design pass produce the detail.
- **What stays/improves in `Notes`**: trigger, rationale/history,
  volatile-layer verify-mechanics pointers (RM-021's dated pins,
  drift alarms), sizing (per the schema), ambiguity, cross-refs.
- **How Done history keeps old verbatim cells**: Done rows adopt the
  new column set but the old Acceptance prose moves VERBATIM into the
  `Success measure` column (acceptance-as-history — the old cell text
  is the record of what shipped and is never reworded, truncated, or
  back-summarized); the old `Trigger`/extra state content moves
  verbatim into `Notes`. The `no-AC` rule applies to NEW/open rows
  only; Done rows carry the historical acceptance text in the Success
  measure column by definition. Long cells are not an error there.
- **Migration rule that preserves the frozen decision stream**: the
  2026-10-09 restructure's convention (an `(2026-10-09 triage: …)`
  suffix annotation on an Acceptance cell leaves the original text
  ahead of it unchanged) carries over — the migration pass preserves
  the annotation pattern on moved cells verbatim, so triage
  annotations and original text stay separable. Migration note for
  this repo's own roadmap: the open-row rank governance
  (`Rank = trigger-state × Priority × ID`, Swamp guards, "bottom
  of the order is a place, not a demotion") carries over — open
  rows re-cast as
  `Horizon` = Now for all fired/triggered rows (their work is live
  strategy) and the trigger-state ordering survives inside the Now
  horizon — the migration boundary in the Excluded list covers this.

### Design decision D2 — the "no negative assertions" eval gap

The behavioral harness has no negative-assertion class (recorded in
the `facilitating-product-vision` manifest honest-limits note): it
cannot runtime-assert the ABSENCE of a `## Slices` section or the
Slices column-label literals in a produced vision artifact. This plan
does NOT change the harness runner (that is RM-021/RM-016 territory
— out of scope). Instead, honest-limits discipline:

- The RM-052 evals' `expect.artifact.phrases` sets are updated to
  pin the POSITIVE vocabulary of the new shape (Outcome Themes
  table, `### Now/Next/Later` theme subheads, new-roadmap-row field
  names) — a produced artifact still carrying Slices-section content
  would fail the *content-match shape* in the hand-review envelope
  (the reviewer checks the Slices row: "the vision artifact contains
  no operational slice table").
- The manifest `notes` gains a dated honest-limits entry: the
  no-slice-table check is hand-review-enveloped, deferred until
  ADR-0003 gains a negative-assertion class — recorded, never green
  silently.

### Design decision D3 — Outcome Themes keeps the horizon subheads

The handoff §A makes Outcome Themes "strategy-only: theme name +
one-line outcome — no Horizon, no capacity band, no slice lists."
Interpretation (defensible and keeps both contracts coherent): the
theme TABLE loses its Horizon and Capacity-band COLUMNS (those are
roadmap-item fields per RM-053), but the `### Now` / `### Next` /
`### Later` horizon SUBHEADS stay as group-level ordering of the
theme list — the vision doc must still answer "what does the strategy
pursue now vs next vs later" (that is the strategy question, not an
operational field). Theme rows become
`| Theme | Outcome (observable, one line) |`. No capacity band, no
slice lists, no per-theme horizon cell.

### Design decision D4 — `Horizon` in this repo's own roadmap

For this repo (ai-framework), the migration watches the maturity-plan
alignment: `docs/maturity-plan.md` §5 initiative names fill `Outcome`
where an initiative matches, otherwise `—`; `Horizon` = the horizon
of the trigger state (fired/in-progress rows = `Now`; dated/waiting
rows with an in-arm's-reach trigger = `Next`; directional/long-tail
waiting rows = `Later`). Rank within a horizon = Impact × Urgency
(the RM-053 cell's rule), with rank = trigger-state × Impact ×
Urgency × ID: in-progress first, triggered before waiting, then
score descending, then ID ascending. This is stated in the plan body
(cold-executable, per RM-034) because the migration pass executes it.

## Acceptance Criteria

1. `skills/triaging-requirements/references/roadmap-format.md`
   documents the item-row schema as exactly:
   `ID | Title | Outcome | Horizon | Category | Impact | Urgency |
   Score | Status | Success measure | Blocked-by | Sources | Notes`
   with per-column meaning (Outcome = vision-doc theme name, `—`
   when none; Horizon ∈ Now/Next/Later; Status set = proposed/open/
   waiting/in-progress/done/skipped per the 2026-10-09 repo restructure;
   Success measure one line outcome-phrased; Blocked-by first-class;
   sizing in Notes; themes never roadmap rows) — verifiable by
   reading the file; a grep of the file header/table block shows the
   13-column header verbatim.
2. roadmap-format.md carries the no-AC rule (a roadmap item carries NO
   acceptance criteria, detailed requirements, or idea/bug dumps —
   ACs live in the item's plan artifact, authoring named as
   `designing-architecture`'s plan-time artifact), the
   confidence-gated detail rule per horizon (Now = specific solutions
   in flight, Next = opportunities under validation, Later = outcomes
   only), and the quarterly re-triage cadence (paired with the
   standing quarterly ALM review) — verifiable by grep for the rule
   text blocks; each cites its research source (Aha! must-not-include,
   Atlassian warning, Torres horizons — verified live 2026-10-11, see
   citations below).
3. The "any extension (first-class Now/Next/Later column,
   success-measure column) is an ADR-gated change and is excluded from
   v1" language is absent from roadmap-format.md, SKILL.md
   (triaging-requirements), artifact-format.md, and SKILL.md
   (facilitating-product-vision) — verifier:
   `grep -rn "ADR-gated" skills/triaging-requirements/
   skills/facilitating-product-vision/` returns 0 matches outside
   evals/evals.json historical notes.
4. `skills/facilitating-product-vision/references/artifact-format.md`
   fixed section order contains NO `## Slices` section; the Outcome
   Themes section validates only `| Theme | Outcome (observable, one
   line) |` columns (no Horizon column, no capacity band, no slice
   lists); the Slices column-label block
   (`| Slice | Outcome theme | AC (observable) | Success measure |
   Blocked-by | Sizing |`) and its `success measure` / `blocked-by`
   literals are absent from the vision contract; the Good-definitions
   table has no Slices row — verifiable by grep.
5. facilitating-product-vision `SKILL.md` steps 3 and 5: items are
   emitted ONLY as roadmap rows (no per-slice artifact content);
   acceptance criteria are explicitly NOT emitted (the words
   "acceptance criteria" + "NOT emitted" or the equivalent literal
   boundary phrase appear); the AC-boundary note routes to
   `designing-architecture` by exact directory name; the
   capacity-envelope language moves to theme level (a captured
   Input/Constraint), Horizon and sizing named as roadmap fields —
   verifiable by grep for the literal phrases the plan names below.
6. facilitating-product-vision SKILL.md frontmatter `description:`
   loses the "outcome-based slice roadmap" literal and describes the
   two-artifact output as vision doc + roadmap rows (eval-3's
   boundary text "this skill emits THEME + SLICE rows, not
   implementation plans" updates to say theme + roadmap-item rows)
   — verifiable by grep for "slice roadmap" returning zero in the
   SKILL.md body and description.
7. artifact-format.md's "Roadmap row contract (sibling)" section no
   longer enumerates its own row-shape rules (Notes-based horizon
   mapping, capacity columns) — it DEFERS to
   `../../triaging-requirements/references/roadmap-format.md` with a
   pointer and a one-line "conform to the item-row schema there"
   statement; it does not duplicate the 13-column schema —
   verifiable by reading the section (≤6 lines with a single
   sibling-pointer; no column enumeration beyond the pointer).
8. `references/consumer-session.md` consumer guidance describes the
   two-artifact flow for a consumer session: (1) vision doc
   (strategy), (2) roadmap rows per the sibling schema; no slice-table
   or per-slice AC language remains — verifiable by grep for
   "slices per theme" / "AC +" returning zero in that file.
9. Eval changes — facilitating-product-vision `evals/evals.json`:
   - eval-1's `expect.artifact.phrases` drop
     "success measure"-as-column-label carriers tied to the Slices
     table; add the positive-shape phrases that pin the new Outcome
     Themes table (e.g. "Outcome") and keep `Inputs & Constraints`,
     `Vision Statement`, `Segments & Jobs-to-be-Done`,
     `Alternatives & Non-goals`, `Value & Business Model`,
     `North Star`, `Guardrails`, `Outcome Themes`, `Compliance`,
     `Phase Gates`, `Open Questions`, `### Now`, `### Next`,
     `### Later`.
   - eval-1's `expected_behavior` replaces the Slices-table assertion
     rows with (a) "the vision artifact contains NO operational slice
     table" (D2: hand-review-enveloped, deferred note in the
     manifest `notes`) and (b) "emitted roadmap rows carry the new
     fields" (Outcome/Horizon/Success measure/Blocked-by as
     roadmap-format columns).
   - eval-4 and eval-5 keep their honest-limits assertions (one-shot
     ask-in-words, turn-2 checkpoint-resume);
     `expect.text` for "success measure"/"blocked-by" of eval-1
     removed or replaced (Aha!/Atlassian-cited no-op literals are no
     longer vision-contract content).
   - existing assertions kept where still true (per the task
     requirement).
   - typed `expect` blocks on every touched eval, per ADR-0003 —
     verifiable by `python3 scripts/check_typed_evals.py --base main`
     exiting 0.
10. Eval changes — triaging-requirements `evals/evals.json`: eval-1's
    `expect.artifact[0].phrases` extend to include `Horizon` and
    `Success measure` (the new columns an initialized roadmap must
    carry); `expected_behavior` adds "a roadmap item carries NO
    acceptance criteria, detailed requirements, or idea/bug dumps"
    and "detail scales with confidence across the Horizon columns"
    expectations. Existing `Impact`/`Urgency` phrase pins retained.
11. Across the two skill bodies + two reference files + two eval
    manifests: no stale "Slices" contract language or
    "success measure as a vision-doc column" language survives
    anywhere (ROADMAP.md historical rows and Done rows excluded —
    those are frozen records, not contract text) — verifier:
    the grep sweep in AC 3/4 returns zero; additionally the plan's
    fresh-source grep of
    `grep -rn "Slices" skills/facilitating-product-vision/
    skills/triaging-requirements/` shows only eval-history notes and
    NOT the vision contract.
12. Offline gates green after each gate-pass commit:
    `python3 skills/authoring-skills/scripts/validate_skill.py --all`
    exits 0;
    `python3 scripts/check_typed_evals.py --base main` exits 0;
    `python3 skills/authoring-skills/scripts/test_runner.py` exits 0;
    `python3 scripts/test_typed_evals.py` exits 0.
13. Behavioral evals recorded honestly on the pinned lane —
    not silently greened:
    `python3 skills/authoring-skills/scripts/run_behavioral_eval.py
    --skill facilitating-product-vision --model
    opencode-go/deepseek-v4.1-flash --ci` and the same with
    `--skill triaging-requirements` run and their results recorded in
    the plan's History / handoff (pass or fail recorded with the
    failure signature — the honest-limits rule); eval-5 (deferred)
    re-run recorded incl. a pass OR a dated deferral note, never a
    silent skip (per the harness contract, `--include-deferred` on
    the Go lane locally).

## Files to Modify

Commit 1 — RM-053 contract (gate-pass unit: offline gates green):

- skills/triaging-requirements/references/roadmap-format.md — item-row
  schema becomes the 13-column contract; Status set updated to
  `proposed/open/waiting/in-progress/done/skipped`; no-AC rule +
  confidence-gated detail + quarterly re-triage cadence added; the
  "ADR-gated extension" language removed; merge-table rows updated for
  the new columns (merge keeps ID stability and Done-history rules);
  Done-row verbatim practice written per design decision D1.
- skills/triaging-requirements/SKILL.md — Step 4/5/6 schema and
  section descriptions updated (column list, Status set, Outcome/
  Horizon semantics); Step 7 merge-table summary updated; "When not
  to use" row for facilitating-product-vision updated (it emits the
  roadmap rows with the new fields; the no-op "slices" phrase is
  replaced).

Commit 2 — RM-053 evals (gate-pass unit: offline gates green):

- skills/triaging-requirements/evals/evals.json — per AC 10 (typed
  expectations extended; existing [fix-verified] assertions preserved
  — the regression net is not weakened).

Commit 3 — RM-052 contract + consumer guidance (gate-pass unit:
offline gates green):

- skills/facilitating-product-vision/references/artifact-format.md —
  per AC 4/5/7 (drop Slices; strategy-only Outcome Themes; label
  literals move out; Good-definitions lose the Slices row; sibling
  roadmap-row contract section de-duplicated to a defer pointer).
- skills/facilitating-product-vision/SKILL.md — per AC 5/6 (description,
  steps 3/5, AC-emission boundary note, capacity-envelope wording).
- skills/facilitating-product-vision/references/consumer-session.md —
  per AC 8 (consumer-facing two-artifact flow, no slice language).

Commit 4 — RM-052 evals (gate-pass unit: offline gates green):

- skills/facilitating-product-vision/evals/evals.json — per AC 9
  (typed phrase sets refreshed; honest-limits manifest notes gain the
  D2 deferred-negative assertion note).

## Scope

### Included

- The two skill contracts' bodies and their two reference docs
  (roadmap-format, artifact-format) + consumer-session guidance.
- Both eval manifests' typed assertions and honest-limits notes.
- The design decisions D1–D4 recorded in the plan body (cold-
  executable — the migration pass and eval authors can execute from
  this file alone, per RM-034).
- An explicit statement (boundary) that docs/ROADMAP.md itself
  migrates on the NEXT triaging-requirements pass (see Excluded).

### Excluded

- The docs/ROADMAP.md migration to the new schema (RM-053's row:
  "migrates to the new schema on its next triage pass after the
  contract lands" — Priority and Phase retire to historical; rank
  within horizon = Impact × Urgency). That is the next triage pass's
  job, not this plan's implementation scope. This plan delivers the
  contract; the future state is named in design decision D4 so the
  migration pass has a spec to execute cold.
- The behavioral-harness runner changes (negative-assertion class,
  eval staging) — RM-021/RM-016 territory; recorded, not built.
- ADR-0003 additions (no new assertion classes proposed here).
- Roo/bootstrapping distributed skill copies: the live library
  mirrors consumers of these skills; propagation of these contracts
  is the repo's normal update flow (not a step in this plan).
- The paragon-consumer ADR-0007's own internal edits (that is the
  consumer's repo).
- RM-054 (handoff §C appendix findings) — already a separate
  roadmap row; not bundled here.
- reference/agent-teams.md persona dispatch (read-only here; not a
  touched file).

## Schema / Type Impacts

None. Docs-and-evals contracts only; no database, no generated types.

## Verification

Gate-pass commands (the project's real commands — from
`.github/workflows/ci.yml`):

- python3 skills/authoring-skills/scripts/validate_skill.py --all
- python3 scripts/check_typed_evals.py --base main
- python3 scripts/test_typed_evals.py
- python3 skills/authoring-skills/scripts/test_runner.py
- grep sweep for AC 3/4/6/8/11 stale-language assertions (run after
  each contract commit; exit 0 on the expected-zero result):
  - `! grep -rn "ADR-gated" skills/triaging-requirements/
    skills/facilitating-product-vision/` (eval-history lines excluded)
  - `! grep -rn "## Slices"
    skills/facilitating-product-vision/references/artifact-format.md`
  - `! grep -rn "slice roadmap"
    skills/facilitating-product-vision/SKILL.md`
  - `! grep -rn "slices per theme"
    skills/facilitating-product-vision/references/consumer-session.md`
- Behavioral eval runs on the pinned lane (recorded honestly, never
  silently green; deferred re-run with `--include-deferred` recorded
  or its deferral noted):
  - python3 skills/authoring-skills/scripts/run_behavioral_eval.py
    --skill facilitating-product-vision --model
    opencode-go/deepseek-v4.1-flash --ci
  - python3 skills/authoring-skills/scripts/run_behavioral_eval.py
    --skill triaging-requirements --model opencode-go/deepseek-v4.1-flash
    --ci

## Open Questions

Both open questions RESOLVED by owner directives, 2026-10-11
(rm-052-053 design review). Recorded here as user-frozen policy
(RM-034); each decision carries its own roadmap row.

- **Eval-lane fallback (replaces the "record honestly and stop"
  default):** if an eval cannot complete because of the model or the
  opencode service — degradation PROVEN from logs (RM-021-diagnosed
  classes: model-resolution deaths, dead streams, provider errors) —
  the run falls back to the **deepseek-v4.1-flash direct API lane**
  rather than stopping. The binding/routing policy itself stays
  RM-039/ADR-0013's domain (a per-run lane switch, never a silent
  re-bind; the eval report marks the fallback lane so pass rates stay
  comparable). Tracked as roadmap row **RM-056** (own design+build;
  this plan's runner-edit exclusion stands — during THIS plan's
  implement window the failure disposition remains the recorded-
  honestly default until RM-056 delivers).
- **Roadmap presentation (replaces the overflow textbox default):**
  the owner rules the overflow issue is solved by a real UI design
  pass for the **objectively best presentation** — reading to be
  enjoyed AND structure understood clearly. Tracked as roadmap row
  **RM-057** (waiting on this plan's deliverable). The schema stays
  first-class (no column dropping); the migration pass does not
  hard-code presentation choices beyond the 13-column contract.

## History

- 2026-10-11 (revision, owner directives) — Open
  Questions resolved and closed: (1) eval-lane fallback to the
  deepseek-v4.1-flash direct API on log-proven model/opencode
  degradation → RM-056 (row added, fired; this plan's implement
  window disposition unchanged); (2) roadmap presentation is a
  real design pass — overflow solved by design, never
  truncation → RM-057 (row added, waits on this plan). No
  AC/commit changes; both rows carry the pointers.
- 2026-10-11 — drafted by the designing-architecture pass (RM-052 +
  RM-053, one plan, two gate-pass commit units). Sources: paragon
  handoff 2026-10-09 §A/§B (read at
  `.scratch/rm-052-053-design/handoff-roadmap-structure.md`), ROADMAP
  rows RM-052/RM-053, both SKILL.md bodies + reference docs, both
  eval manifests, eval harness reference, ci.yml verify commands.
  Live-doc verification done in this design pass (2026-10-11):
  - Teresa Torres, producttalk.org/product-roadmaps (fetched
    2026-10-11) — verbatim confirmed: "Now column contains specific
    solutions in progress … the Next column contains opportunities —
    customer needs and pain points, not yet committed solutions …
    the Later column contains outcomes — the measurable results
    teams are driving toward." (the confidence-gated detail rule in
    AC 2).
  - Atlassian, atlassian.com/agile/product-management/roadmaps
    (fetched 2026-10-11) — verbatim confirmed in-page: "Detailed
    requirements are weighing down the roadmap" (warning sign;
    supports the no-AC / no-detailed-requirements rule) and the
    quarterly review cadence ("review … quarterly, adjust as needed").
  - Aha! and SVPG/Cagan 2009 citations from the handoff are treated
    as given (the handoff's source appendix; the repo's treating
    rule): they are NOT load-bearing for this plan's core ACs — the
    verified Torres/Atlassian rules carry the two load-bearing
    claims (no-AC + horizon detail-scaling). The Aha! must-not-include
    (ideas/backlogs/bug lists stay out of the roadmap) is cited in
    roadmap-format.md as a secondary source without a live recheck
    in this pass, flagged as hand-taken (honest-limits,
    logged as a residual).
- Evaluations note: the closed `expect` schema has no negative-
  assertion class — the "no operational slice table" check is
  hand-review-enveloped and deferred, per design decision D2 (record
  never greens silently). No council-ux consult needed this pass —
  no user-facing UI component is introduced or changed (all changes
  are text contracts and eval JSON); `no user-facing UI — council-ux
  consult skipped` recorded per the skill's explicit-skip rule.
- Commit note (per ADR-0008 and plan-format history): the plan and
  all references above stay in repo-relative paths; the plan file is
  committed on `docs/rm-052-053-plan` (only this file — not
  docs/ROADMAP.md which has live uncommitted triage working-tree
  changes).
