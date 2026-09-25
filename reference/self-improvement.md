# Self-improvement loop — exercises leave both repos better

## Contents

- The loop in one paragraph
- The exercise file
- Improvement candidates (upstream)
- Uplift ledger (downstream)
- The capture-don't-fix rule
- Promotion rules (session close)
- Registry tie-in

## The loop in one paragraph

When the framework is exercised on a target repo, the working session
captures framework-improvement **candidates** (fixed shape, below) in the
target repo's `.opencode/exercise.md` — captured, not fixed inline — and
records what the target repo **gained** in the same file's uplift ledger.
At session close, candidates are promoted to GitHub issues on
`hierovision/ai-framework` (triaged into its ROADMAP by the standing
triage pass), and uplift items are written into the target repo's own
three-tier memory (its `AGENTS.md`, its ADRs, its ROADMAP). The exercise
file itself is archived — essence lives in the repos, the archive is an
audit trail (ADR-0008).

## The exercise file

One file per target repo: `<target-repo>/.opencode/exercise.md`. Two
append-only sections: `## Improvement candidates` and `## Uplift ledger`.
Opened (or read) at exercise start — the ledger tells this session what
the last one left behind. At close: candidates promoted, uplift
converted, file moved to `<target-repo>/.opencode/plans/archive/`.

## Improvement candidates (upstream)

One block per candidate, appended mid-exercise the moment the gap is
observed — never batched from memory at the end:

```markdown
### Candidate: <kebab-slug>
- date: YYYY-MM-DD
- skill: <skill-name> (or `framework`)
- observed: <what actually happened>
- expected: <what the skill's guidance should have produced>
- correction: <proposed change — behavior, not vibes>
- evidence: <transcript / log / run reference>
- status: proposed
```

Promotion (session close): each candidate with evidence becomes a GitHub
issue on `hierovision/ai-framework` — the block verbatim as the body,
labeled `skill-improvement` — and the local block's status flips to
`promoted to issue #N (<date>)`. The standing triage pass consumes those
issues like any other source; adoption then follows the normal loop
(design → evals-first fix → review). A candidate without evidence is
superseded, not silently promoted.

## Uplift ledger (downstream)

One dated entry per exercise, written as the work happens:

```markdown
### YYYY-MM-DD — <exercise name>
- standing rules added: <cross-session imperatives the repo learned>
- decisions recorded: <ADR-n or proposed ADR topics>
- roadmap: <rows added/updated in the target repo's ROADMAP.md>
- gates added: <CI checks, validators, evals the repo gained>
```

Promotion (session close): standing rules → the target repo's own
`AGENTS.md` (cross-session imperatives only — no process knowledge, no
per-session state); decisions → the target repo's own `docs/ADRs/` with
maturity status; priorities/backlog → its own `ROADMAP.md`. The ledger
is a working artifact — its essence is extracted before close and the
file is archived. **No archive-as-memory tier.**

## The capture-don't-fix rule

Candidates are captured, not fixed inline. Editing a skill mid-exercise
would (a) fork the consumer's feature branch with framework changes and
(b) skip the evals-first protocol the library requires for skill changes.
The only exception is already the library's rule: a framework tweak that
is *required by the feature* is part of the feature's scope, done
properly, and recorded as a deviation. Everything else is a candidate.

## Registry tie-in

Exercises are the evidence source for the registry's L2→L3 promotion bar
(ADR-0009): a skill that performed in a real loop, with evals green and
independent review, accumulates promotion evidence — recorded in the
harvest (RM-012), applied by the standing triage pass.
