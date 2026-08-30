# ROADMAP

Established: 2026-08-28
Maturity baseline: Level 2–3 (Defined), trending. Target: Level 4 (Operated / Capable) on speed and quality.

Reference models (what we use, and why):
- Authoritative backbone: ISO/IEC 42001:2023 + NIST AI RMF + CMMI/DevOps. Real standards. They give the plan defensible authority.
- Operational rubric: Rex Black 7-axis. A consultancy framework, NOT a standard. Used only as a practical scoring checklist because its 7 axes match our gaps.
- Borrowed mechanic: ALM stage-gate. Used for the "no advance without a passing gate" pattern (its NIST/ISO lineage is credible).
- Deferred: Microsoft Agentic AI Adoption (team-scale only).
- Not used as a lens: LLMOps. Its two useful ideas are folded in — token cost → RM-009, drift → RM-001/RM-002. MLOps excluded.

Note: No single standard exists for an "agentic dev lifecycle." We compose the above. Authority comes from the backbone; day-to-day scoring uses the Rex Black rubric.

## Legend
- Status: `backlog` | `next` | `in-progress` | `done`
- Priority: 1 (highest) – 5 (lowest). Composite of leverage on speed/quality and unblocking value.
- Phase: delivery wave (see `docs/maturity-plan.md` §6).
- "plan" in Source columns = `docs/maturity-plan.md`.

## Roadmap

| ID | Category | Title | Priority | Phase | Status | Source | Acceptance |
|---|---|---|---|---|---|---|---|
| RM-001 | observability | Run-log schema + `observing-runs` skill | 1 | 1 | next | plan §5-A; repo audit (Observability L1) | Structured `logs/run-*.jsonl` emitted on every skill/agent invocation with skill, agent, model, tokens, duration, outcome, eval pass/fail; query script returns cost/task, latency, eval-pass rate. |
| RM-002 | evaluation | Wire behavioral eval suite into CI | 1 | 1 | next | plan §5-B; `skills/authoring-skills` eval protocol | Fresh-agent eval protocol runs on schedule/hermetic CI; regression failures block the run; no manual "I tried it" gates. |
| RM-003 | evaluation | Eval report artifact + dashboard | 2 | 1 | backlog | plan §5-B | Per-run eval scores persisted and queryable; report links from CI summary. |
| RM-004 | governance | Formal governance artifacts | 2 | 2 | backlog | plan §5-C; repo audit (Governance L2) | `CONTRIBUTING.md`, `CODEOWNERS`, `SECURITY.md`, `docs/ADRs/` exist and are referenced by contribution flow. |
| RM-005 | governance | Skill/agent registry manifest | 2 | 2 | backlog | plan §5-D | Machine-readable manifest listing each skill/agent: owner, maturity level, boundary ref. Consumed by tooling. |
| RM-006 | integration | Adoptable CI/CD templates | 3 | 2 | backlog | plan §5-D; `skills/designing-cicd` | `templates/` YAML a consumer repo can copy to get evaluate→build→deploy golden path. |
| RM-007 | integration | PR annotations from eval + run logs | 3 | 3 | backlog | plan §5-D | PR checks annotate eval result + link run-log; regression blocks merge. |
| RM-008 | decision-boundaries | Encoded boundary manifest per agent | 3 | 3 | backlog | plan §5-E; repo audit (Boundaries L2) | Each agent has decide/escalate/never manifest in config; enforced where automatable. |
| RM-009 | roi-math | Cost/ROI tracker (4 numbers) | 4 | 3 | backlog | plan §5-F | Script reads run logs → hours×rate, error-rate Δ, cycle-time Δ, ramp-time avoided per project. |
| RM-010 | human-in-the-loop | Standardized escalation/override artifact | 4 | 3 | backlog | plan §5-G; repo audit (HITL L3) | Every handoff emits consistent escalation-context payload + recorded-override entry. |
| RM-011 | optimize | Drift detection + quarterly ALM reviews | 5 | 4 | backlog | plan §5-A/B; ALM | Behavioral drift score per skill tracked; quarterly stage-gate review held per owner. |

## Sequencing rationale
Phase 1 (RM-001, RM-002, RM-003) is the fast win: observability + continuous
eval directly accelerate quality and speed, the stated goal. Phase 2 (RM-004,
RM-005, RM-006) converts prose rules into enforced artifacts and ships reusable
pipelines. Phase 3 (RM-007, RM-008, RM-009, RM-010) closes integration,
boundary-encoding, ROI, and HITL consistency. Phase 4 (RM-011) is the
optimizing loop.

## Next-session entry
Start RM-001 + RM-002 (Phase 1). Both are independent and unblock all later
work. Design artifacts for each belong in `.opencode/plans/` via
`designing-architecture` before `implementing-features` executes.
