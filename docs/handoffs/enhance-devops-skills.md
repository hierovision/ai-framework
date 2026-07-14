# Handoff: Enhance ai-framework with DevOps/Release Skills + Free-Tier Council Fallback

Dispatch to a fresh **hy3-free** session in `~/repos/ai-framework`.
(This is a library-enhancement task: you add skills to the framework and
extend its model-routing — you do NOT touch pt's application code or its
`.github/workflows`. Verify exact free-model IDs via `opencode models`
before binding them.)

Paste everything below the line.

---

# Your task

Enhance the `~/repos/ai-framework` skill library with **DevOps / release-engineering
coverage** (currently zero) and add a **free-tier model-routing + council fallback**
so the library keeps working when paid budget/credits run out. Produce a
validator-clean result and commit per repo convention.

This is planning/authoring work only. Do not modify application code in any
other repo.

# 0. Orientation — read these FIRST (in order)

1. `docs/ORCHESTRATOR-HANDOFF.md` — how this library is maintained, the
   validator command, and commit conventions.
2. `reference/model-routing.md` — the single source of model IDs and the
   role→model binding table. You will EXTEND this file (Section 5).
3. `skills/authoring-skills/SKILL.md` — THE skill to drive authoring of each
   new skill. Follow it (snapshot → baseline → edit → eval → validate).
4. `skills/designing-architecture/SKILL.md` + `references/plan-format.md` —
   the plan-artifact voice/conventions to mirror.
5. `skills/reviewing-code/SKILL.md`, `skills/writing-e2e-tests/SKILL.md` —
   examples of the library's tone (concise, checklist-driven, stops at a gate).
6. Run the skill validator (command in ORCHESTRATOR-HANDOFF.md). The library
   is currently **12 skills, validator-clean**. Preserve that invariant: after
   adding skills, re-run and confirm still clean (target: 17 skills clean).

# 1. Why this exists (context for your decisions)

The library covers the *build* lifecycle (architecture, implement, test, review,
debug, accessibility, UI evidence/correction, skill-authoring, triage). It has
**no coverage of *release/operate***: CI/CD, cloud deploy, DB migrations in CI,
release engineering, infra/security. This gap was found in practice while using
the library to drive a real Vue 3 + Supabase + PWA project: evaluating GitHub
Actions workflows, sequencing prod migration before prod deploy, Azure SWA
preview environments, and "run e2e against the PR preview" specs all fell outside
every existing skill. Your job is to close that gap and make the library
resilient to a free-model budget.

# 2. Skills to add (pre-ranked — confirm with `triaging-requirements`)

Use the `triaging-requirements` skill to rank; the recommended order is:

- **P0 — `designing-cicd`**: GitHub Actions topology — triggers
  (`push` / `pull_request` / `workflow_run` / `workflow_dispatch`), job
  sequencing via `needs`, `concurrency` (`queue: max` vs `cancel-in-progress`),
  `environment` + protection rules (required reviewers / wait timer / deployment
  branches), secrets vs vars, matrix, caching, artifacts, required checks. Golden
  paths: test → build → deploy, and **migrate-before-deploy**. When to use: any
  "how should CI work", "sequence deploy vs migration", "gate prod" question.
  References: GitHub Docs *Events that trigger workflows*, *Environments*,
  *Concurrency*; Supabase *Managing Environments* CI pattern.

- **P0 — `deploying-with-supabase`**: `supabase db push` forward-only semantics,
  "only one `db push` at a time" (concurrency), migrations in CI (session-mode
  `--db-url` vs `link` + `SUPABASE_ACCESS_TOKEN`), Supabase Branching,
  staging-canary, pgaudit / audit-logging safety, declarative schemas.
  References: Supabase CLI docs, *Database Migrations* guide.

- **P1 — `deploying-to-azure-swa`**: Azure Static Web Apps GitHub Actions —
  preview-per-PR environments, production promotion, the `static_web_app_url`
  action output, `skip_app_build`, Oryx build, custom domains. References: Azure
  SWA *build-configuration* + *deploy-to-azure-static-web-app* docs.

- **P1 — `securing-ci`**: least-privilege tokens (OIDC vs PAT /
  `SUPABASE_ACCESS_TOKEN`), environment-secret scoping, never log secrets, branch
  protection for required checks, SHA-pinning third-party actions. References:
  GitHub *Security hardening for GitHub Actions*.

- **P2 — `validating-against-official-docs`**: the meta-discipline — fetch
  authoritative Supabase / GitHub / Azure docs and emit an adherence report
  (what adheres, what gaps, cited fixes). Formalizes the ad-hoc review we did.

Authoring rules for each: use `authoring-skills`; write a `description` tuned
for the available_skills matcher, explicit `when-to-use` triggers, a step
process, official-doc References, and **evals**. Mirror the concise,
checklist-driven voice of `designing-architecture`.

# 3. Integration with existing skills (light touch)

- `designing-architecture`: mention `designing-cicd` for deploy/release
  decisions; `reviewing-code`: note CI/workflow changes are in scope;
  `writing-e2e-tests`: note `designing-cicd` decides *where/whether* e2e runs
  (e.g., against PR previews). Add cross-references only where natural — do not
  bloat descriptions.
- Optional: a `references/stacks/` CI/migration addendum for the `vue-supabase`
  stack. Skip if it adds no decision value.

# 4. Execution steps (ordered)

1. Read orientation (Section 0).
2. `git status` / `git branch --show-current`. Create a feature branch
   (e.g. `enhance/devops-skills`) unless repo convention says otherwise.
3. Run `triaging-requirements` to rank the 5 skills (confirm P0/P1/P2) — or
   accept the pre-rank above and note it.
4. Author **P0**: `designing-cicd`, `deploying-with-supabase` via
   `authoring-skills` (SKILL.md + evals each). Validate after each.
5. Author **P1**: `deploying-to-azure-swa`, `securing-ci`.
6. Author **P2**: `validating-against-official-docs`.
7. Extend `reference/model-routing.md` with the **free-tier fallback** + **council
   protocol** (Section 5). Add minimal agent defs / a `docs/FREE-TIER-COUNCIL.md`
   as needed. Keep `model-routing.md` the single home of model IDs (its own rule).
8. Cross-reference new skills from `designing-architecture` / `reviewing-code` /
   `writing-e2e-tests` descriptions (light touch).
9. Re-run the skill validator; ensure 12 → 17 skills still clean. Fix warnings.
10. Update `docs/ORCHESTRATOR-HANDOFF.md` / `PLAN.md` roadmap (note new DevOps
    coverage + free-tier council).
11. Commit per repo style (one commit per skill, or a single
    "enhance: add DevOps skills + free-tier council" — match convention). Push
    only if authorized.

# 5. Free-tier fallback + council (the novel part)

Extend `reference/model-routing.md` with a **"Free-tier fallback"** section and a
**council protocol**. Intent: when budget/credits run out, fall back to free
models and run a council for objectivity on **planning** and **review** steps.

## 5.1 Free-model roster
(Verify exact opencode IDs via `opencode models` / config before binding.
`deepseek-v4-flash` and `mimo-v2.5` already appear in the current table — confirm
whether the "-free" branded IDs are distinct free-tier entries and use those.)

| Role | Free model | Maps to existing role row |
|---|---|---|
| `planner` (planning/design/architecture) | **hy3-free** | planner (glm-5.2 / claude-opus) |
| `implementer` / `test-writer` / `debugger` (coding) | **deepseek v4 flash free** | triager/debugger (deepseek-v4-flash) |
| devops / CI / cloud / security | **mimo-v2.5-free** | triager (mimo-v2.5) |

## 5.2 Routing rules (free-tier mode)
- Activated by an explicit toggle (e.g. env `AI_FRAMEWORK_FREE_TIER=1`) OR
  auto when paid providers are exhausted. Implement a clear toggle and document
  it; do NOT break the existing paid rows.
- Single-task execution uses the one mapped model (cheap, no council) to
  conserve free quota:
  - planning/design → hy3-free
  - any coding → deepseek v4 flash free
  - devops/CI/cloud/security → mimo-v2.5-free

## 5.3 Council structure (objectivity for planning & review)
Free models are individually weaker, so run **planning** and **review** as a
multi-model council and synthesize. Design:

- **Planning council** (producing a plan/spec via `designing-architecture`,
  `designing-cicd`, etc.):
  - A — hy3-free: primary planner.
  - B — mimo-v2.5-free: devops/security critique (CI safety, secrets, environments?).
  - C — deepseek v4 flash free: coding-feasibility critique (realizable? are ACs testable?).
  - Synthesis: hy3-free writes the final plan folding in B/C; **surface disagreements explicitly**.
- **Review council** (reviewing code/skills/workflows, `skill-reviewer`):
  - A — deepseek v4 flash free: coding review.
  - B — mimo-v2.5-free: devops/security review.
  - C — hy3-free: plan/architecture coherence + synthesis.
  - Output: per-member findings + consensus verdict + unresolved disagreements flagged.

Mechanism: the orchestrator spawns subagents (Task tool) with `subagent_type`
bound to agent defs that set `model:` to the free IDs, runs them (parallel where
possible), then synthesizes. Add minimal agent defs
(`.opencode/agents/free-council-planner.md`, `free-council-devops.md`,
`free-council-coder.md`) OR a single procedural prompt — decide per the repo's
agent conventions. Keep it simple.

## 5.4 Guardrails
- Council only for **planning & review** (per directive), not raw execution.
- Always surface disagreements; never let one model silently override.
- Free-tier mode must coexist with the existing paid routing (toggle between).

# 6. Acceptance criteria

- 5 new skills authored, each validator-clean, each with evals, voice matching
  the library.
- `designing-cicd` + `deploying-with-supabase` close the real gaps
  (migrate-before-deploy, `concurrency`, `environment` protection, `supabase db
  push` in CI).
- `reference/model-routing.md` documents the free-tier fallback (3 models +
  routing) and the planning/review council protocol.
- Free-tier council is demonstrably used for planning & review when toggled.
- Library still validator-clean (17 skills).

# 7. Open questions (resolve as you go)

- Exact opencode model IDs for the three "-free" models (`opencode models`).
- Toggle mechanism: env var vs config flag vs auto-detect on provider exhaustion.
- Dedicated agent defs vs a procedural prompt for the council.
- Whether to add a `references/stacks/` CI/migration addendum for `vue-supabase`.

# 8. Out of scope

- Do NOT modify pt's application code or its `.github/workflows`.
- Do NOT change existing paid routing rows unless a deprecation forces it
  (see the Deprecation watch in `model-routing.md`).
