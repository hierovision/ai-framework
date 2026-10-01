# Technical English Baseline

The communication convention for every agent in this library. A **baseline**,
not a style manual: only the parts of standard technical English that make
AI-to-AI and AI-to-human engineering communication clearer. Established
2026-08-14; every `agents/*.md` file points here. When a skill or agent
specifies stricter style rules, the stricter rule wins for its artifacts.

## Why

Agent output is consumed by an experienced engineer who skims. The reader
knows software and knows agents; what they do not know is this project's own
wording. A reply that buries its result, rotates synonyms, or uses workshop
words costs re-reading. The rules below exist to keep every output **plain,
short, and readable at a glance**.

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

9. **End with next.** Every response closes with a `## Next` section — the
   single logical next step in the current effort, with the actor. Never
   omit it, including in short or purely informational replies; when
   nothing is pending, write `None — awaiting <X>`. Handoffs say, in that
   order: done → verified → blocked → next, in the fewest sentences (what
   was completed, what is verified and how, what blocks progress, what
   the next step is).

10. **Scope.** This governs engineering communication — agent responses,
    analyses, plans, reports, summaries, commit messages, and doc edits.
    Ordinary conversation with the user is not subject to item 2's
    word-blacklist; it is subject to 1, 3, 4, 7, 9, 11, 12, and 13
    (clarity beats politeness padding, but be a person, not a robot).

11. **Approval asks carry the full link.** When asking the user to approve,
    merge, or review a pull request (or issue), include the
    repository-qualified URL and title — never a bare number, branch name,
    or file path. The user works several repos at once; an unlinked ask is
    incomplete.

12. **Lead with the answer; keep it short.** State the status or result in
    the first line, then only the evidence that supports it, then a path or
    link for digging deeper. A routine update is one short paragraph. A
    normal reply stays under about 15 lines. Cut anything that does not
    change what the reader knows or does.

13. **One fixed word per idea; explain only our own words.** Industry terms
    (`PR`, `CI`, `API`, `schema`, `migration`, `AC`) need no explanation.
    This project's own words are defined once in `reference/glossary.md`
    and used exactly as defined — never workshop words around the user. Do
    not rotate synonyms: one word per idea for the whole session. A word
    that is neither in the glossary nor standard industry vocabulary is
    defined in the same sentence.

## Enforcement

- The rule is a prompt-level baseline: every agent references this file.
  It is not a hard technical constraint — treat violations as
  self-correctable drift.
- The `reviewing-code` review pass checks artifact language against items
  1-13 when reviewing a diff or handoff.
- If an agent's output violates the baseline, point at the specific rule;
  do not restyle wholesale.