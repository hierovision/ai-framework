# Red-first contract (Step 5)

Read this from Step 5 when authoring the pre-implementation tests. The SKILL.md
body carries the imperative; this file owns the detail and rationale.

## The pre-implementation red

After recon, before any source edit: author the behaviour the plan asks for as
a failing test, *before* the behaviour exists. The point is to capture each
testable Acceptance Criterion as real red against real absence, so
implementation goes green against a test proven to exercise the intended path
— never a test written after the fact to mirror the implementation.

For each testable AC (a verifier that names a test command), once:

1. **Classify the right layer** using the identical routing table the trio
   skills define (see `../../writing-unit-tests/SKILL.md` Step 2 — the same
   table is duplicated across all three trio skills by design; use it, do not
   restate it). The classification is a **best guess**: a plan cannot know the
   true seam boundaries before code exists, so a wrong guess is **expected and
   normal** — Step 9's coverage gate corrects it once real code reveals the
   seam. Do not treat a wrong red-first guess as a plan defect; there is
   nothing to fix upstream.
2. **Invoke the matching trio skill** to author **one test** (or a minimal
   table-driven set) **for that AC only**, explicitly telling it this is a
   **red-first, pre-implementation call** (the trio's meaningfulness proof
   branches on that mode). Bounded: one test per AC; edge cases are the
   coverage gate's expand leg, once real code reveals what is worth covering.
3. **Run it. It MUST fail.** The natural failure IS the proof — and the proof
   obligation is to **confirm it fails for the right reason**: the actual
   failure output names the *missing/wrong behaviour* the AC describes (a
   `ReferenceError` for a not-yet-written function; an assertion expecting
   `409` and observing `200`; a `not found` for an absent route or table).
4. **Red for the wrong reason is a trap, not a proof.** A failure from a
   broken test **setup** — a typo, a bad import unrelated to the feature, a
   wrong fixture, a mismatched selector/field — does not name the missing
   behaviour. When it happens, fix the **test's own setup** (the feature does
   not exist yet) and re-run until it fails for the right reason. This is a
   test-authoring correction, not a `debugging-test-failures` scenario — there
   is no working code to regress from yet.
5. **Record** the AC → test-file mapping and the confirmed red evidence — the
   actual failure text that named the missing behaviour — for the plan
   `## History` and the handoff.

## Honest stops

Both reuse existing postures; neither is new:

- **An AC's verifier cannot produce a red-first test at all** (genuinely
  untestable as written — names infrastructure the plan does not add): the
  **contract-breaking** path (Step 4). STOP, report, route to
  `designing-architecture`. Do not invent a workaround test.
- **A red-first test cannot be made to fail for the right reason after
  reasonable correction attempts** (every failure names a harness defect):
  the **N-attempts non-convergence** path (Step 7). STOP, report, hand to
  `debugging-test-failures`. Do not proceed to implementation on an unverified
  red — that silently turns red-first back into test-after and gives up the
  proof this step exists to produce.

## Pre- vs post-implementation proof

This is the **pre-implementation red**: the natural absence IS the proof. It is
distinct from the post-implementation break → red → restore → green the trio
already does — Step 9 reuses *that* proof for re-confirmation and new coverage.
A test born red-first does not need a break/restore to prove its authoring: it
already went red against real absence. Do not conflate the two.
