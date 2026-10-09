---
name: facilitating-product-vision
description: "Facilitates an owner-led product vision session and produces a vision artifact plus an outcome-based slice roadmap (Now/Next/Later themes sliced into testable units with success measure + blocked-by). Use when the user says 'define/refresh the product vision', 'our roadmap is too lean', 'turn the vision into slices', 'run a vision/strategy session', or 'help me shape the product direction'. Not for: ranking an existing backlog (triaging-requirements), planning one named item (designing-architecture), persisting a roadmap as issues (managing-github-issues), refining a single issue's ACs (refining-issue-acceptance), or read-only product analysis of a draft (council-product). The phrase 'product vision' is the trigger — this skill is about product/strategy, not visual UI critique; UI/screenshot 'vision' reviews belong to council-ux/validating-ui."
---

# Facilitating Product Vision

Run a structured, owner-led session that turns product ambition into a
vision artifact and an outcome-based slice roadmap. The output is two
artifacts (vision document + provisional `ROADMAP.md` rows) plus a
working session record — never a rebuild of an existing roadmap and
never a strategy invented under the owner's name.

The session is owner-driven. Every judgment call is owner-owned and
recorded with a one-line rationale; the facilitator does not invent
strategy. The artifact is the contract: a separate reviewer reads it
cold and must be able to defend the strategy and slice plan.

## Contents

- The session (process checklist)
- Step 1 — Inputs & constraints (incl. Step 1a — decide the session mode)
- Step 2 — Strategy batch + Checkpoint 1
- Step 3 — Roadmap batch + Checkpoint 2
- Step 4 — Compliance & phase gates + Checkpoint 3
- Step 5 — Write the artifacts
- Step 6 — Council consults and handoffs
- Boundary routing
- References

## The session (process checklist)

Copy this checklist and check off items as you complete them. Owner
checkpoints are batched into three decision points — not one pause per
piece — to keep the session conversational and avoid late-session
rubber-stamping.

```
Vision Session Progress:
- [ ] 1. Inputs & constraints (ambition, current assets, envelope, non-negotiables, vision-artifact home)
- [ ] 1a. Decide mode (interactive multi-turn | declared one-shot | decisions pre-supplied inline) — the mode determines what fills Open Questions and what the final response must say
- [ ] 2. Strategy batch draft (vision, segments+JTBD, alternatives+non-goals+anti-vision, value model, north star + guardrails)
- [ ] 2a. CHECKPOINT 1 — strategy batch: present draft as questions-with-proposals; owner decides, every call recorded (skipped only when decisions are pre-supplied — recorded instead)
- [ ] 3. Roadmap batch draft (3–6 outcome themes banded Now/Next/Later under the capacity envelope; each theme sliced into testable units: AC + success measure + blocked-by + sizing; risk-first ordering)
- [ ] 3a. CHECKPOINT 2 — roadmap batch: same Q-with-proposal cadence (skipped only when decisions are pre-supplied — recorded instead)
- [ ] 4. Compliance & phase gates draft (consent/privacy/regulatory milestones, phase gates that unlock later segments)
- [ ] 4a. CHECKPOINT 3 — compliance + gates: confirm gates and owners (skipped only when decisions are pre-supplied — recorded instead)
- [ ] 5. Write artifacts (vision doc at the owner-confirmed home using EXACT Title-Case headings and Slices column labels; append theme + slice rows to ROADMAP.md per the sibling format; record the session as a working artifact)
- [ ] 6. Optional council consults + handoffs (triaging-requirements ranks, designing-architecture plans the top slice)
```

## Step 1 — Inputs & constraints

Capture what the strategy is constrained by. Read the consumer's
existing decision-doc convention (an `AGENTS.md`, a `docs/`, an ADR
index) for the project name, the team's pre-existing context, and the
canonical home for a long-lived document.

Ask the owner, and record in a one-line recap:

- **Ambition** — what the product is for, in the owner's own words.
- **Current assets** — what already exists (live code, design system,
  installed skills, an established `ROADMAP.md`, a prior vision doc).
- **Budget / time envelope** — team capacity, regulatory deadlines,
  quarters the session is planning into.
- **Non-negotiables** — pre-decided constraints the strategy must
  respect (legal posture, a platform commitment, a partner contract).

Then ask the **canonical home for the vision artifact** and record the
owner's answer. The vision artifact's path is a consumer decision, not
a default. The skill cites the artifact's content contract
(`references/artifact-format.md`, resolved against this skill's own
directory — not the project's); the owner decides where it lives.

If the owner names an established `ROADMAP.md`, read it. The session
appends to it; it never rebuilds it from scratch (the
established-once rule below).

### Step 1a — Decide the session mode

Three modes, picked from the prompt before drafting starts. The
mode determines what fills the artifact and what the final response
is required to say. Pick one and stay in it for the whole session:

- **Interactive multi-turn (default).** The session pauses at each
  of the three checkpoints and asks the owner. Owner decisions are
  recorded in-session as they are given.
- **Declared one-shot (no back-and-forth).** The owner has said
  they cannot answer back (e.g., "this is a one-shot, I'll read the
  doc later"). The session still writes the artifact (it does not
  end with an intention to write it later). Sections that require
  owner input — Segments & Jobs-to-be-Done, Alternatives &
  Non-goals, Value & Business Model, North Star + Guardrails,
  Compliance & Phase Gates, the capacity envelope — get a
  placeholder of the form
  `Open question: <what is needed, which section it will land in>`
  rather than invented content. The final response addresses the
  owner and lists every open question in plain text — using the
  literal words "owner" and "question" — so the consumer can
  recover the artifact on a later pass. The session does not
  present an invented strategy as decided.
- **Decisions pre-supplied inline.** The owner has already supplied
  every (or most) owner decisions for THIS run in this turn's
  prompt, or in an owner-notes file the session has read. Each
  pre-supplied decision is recorded as a decision with its source
  cited. Anything the owner has NOT pre-supplied is surfaced as an
  Open Question. The session does not invent the missing inputs.

The boundary between *interactive* and *pre-supplied* is whether
the owner can answer back; the boundary between *one-shot* and
*pre-supplied* is whether the owner has already given the
decisions. A prompt that says "complete in one pass, here are the
answers" is *pre-supplied*, not one-shot: the decisions exist;
they are recorded. A prompt that says "I can't answer, write what
you can" is one-shot: the decisions do not exist; they are
surfaced.

## Step 2 — Strategy batch + Checkpoint 1

Draft the strategy batch. Read
[references/artifact-format.md](references/artifact-format.md) (resolved
against this skill's own directory) for the fixed section order and
section schemas — the body cites it, never duplicates it. Cover:

1. **Vision statement** — one paragraph (≤120 words). The owner can
   quote it in a hallway.
2. **Segments & jobs-to-be-done** — segments are durable user-types;
   JTBD is the verb-form job. Every segment's job is visibly
   underserved today; no segment without a workaround.
3. **Alternatives & non-goals (incl. anti-vision)** — three
   sub-blocks: alternatives considered and the one-line reason each
   was set aside; non-goals (with a one-line reason each); and an
   anti-vision (the *opposite* outcome the strategy is designed to
   prevent — concrete, not generic).
4. **Value & business model** — how value is captured; defensible in a
   board meeting ("we make money because X").
5. **North Star + guardrails** — one metric that captures value
   capture (not vanity) plus 2–4 guardrails the strategy refuses to
   regress.

**Checkpoint 1 (strategy batch).** Stop. Present the draft as
questions-with-proposals, not as a fait accompli. Every judgment call
is owner-owned and recorded with a one-line rationale. Do not proceed
to themes or slices until the strategy batch is decided.

## Step 3 — Roadmap batch + Checkpoint 2

Draft the roadmap batch.

1. **3–6 outcome themes** — what the product is *trying to make true
   for users* over each horizon. Themes are banded under three
   horizons: **Now** (this quarter), **Next** (this half),
   **Later** (this year, may slip). Apply the **capacity envelope**
   (a throughput ceiling the owner gives) at the *theme* level — a
   `Later`-banded theme sized `L` is a mis-fit the table exposes.
   Themes without slices in the next step are not themes; cut or
   rewrite.
2. **Slices per theme** — the smallest unit of work that ships
   user-visible value and is independently testable. Every slice
   carries: an observable AC; a success measure (the *metric* that
   proves the slice delivered value, not just the build AC); a
   blocked-by mapping (the slice(s) or external dependency this
   slice cannot start without; `[]` if none); and a sizing (S/M/L
   or person-weeks, the owner's call — do not invent hours from
   nothing). A slice without all four is a feature, not a slice.
3. **Risk-first ordering** — the slice that proves the scariest
   assumption lands first. A roadmap of mutually independent slices
   is suspicious; the blocked-by column surfaces the dependency
   graph the owner uses to sequence work.

**Checkpoint 2 (roadmap batch).** Same Q-with-proposal cadence. The
owner confirms the themes, the horizon banding, the capacity
envelope, and the slice plan; the facilitator records every call.

## Step 4 — Compliance & phase gates + Checkpoint 3

Weave in the compliance and phase-gate milestones the strategy must
satisfy to ship. Each gate names the slice(s) it gates and the entity
that owns the gate (security review, legal, the owner). A strategy
that ships without naming its gates is a strategy the team will
discover its gates inside an incident.

Examples of gates to ask about (the list is owner-supplied, not
assumed):

- **Consent / privacy** — student-data slices, PII, regional
  residency.
- **Regulatory** — FERPA, HIPAA, GDPR, SOC 2, district contracts.
- **Phase gates that unlock later segments** — a private beta that
  must clear before the Next horizon opens, a compliance review that
  must land before a regulated feature ships.

**Checkpoint 3 (compliance + gates).** Confirm each gate and its
owner. This is the last decision point before artifact writing.

## Step 5 — Write the artifacts

Three artifacts, one session:

1. **Vision document** at the owner-confirmed home (Step 1). Follow
   the fixed section order in
   [references/artifact-format.md](references/artifact-format.md) —
   the contract a cold reviewer can defend. If a section has no
   content for this item, write `None.` rather than omitting it; an
   empty section is a signal, not a deletion. Now/Next/Later band
   headers appear under the *Outcome Themes* section.

   The top-level section headings are EXACT and Title-Cased; do
   NOT paraphrase or lowercase them — a typed assertion (and a cold
   reviewer) reads the literal wording:

   ```markdown
   ## Inputs & Constraints
   ## Vision Statement
   ## Segments & Jobs-to-be-Done
   ## Alternatives & Non-goals     (incl. anti-vision)
   ## Value & Business Model
   ## North Star + Guardrails
   ## Outcome Themes               (Now / Next / Later; capacity-envelope applied)
   ## Slices                       (per slice: AC + success measure + blocked-by + sizing)
   ## Compliance & Phase Gates
   ## Open Questions               (owner decisions, not invented strategy)
   ```

   The Slices table uses these EXACT column labels (do NOT rename
   them — "outcome metric" / "dependency" / "dependencies" lose
   the contract):

   ```markdown
   | Slice | Outcome theme | AC (observable) | Success measure | Blocked-by | Sizing |
   ```

   The literal phrases `success measure` and `blocked-by` appear
   as column labels AND in the final response text when the
   session describes the slice plan, so a typed text-assertion can
   detect them. The capacity envelope is applied at the *theme*
   level (a `Now`-banded theme sized `L` is a mis-fit the table
   exposes).
2. **ROADMAP.md rows** (theme + slice). Conform to the item-row
   schema and frontmatter of the sibling format
   [`../triaging-requirements/references/roadmap-format.md`](../triaging-requirements/references/roadmap-format.md)
   (exact sibling-relative path; the path resolves in both the repo
   and the symlinked global install). Outcome/Now-Next-Later
   semantics are recorded via the roadmap's `rubric:` frontmatter +
   the `Notes` cell (e.g. `horizon: Now; capacity: M`), not as new
   columns. A first-class Now/Next/Later column or success-measure
   column is an ADR-gated schema extension and is excluded from v1.
3. **Session record** as a working artifact under the consumer's
   plan convention (the same path `designing-architecture` uses for
   plans — usually `.opencode/plans/`). The record is a working
   artifact: the dated transcript of decisions and rationale, not
   part of the published docs.

**Established-once rule.** The session emits **themes + provisional
slices** and appends them to the existing `ROADMAP.md`. It never
rebuilds an established `ROADMAP.md` from scratch — that violates the
durable-merger contract. **`triaging-requirements` owns scoring,
ranking, and the durable merge**; the next triage pass scores the
provisional rows, ranks them, and folds them into the published
order. The session is upstream of triage, not a replacement for it.

**One-shot honesty rule.** When the session cannot get live owner
input (see Step 1a modes), the behavior is a hard mandate, not a
soft preference:

- The session STILL writes the artifact — it does not end with an
  intention to write it later, and it does not silently proceed as
  if the owner had answered.
- Sections that require owner input — Segments & Jobs-to-be-Done,
  Alternatives & Non-goals (incl. anti-vision), Value & Business
  Model, North Star + Guardrails, the capacity envelope, Compliance
  & Phase Gates — get a placeholder of the form
  `Open question: <what is needed, which section it will land in>`
  rather than invented content. The session never invents strategy
  under owner-owned sections.
- The final response addresses the owner and lists every open
  question in plain text — using the literal words "owner" and
  "question" — so the consumer can recover the artifact on a later
  pass and a typed text-assertion can detect the ask.
- A vision with no open questions has either been completely
  decided (rare; record the session date and skip the question)
  or is silently inventing strategy — the cardinal failure mode.

## Step 6 — Council consults and handoffs

**Optional council consults.** At each checkpoint, the owner may
invoke the council for one review round (e.g. `council-product` on the
strategy batch, `council-ux` if a Now-horizon slice changes visible
behavior). The consult is **advisory** and uses the
`agents/council.md` delegated-result contract (cite it at the call
site); an empty or malformed result is a failed run, never a silent
clean. The facilitator drives; the owner decides; the consult's
output is recorded in the session record with its outcome (clean /
fallback / explicit skip). One round per batch — no fix loop.

**Handoffs.** When the artifacts are written, the session hands off:

- `triaging-requirements` — scores and ranks the provisional rows
  and folds them into the published `ROADMAP.md` order.
- `designing-architecture` — plans the top-ranked slice into a
  verifiable plan artifact, then stops at user approval.

This skill duplicates neither. It produces themes, slices, and the
vision document; the next two skills take it from there.

## Boundary routing

| Request | Route |
|---|---|
| Run a vision / strategy session, define or refresh the product vision, turn a wishlist into outcome themes + slices | this skill |
| Scattered ideas wanting structure, "shape the product direction", "what should we be working on" (ambiguous) | this skill (asks the owner which mode) |
| Rank / score an existing backlog; update an established `ROADMAP.md` | `triaging-requirements` (not this skill) |
| Plan ONE named item from the roadmap into an implementation plan | `designing-architecture` (not this skill) |
| Persist an established `ROADMAP.md` as GitHub issues | `managing-github-issues` (not this skill) |
| Refine a single issue's acceptance criteria | `refining-issue-acceptance` (not this skill) |
| Read-only product analysis of an existing draft / strategy doc | `council-product` lens (not this skill) |
| UI / screenshot "vision" review (perceptual, visual) | `council-ux` / `validating-ui` — "vision" there is perceptual, not product/strategy (collision guard) |
| Author a slice's unit / integration / e2e tests | the test trio (`writing-unit-tests`, `writing-integration-tests`, `writing-e2e-tests`) |
| Run the session in a consumer project — what comes back, where the artifacts live | see [references/consumer-session.md](references/consumer-session.md) (this skill) |

The five siblings named in the description — `triaging-requirements`,
`designing-architecture`, `managing-github-issues`,
`refining-issue-acceptance`, `council-product` — own the rows this
skill does not own: ranking, plan-writing, issue persistence,
AC-refinement, and read-only product lens work. This skill produces
strategy + slice plan; it does not score, plan, or persist.

**A route is a spoken action, not a silent refusal.** When the
session identifies that the request is outside this skill's domain
and either loads a sibling skill to handle it or declines because
the request belongs to a sibling, the final response MUST name that
sibling skill by its exact directory name (`triaging-requirements`,
`designing-architecture`, `managing-github-issues`,
`refining-issue-acceptance`, `council-product`) and state the
one-line boundary reason. A silent use of the sibling skill (the
agent calls the sibling via `skill`/`task` tool calls but never
names it in the final response) leaves the consumer unable to
verify the route and a typed routing assertion cannot detect it.
The boundary reason is stated, not implied — e.g., "routing to
`triaging-requirements`: ranking an existing backlog is owned by
triage, not by this skill."

## References

- [references/artifact-format.md](references/artifact-format.md) — the
  vision artifact's fixed section vocabulary and section schemas
  (read in Step 2 before drafting; in Step 5 before writing). Resolved
  against this skill's own directory.
- [references/consumer-session.md](references/consumer-session.md) —
  generic consumer adoption flow: how a consumer repo runs the
  session against a named roadmap item, what comes back, the
  checkpoint cadence (read when a consumer is on the other end of
  the table).
- [`../triaging-requirements/references/roadmap-format.md`](../triaging-requirements/references/roadmap-format.md) —
  the sibling's `ROADMAP.md` schema, section order, item-row shape,
  and merge table. The session's emitted rows conform to it. Cited
  by exact sibling-relative path; the path resolves in both the
  repo layout and the symlinked global install.
- `agents/council.md` — the council consult protocol + the
  delegated-result contract. Cite at the call site when invoking a
  lens; the contract is non-negotiable (empty / malformed result =
  failed run).
