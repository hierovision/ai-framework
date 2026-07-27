# Free-Tier Council

The free-tier model routing + council protocol for the ai-framework skill
library. Companion to `reference/model-routing.md` (Section "Free-tier
fallback + council") — that file is the single home of the model IDs; this
doc is the **procedure** for running the council on free models.

The council **defaults to free models** (`opencode/*-free`) for any council
task (the `council-*` agents shipped in this repo are bound to free models).
A **paid or Go-escalation council is an opt-in workflow** the user chooses —
bind the subagents to stronger models (see the `council-member` row in
`reference/model-routing.md`; the frontier opt-in set is
`claude-opus-5 + gemini-3.1-pro + gpt-5.6-sol`, one model per vendor family for
maximum objectivity). Separately, when you want to force the free tier even
with paid keys present, set `AI_FRAMEWORK_FREE_TIER=1` and every task uses a
free model. Free models are individually weaker, so the council exists only
where one weak model is riskiest: **planning** and **review**.

> **`hy3-free` was removed from the catalog on 2026-07-25.** The free
> generalist default (planner / chairman / synthesis) is **`opencode/ling-3.0-flash-free`**,
> chosen by a clean, no-tool head-to-head (2026-07-26) against the other free
> generalists (`nemotron-3-ultra-free`, `north-mini-code-free`, `laguna-s-2.1-free`):
> all four are competent and reliable; `ling` + `nemotron` tied for best output
> (10/10 on triage + planning), and `ling` had the cleanest reliability across
> all invocation contexts. `mimo-v2.5-free` and `deepseek-v4-flash-free` remain
> valid free IDs, so devops/security and coding lenses keep their original
> free models. See Free-tier caveats in `reference/model-routing.md` for
> detail; for risk-bearing planning or skill review you may still escalate to
> the Go/Zen tier.

## Model IDs (verified 2026-07-25 via catalog fetch)

| Role | Free model | Paid/Go row it stands in for |
|---|---|---|
| planner / chairman / generalist | `opencode/ling-3.0-flash-free` | `planner` (glm-5.2 / claude-opus) |
| coder (implement / test / debug) | `opencode/deepseek-v4-flash-free` | `implementer` (kimi-k2.7-code) |
| devops / security | `opencode/mimo-v2.5-free` | `triager` (mimo-v2.5) |

The `-free` IDs are **distinct catalog entries** from `deepseek-v4-flash`
and `mimo-v2.5` (which stay as the Go escalation rows). Skills reference
roles, never these IDs.

## Agent-def sketches (drop into `.opencode/agents/`)

Three minimal agent defs. Each sets `model:` to one free ID and a narrow
critique role. The orchestrator spawns them via the Task tool with the
matching `subagent_type`.

### `.opencode/agents/free-council-planner.md`

```markdown
---
name: free-council-planner
model: opencode/ling-3.0-flash-free
tools: [read, glob, grep, write]
---

You are the PRIMARY PLANNER in a free-tier council. Given a planning request
(or an existing plan draft), produce or refine a verifiable plan artifact
following the ai-framework skills (designing-architecture, and the DevOps
skills designing-cicd / deploying-with-supabase / deploying-to-azure-swa /
securing-ci as relevant).

You will receive critique from two council members (devops/security and
coding-feasibility). Fold their findings into a FINAL plan. CRITICAL: where
you disagree with a council member, SURFACE the disagreement explicitly in the
plan's Open Questions — never silently override a finding. Output the final
plan as the synthesized council result.
```

### `.opencode/agents/free-council-devops.md`

```markdown
---
name: free-council-devops
model: opencode/mimo-v2.5-free
tools: [read, glob, grep]
---

You are the DEVOPS / SECURITY critic in a free-tier council. Given a plan or
workflow under review, critique ONLY the devops/security dimension: CI trigger
trust boundary (no prod deploy from pull_request), migrate-before-deploy
ordering, concurrency (one deploy / one db push at a time), environment
protection rules, secret scoping (secrets not vars, OIDC over PAT), minimal
permissions, SHA-pinned third-party actions.

Be concrete: cite the exact file/hunk and the rule it breaks. Do NOT edit
anything — return findings as a list. Flag uncertainty rather than guessing.
```

### `.opencode/agents/free-council-coder.md`

```markdown
---
name: free-council-coder
model: opencode/deepseek-v4-flash-free
tools: [read, glob, grep]
---

You are the CODING-FEASIBILITY critic in a free-tier council. Given a plan or
workflow under review, critique ONLY whether the proposed work is realizable
and verifiable: are the acceptance criteria testable? does the plan name real
files/commands? is there a meaningful red-first path? are the implementation
steps ordered so each AC can be verified?

Be concrete: cite the AC or step and the feasibility gap. Do NOT edit anything
— return findings as a list. Flag uncertainty rather than guessing.
```

## Council procedure

### Planning council (producing a plan/spec)

1. Orchestrator receives the planning request; loads the relevant skill
   (e.g. `designing-cicd`).
2. Spawn **three** subagents in parallel:
    - `free-council-planner` (`opencode/ling-3.0-flash-free`) — drafts the plan.
    - `free-council-devops` (`opencode/mimo-v2.5-free`) — devops/security critique.
    - `free-council-coder` (`opencode/deepseek-v4-flash-free`) — coding-
      feasibility critique.
3. Planner folds B/C findings into a FINAL plan; disagreements go to Open
   Questions (never silenced).
4. Orchestrator presents the synthesized plan + the surfaced disagreements;
   stops at approval (the skill's own gate).

### Review council (reviewing a diff / skill / workflow)

1. Orchestrator receives the diff; loads `reviewing-code`.
2. Spawn three subagents in parallel with the diff in context:
    - `free-council-coder` (`opencode/deepseek-v4-flash-free`) — coding review.
    - `free-council-devops` (`opencode/mimo-v2.5-free`) — devops/security review.
    - `free-council-planner` (`opencode/ling-3.0-flash-free`) — plan/architecture
      coherence + synthesis.
3. Output: per-member findings + a consensus verdict + any unresolved
   disagreements flagged. A disagreement is reported, not averaged away.

### Guardrails

- Council ONLY for planning & review. Raw coding/test/debug execution stays
  single-model (`opencode/deepseek-v4-flash-free`) to conserve free quota.
- Always surface disagreements; one model must not silently override another.
- Free-tier mode coexists with escalation routing via the `AI_FRAMEWORK_FREE_TIER`
  toggle; enabling it does not modify the escalation rows in
  `reference/model-routing.md`.

## Worked example (planning council)

Request: "design the CI/CD topology for our API — PR validation + prod deploy
on merge, migrations must run before deploy."

- `free-council-planner` drafts: PR `pull_request` test+build job; prod deploy
  on `push` to main via `workflow_run`/`workflow_dispatch`, gated by a
  `production` environment; a `migrate` job `needs: [build]` that `deploy`
  `needs: [migrate]`; `concurrency` queue (not cancel) on deploy.
- `free-council-devops` flags: confirm prod `concurrency.cancel-in-progress:
  false` (queue, not cancel an in-flight deploy); confirm `SUPABASE_ACCESS_TOKEN`
  is in `secrets`, not `vars`; confirm a staging-canary gate exists or is an
  explicit opt-out.
- `free-council-coder` flags: AC "migrations run before deploy" is testable by
  asserting `deploy.needs` includes `migrate`; the plan should name the exact
  workflow file (`.github/workflows/ci.yml`).
- Planner synthesizes: adopts both findings; records the staging-canary opt-out
  as an Open Question (surfaced, not silently dropped). Orchestrator presents
  the plan + the one disagreement (staging-canary) for the user to resolve at
  approval.
