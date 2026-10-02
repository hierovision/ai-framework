---
name: implementing-features
description: Execute ONE approved plan artifact — code changes strictly within the plan's scope, verified by the plan's Verification commands — then stop at a manual-validation handoff. Use whenever the user says "implement the plan", "build feat-x", "execute the plan at .opencode/plans/<slug>.md", "the plan is approved, go", or hands off from a design pass — even without saying "implement" or "build". Refuses scope creep (cites the plan's Excluded list; records follow-ups). Mechanical plan-vs-reality mismatches proceed with a History note; contract-breaking ones stop and route back to designing-architecture. Not for trivial single-file changes with no plan (just edit), authoring or revising plans (that is designing-architecture), or deep debugging (separate skill).
---

# Implementing Features

Execute one approved plan artifact. The plan is a contract: implement what
`Files to Modify` + `Included` scope say, after a red-first test per
Acceptance Criterion (Step 5), a runtime validation of the changed flow
(Step 8), and a coverage-and-quality gate (Step 9); run the plan's
`Verification` until exit 0, append a `## History` entry, then **stop** at a
manual-validation handoff. Success is exit codes, never intent — and a
criterion that needs human eyes is never self-certified.

## The implement pass

Copy this checklist and check off items as you complete them.

```
Implement Progress:
- [ ] 1. Read the plan artifact (frontmatter status first)
- [ ] 2. Resolve scope contract: Files to Modify + Included + Excluded
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Reconcile plan vs the actual repo (deviation triage BEFORE edits)
- [ ] 5. RED — capture core behavior from Acceptance Criteria (one test per AC, before any edit; confirm red for the right reason)
- [ ] 6. Implement exactly Files to Modify (scope discipline)
- [ ] 7. Run the plan's Verification; fix + re-run until all exit 0
- [ ] 8. Runtime UI validation (invoke validating-ui; console net + UX review; bounded fix loop)
- [ ] 9. Coverage-and-quality gate (rebalance layer guesses; re-prove meaningfulness; expand only on a real gap)
- [ ] 10. Update the plan (History entry; status per the user's convention)
- [ ] 11. Completion handoff summary + MANUAL validation steps; STOP
```

### Step 1 — Read the plan artifact

The skill starts only when given a plan artifact path. Read it before touching
any source — the prompt alone is not the spec; the plan is.

Git setup first (per `reference/git-workflow.md`): confirm the working tree is
on the plan's branch — `<type>/<name>` derived from the slug (e.g.
`fix-activity-image-delete` → `fix/activity-image-delete`), created from a
current `main` if it does not exist. Never work on `main`; only PRs merge.

- **No plan path given**, work is multi-file or schema-touching → route to
  `designing-architecture` and stop. This skill does not reverse-engineer a
  plan from a prompt; skipping the design stage destroys the auditability.
- **No plan path given**, single-file trivial change → just edit it; a plan
  costs more than the change (see "When not to use").

Read the frontmatter `status:` next:

- `approved` → proceed.
- `draft` → not approved. **Stop and confirm with the user** before editing
  ("the plan at `<path>` is `status: draft` — treat as approved, or hand back
  to design?"). Do not silently treat a draft as approved.
- `superseded` → do not implement; follow the `related:` pointer to the
  superseding plan.

A plan missing `Files to Modify`, `Verification`, or `Scope` is a contract
defect — route back to `designing-architecture` rather than improvising.

### Step 2 — Resolve the scope contract

The scope contract is three lists, read together:

1. **Files to Modify** — the only files you may create or edit; a file not on
   the list is out of scope. Do not tidy, refactor, or fix a pre-existing bug
   in it on the way past.
2. **Scope → Included** — what the plan delivers; confirms intent when a
   per-file note is ambiguous.
3. **Scope → Excluded** — the boundary you cite when refusing scope creep
   (non-empty by plan-format contract).

Hold the three in working memory for the whole pass; every "should I do this
too?" is checked against them.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from its rules file (`AGENTS.md` /
`.opencode/agents.md`). If a matching `references/stacks/<stack>.md` exists in
this skill's own directory (not the project's), read it now and apply its
implementation-time concerns. If none exists, proceed generically and flag the
gap in the handoff. The available stack references are listed under
**References**.

### Step 4 — Reconcile plan vs the actual repo (BEFORE editing)

Before editing, match every `Files to Modify` entry against what is on disk and
read each named file. Classify each mismatch immediately:

- **Mechanical** — the feature is unchanged; only a mechanical detail differs
  (file moved/renamed, import alias drift). Proceed at the corrected detail and
  record a dated `## History` note with the reason.
- **Contract-breaking** — the mismatch changes what is being built (a different
  feature, a schema differing from `Schema / Type Impacts`, an AC untestable as
  written). **STOP**. Do not edit source. Report the mismatch and route back to
  `designing-architecture`; the implementer never improvises a different design.

The dividing question is *does the difference change the feature being built?*
When in doubt, stop — a stop is recoverable, a built-wrong-feature is not. The
full classification table is in `references/deviation-protocol.md` (read it
when a mismatch is ambiguous).

### Step 5 — RED — capture core behavior from Acceptance Criteria

Before any source edit, author each testable AC as a failing test — one test
per AC, before the behaviour exists. Invoke the matching test-trio skill in its
**red-first, pre-implementation** mode (the right-layer table lives there).
**Run it: it must fail for the right reason** — the failure output names the
missing behaviour, not a fixture gap or a typo; fix the test's own setup until
it does. Record each AC → test file and the red evidence for the plan History
and the handoff at Step 11.

Honest stops: an AC whose verifier cannot produce a red-first test is
contract-breaking (Step 4); a red that never fails for the right reason is the
N-attempts stop (Step 7) — hand to `debugging-test-failures`. Do not proceed on
an unverified red; that silently turns red-first back into test-after.

Full contract, rationale, and the pre- vs post-implementation distinction:
`references/red-first.md`.

### Step 6 — Implement exactly Files to Modify (scope discipline)

Edit only the files named in `Files to Modify`, and only the changes the
per-file note plus `Included` scope describe.

- **The user asks for an adjacent extra** — refuse, citing the plan's
  `Excluded` list (or the absence from `Files to Modify`); record it as a
  follow-up in `### Follow-ups` under `## History`. In a framework exercise,
  capture the urge as a candidate per `reference/self-improvement.md`. Do not
  build it.
- **The code tempts a refactor** — refuse unless the plan names it; record it
  as a follow-up.

Every in-scope edit has a plan citation; every out-of-scope urge is recorded,
not built. A silent expansion destroys the diff ↔ plan mapping a reviewer
relies on.

### Step 7 — Run the plan's Verification (objective closure)

Run the commands from the plan's `## Verification` — not a generic `npm test`,
not a subset you chose. Fix within scope and re-run until **every** command
exits 0; exit codes are the only success signal (lint warnings included). A
verifier that fails only on one route is usually a compile/runtime error in
that route's lazily-imported component — check the stack reference before
blaming the sandbox.

Honest stops: N focused fix attempts without convergence → stop, report, and
hand to the debug stage (do not thrash); a verifier that cannot pass for any
in-scope implementation → contract-breaking (Step 4) — do not "win" it by
adding an out-of-scope dependency.

### Step 8 — Runtime UI validation (invoke validating-ui)

After green verification, invoke `validating-ui` (sibling skill). It owns the
changed-flow journey, the console net (errors **and warnings** block unless
dated-allowlisted), journey completeness, the bounded ≤2-cycle fix loop, and
the `council-ux` text-evidence review — do not restate its process here. A
delegated `council-ux` result is validated per
`reference/delegated-result-contract.md` (an **empty or malformed** result is a
**failed run**, never clean); a **transient** failure is retried, a
**deterministic** one is retried once then the vehicle is switched or the work
taken over inline, and the outcome is **recorded** in the handoff. A change
with **no visible UI** skips with an explicit note; a missing dev
server/chromium is recorded as DEFERRED, and the handoff carries the note.

Long delegated workstreams follow `reference/subagent-supervision.md`: bound
each dispatch to ≤ ~10 min, require a heartbeat file, and run
`scripts/watch_agent.py` while it works; long evals detach with a log and are
polled, never a blocking black box.

### Step 9 — Coverage-and-quality gate (rebalance + expand)

With real code in place:

- **(a) Rebalance** every Step-5 AC→test onto the cheapest layer that still
  exercises the behaviour; supersede a mislayered test by re-authoring it with
  the correct trio skill and re-proving it break → red → restore → green.
- **(b) Expand** only on a concrete gap the real implementation reveals (an
  error path, a boundary); re-prove every AC test still meaningful.

Cite the specific misclassification or gap — padding is refused. When there is
no gap, **say so explicitly** in the handoff ("coverage reviewed; no high-value
gap found beyond the AC set"). Full contract: `references/coverage-gate.md`.

### Step 10 — Update the plan artifact

Once verification is green, **append** to the plan — never rewrite prior
sections or clobber History:

- A dated `## History` entry: what was implemented + the verification result;
  any Step 4 mechanical deviation note.
- A `### Follow-ups` block under `## History` for Step 6's recorded asks.
- The frontmatter `status` only per the user's stated convention — if unknown,
  leave it and surface the question in the handoff. Do not pre-flip.
- Append the revision date to `revised:` (never replace the array).
- If the plan's slug is a `docs/ROADMAP.md` ID, flip that row to `done` with
  the date + PR link in the **same** PR (`reference/git-workflow.md` → Roadmap
  closure). A PR that closes a roadmap item but leaves the row `backlog` is
  incomplete.

The plan is the audit trail: a future reader reconstructs the plan, the action,
and any divergence from the plan file alone.

### Step 11 — Completion handoff summary; STOP

Present a **concise** handoff and wait. The sections — what changed,
acceptance-criteria status, red evidence, rebalancing outcome, coverage-gate
outcome, runtime-validation outcome, manual validation steps, plan state, PR
readiness, follow-ups, next step — are templated in
`references/handoff-template.md`; load it here. Never self-certify a criterion
that needs human eyes (mark it `manual — steps below`), and never answer a
required section with silence — an explicit negative is the closure signal.

Then **STOP** and wait. Do not commit/push/merge or open a PR unless the user
asks; do not move to the next roadmap item; do not run `reviewing-code` on
yourself.

## When not to use this skill

- **Single-file trivial change** (rename a helper, tweak a constant, fix a
  typo) — just edit it; a plan costs more than the change.
- **No plan exists and the work is multi-file or schema-touching** — route to
  `designing-architecture` first; this skill consumes a plan, it does not
  author one.
- **Authoring or revising the plan itself** — that is
  `designing-architecture`; this skill only appends History/follow-ups and
  optionally flips status per convention.
- **Deep multi-session debugging** — a failure that resists N fix attempts is
  a stop, not a thrash session; the debug stage owns it.
- **Pure research / explanation** — answer; do not implement.
- **Ranking a backlog or producing a plan** — `triaging-requirements` or
  `designing-architecture`.

## References

- `references/red-first.md` — Step 5's full contract: the pre-implementation
  red, the wrong-reason trap, the two honest-stop conditions, and how it
  differs from the post-implementation break/restore proof.
- `references/coverage-gate.md` — Step 9's full contract: rebalance, expand,
  and the meaningfulness re-proof.
- `references/deviation-protocol.md` — Step 4's classification table (every
  mechanical / contract-breaking / honest-stop case).
- `references/handoff-template.md` — Step 11's required handoff sections.
- `references/stacks/vue-supabase.md` — Vue 3 + Pinia + Supabase + PWA stacks.
- `references/stacks/skills-library.md` — this skills/agents Python+Node
  library itself.
- Upstream: `../designing-architecture/references/plan-format.md` — the plan
  artifact contract this skill consumes.
