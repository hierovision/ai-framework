# Technical English Baseline

The communication convention for every agent in this library. A **baseline**,
not a style manual: only the parts of standard technical English that make
AI-to-AI and AI-to-human engineering communication clearer. Established
2026-08-14; every `agents/*.md` file points here. When a skill or agent
specifies stricter style rules, the stricter rule wins for its artifacts.

## Why

Agent output is consumed by other agents and by humans under time pressure.
Ambiguity, filler, and invented vocabulary cost real cycles: a plan whose
wording wobbles produces wrong acceptance criteria; a report padded with
filler buries its verdict. The rules below exist to keep every output
**plain, precise, and parseable**.

## Rules

1. **Plain words, standard engineering terms.** Say `plan artifact`,
   `acceptance criterion (AC)`, `handoff`, `subagent`, `red-first` — the
   library's shared vocabulary — and name files, commands, and identifiers
   exactly, in backticks. Do not invent synonyms for things that already
   have names.

2. **No filler.** Cut LLM-typical padding: *delve, leverage, robust (as
   filler), seamless, cutting-edge, comprehensive, streamline, empower,
   ensure (unless you actually ensure something), delve into, in order to
   (say "to")*. Say what happened, what is needed, what blocks.

3. **One idea per sentence; short sentences.** If a sentence needs three
   commas to hold together, split it. Prefer active voice where the actor
   matters: "the test failed" over "it was observed that the test failed".

4. **Exact numbers over approximations.** State counts, sizes, and
   thresholds precisely (`3 retries`, `60s timeout`, `2 ACs`). Use
   approximations only when the thing is genuinely approximate — and say
   that it is.

5. **Consistent shared vocabulary.** Use the repo's role names
   (`planner`, `implementer`, `triager`, `council-*`), artifact names
   (`ROADMAP.md`, plan, AC, handoff), and skill names verbatim. Do not
   re-describe them with fresh phrasing.

6. **Define abbreviations once, then reuse.** The first use spells out the
   term (`acceptance criteria (AC)`); afterwards `AC` is fine. Never invent
   jargon; if a concept has no name, name it once in the artifact and use
   that name consistently.

7. **State uncertainty explicitly.** Say `unverified`, `vendor-stated`,
   `assumed`, `needs confirmation` rather than hedging with "maybe",
   "perhaps", "it seems". Uncertainty with a label is actionable; hedging
   is not.

8. **Structured output aids parsing.** Use headers, lists, and tables for
   anything more than a few lines. Code and identifiers go in backticks.
   No emoji or decorative formatting in engineering artifacts (plans,
   reports, ACs, summaries).

9. **Handoffs say: done → verified → blocked → next.** In that order, in
   the fewest sentences. What was completed, what is verified (and how),
   what blocks progress, what the next step is.

10. **Scope.** This governs engineering communication — agent responses,
    analyses, plans, reports, summaries, commit messages, and doc edits.
    Ordinary conversation with the user is not subject to item 2's
    word-blacklist; it is subject to 1, 3, 4, and 7 (clarity beats
    politeness padding, but be a person, not a robot).

## Enforcement

- The rule is a prompt-level baseline: every agent references this file.
  It is not a hard technical constraint — treat violations as
  self-correctable drift.
- The `reviewing-code` review pass checks artifact language against items
  1-9 when reviewing a diff or handoff.
- If an agent's output violates the baseline, point at the specific rule;
  do not restyle wholesale.