# Coverage-and-quality gate (Step 9)

Read this from Step 9, once real code exists. Two responsibilities, both
**gates**: cite the specific misclassification or the concrete gap. Padding for
its own sake is refused with the trio's own language — "a case that exercises
no observable the AC names is padding, not coverage."

## (a) Rebalance

Step 5 classified each AC's test layer as a best guess. Re-examine each Step-5
AC→test pair against the **same** right-layer table, this time with the real
implementation to look at:

- Did a **unit** test end up mocking a real seam into existence (vacant, per
  the trio's "mocking the behaviour under test" rule — the behaviour only
  exists where two collaborators meet)?
- Did an **e2e** test turn out to guard pure logic a unit test would prove
  faster and more precisely?

If a test landed at the wrong layer, **supersede** it: invoke the CORRECT trio
skill to re-author it at the right layer, and re-prove meaningfulness there via
break → red → restore → green (the trio's post-implementation proof; this is
the one place break/restore applies, because code now exists to break). This is
the testing-pyramid correction: push each test down to the cheapest layer that
still meaningfully exercises the behaviour. Record which AC-tests were
rebalanced and why. A corrected red-first guess is the system working as
designed — not a defect to push upstream into the plan format (the library's
convention: no per-AC layer tag at design time).

## (b) Expand

Re-run the existing meaningfulness proof (break/restore) on each (possibly
rebalanced) Step-5 AC test to confirm it is **still** meaningful once the
implementation exists — cheap insurance the code did not accidentally make a
test vacuous. Then ask a **bounded** coverage question: given the **actual**
implementation (branches, error paths, boundaries visible now but not at
design time), is there a genuinely valuable gap the AC set did not reach?

- **Yes** — invoke the matching trio skill in its existing "untested behaviour"
  entry mode to add the test(s); prove meaningfulness via the existing
  break/restore; confirm additive-to-the-net. One targeted test per genuine
  gap; do not expand beyond the cited gaps.
- **No** — **say so explicitly** in the handoff ("coverage reviewed; no
  high-value gap found beyond the AC set"). The explicit negative is the
  closure signal; silence is not.

Both legs must cite: rebalancing the **specific misclassification** being
corrected; expansion a **concrete gap** in the real implementation (an error
path, a boundary the code special-cases). Refusing to pad is a feature here,
not a skipped step.
