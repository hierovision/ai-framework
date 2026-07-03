# Skill Authoring Best Practices (distilled)

Distilled from primary sources, retrieved 2026-07-03:

- Anthropic, "Skill authoring best practices" —
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Anthropic, `skill-creator` skill —
  https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Anthropic, "Equipping agents for the real world with Agent Skills" —
  https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Agent Skills specification — https://anthropics-skills.mintlify.app/spec/overview

Adapted where noted for a multi-model opencode environment.

## Contents

- Core principles
- Progressive disclosure (the three levels)
- Writing the description (triggering)
- Degrees of freedom
- Workflows and feedback loops
- Content guidelines
- Common patterns
- Scripts and executable code
- Eval-driven development
- Anti-patterns
- Quality checklist

## Core principles

**Concise is key.** The context window is a public good. Once a skill
loads, every token competes with conversation history and the actual task.
Default assumption: the model is already very smart. Only add context it
doesn't have. Challenge each piece: "Does this paragraph justify its token
cost?" A concise instruction block (~50 tokens) beats a tutorial-style
explanation (~150 tokens) that restates what the model knows.

**Explain the why.** Modern models have good theory of mind. Reasoning
("filter test accounts because they skew revenue metrics") generalizes to
edge cases; bare commands don't. Finding yourself writing ALWAYS/NEVER in
caps is a yellow flag — reframe with the reason instead.

**Test across the models you'll run.** Skills act as additions to models,
so effectiveness depends on the model underneath. What works for a frontier
model may underspecify for a mid-tier one; what a mid-tier model needs may
be redundant over-explanation for a frontier one. Aim for instructions that
work across the fleet. (Anthropic frames this as Haiku/Sonnet/Opus; in this
library it means Go-tier open models and Zen-tier proprietary models — see
repo-root `reference/model-routing.md`.)

**Iterate with the model, driven by observation.** Develop skills with one
agent ("author") and test with fresh agents ("users"). Watch real
trajectories: unexpected exploration order, missed references, over-read
sections, never-read files. Fix what's observed, not what's imagined. Ask
the agent to self-reflect when it goes off track while using the skill.

## Progressive disclosure (the three levels)

1. **Metadata** (name + description): pre-loaded into the system prompt for
   every installed skill, always paying rent (~100 words).
2. **SKILL.md body**: loaded only when the skill triggers. Keep under 500
   lines; far less is better.
3. **Bundled resources** (`references/`, `scripts/`, `assets/`): loaded or
   executed only as needed. Unlimited size; scripts can run without ever
   entering context.

Rules that follow:

- When SKILL.md approaches the limit, split content into `references/` with
  clear pointers about when to read each file.
- **References one level deep only.** Nested reference chains cause partial
  reads (`head -100`) and incomplete information. Every reference file links
  directly from SKILL.md.
- **TOC at the top of any reference file >100 lines** so partial reads still
  convey full scope.
- **Organize by domain/variant** when content is mutually exclusive
  (e.g., `references/stacks/aws.md` vs `gcp.md`) — the agent reads only the
  relevant one, keeping token usage flat as the skill grows.
- Name files descriptively (`form-validation-rules.md`, not `doc2.md`).

## Writing the description (triggering)

The description is the primary and near-sole triggering mechanism. The
agent chooses from potentially 100+ skills using descriptions alone.

- Include **both** what the skill does **and** when to use it — all
  "when to use" information goes in the description, not the body.
- **Third person only** ("Processes Excel files..."), because it injects
  into the system prompt; first/second person degrades discovery.
- Include specific trigger terms, file types, and user phrasings.
- **Be slightly pushy.** Models undertrigger skills. Extend the description
  with "Use whenever the user mentions X, Y, Z, even if they don't
  explicitly ask for W."
- Consider negative triggers ("not for X — use Y instead") when a
  neighboring skill competes.
- Simple one-step queries may not trigger skills at all — agents consult
  skills for tasks they can't trivially handle. Eval prompts must be
  substantive enough to benefit from the skill.

Naming: gerund form preferred (`processing-pdfs`, `writing-e2e-tests`);
lowercase/numbers/hyphens; never vague (`helper`, `utils`, `tools`).

## Degrees of freedom

Match specificity to task fragility — the robot-on-a-path analogy: open
field → give direction (high freedom); narrow bridge over a cliff → give
exact steps (low freedom).

| Freedom | Form | Use when |
|---|---|---|
| High | text heuristics | many valid approaches; context decides (code review) |
| Medium | pseudocode / parameterized template | preferred pattern exists; variation OK (report generation) |
| Low | exact script, "run exactly this" | fragile, error-prone, consistency-critical (migrations) |

## Workflows and feedback loops

**Checklist pattern** for complex multi-step tasks: provide a literal
checklist the agent copies into its response and checks off. Prevents
skipped validation steps and makes progress visible.

**Feedback loop pattern**: run validator → fix → re-run → only proceed on
pass. The "validator" can be a script (lint, tests, schema check) or a
reference document (style guide the agent checks output against). This
pattern is the single biggest quality lever.

**Conditional workflow pattern**: explicit decision points ("Creating new
content? → workflow A. Editing? → workflow B"). If branches grow large,
push each into its own reference file.

**Plan-validate-execute** for high-stakes/batch operations: have the agent
write a machine-checkable plan artifact (e.g., `changes.json`), validate it
with a script, and only then execute. Catches errors before they touch
anything real. Make validator errors verbose and specific ("Field
'signature_date' not found. Available fields: ...").

## Content guidelines

- **No time-sensitive information** in skill bodies ("before August 2025
  use the old API"). Use a "current method" section plus a collapsed "old
  patterns" section — or, in this library, quarantine volatile facts in the
  repo-root dated `reference/` files.
- **Consistent terminology**: one term per concept, throughout ("API
  endpoint" everywhere — not endpoint/URL/route interchangeably).
- **Concrete examples** (input → output pairs) where output quality depends
  on style; they beat abstract description.
- **Templates** for output structure: strict template when format is a
  contract; "sensible default, adapt as needed" when flexibility helps.
- **One default with an escape hatch**, not a menu ("Use pdfplumber; for
  scanned PDFs use pdf2image + pytesseract") — option lists cause dithering.

## Scripts and executable code

- Bundle scripts for deterministic, repetitive operations: more reliable
  than regenerated code, zero context cost until output returns.
- **Promotion signal**: if eval transcripts show the model writing the same
  helper in every run, promote it into `scripts/`.
- Make intent explicit: "Run `scripts/analyze.py`" (execute) vs "See
  `scripts/analyze.py` for the algorithm" (read).
- Scripts should solve, not punt: handle error conditions inside the script
  rather than failing out to the agent.
- No voodoo constants — justify every threshold/timeout in a comment. If
  the author can't justify the value, the agent can't adapt it.
- Don't assume packages are installed; state install commands.
- Forward-slash paths everywhere, even on Windows.

## Eval-driven development

Build evals **before** writing extensive documentation:

1. Run the target task without the skill; document specific failures/gaps.
2. Write ~3 scenarios that exercise those gaps.
3. Establish the without-skill baseline.
4. Write the minimum skill content that closes the gaps.
5. Re-run, compare, refine.

Eval prompts must be realistic: concrete file names, situational backstory,
casual phrasing, typos — what a user actually types, not "Extract text from
PDF." For trigger testing, include should-trigger and should-not-trigger
sets; the valuable negatives are near-misses that share keywords but need a
different tool.

Grade with observable assertions where outputs are objective; use human
review where they're subjective (writing style, visual design). Don't force
assertions onto judgment calls.

## Anti-patterns

- Windows-style paths (`scripts\helper.py`)
- Option menus without a default
- Nested reference chains (two+ levels deep)
- Time-sensitive facts in the body
- ALL-CAPS command stacks in place of explained reasoning
- Duplicated "when to use" info in the body (belongs in description)
- Bloated SKILL.md that should have been split into references
- Overfitting a skill to its eval prompts (fiddly rules matching eval
  wording rather than generalized guidance)
- First/second-person descriptions

## Quality checklist

Frontmatter

- [ ] Name: lowercase/hyphens, gerund form, matches directory
- [ ] Description: what + when, third person, trigger terms, slightly pushy
- [ ] Description: negative triggers if a sibling skill competes

Structure

- [ ] Body <500 lines (target far less)
- [ ] Large/conditional content split into `references/`, linked one level
      deep with when-to-read guidance
- [ ] TOC in any reference >100 lines
- [ ] Deterministic repetitive work in `scripts/` with execute-vs-read
      intent stated

Content

- [ ] Imperative form; explains why, not just what
- [ ] Concrete examples; consistent terminology; one default + escape hatch
- [ ] No time-sensitive facts; no model IDs (roles only — library rule)
- [ ] Feedback loops for quality-critical steps; checklists for multi-step
      workflows

Testing

- [ ] `evals/evals.json` with 2–3 realistic prompts (library rule:
      mandatory)
- [ ] Tested with a fresh agent, ideally against a without-skill baseline
- [ ] Tested on Go-tier and Zen-tier models
- [ ] Iterated on observed transcripts, not assumptions
