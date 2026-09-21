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
| RM-001 | observability | Run-log schema + `observing-runs` skill | 1 | 1 | done | plan §5-A; repo audit (Observability L1) | Structured `logs/run-*.jsonl` emitted on every skill/agent invocation with skill, agent, model, tokens, duration, outcome, eval pass/fail; query script returns cost/task, latency, eval-pass rate. |
| RM-002 | evaluation | Wire behavioral eval suite into CI | 1 | 1 | done | plan §5-B; `skills/authoring-skills` eval protocol | Fresh-agent eval protocol runs on schedule/hermetic CI; regression failures block the run; no manual "I tried it" gates. Done covers the scheduled, hermetic CI gate with regression-blocking (verified via negative-path canary); per-change triggering and the two deferred network-fetching suites remain open under RM-003. AC5 live-dispatch regression check verified live 2026-09-16 ([run 35108912831](https://github.com/hierovision/ai-framework/actions/runs/35108912831)): broken-eval canary failed the job red and emitted an `eval_pass=false` record to the uploaded `logs/` artifact. Two network-fetching suites deferred — RM-003 tracks the coverage gap. Logs artifact contains schema-narrow metadata only (ts, run_id, skill, model, tokens, duration, outcome, eval_pass; failure-only detail ≤512 chars) — never prompts, outputs, tool args, or credentials; secrets masked; 30-day retention; inherits PUBLIC repo visibility. |
| RM-003 | evaluation | Eval report artifact + dashboard | 2 | 1 | done | plan §5-B; implemented on `feat/rm-003-eval-report-gating` | Delivered 2026-09-21 (PR 23): per-run eval report + coverage-gap artifacts (30-day retention) with CI-summary links; per-change eval gating via changed-files → skill mapping (matrix, one canary per changed skill); three-layer gating (pre-commit hermetic validators / advisory pre-push / required PR check); typed-assertion protocol (action/artifact/text over `opencode run --format json` event streams) with Layer-1 enforcement; retry + quarantine + deterministic continuation; first green-run capture pending the next qualifying weekly run (earliest: 2026-09-22 10:30 UTC, recorded per AC4). Evals run on the direct-key lane (`deepseek/deepseek-flash`, user directive 2026-09-21) at ~$0.68/weekly run (off-peak, measured). Remaining open under RM-003 follow-ups: two canary assertion-tuning fixes (reviewing-code, releasing-a-version), first green-run record, legacy-assertion migration of ~75 evals (migrate-on-touch). |
| RM-004 | governance | Formal governance artifacts | 2 | 2 | backlog | plan §5-C; repo audit (Governance L2); 2026-09-18 session | `CONTRIBUTING.md`, `CODEOWNERS`, `SECURITY.md`, `docs/ADRs/` exist and are referenced by contribution flow. Scope also includes the three-tier repo-memory structure (user-approved 2026-09-18): (1) `AGENTS.md` standing rules — auto-loaded, cross-session imperatives only; (2) `docs/ADRs/` decision record with `accepted`/`superseded`/`reversed` maturity, capturing binding and structure decisions; (3) plan lifecycle — plans are working artifacts whose essence is extracted into tracked docs before merge, then archived; no archive-as-memory tier. |
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

RM-001, RM-002, and RM-003 are done. RM-003 delivered the eval report/dashboard artifacts, per-change eval gating (changed-files mapping, matrix), typed-assertion protocol with Layer-1 enforcement, three-layer gating, retry/quarantine/continuation policies, and the direct-key eval lane (2026-09-21). Remaining RM-003 follow-ups: the two canary assertion-tuning fixes (reviewing-code, releasing-a-version), recording the first steady-state green weekly run (weekly cron now 10:30 UTC), and legacy-assertion migration of ~75 evals via migrate-on-touch. The next roadmap item is RM-004 (governance artifacts + the three-tier repo-memory structure). Design artifacts belong in `.opencode/plans/` via `architect` before `implementer` executes.
