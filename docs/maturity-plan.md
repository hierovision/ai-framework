# Agentic Development Lifecycle — Maturity Plan

Status: draft for refinement
Date: 2026-08-28
Author: triage agent (planning pass)
Location: `docs/maturity-plan.md` (moved from `~/repos/temp`)

## 1. Scope & intent

Turn ideas into high-quality web applications as fast as possible, using agentic
loops built on the opencode skill/agent library in `ai-framework`. This is a
**development-process maturity** effort, not ML productization.

Out of scope:
- Training, fine-tuning, or building ML/LLM models.
- RAG serving, model registries, feature stores (MLOps).

In scope:
- Maturing the agentic dev workflow itself: how skills/agents plan, build, test,
  review, deploy, and observe.
- LLMOps is NOT a separate lens. Its two additive ideas fold into the spine:
  token economics → ROI-math axis (RM-009); behavioral drift over time →
  observability/eval axes (RM-001/RM-002). MLOps excluded.

## 2. Reference models (what we use, and why)

No single standard covers an "agentic dev lifecycle." We compose three roles:

| Role | Model | What it is | How we use it |
|---|---|---|---|
| Authoritative backbone | ISO/IEC 42001:2023, NIST AI RMF, CMMI/DevOps | Real published standards | Gives the plan defensible authority for governance and engineering discipline |
| Operational rubric | Rex Black 7-axis | Consultancy framework (NOT a standard) | Day-to-day scoring checklist; its 7 axes match our gaps (see §3) |
| Borrowed mechanic | ALM stage-gate | Pattern from Agent Lifecycle Management (NIST/ISO lineage) | "No advance without a passing gate" rule for skill contributions |

Deferred / excluded:
- **Microsoft Agentic AI Adoption** — deferred. It is org/team-scale (exec sponsorship, culture). A solo framework cannot evidence those pillars, so it risks maturity theater. Revisit if we scale to a team.
- **LLMOps** — not a separate lens. Its only useful ideas fold into the rubric: token cost → RM-009 (ROI); behavioral drift → RM-001/RM-002 (observability/eval).
- **MLOps** — excluded (training, feature stores, model registries; not our domain).

Why not treat Rex Black as the authority? It is a 2026 consultancy position piece with no published validation or appraisal data. Its value is face validity and a clean axis list — good enough as a *rubric*, not as a *standard*. The backbone supplies the authority it lacks.

## 3. Current-state verdict (from repo audit)

Strong on craft discipline, weak on measurement and formal governance.

| Rex Black axis | Current | Evidence |
|---|---|---|
| Human-in-the-loop | L3 | Explicit `STOP` gates, designed handoffs, `REVIEW.md`/`ADHERENCE.md` |
| Evaluation (structural) | L3 | `validate_skill.py`, offline `verify` suites, 21× `evals.json` |
| Evaluation (behavioral) | L1 | Fresh-agent eval protocol exists but **not wired to CI** |
| Decision boundaries | L2 | Boundaries in prose (skill `STOP`s), not encoded/enforced in config |
| Governance | L2 | Rules in prose (`council.md`, `git-workflow.md`); **no CONTRIBUTING/CODEOWNERS/SECURITY/ADR** |
| Integration | L2–3 | GitHub issues/PRs/projects + opencode; no change-mgmt/audit wiring |
| Observability | L1 | **No run logs, traces, cost, or eval-history queryability** |
| ROI math | L1 | **No cost/cycle-time/error-rate tracking** |

Overall: ~Level 2–3 ("Defined") trending, gated by observability + continuous
eval + formal governance.

## 4. Target — the next maturity level

Advance to **Level 4 ("Operated / Capable")** on the axes that unblock speed and
quality first: **Observability → Continuous behavioral Evaluation → Formalized
Governance & Integration**; then Decision-boundaries (encoded) and ROI math.

Per Rex Black, L4 cannot be claimed on one axis alone — all must clear. The plan
moves them together but sequences the fast-wins first.

Target definition (evidence-based): "We can answer 'why did the agent do X, and
did it regress?' from queryable logs; every change runs an eval gate that blocks
regressions; each skill has a named owner and a calendared review; agents
participate in change management via PR checks + a registry."

## 5. Initiatives

A. **Observability (new — biggest gap)**
   - Run-log schema (skill, agent, model, tokens, duration, outcome, eval
     pass/fail) → structured `logs/run-*.jsonl` (or `.opencode/telemetry`).
   - `observing-runs` skill + query/aggregate script (cost/task, latency,
     eval-pass rate, drift score).

B. **Continuous behavioral evaluation (upgrade existing)**
   - Wire the `authoring-skills` fresh-agent eval protocol into a scheduled or
     hermetic CI job (`make eval` / nightly).
   - Per-skill regression + adversarial test sets; new capabilities ship with
     new tests.
   - Publish an eval report artifact (scores per run, queryable).

C. **Formal governance (encode the prose)**
   - Add `CONTRIBUTING.md`, `CODEOWNERS`, `SECURITY.md`, `docs/ADRs/`.
   - Owner-per-skill + quarterly review cadence; ALM-style stage-gate template
     for new skills.

D. **Integration depth**
   - Ship adoptable `templates/` CI/CD YAML (today `designing-cicd` only
     instructs).
   - Agent/skill registry manifest (owner, maturity level, boundaries).
   - Annotate PRs with eval results + run-log links.

E. **Decision boundaries encoded**
   - Machine-readable boundary manifest per agent (decide / escalate / never) —
     extend agent frontmatter or `boundaries.json`; enforce where possible.

F. **ROI math (lightweight, for you)**
   - Cost tracker reading run logs → the 4 numbers (hours×rate, error-rate Δ,
     cycle-time Δ, ramp-time avoided).

G. **Human-in-the-loop (refine, already strong)**
   - Standardize escalation-context payload + recorded-override format across
     handoffs.

## 6. Roadmap

The canonical, prioritized, itemized roadmap is `./ROADMAP.md` (`RM-001` …
`RM-011`). That file is the single source of truth for phases, priority, status,
and acceptance criteria. Do not duplicate it here.

Phase grouping (orientation only):
- Phase 1 (fast wins): RM-001, RM-002, RM-003
- Phase 2: RM-004, RM-005, RM-006
- Phase 3: RM-007, RM-008, RM-009, RM-010
- Phase 4 (optimize): RM-011

## 7. Exit criteria (how we know we arrived)

- [ ] Queryable run logs answer "why did the agent do X" (Observability L4)
- [ ] Eval suite runs per change / scheduled and blocks regressions (Eval L4)
- [ ] Named owner + calendared governance review exists (Governance L4)
- [ ] Agents in change mgmt via PR checks + registry (Integration L4)
- [ ] Decision boundaries enforced in config (L4)
- [ ] Defended 4-number ROI per project (L3+)

## 8. Risks

- Over-instrumenting slows the speed you want — keep observability file-based,
  zero external services initially.
- "L4 on paper" trap (Rex Black's warning) — evidence required, not docs.
- Maturity theater — governance artifacts must be used, not filed.
