# AI Framework — Skill Library Plan

Status: APPROVED DIRECTION — decisions locked 2026-07-03 (see Decisions)
Date: 2026-07-03
Repo: <https://github.com/hierovision/ai-framework.git>

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
│   ├── auditing-accessibility/
│   │   # auditing-visual-design SKIPPED (2026-07-12) — see Decisions log
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
4. **Phase 3 — UI loop skills** (see "Phase 3 Design" below): reactive
   capture + correct first (`capturing-ui-evidence`, `correcting-ui`);
   proactive accessibility auditing as a follow-on (built). Proactive
   visual-design auditing was scoped, assessed, and **skipped** — see
   Decisions log 2026-07-12. Phase 3 is closed.
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

## Phase 3 Design — UI Iteration Loop (decisions locked 2026-07-06)

The perception-verified counterpart to the core loop. Parallel shape:

| Core loop | UI loop |
|---|---|
| reproduce (run command) | capture (screenshot + computed CSS + bounding boxes) |
| hypothesis + discriminating experiment | triangulate 4 sources → pin symptom to a source rule |
| implement at root cause | edit styles adhering to the system in place |
| verification exit codes | re-capture + compare computed-CSS / geometry deltas |
| full suite still green | regression guard: other elements' boxes/computed unchanged |
| (n/a) | perceptual acceptance: vision critic vs stated intent |

Decisions:

1. **Scope now: two reactive skills.** `capturing-ui-evidence` (the
   Playwright harness, dependency) + `correcting-ui` (the diagnose-and-fix
   brain). Proactive `auditing-visual-design` and `auditing-accessibility`
   deferred to a follow-on phase. (`auditing-accessibility` built
   2026-07-11; `auditing-visual-design` skipped 2026-07-12 — see
   "Decision: auditing-visual-design skipped" below.)
2. **Capture supports both modes, selected per invocation:** real running
   app (dev-server URL + route, auth via the e2e auth-fixture pattern) and
   isolated components (Storybook / component harness). The harness picks
   based on the target the invocation names.
3. **CSS system is a plugin dimension.** Seed
   `references/systems/vuetify-scss.md` (the pt reality: theme tokens, SCSS
   variables, prefer component props over raw CSS). BEM and Tailwind become
   additional `references/systems/*.md`. System detected from the rules
   file + config files (tailwind.config, vuetify theme, stylelint config).
   Note: UI-loop references split into `systems/` (CSS methodology) and,
   where needed, `stacks/` (framework capture specifics) — a second
   reference axis beyond the core loop's single `stacks/`.
4. **Objective-first closure; vision is the final perceptual acceptance
   only.** The loop closes on measurable signals wherever the intent is
   measurable — geometry (alignment = equal coords, overflow = child box ⊄
   parent box, spacing = computed value == target), computed-CSS target
   values, a regression guard (other elements' boxes/computed CSS
   unchanged), and stylelint + convention checks (no specificity increase,
   no new `!important`, naming matches the system). The vision critic
   adjudicates only the genuinely perceptual residue and gives final
   sign-off. Never closes on "looks better" alone.
5. **Fixes snap to tokens (hybrid).** Honor a design-token / theme scale
   when present (named token = self-documenting); otherwise reuse an
   existing SCSS variable or introduce a well-named one — DRY and
   self-documenting by construction, never a magic px.
6. **Vision critic tiered** (Decision 4, repo-wide): `vision-critic-fast`
   per iteration, `vision-critic-final` for sign-off. Zen-billed.

Key lever for the stated pain (vision models fumbling CSS from text): the
capture harness opens a **CDP session** and calls
`CSS.getMatchedStylesForNode`, returning which authored selector at which
source location set each property (and what overrode it). This collapses
symptom→source mapping into a deterministic lookup. Division of labor:
vision says *what looks wrong*; matched-styles says *which rule*; the
prompt says *intended*. The model never guesses CSS from prose.

`correcting-ui` is an implement-class skill (it edits source): trivial
corrections proceed directly; a large restyle routes to
designing-architecture first, and out-of-scope urges are recorded as
follow-ups (implementing-features posture). Review of the CSS output is
folded in as the second closure condition (stylelint + convention +
regression), not a separate reviewing-code pass.

Build-time constraints to carry into the handoffs:

- **Real-browser deferral** (as with `writing-e2e-tests`): the eval
  harness likely lacks a browser. Capture/compare scripts get structural
  verification; real screenshot/computed-CSS runs are a documented
  deferred validation. Fixtures ship a tiny static page + a
  component-isolation stub Playwright *could* hit.
- **Computed-CSS curation:** `getComputedStyle` yields ~300 longhands.
  The harness captures a curated profile (box model, layout, typography,
  color, positioning) and/or diffs against baseline, never dumps all 300.
- **Evidence is structured + addressable:** capture writes a stable
  artifact (screenshot path + JSON of computed profiles + bounding boxes
  keyed by selector) that `correcting-ui` consumes and re-captures against
  for the delta/regression comparison.

## Core Loop Refinement — TDD-Aware Implement Sequencing (decisions locked 2026-07-11)

Gap identified in review: `implementing-features` runs the plan's
`## Verification` commands and fixes code until they pass, but nothing
requires a test to exist — let alone fail — *before* the code does. Test
authoring (the trio) is invoked "separately by the user," with no
enforced order. This lets test-after silently substitute for test-first,
and a coverage/quality check happens only if a separate `reviewing-code`
pass catches it after the fact.

**Goal:** the best parts of TDD without full micro-loop TDD. Core
behavioral capture as failing tests directly from the plan's Acceptance
Criteria, *before* implementation (the first step) — then implement to
green — then a bounded coverage-and-quality gate near the end of the
pass (not exhaustive upfront authoring, not silent test-after).

**The load-bearing distinction — two kinds of "red," both kept:**

| | Pre-implementation red (NEW) | Post-implementation meaningfulness proof (EXISTING) |
|---|---|---|
| When | Before the feature exists | After the feature exists |
| How it goes red | Naturally — the behavior isn't there yet | Deliberately broken, then restored |
| Proves | The test exercises the intended path, for real | The test can still detect a regression |
| Risk it guards against | A test that never ran against pre-feature reality (test-after mirrors the implementation) | A test that passed for the wrong reason once code shaped around it |
| The trap | Red for the *wrong* reason (a typo, bad import, broken fixture) — must confirm the failure names the missing/wrong behavior, not a harness defect | (unchanged from today) |

Decisions:

1. **`implementing-features` gains two new steps**, not a rewrite: a
   **red-first step** immediately after plan-reconciliation and before any
   source edit (author one test per testable Acceptance Criterion via the
   matching test-trio skill, run it, confirm it fails **for the right
   reason** — not a harness defect), and a **coverage-and-quality gate**
   after the plan's Verification is green (see Decision 3 for its full,
   two-part scope).
2. **The test trio gains a mode, not a rewrite.** `writing-unit-tests` /
   `writing-integration-tests` / `writing-e2e-tests` already accept plan
   ACs as input; what's missing is branching the *meaningfulness proof*
   step on whether code exists yet. Red-first mode: the natural
   pre-implementation failure *is* the proof, gated on the "right reason"
   check. Coverage-expansion / standalone mode: unchanged, today's
   break→red→restore→green. The "invoked separately" language is
   clarified, not reversed — the trio still never cascades into each
   other; `implementing-features` orchestrating them at two named steps
   is now a documented, intentional caller.
3. **No plan-format.md schema change — locked, not a wait-and-see.**
   Best-guess layer classification at red-first time is **correct by
   design**, not a stopgap: a plan cannot know the true seam boundaries
   until code exists, so demanding a precise per-AC layer tag at design
   time would ask `designing-architecture` to know something it
   structurally cannot yet know. The correction belongs downstream, where
   the real implementation has revealed the truth — which is exactly what
   the coverage-and-quality gate is for. Concretely, the gate now has
   **two responsibilities, not one**:
   - **Rebalance** — for each AC-test pair the red-first step produced,
     re-examine it against the real implementation: did it land at the
     wrong layer (a "unit" test that ended up mocking a real seam into
     existence — vacant per the trio's own rule; an "e2e" test for
     something that turned out to be pure logic — slow and brittle for no
     reason)? If so, supersede the misplaced test, invoke the correct
     trio skill to reauthor it at the right layer, and re-prove
     meaningfulness there (break/restore). This is the testing-pyramid
     correction: push each test down to the cheapest layer that still
     meaningfully exercises the behavior, using the SAME right-layer
     table the red-first step used to guess — now applied with the
     benefit of real code to look at.
   - **Expand** — unchanged from the original design: given the actual
     implementation, is there a genuinely valuable gap the AC set didn't
     reach? Expand with a citation, or explicitly declare none found;
     silence is not an answer.
   A red-first guess is never required to be right the first time; it is
   required to be *correctable* the second time, with a named mechanism
   for doing so.
4. **`reviewing-code` gets a small, additive cross-reference**, not new
   logic: when the new red evidence + coverage-gate outcome (including
   any layer rebalancing) are present in the plan's `## History`, the
   reviewer spot-checks them as evidence rather than re-deriving the
   meaningfulness check from zero.
5. **Bounded, not exhaustive.** The red-first step is ONE test (or a
   minimal table-driven set) per AC, at a best-guess layer — core behavior
   only, no invented edge cases yet, no requirement to get the layer
   right. The coverage gate is a gate, not a license: rebalancing must
   cite the specific misclassification it's correcting; expansion must
   cite a real gap in the actual implementation (an error path, a
   boundary the code special-cases) or explicitly declare none found.
   Padding coverage for its own sake is refused exactly as the trio
   already refuses it today ("a case that exercises no observable the AC
   names is padding, not coverage").
6. **Out of scope for this pass** (record as follow-ups if raised): no
   change to `debugging-test-failures` (a red-for-the-wrong-reason test is
   a test-authoring correction, not a regression to diagnose — no code
   ever worked, so there's nothing to diagnose); no change to any UI-loop
   skill (they already have their own objective-first disciplines); no new
   bundled scripts (this is a workflow/prose change).

See `docs/handoffs/tdd-sequencing.md` for the dispatchable author-session
handoff implementing these decisions.

## Decision: auditing-visual-design skipped (2026-07-12)

Phase 3's last placeholder (`auditing-visual-design` — "critique against
design intent," a one-line aspiration from the Phase 0 scaffold, never
designed further) is **skipped**, not silently dropped. Reasoning:

`auditing-accessibility` earns its "proactive, unprompted scan" shape
because a real, external, authoritative rule engine already exists (axe-
core, mapping to WCAG success criteria) — roughly 30-40% of the job is
genuinely mechanical, and the skill is explicit about the rest (the
`manual_checklist`). Visual design quality has no equivalent universal
rule set: "this spacing is inconsistent" or "this hierarchy doesn't read
well" isn't checkable against a spec, only against a given project's own
design system — and most projects don't have one specified precisely
enough to serve as one.

Splitting the idea in two exposes the actual value:

- **The objectively-checkable slice** (computed spacing off a declared
  token scale, a raw hex color where a theme token exists, a specificity/
  `!important` violation) is real but narrow, and roughly 80% already
  exists as `correcting-ui`'s adherence checker
  (`check-adherence.js`) — the net-new work would be a thin proactive
  wrapper that batch-runs it across more routes/selectors than one
  reactive fix touches.
- **The part that would make it feel like "auditing visual design" as
  named** — actual critique of hierarchy, balance, polish — has no
  objective backbone. Building it would mean either overreaching into
  unanchored vision-model opinion (inverting this library's foundational
  principle: "vision is the last-resort perceptual residue only, never
  the first signal") or quietly shrinking to a design-token linter
  wearing a bigger name.

**Decision: do not build now.** Revisit only when a concrete need makes
the objective backbone clear — e.g. a project ships a precise,
machine-checkable design-token spec (not just a style guide) that a
proactive scan could genuinely check against, the way WCAG serves
`auditing-accessibility`. Until then this is speculative scope, not a
demonstrated gap — unlike the TDD-sequencing fix above, which had a
concrete failure mode and a provable closure condition before any skill
body was touched. `iterating-on-ui` (the loop-orchestration skill) and
`managing-database-changes` remain the same kind of un-actioned Phase 0
placeholder and are not reopened here.

Phase 3 (UI Iteration Loop) is **closed**: `capturing-ui-evidence`,
`correcting-ui`, `auditing-accessibility` shipped; `auditing-visual-
design` skipped by this decision.

---

## Appendix A — Status & open items (2026-07-14)

Single source of current library state. Updated as phases close.

### Library state
- **19 skills shipped** across all loops: build, test, release, and the
  product/requirements loop (`triaging-requirements`,
  `managing-github-issues`, `refining-issue-acceptance`).
- **Both core loops are complete**: build (architecture → implement →
  test trio → review) and test (unit / integration / e2e).
- **DevOps/release phase done**: `designing-cicd`, `deploying-to-azure-swa`,
  `deploying-with-supabase`, `securing-ci`, `validating-against-official-docs`.
- **Free-tier council shipped**: default `hy3-free`, three paid models
  opt-in (`glm-5.2`, `gpt-5.4`, `claude-opus-4-7`). Defined in
  `agents/council.md` + `agents/council-*.md`; strategy in
  `reference/model-routing.md`; walkthrough in `docs/FREE-TIER-COUNCIL.md`.
  This closes the previously-deferred `running-councils` item.

### pt (prompt-toolkit app) migration
- App-code review completed: **approve-with-nits** committed in pt's repo.
- 6 first-round review comments remain open in pt's PR #10, including an
  auth-listener bug — tracked in pt, **not** a library concern. No further
  library work until pt resolves them.

### Still open / deferred
- **`releasing-changes`** (changelog / versioning / PR hygiene skill) — the
  only remaining Phase 0 placeholder not yet built.
- **Phase 5 eval harness** (deep synthetic-eval runner) — lower priority,
  not started. Deferred until a concrete need appears.
- `iterating-on-ui` and `managing-database-changes` remain un-actioned
  Phase 0 placeholders (see Phase 3 decision above).
