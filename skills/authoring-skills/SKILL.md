---
name: authoring-skills
description: Author new agent skills, improve existing skills, and validate them with evals, following Anthropic best practices and the ai-framework library conventions. Use whenever the user wants to create a skill, turn a workflow or conversation into a skill, edit or optimize a SKILL.md, write skill evals, or asks how a skill should be structured, named, or described — even if they don't say the word "skill" (e.g., "capture this process so agents can reuse it").
metadata:
  library: ai-framework
  phase: "1"
---

# Authoring Skills

Author skills that a mid-tier model can execute reliably. The context window
is a public good: every line must justify its token cost once loaded.

Detailed guidance lives in two references — consult them at the steps below:

- [references/anthropic-best-practices.md](references/anthropic-best-practices.md)
  — distilled authoring guidance: progressive disclosure, descriptions,
  degrees of freedom, patterns, anti-patterns, quality checklist
- [references/opencode-spec.md](references/opencode-spec.md)
  — frontmatter rules, name validation, discovery paths, permissions

## The authoring loop

Copy this checklist and check off items as you complete them:

```
Authoring Progress:
- [ ] Step 1: Capture intent
- [ ] Step 2: Interview for specifics
- [ ] Step 3: Draft evals BEFORE the skill body
- [ ] Step 4: Draft the skill
- [ ] Step 5: Self-review against the checklist
- [ ] Step 6: Test with a fresh agent
- [ ] Step 7: Iterate on observed behavior
- [ ] Step 8: Finalize and install
```

### Step 1: Capture intent

Determine what the skill should enable and when it should trigger. If the
current conversation already contains the workflow (the user says "turn this
into a skill"), extract from history first: tools used, step sequence,
corrections the user made, input/output formats. Confirm the extraction with
the user before proceeding.

### Step 2: Interview for specifics

Ask about edge cases, input/output formats, success criteria, and
dependencies. Do not guess — the cost of one clarifying question is far
below the cost of a skill built on a wrong assumption. Establish:

1. What should the skill enable?
2. What user phrases/contexts should trigger it?
3. What is the expected output format?
4. Is the output objectively verifiable (favors eval assertions) or
   subjective (favors human review)?

### Step 3: Draft evals before the skill body

Write 2–3 realistic test prompts to `evals/evals.json` in the skill
directory — the kind of thing a real user would actually type, concrete and
specific (file paths, situational backstory, casual phrasing), not abstract
requests. Share them with the user for approval. Evals-first keeps the skill
solving real problems instead of documenting imagined ones.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "Realistic user request here",
      "expected_behavior": [
        "Observable outcome 1",
        "Observable outcome 2"
      ],
      "files": ["fixtures/sample-input.json"]
    }
  ]
}
```

**Evals must be self-contained.** Any file an eval depends on lives in
`evals/fixtures/` inside the skill directory and is listed in `files[]`
(paths relative to `evals/`). Fixtures left in `/tmp` or pointing at a
live repo make the eval unreproducible after the environment resets —
which means no regression testing on the next edit. Embedding fixture
content directly in the prompt is equally valid for text sources.

### Step 4: Draft the skill

Create `skills/<name>/SKILL.md` plus bundled resources as needed. Follow the
library conventions below and the detailed guidance in
[references/anthropic-best-practices.md](references/anthropic-best-practices.md).
Validate frontmatter against
[references/opencode-spec.md](references/opencode-spec.md).

Structure decisions:

- **Body <500 lines** (aim far lower). Approaching the limit means content
  belongs in `references/`.
- **`references/`** for detail loaded only when needed; link each file
  directly from SKILL.md with guidance on *when* to read it; one level deep
  only; TOC at the top of any reference >100 lines.
- **`scripts/`** for repetitive tasks with deterministic output. Signal to
  bundle a script: test runs show the model repeatedly writing the same
  helper. State clearly whether a script is to *execute* or to *read as
  reference*.
- **`assets/`** for templates/files used in output.

### Step 5: Self-review against the checklist

Re-read the draft with fresh eyes against the quality checklist in
[references/anthropic-best-practices.md](references/anthropic-best-practices.md).
Cut anything the model already knows. Challenge every paragraph: "does this
justify its token cost?"

### Step 6: Test with a fresh agent

Run each eval prompt against a fresh agent session with the skill installed
(subagent via the task tool, or a separate session). Where feasible, also
run a baseline without the skill for comparison. The author must not grade
its own memory — only the fresh agent's observable behavior counts.

Test with the models that will actually run the skill — at minimum one
Go-tier open model and one Zen-tier model (see
`reference/model-routing.md` at the repo root for current role bindings).
Guidance sufficient for a frontier model may underspecify for a mid-tier
one; that gap is a finding, not an annoyance. If the harness cannot vary
the model (e.g. subagents are pinned to one tier), document the deferred
validation in `evals.json` notes so it is re-run when the harness allows
— a documented deferral is honest; a silent skip looks like coverage.

For skills that must stop and ask the user before proceeding, a
single-turn eval cannot test the full behavior. Use a **two-turn
harness**: turn 1 expects the agent to stop at the gate and ask the
right questions; turn 2 resumes the same session with answers and
expects the answers recorded in the output artifact. Grade both turns.

### Step 7: Iterate on observed behavior

Generalize from feedback — the skill will run against prompts far outside
the eval set, so fix root causes rather than overfitting to eval wording.
Read the transcripts, not just outputs: remove sections that send the model
down unproductive paths; make prominent what it missed. Explain *why* things
matter instead of stacking ALL-CAPS MUSTs — all-caps is a yellow flag that
reasoning is missing. Repeat Steps 6–7 until evals pass and the user is
satisfied.

**Encode every fix as an eval assertion before declaring stable.** When a
test round finds a defect and you fix it, add an expected_behavior line
that asserts the fixed behavior (tag it, e.g. `[fix-verified]`). The
reports from a test round are ephemeral; `evals.json` is the regression
net. A fix that exists only in the skill body can be silently reverted by
a future edit — a fix that exists as an assertion cannot. Also scan skill
instructions and references for content that gives away eval answers
(project-specific examples mirroring eval scenarios): it inflates eval
results and leaks one project's details into a portable skill. Fixture
data may be project-flavored; instructions must not be.

### Step 8: Finalize and install

1. Offer to optimize the description: draft should-trigger and
   should-not-trigger phrasings and verify the description catches the
   former and excludes the latter. The near-misses matter most — queries
   sharing keywords with the skill that need something else.
2. Run `./install.sh` from the repo root and verify the symlink appears in
   the global skills directory.
3. Commit with a message noting what the skill covers and its eval status.

## Library conventions (ai-framework)

These apply to every skill in this library, on top of the general guidance:

- **Gerund names**: `writing-e2e-tests`, `iterating-on-ui` — never vague
  (`helper`, `utils`).
- **Evals are mandatory**: no skill merges without `evals/evals.json`.
- **Roles, not model IDs**: skills say "escalate to the `planner` role",
  never "use glm-5.2". Bindings live only in `reference/model-routing.md`.
- **No volatile facts in skill bodies**: prices, model names, deprecation
  dates, version-specific behavior all belong in dated files under the
  repo-root `reference/` directory.
- **Stack plugin pattern**: skill workflows stay framework-neutral.
  Stack-specific detail goes in `references/stacks/<slice>.md` scoped to
  that skill's discipline. The workflow includes a selection step:
  identify the project stack from its rules file (`AGENTS.md` /
  `.opencode/agents.md`), load the matching stack reference if present,
  proceed generically and flag the gap if not.
- **Loops close on objective signals**: test exit codes, screenshots,
  computed styles — a skill must never declare success from intent alone.

## Improving an existing skill

Enter the loop at Step 3: snapshot the current version, confirm or create
evals, then test the existing skill to establish a baseline before editing.
Preserve the skill's `name` (and directory name) unchanged. Diagnose before
rewriting — read transcripts of the skill in use where available.

## Writing style essentials

Imperative form. Third-person descriptions (they inject into the system
prompt). Consistent terminology — one term per concept throughout. Concrete
examples over abstract explanation. Provide one default approach with an
escape hatch, not a menu of options. Forward-slash paths only.
