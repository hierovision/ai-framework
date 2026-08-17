---
name: designing-architecture
description: Turn ONE selected roadmap entry or direct feature request into a verifiable implementation plan that a separate build session can execute cold — then stop at user approval, never implementing. Researches the codebase, defines goal + objective acceptance criteria + boundaries, and writes a plan artifact. Use whenever the user says "plan this feature", "design the approach for X", "how should we build item N from the roadmap", "write an implementation plan", or surfaces a multi-file feature or a database/schema change needing design — even without saying the word "plan" or "design". Not for single-file trivial changes, pure research questions, or small edits to an existing plan (just edit it — but a full re-design pass over an existing draft IS this skill). For ranking a backlog, use triaging-requirements instead.
---

# Designing Architecture

Turn one selected work item into a plan artifact that a separate build
session can execute without having been part of the design conversation.
A design pass is **done** when the plan artifact exists, every acceptance
criterion is an observable, independently-verifiable check, and the user
has approved it. The skill stops at approval — it is planning-only. It
does not implement, run migrations, or edit source.

## The design pass

Copy this checklist and check off items as you complete them.

```
Design Progress:
- [ ] 1. Take one item (roadmap entry or direct request)
- [ ] 2. Resolve plan path & slug (configurable; revise-don't-clobber)
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Research the codebase
- [ ] 5. Extract goal, acceptance criteria, boundaries (ask if vague)
- [ ] 5b. UX consult: council-ux on user-facing items (explicit skip note if none)
- [ ] 6. Draft the plan artifact (full format in references/plan-format.md)
- [ ] 7. Self-check: every criterion is verifiable
- [ ] 8. Present summary + approval question; STOP
```

### Step 1 — Take one item

Take a single work item: one roadmap entry (identified by ID or "the
Nth from the roadmap") or one direct feature request. If the user gives
you a backlog or a pile of items, that is triage, not design — point them
at the `triaging-requirements` skill and stop. A design pass scopes to
one item so the plan can be executed cold by someone who was not in the
conversation.

If the user references a roadmap, read the entry for the named ID and
treat it as the seed for goal + scope. Do not plan the whole roadmap.

### Step 2 — Resolve plan path & slug

Read the project rules file (`AGENTS.md` / `.opencode/agents.md`) for a
`plans_dir:` or `plans:` key. Default to `.opencode/plans/` if none. The
plan file is always `<plans_dir>/<slug>.md`; the slug is the roadmap ID
when one exists, otherwise lowercase-kebab derived from the feature.

If a plan file already exists for the slug, **revise in place** —
preserve the frontmatter history and prior sections, append a dated
revision block, and add a `## History` entry. Never clobber. See the
"Revising an existing plan" section of
[references/plan-format.md](references/plan-format.md). If the approach
has fundamentally changed, supersede the old plan with a new slug and
point at it; do not silently replace.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from the rules file. If this skill bundles a
matching stack reference under `references/stacks/` (resolved against
this skill's own directory — not the project's), read it now and apply
its planning concerns. If none exists, proceed generically and flag the
gap in the plan's Open Questions — the absence of stack-specific
guidance is a finding, not a silent "I'll wing it."

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase (Postgres + Auth +
  RLS) with a PWA / offline outbox. Applies schema-first planning,
  generated-types handling, RLS planning, and offline/PWA checks.

### Step 4 — Research the codebase

Read the files the plan will touch and the files the feature will reuse:
stores, the data-access client, the schema and generated types, the test
setup, and the rules file's verification commands. Ground every
`Files to Modify` entry in files you actually read — a plan that names a
path you never opened is a guess, and a cold implementer will pay for
that guess. When a feature touches a schema, always read both the schema
source of truth (`db/schema.sql` or equivalent) **and** the generated
types file, so the plan describes the round trip, not just one side.

### Step 5 — Extract goal, acceptance criteria, boundaries

Pull three things out of the item + your research:

1. **Goal** — one sentence: what the feature achieves, stated as the
   user-facing outcome, not the implementation.
2. **Acceptance criteria** — observable behaviors with verifiers. This
   is the heart of the skill; downstream unit / integration / e2e skills
   consume these. Each criterion names the observable behavior **and** how
   to verify it (test command, Playwright selector, SQL/RLS query result,
   exit code, diff). A criterion that restates the feature description
   ("the timer works offline") without a verifier is incomplete — keep
   refining until the verifier is concrete, or move it to Open Questions.
3. **Boundaries** — included and excluded scope. An explicit Excluded
   list is what lets an implementer refuse scope creep with a citation.

**Two kinds of ambiguity, treated differently.** The skill asks before
drafting only when ambiguity is about *what feature is being built*, not
*how to build it*.

- **Feature-identity ambiguity → ask before drafting.** The request names
  a behavior whose meaning splits into distinct *features* — different
  interpretations produce different acceptance-criteria sets, not just
  different implementations. "Share a timer with someone" is this kind:
  read-only anonymous link, collaborative co-control, and exported
  snapshot are three different features with different data models and
  different observables. Picking one silently builds the wrong feature.
  Ask the dimensions that split the feature identity (read-only vs
  co-control; public vs authenticated; single recipient vs group; live
  vs snapshot). Do not draft until the feature is pinned.

- **Design-decision ambiguity → draft with defaults.** The feature is
  clear from the request and research; what remains open are
  implementation choices, each with a defensible default. "Add teams so
  users can share playlists with their team — needs new tables, design
  the approach" names the feature (team-based playlist sharing);
  invitation method, single-admin vs multi-admin, real-time vs snapshot
  refresh, and a member cap are *how* — they have sane v1 defaults and do
  not change what gets built. Write the plan now, record each open
  choice in `## Open Questions` with a proposed default, and surface them
  in the summary. An implementer can build the right feature and the
  user can swap defaults at approval.

The decision test: *"Given a defensible default for every open
dimension, would the implementer still build the right feature?"* If
yes → draft with Open Questions. If different defaults would build
different features → the request is feature-identity-ambiguous; ask.

When you do ask (feature-identity ambiguity), two situations:

- The user is **interactive and answering** → ask the clarifying
  questions and **wait**. Do not write the plan until the feature
  identity is pinned. Record the user's answers into the plan as design
  decisions, so an implementer reading cold sees the constraints the
  design was built on.
- The user is non-responsive for this turn or explicitly says "just
  decide" → proceed under one **labeled provisional** interpretation per
  open identity dimension, mark each provisional in the plan's Open
  Questions, and surface them at the top of the summary. A silent
  guess is indistinguishable from a decision; a labeled guess is honest.

The cost of one clarifying question on a feature-identity split is below
the cost of an implementable plan built on the wrong feature.

### Step 5b — Consult council-ux on user-facing items

Run the UX consult **only when the item changes user-facing behavior** —
a screen, form, dialog, or flow, or a change to existing UI. A pure-
backend or internal-logic item gets the explicit skip instead: record
`no user-facing UI — council-ux consult skipped` in the plan's History
and proceed. The explicit negative is the closure signal; do not invent
UI to review.

For a user-facing item, invoke `council-ux` (subagent_type `council-ux`)
**before drafting**, so concerns land in the plan, not in revisions:

- **Brief**: the goal, the draft acceptance criteria, the Included /
  Excluded scope, and the Step 4 codebase context — the components and
  patterns the feature will reuse.
- **Review areas**: loading / empty / error states, keyboard
  accessibility, color contrast, mobile responsiveness, form validation
  UX, error message clarity, onboarding friction, component / library
  consistency.
- **Contract**: text-only input — there is no UI to screenshot at plan
  time and council-ux is a text-only model; it judges the planned
  experience from the brief. Output is 3–5 concerns, advisory.

Fold each concern into the plan: a new or refined acceptance criterion
(with a concrete verifier), an Open Question (with a proposed default),
the Approach paragraph, or an Excluded entry. A concern with no
verifiable plan-time resolution is recorded as a residual follow-up for
the runtime validation handoff (`validating-ui`), never silently
dropped. One consult round — no plan-time fix loop.

Record the consult in `## History` (one line, dated): `UX consult via
council-ux; N concerns — folded into ACs / Open Questions / Excluded /
deferred to runtime validation`.

### Step 6 — Draft the plan artifact

Write the plan file at the path from Step 2. Use the fixed section
format in [references/plan-format.md](references/plan-format.md):

- Frontmatter (`slug`, `title`, `status: draft`, `created`, `revised`).
- `## Goal / Approach`
- `## Acceptance Criteria`
- `## Files to Modify`
- `## Scope` (Included / Excluded, both non-empty)
- `## Schema / Type Impacts` (`None.` only when there is truly none)
- `## Verification` (the project's actual commands)
- `## Open Questions` (non-blocking, each with a proposed default)
- `## History`

If the request is vague and you are in the interactive situation from
Step 5, **do not reach Step 6** until the questions are answered.

### Step 7 — Self-check (objective closure)

Re-read each acceptance criterion and ask: can a third party, given only
the verifier, tell whether it passed? Rewrite any that fail this test.
A design pass is **done** when, and only when:

- the plan artifact exists at the configured path;
- every acceptance criterion is observable and carries a concrete
  verifier (no "works well" / "is secure" / "looks right");
- the Included and Excluded scope are both present;
- schema/type impacts and verification reflect the project's actual
  commands from the rules file;
- **and** the user has approved.

Until the user approves, the pass is not done. The skill stops there.

### Step 8 — Present summary + approval question; STOP

Hand the user a short summary: the plan path, the goal line, the count
of acceptance criteria, the one-line scope boundary, and any Open
Questions the user must resolve. End with the explicit approval
question (e.g. "Approve this plan, or want revisions?"). Do not start
editing implementation files, running migrations, or regenerating types
— approval is the gate to the implement stage, and that stage may run in
a fresh session that loads the plan from disk.

If the user asks for revisions, revise the plan file (Step 6, preserving
history) and re-present. The skill never declares success from intent —
it declares success from a written, verifiable, approved plan artifact.

## When not to use this skill

- **Single-file trivial change** (rename a helper, tweak a style) → just
  edit it. A plan artifact costs more than the change.
- **Pure research question** ("what does this library do?", "why is
  this slow?") with no plan output desired → answer it; do not produce a
  plan.
- **A plan already exists and the user wants small edits to it** → edit
  the plan directly; a full design pass is not needed.
- **Ranking a backlog / reconciling many items** → that is triage; use
  the `triaging-requirements` skill.
- **Designing a release/operate pipeline** (CI/CD topology, deploy,
  migrations, CI security) → that is `designing-cicd` (and its siblings
  `deploying-with-supabase`, `deploying-to-azure-swa`, `securing-ci`) —
  this skill designs the feature; the DevOps skills design how it ships.
- **The user has already approved and wants implementation** → hand off
  to the implement stage; this skill stops at approval.

## References

- [references/plan-format.md](references/plan-format.md) — the plan
  artifact contract: frontmatter, section order, section schemas, the
  acceptance-criteria quality bar (with good/bad pairs), and the
  revise-don't-clobber rules. Read when drafting (Step 6) or revising.
- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — schema-first planning, generated-types handling, RLS planning, and
  offline/PWA checks for Vue 3 + Supabase stacks. Read at Step 3 when
  the project's rules file declares stack `vue-supabase`.