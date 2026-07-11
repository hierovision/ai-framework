# Handoff: TDD-aware implement sequencing

Dispatch to a fresh **GLM 5.2** author session in `~/repos/ai-framework`.
(Escalation tier: this touches FOUR existing skill contracts with a subtle
cross-file distinction — worth GLM's instruction-following discipline over
the MiniMax M3 default, same rationale as `auditing-accessibility`.)
Paste everything below the line.

---

```
Use the authoring-skills skill to REVISE four existing skills in this repo
(~/repos/ai-framework): implementing-features, writing-unit-tests,
writing-integration-tests, writing-e2e-tests, and a small additive touch
to reviewing-code (five skills total). Enter authoring-skills' loop at
"Improving an existing skill" (Step 3): snapshot each current version,
confirm/extend its evals, test the existing skill to establish a baseline
BEFORE editing. Re-read authoring-skills fully first; it bundles
scripts/validate_skill.py which you RUN (not read) throughout.

CONTEXT

Read first:
- PLAN.md, section "Core Loop Refinement — TDD-Aware Implement
  Sequencing" (the decisions this handoff implements — read it in full,
  it is the spec).
- skills/implementing-features/SKILL.md (the skill gaining two new
  steps) + its evals/evals.json (the existing fixture + scenarios you
  are extending).
- skills/writing-unit-tests/SKILL.md, skills/writing-integration-tests/
  SKILL.md, skills/writing-e2e-tests/SKILL.md (each gaining a mode
  branch in the meaningfulness-proof step) + their evals.
- skills/reviewing-code/SKILL.md, specifically Step 4 point 2 ("the test
  net") and the References section (the small cross-reference addition).
- skills/debugging-test-failures/SKILL.md — read for the cardinal rule
  and the class taxonomy; you are NOT editing this skill, but the new
  "red for the wrong reason" discipline in implementing-features/the
  trio must be worded consistently with it (a broken test fixture before
  any code was written is a test-authoring correction, not a debugging-
  test-failures scenario — there is no working code to regress from).
- skills/designing-architecture/references/plan-format.md — read for the
  Acceptance-Criteria schema. You are NOT changing this file's structure
  (see Requirements, "do not touch").

THE CORE DISTINCTION (get this right; it is the whole point of the pass)

Two different kinds of "red," BOTH kept, never merged into one:

1. Pre-implementation red (NEW): a test authored against a behavior that
   does not exist yet. Run it before any implementation edit. It MUST
   fail. The proof obligation is NOT "break it, see red, restore, see
   green" (there is nothing working yet to break) — it is "read the
   actual failure output and confirm it names the missing/wrong
   behavior" (e.g. a ReferenceError naming the not-yet-written function,
   or an assertion expecting 409 and observing 200). A failure from a
   broken test SETUP (a typo, a bad import unrelated to the feature, a
   wrong fixture) is red for the WRONG reason — that is a trap, not a
   proof. When it happens, fix the TEST's own setup (not the feature,
   which doesn't exist yet) and re-run until it fails for the right
   reason.
2. Post-implementation meaningfulness proof (EXISTING, unchanged): the
   trio's current break-the-behavior -> red -> restore -> green. This
   stays exactly as it is today, used for two things: (a) re-proving the
   Step-5 AC tests are STILL meaningful once real implementation exists
   (cheap insurance the implementation didn't accidentally make a test
   vacuous), and (b) proving any coverage-expansion test added at the
   new end-of-pass gate, where code already exists so this is the only
   available proof mechanism.

Do not conflate these. A test born in mode 1 does not need mode 2's
break/restore to prove ITS original authoring — it already went red for
real, against real absence. Mode 2 is reused for re-confirmation +
new coverage tests, not as a redundant re-proof of the same claim mode 1
already established.

REQUIREMENTS — implementing-features/SKILL.md

Insert two new steps into the existing 8-step checklist (renumber the
rest; do not renumber-and-rewrite steps whose content is unchanged,
just shift their step numbers):

- New step (after "Reconcile plan vs the actual repo", before "Implement
  exactly Files to Modify"): RED — capture core behavior from Acceptance
  Criteria. For each testable AC (a verifier that names a test command;
  skip manual-only ACs exactly as today, noted not silently dropped):
  classify the right layer using the IDENTICAL routing table already
  defined in the three trio skills (reuse via link, do not duplicate);
  invoke the matching trio skill to author ONE test (or a minimal
  table-driven set) FOR THAT AC ONLY, explicitly telling it this is a
  red-first, pre-implementation call; run it; confirm it fails for the
  right reason per the Core Distinction above; record the AC -> test
  mapping + the red evidence (the actual failure text). Bounded: one
  test per AC here, no invented edge cases yet — edge cases are the new
  end-of-pass gate's job, once real code exists to reveal what's worth
  covering.
- New step (after Verification is green, before "Update the plan
  artifact"): coverage-and-quality gate, with TWO responsibilities (get
  both into the skill body -- this is not a single "expand coverage"
  step):
  (a) REBALANCE. The red-first step (Step 5) classified each AC's test
  layer as a BEST GUESS -- this is correct by design, not a shortcut: a
  plan cannot know the true seam boundaries until code exists, so the
  guess is expected to sometimes be wrong. Now that real code exists,
  re-examine each Step-5 AC-test pair against the SAME right-layer table:
  did a "unit" test end up mocking a real seam into existence (vacant,
  per the trio's own "mocking the behaviour under test" rule)? Did an
  "e2e" test turn out to guard pure logic that a unit test would prove
  faster and more precisely? If a test landed at the wrong layer,
  supersede it, invoke the CORRECT trio skill to reauthor it at the right
  layer, and re-prove meaningfulness there (break/restore). This is the
  testing-pyramid correction -- push each test down to the cheapest layer
  that still meaningfully exercises the behaviour. Record which AC-tests
  were rebalanced and why.
  (b) EXPAND. Re-run the EXISTING meaningfulness proof (break/restore) on
  each (possibly rebalanced) Step-5 AC test. Then ask a BOUNDED coverage
  question: given the ACTUAL implementation (branches, error paths,
  boundary conditions visible now but not obvious at design time), is
  there a genuinely valuable gap the AC set didn't reach? If yes, invoke
  the matching trio skill in its EXISTING "untested behaviour" entry mode
  to add the test(s), prove meaningfulness via the existing break/restore,
  confirm additive-to-the-net. If no gap: say so explicitly in the
  handoff ("coverage reviewed; no high-value gap found beyond the AC
  set") -- an explicit negative is the closure signal; silence/omission
  is not.
  Both (a) and (b) are a GATE, not a license -- rebalancing must cite the
  specific misclassification being corrected; expansion must cite a
  concrete gap in the real implementation; padding for its own sake is
  refused either way (reuse the trio's own "a case that exercises no
  observable the AC names is padding, not coverage" language, do not
  weaken it).

The completion handoff summary (final step) gains three new fields: Red
evidence (which AC-tests were proven red pre-implementation + the
confirmed failure reason), Rebalancing outcome (any AC-test moved to a
different layer + why, or explicitly none needed), and Coverage-gate
outcome (expanded with reasoning, or explicitly no-gap-found).

Two honest-stop additions consistent with the existing Step-6
non-convergence / contract-breaking postures: if an AC's verifier cannot
produce a red-first test at all (the criterion is genuinely untestable
as written), that is the EXISTING contract-breaking deviation path (stop,
report, route to designing-architecture) -- do not invent a workaround
test. If a red-first test cannot be made to fail for the right reason
after reasonable correction attempts, treat it as the existing N-attempts
non-convergence path (stop, report, hand to debugging-test-failures) --
do not proceed to implementation on an unverified red.

REQUIREMENTS — the test trio (writing-unit-tests / writing-integration-
tests / writing-e2e-tests)

Each of the three needs the SAME shape of change, adapted to its layer:

- The meaningfulness-proof step (currently a single break/restore
  recipe) branches on an explicit CALLER-STATED mode: red-first
  (pre-implementation) vs coverage-expansion-or-standalone
  (post-implementation, today's unchanged behavior). Red-first mode's
  proof is: the natural failure IS the red; confirm it fails for the
  right reason (the Core Distinction's trap) rather than performing a
  synthetic break (there is nothing to break yet). State this plainly:
  a test that fails because the referenced function/route/table does
  not exist yet has satisfied its proof obligation once you've confirmed
  the failure message names that absence, not an unrelated setup defect.
- The "Do not move to integration/e2e on your own -- those are sibling
  skills the user invokes separately" language is CLARIFIED, not
  reversed: the trio still never cascades into EACH OTHER. Add one
  sentence naming implementing-features as a documented, intentional
  caller at its two new named steps (red-first, coverage gate) -- this
  is orchestration by a sibling skill, not the trio skill choosing to
  chain on its own initiative.
- The handoff (final step) gains a one-line mode note (which mode ran)
  so implementing-features can fold the evidence into its own records
  without re-deriving it.
- writing-e2e-tests specifically: its existing "meaningfulness honesty"
  paragraph already distinguishes real-browser vs no-browser proof; add
  the red-first/coverage-expansion axis ORTHOGONALLY to that (a red-first
  e2e spec still needs the real-browser-vs-structural-proxy distinction
  for ITS proof, layered under the red-first framing) -- do not collapse
  the two axes into one, they answer different questions (when the test
  goes red vs whether a browser is available to observe it).

REQUIREMENTS — reviewing-code/SKILL.md (small, additive only)

In Step 4 point 2 ("the test net"), add one sentence: when the plan's
`## History` carries implementing-features' new red evidence +
coverage-gate outcome, the reviewer spot-checks those claims (does the
recorded red evidence actually name the right failure? does the
coverage-gate reasoning hold up against the diff?) rather than
re-deriving the meaningfulness check from zero. Do not add a new
severity category or a new step -- this is a cross-reference, not new
logic. Add the implementing-features SKILL.md link to References if not
already sufieicnt.

DO NOT TOUCH

- skills/designing-architecture/references/plan-format.md -- LOCKED, not
  a wait-and-see: do not add per-AC layer tags, ever, in this pass or a
  future one. Best-guess layer classification at red-first time is
  correct BY DESIGN -- a plan cannot know the true seam boundaries before
  code exists, so asking design time to pre-classify precisely would ask
  it to know something it structurally cannot yet know. The correction
  belongs to the coverage-and-quality gate's REBALANCE responsibility
  (see above), which has the real implementation to look at. A
  misclassified red-first guess is expected and NORMAL, not a defect to
  fix upstream -- it is fixed downstream, every time, by the mechanism
  this handoff builds. Do not treat eval-loop misclassifications as
  evidence for a plan-format.md change; treat them as the rebalance
  step's routine job and confirm rebalancing actually corrects them.
- skills/debugging-test-failures/SKILL.md -- no edits. Word the new
  "red for the wrong reason" discipline consistently with its class
  taxonomy, but this skill's body does not change.
- Any UI-loop skill (capturing-ui-evidence, correcting-ui,
  auditing-accessibility) -- out of scope.
- No new bundled scripts. This is a workflow/prose change to existing
  skills, not a new harness.

EVAL DESIGN

For implementing-features (extend its existing fixture; do not replace
the current 4 scenarios -- add scenarios, all still against a writable
copy per its existing evals.json convention):

1. Red-first-then-green (core scenario): an approved plan with 2-3 clear,
   testable Acceptance Criteria and NO pre-existing tests or
   implementation for them. The agent must: author one test per AC
   BEFORE any source edit, run each and observe a natural failure,
   confirm (in the transcript) each failure names the missing behavior,
   THEN implement, THEN reach green, THEN run the coverage gate. Grade:
   test files exist and are dated/ordered before the implementation edit
   (or the transcript explicitly shows red observed pre-edit); the
   red evidence recorded matches an actual pre-implementation test run;
   zero scope creep.
2. Red-for-the-wrong-reason trap: seed the fixture so a naively-written
   AC test would fail for a WRONG reason first try (e.g. the fixture's
   test helper has a subtly wrong import path, or the AC's naming
   implies a selector/field that doesn't match the fixture's actual
   scaffold) -- the agent must notice the failure message does NOT name
   the missing feature, fix the test's own setup, re-run, and only THEN
   treat it as a valid red. FAIL the eval if the agent proceeds to
   "implement" against a red that was actually a broken harness.
3. Coverage-gate: rebalance leg (THIS IS A CORE SCENARIO, not optional --
   it proves the central design decision that best-guess red-first
   classification is correct-by-design because the gate corrects it).
   Seed the fixture so an AC's WORDING plausibly reads as pure logic (a
   reasonable red-first guess would pick unit), but the actual
   implementation necessarily touches a real seam (e.g. the "obvious"
   calculation turns out to require a DB lookup / policy check once
   built) -- OR the reverse, an AC that reads seam-shaped but the real
   implementation is pure logic. The agent's red-first test at the wrong
   layer should be EXPECTED here (that's the point), not a defect. Grade
   the coverage-gate step: does it notice the mismatch once the real
   implementation exists, supersede the wrong-layer test, invoke the
   correct trio skill, and re-prove meaningfulness at the correct layer?
   FAIL the eval if the agent either (a) never notices and ships a vacant
   unit test that mocks the seam into existence, or (b) treats the
   red-first guess as immutable and leaves it wrong. This scenario is
   what makes Decision 3 (no plan-format.md schema change, ever) safe to
   rely on -- it must demonstrably work, not just be asserted.
4. Coverage-gate: no-gap-found leg -- a scenario where the real
   implementation genuinely has no valuable gap beyond the AC set AND no
   rebalancing is needed; the agent must explicitly say so on both counts
   (not silently skip the gate, not manufacture a padding test to seem
   thorough).
5. Coverage-gate: real-gap leg -- a scenario where the implementation
   reveals a genuine edge case / error path the ACs didn't name (e.g. an
   AC covers the happy path only, but the implementation necessarily adds
   a validation branch); the agent must add ONE targeted test citing the
   specific gap, prove it via break/restore, and NOT expand beyond that
   one gap.
6. Manual-only AC handling unchanged -- confirm an existing scenario (or
   extend one) still correctly notes a manual-only AC rather than forcing
   a red-first test for it.

For the trio (one added scenario is enough per skill, reusing existing
fixture conventions): a red-first-mode scenario proving the natural-
failure + right-reason-check discipline, structurally mirroring how each
skill's existing meaningfulness-proof scenario is graded. Where a real
runtime is unavailable (writing-e2e-tests' existing real-browser
deferral), the structural proxy from Step 6 already documents this --
extend it to also cover red-first structurally (the spec, run against
the pre-feature fixture, produces the expected non-passing structural
signal) and document the real-browser red-first proof as the SAME kind
of deferral already in place, not a new one.

For reviewing-code: extend one existing scenario (do not add a new one)
so its fixture's plan `## History` carries a red-evidence + coverage-gate
record, and assert the reviewer's REVIEW.md references/spot-checks it
rather than ignoring it.

Encode every actual fix found during the loop as a [fix-verified]
assertion, per the library's convention.

PROCESS EXPECTATIONS

- Full eval loop with fresh subagents, with-skill vs baseline, for EACH
  of the five touched skills. Reports to /tmp/opencode/tdd-sequencing-
  eval/ AND fold the loop log into each skill's evals.json notes (the
  durable record; /tmp gets cleaned between sessions).
- Copy fixtures to temp dirs per run; never write into evals/fixtures/
  source.
- Run validate_skill.py --all before finishing; leak scan clean; roles-
  not-model-IDs preserved; each touched SKILL.md body stays under 500
  lines (implementing-features and the e2e skill are already the
  longest in the library -- if a body would cross 500 lines, move detail
  into a reference file rather than trimming the discipline).
- Cross-skill contracts stay linked, never duplicated: the right-layer
  table is defined ONCE (already lives identically in all three trio
  skills today -- keep that existing duplication pattern as-is, do not
  introduce a NEW duplication for the red-first/coverage-mode language;
  word each skill's version for its own layer but keep the underlying
  rule identical).
- Do NOT commit. Leave all five skills' edits in the working tree and
  eval reports in /tmp/opencode/tdd-sequencing-eval/ for independent
  orchestrator review.
```
