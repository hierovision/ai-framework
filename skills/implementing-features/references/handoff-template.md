# Completion handoff template (implementing-features Step 11)

Loaded only when composing the Step 11 handoff. The body defines the
contract and the STOP; this file is the full per-section template. Every
section below is required; absence of evidence for a section is stated
explicitly, never omitted.

- **What changed** — which files were edited / created, in one line per
  file, referencing the plan's `Files to Modify`.
- **Acceptance-criteria status** — per criterion, the status as
  evidenced by the verifier that greened. Criteria whose verifier is a
  command that greened: mark them satisfied (with the command). Criteria
  whose verifier requires human judgement (visible behaviour, a manual
  workflow like "go offline, start a timer, reload, come back online,
  watch the replay"): mark them `manual — steps below`. **Do not
  self-certify criteria that require human eyes.**
- **Red evidence** — which Step-5 AC-tests were proven red
  pre-implementation, and for each the confirmed failure reason (the
  actual failure text that named the missing behaviour). A manual-only
  AC is noted here as manual, not silently dropped.
- **Rebalancing outcome** — any Step-9(a) AC-test moved to a different
  layer and why, or an explicit "none needed" when the best-guess layers
  held against the real implementation.
- **Coverage-gate outcome** — Step-9(b) expanded (citing the specific
  gap(s) the real implementation revealed) or an explicit "no
  high-value gap found beyond the AC set". Silence is not an answer.
- **Runtime-validation outcome** — Step 8's net verdict (clean /
  blocked with the offending messages), the council-ux findings (fixed
  + residual), the evidence paths (`.opencode/evidence/<plan-slug>/`
  — evidence.json, screenshot), or the explicit "no visible UI" /
  DEFERRED note.
- **MANUAL validation steps** — the concrete sequence the human should
  run to green the human-only criteria. Numbered, in the order the user
  would perform them, ending with "what you should observe". The
  archived screenshot from Step 8 is the visual reference for the
  human-only UI criteria.
- **Plan state** — the plan's path, the History entry you appended, the
  status (flipped or not).
- **PR ready** — the branch pushed (`<type>/<slug>`), the PR URL/title,
  and the note that merging is user-initiated (main is protected; only
  PRs merge). Commits on the branch are part of the pass and need no
  request; the merge is the gated action.
- **Follow-ups** — any recorded scope-creep requests, surfaced so the
  user can decide whether to hand them to triage / design.
