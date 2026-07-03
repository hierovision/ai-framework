# AI Framework — Skill Library Plan

Status: APPROVED DIRECTION — decisions locked 2026-07-03 (see Decisions)
Date: 2026-07-03
Repo: https://github.com/hierovision/ai-framework.git

## Vision

A portable, versioned library of agent skills that covers current and future
engineering needs across all projects. Two durable feedback loops anchor the
library:

1. **Core engineering loop** — feature work verified by tests (unit,
   integration, e2e).
2. **UI iteration loop** — visual refinement verified by Playwright
   screenshots and computed CSS.

Built for longevity: knowledge that has proven stable over years of agentic
engineering (progressive disclosure, feedback loops, plan-then-execute,
verification gates) lives in skills; volatile bindings (model IDs, pricing,
provider quirks) live in small, dated reference files that are cheap to
update.

## Research Foundation (primary sources, retrieved 2026-07-03)

| Source | Key takeaways |
|---|---|
| [Anthropic: Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Concise is key ("context window is a public good"); 3-level progressive disclosure (metadata → SKILL.md body <500 lines → bundled resources); description is the trigger mechanism — third person, what + when + key terms; degrees of freedom matched to task fragility; feedback loops (run validator → fix → repeat); eval-driven development BEFORE writing docs; references one level deep; TOC for files >100 lines; no time-sensitive info in body |
| [Anthropic: skill-creator skill](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) | Canonical meta-loop: capture intent → interview → draft → 2-3 realistic test prompts → run with/without skill → human review + quantitative evals → generalize from feedback → repeat. Descriptions should be slightly "pushy" (models undertrigger). Explain the *why* instead of heavy MUSTs. Bundle scripts when test runs repeatedly reinvent the same helper |
| [Anthropic: Equipping agents for the real world](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | Start with evaluation of real gaps; structure for scale (split mutually-exclusive contexts into separate files); think from the model's perspective; iterate with the model capturing its own successful approaches |
| [opencode: Agent Skills](https://opencode.ai/docs/skills/) | Discovery paths: `.opencode/skills/`, `~/.config/opencode/skills/`, `.claude/skills/`, `~/.claude/skills/`, `.agents/skills/`, `~/.agents/skills/`. Frontmatter: `name` + `description` required; `license`, `compatibility`, `metadata` optional. Name regex `^[a-z0-9]+(-[a-z0-9]+)*$`, must match dir name. Pattern-based skill permissions per agent |
| [opencode: Zen models](https://opencode.ai/docs/zen/) | Current catalog + pricing + deprecation schedule (see `reference/model-routing.md`) |
| [opencode: Go models](https://opencode.ai/docs/go/) | Flat $10/mo subscription; GLM-5.2, Kimi K2.7 Code, Qwen3.7 Max/Plus, DeepSeek V4 Pro/Flash, MiniMax M3/M2.7, MiMo-V2.5/Pro. Usage limits in dollar value |

## Design Principles (the stable factors)

1. **Skills carry the knowledge; agents are thin bindings.** The current pt
   setup inverts this (skills point at agent files). Skill bodies are
   model-agnostic and portable across harnesses (opencode, Claude Code,
   anything honoring the Agent Skills spec). Agent definitions (model,
   temperature, permissions) are per-project config that reference skills —
   they churn with the model market; skills don't.
2. **Progressive disclosure everywhere.** SKILL.md <500 lines; stack- and
   tool-specific detail in `references/`; deterministic operations in
   `scripts/`; references one level deep.
3. **Loops close on objective signals.** Core loop closes on test exit codes.
   UI loop closes on screenshot + computed-CSS evidence. Never on "looks
   done."
4. **Generic core, stack-specific references.** Each skill's workflow is
   framework-neutral; per-stack knowledge (Vue/Vuetify, Supabase, Playwright)
   lives in reference files selected at runtime. Adding a new stack = adding
   a reference file, not rewriting a skill.
5. **Volatile facts are quarantined and dated.** Model IDs, prices,
   deprecations live only in `reference/model-routing.md` with a
   retrieved-on date. Skills refer to *roles* (planner, implementer,
   reviewer, vision-critic), never model IDs.
6. **Eval-driven authoring.** Every skill ships with `evals/evals.json`
   (2-3 realistic prompts + expected behavior). The `authoring-skills` skill
   enforces this.

## Proposed Repository Layout

```
ai-framework/
├── README.md                 # what this is, how to install
├── PLAN.md                   # this document
├── install.sh                # symlink/copy into discovery path(s)
├── skills/
│   ├── authoring-skills/     # THE META-SKILL — built first
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── anthropic-best-practices.md   # distilled, cited
│   │   │   └── opencode-spec.md              # frontmatter/discovery rules
│   │   └── evals/evals.json
│   │
│   │  # ── Core engineering loop ──
│   ├── triaging-requirements/
│   ├── designing-architecture/
│   ├── implementing-features/         # backend + frontend refs
│   ├── managing-database-changes/
│   ├── writing-unit-tests/
│   ├── writing-integration-tests/
│   ├── writing-e2e-tests/
│   ├── debugging-test-failures/
│   ├── reviewing-code/
│   │
│   │  # ── UI iteration loop ──
│   ├── iterating-on-ui/               # the loop orchestration itself
│   ├── capturing-ui-evidence/         # Playwright screenshot + computed CSS scripts
│   ├── auditing-visual-design/        # critique against design intent
│   ├── auditing-accessibility/
│   │
│   │  # ── Cross-cutting ──
│   ├── running-councils/              # multi-perspective review (ported from pt)
│   └── releasing-changes/             # changelog, versioning, PR hygiene
├── agents/                            # TEMPLATES (copy into project .opencode/agents/)
│   └── *.md
├── reference/
│   ├── model-routing.md               # dated: roles → recommended Zen/Go models
│   └── loop-diagrams.md
└── evals/                             # shared eval runner (later phase)
```

## The Two Loops

### Loop 1 — Core Engineering (test-verified)

```
triage → design → implement → verify → review → done
  ↑                              │
  └──── failures/gaps ───────────┘
```

- **triage**: consolidate requirements, define acceptance criteria as
  testable assertions.
- **design**: plan files/schema/boundaries; output a plan artifact.
- **implement**: backend and frontend work per plan, following stack refs.
- **verify**: type-check → lint → unit → integration → e2e. Failures route
  to `debugging-test-failures`, which feeds back into implement.
- **review**: code review (and optional council) before handoff.

### Loop 2 — UI Iteration (perception-verified)

```
intent → capture baseline → change → capture → compare → critique
              ↑                                             │
              └──────────── not converged ──────────────────┘
```

- **capture**: Playwright script grabs screenshot(s) at defined viewports +
  computed CSS (`getComputedStyle`) for target selectors → evidence files.
- **compare**: diff computed CSS before/after; view screenshots (requires a
  vision-capable model for the critic role).
- **critique**: judge against stated design intent + heuristics
  (spacing scale, contrast, alignment, theme token usage).
- Converges when critique passes and computed CSS matches intent.

## Model Landscape (snapshot 2026-07-03 — lives in reference/model-routing.md)

Roles, not models, appear in skills. Current recommended bindings:

| Role | Go (flat-rate default) | Zen (escalation) | Notes |
|---|---|---|---|
| Planner/architect | glm-5.2 | claude-opus-4-8, gpt-5.5 | deep reasoning |
| Implementer | kimi-k2.7-code, qwen3.7-plus | claude-sonnet-5, gpt-5.4 | qwen3.6-plus still fine; 3.7-plus is newer + cheaper |
| Triage/bulk | deepseek-v4-flash, mimo-v2.5 | gpt-5.4-mini, claude-haiku-4-5 | near-free on Go |
| Vision critic (UI loop) | — (open models weak on vision) | gemini-3.1-pro, claude-sonnet-5, gpt-5.4 | UI loop REQUIRES vision; budget accordingly |
| Council diversity | glm-5.2 + minimax-m3 + qwen3.7-max | mix families | diversity beats raw strength |

Deprecation watch (from Zen docs): GLM 5 (May 2026, gone), Kimi K2.5 +
MiniMax M2.5 (Aug 2026), several Codex variants (Jul 23, 2026).

## Build Order

1. **Phase 0 — Scaffold**: repo layout, README, install.sh, this plan.
2. **Phase 1 — Meta-skill**: `authoring-skills` with distilled references
   (Anthropic best practices, opencode spec) + its own evals. Everything
   else is authored *through* it.
3. **Phase 2 — Core loop skills** (triage → design → implement → test×3 →
   debug → review), each with evals + pt-stack references +
   `docs/adding-a-stack.md`.
4. **Phase 3 — UI loop skills** (iterate/capture/audit×2) including bundled
   Playwright capture scripts (screenshot + computed CSS extraction).
5. **Phase 4 — Cross-cutting** (councils, releasing) + agent templates +
   pt migration (pt's `.opencode` consumes the library; keep only
   project-specific rules locally).
6. **Phase 5 — Eval harness**: benchmark runner executing each skill's
   evals with/without the skill, per skill-creator methodology.

## Decisions (locked 2026-07-03)

1. **Distribution: global symlink.** `install.sh` symlinks each
   `skills/<name>/` into `~/.config/opencode/skills/`. One `git pull`
   updates every project. Per-project `.opencode/skills/` still wins for
   overrides. Skill permissions (`opencode.json` patterns) can gate
   experimental skills per project.
2. **Skills carry substance; agents are thin bindings.** Skill bodies are
   model-agnostic and portable across harnesses. `agents/` in this repo
   ships template files (model role + permissions + one-line pointer to the
   skill) that projects copy and bind to current model IDs.
3. **Eval-driven from Phase 1.** Every skill ships with `evals/evals.json`
   (2-3 realistic prompts + expected behavior) at creation time. Full
   benchmark runner arrives in Phase 5, but prompts exist from day one.
4. **UI vision critic is tiered.** Routine iteration passes use a cheap
   vision model (gemini-3-flash / gpt-5.4-mini); final review escalates to
   gemini-3.1-pro / claude-sonnet-5. Encoded as two roles in
   `reference/model-routing.md`: `vision-critic-fast`, `vision-critic-final`.
5. **Stacks are plugins, pt is merely the first.** pt's stack
   (Vue 3/Vuetify/Pinia/Supabase/Vitest/Playwright) seeds the references,
   but the architecture must assume many future stacks of greater
   complexity. See "Stack Plugin Architecture" below.
6. **Gerund naming.** `authoring-skills`, `writing-e2e-tests`,
   `iterating-on-ui`, etc.
7. **Loops are skills-with-checklists** (Anthropic's validated pattern),
   harness-portable. Additionally: bundle small shell/Python scripts inside
   skills for repetitive tasks with deterministic output — "right tool for
   the job." Scripts are more reliable than generated code, cost zero
   context until their output returns, and Anthropic's signal for when to
   bundle one is: if test runs show the model repeatedly writing the same
   helper, promote it to `scripts/`. Concrete decisions per loop happen in
   Phases 2–3.
8. **Model bindings are evaluated, not assumed.** `reference/model-routing.md`
   starts from published pricing/benchmarks, but each role binding gets
   validated empirically via the Phase 5 eval harness (run the same skill
   evals across candidate models, compare pass rate / tokens / latency).
   Routing recommendations carry a retrieved-on date and a review cadence.

## Authoring Model Strategy

- **Phase 0–1 (foundation): claude-fable-5.** One-time architecture and
  meta-skill distillation; errors here compound downstream, and the model
  is available now.
- **Phase 2, first skill: mid-tier model (claude-sonnet-5 or glm-5.2)
  authoring *through* `authoring-skills`.** This doubles as the meta-skill's
  first real eval: if a mid-tier model can't produce a quality skill with
  it, fix the meta-skill, don't upgrade the model.
- **Phases 2–4 (long tail): cheapest model that passes the above bar**,
  with Fable/Opus reserved for reviewing skill drafts, not writing them.

## Stack Plugin Architecture

Requirement: pt is a deliberately simple stack; future apps will use varied
and richer stacks. Stack knowledge must be addable without touching skill
workflows.

- Each skill's SKILL.md contains the **generic workflow** plus a short
  **stack selection step**: "Identify the project stack (check
  `references/` for a matching file; if none exists, proceed generically
  and flag the gap)."
- Stack detail lives in per-skill `references/stacks/<stack-slice>.md`,
  scoped to that skill's discipline only. This avoids cross-skill
  duplication naturally — e.g.:
  - `writing-e2e-tests/references/stacks/playwright.md`
  - `implementing-features/references/stacks/vue-vuetify.md`
  - `managing-database-changes/references/stacks/supabase.md`
- Reference files >100 lines start with a table of contents (Anthropic
  guidance) so partial reads still convey scope.
- **Adding a stack** = dropping new reference files into the skills that
  need them + one line in each SKILL.md's stack table. A
  `docs/adding-a-stack.md` checklist (authored in Phase 2) enumerates which
  skills accept stack references.
- Projects declare their stack in their own rules file (`AGENTS.md` /
  `.opencode/agents.md`), which skills read at the selection step.
