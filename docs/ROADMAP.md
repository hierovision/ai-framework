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

## Swamp guards (how rows keep earning their place)

- **A row earns its place with a trigger, not an aspiration**: every open
  row cites what fires it — a dated wait, a signal from a real session,
  or an unblocked dependency. Rows whose trigger has not fired yet are
  legitimate table rows at their earned priority (bottom of the order is
  a place, not a demotion); the backlog notes are only for items without
  a trigger or an acceptance criterion yet.
- **Volatile-layer items get verify-mechanics, not build-mechanics**:
  artifacts that carry Layer-4 facts (dated pins, versions, provider
  specifics) carry their anti-rot mechanic in the row itself — re-verify
  on touch against current docs, CI drift alarm, dated headers.
- **The roadmap prunes, it never just appends**: rows that lose relevance
  are superseded or absorbed in place, with a dated note. The quarterly
  ALM review (RM-011) is the standing pruning mechanism.

## Roadmap

| ID | Category | Title | Priority | Phase | Status | Source | Acceptance |
|---|---|---|---|---|---|---|---|
| RM-001 | observability | Run-log schema + `observing-runs` skill | 1 | 1 | done | plan §5-A; repo audit (Observability L1) | Structured `logs/run-*.jsonl` emitted on every skill/agent invocation with skill, agent, model, tokens, duration, outcome, eval pass/fail; query script returns cost/task, latency, eval-pass rate. |
| RM-002 | evaluation | Wire behavioral eval suite into CI | 1 | 1 | done | plan §5-B; `skills/authoring-skills` eval protocol | Fresh-agent eval protocol runs on schedule/hermetic CI; regression failures block the run; no manual "I tried it" gates. Done covers the scheduled, hermetic CI gate with regression-blocking (verified via negative-path canary); per-change triggering and the two deferred network-fetching suites remain open under RM-003. AC5 live-dispatch regression check verified live 2026-09-16 ([run 35108912831](https://github.com/hierovision/ai-framework/actions/runs/35108912831)): broken-eval canary failed the job red and emitted an `eval_pass=false` record to the uploaded `logs/` artifact. Two network-fetching suites deferred — RM-003 tracks the coverage gap. Logs artifact contains schema-narrow metadata only (ts, run_id, skill, model, tokens, duration, outcome, eval_pass; failure-only detail ≤512 chars) — never prompts, outputs, tool args, or credentials; secrets masked; 30-day retention; inherits PUBLIC repo visibility. |
| RM-003 | evaluation | Eval report artifact + dashboard | 2 | 1 | done | plan §5-B; implemented on `feat/rm-003-eval-report-gating` | Delivered 2026-09-21 (PR 23): per-run eval report + coverage-gap artifacts (30-day retention) with CI-summary links; per-change eval gating via changed-files → skill mapping (matrix, one canary per changed skill); three-layer gating (pre-commit hermetic validators / advisory pre-push / required PR check); typed-assertion protocol (action/artifact/text over `opencode run --format json` event streams) with Layer-1 enforcement; retry + quarantine + deterministic continuation; first green-run capture pending the next qualifying weekly run (earliest: 2026-09-22 10:30 UTC, recorded per AC4). Evals run on the direct-key lane (`deepseek/deepseek-flash`, user directive 2026-09-21) at ~$0.68/weekly run (off-peak, measured). Remaining open under RM-003 follow-ups: two canary assertion-tuning fixes (reviewing-code, releasing-a-version), first green-run record, legacy-assertion migration of ~75 evals (migrate-on-touch). |
| RM-004 | governance | Formal governance artifacts | 2 | 2 | done | plan §5-C; repo audit (Governance L2); 2026-09-18 session | Delivered 2026-09-23 (feat/rm-004): the three-tier repo-memory structure live — (1) `AGENTS.md` standing rules (cross-session imperatives only); (2) `docs/ADRs/` founding set ADR-0001…0008 with `accepted`/`superseded`/`reversed` maturity + routing-table README; (3) plan lifecycle per ADR-0008 — plans and session handoffs are working artifacts in `.opencode/plans/` (tracked in this repo; the untracked-ledger gap closed), essence extracted before merge, archived after. `CONTRIBUTING.md` (gates matching ci.yml), `.github/CODEOWNERS`, `SECURITY.md` in place; `docs/handoffs/` retired (ADR-0008). RM-003 consolidation closed in the same pass: canary retype, error-guidance, SKILL body split, ledger reconcile; the two dated waits (first green-run record Mon 2026-09-28 10:30 UTC; fail-fast flip-back after two consecutive green runs) stay tracked under RM-003 follow-ups. |
| RM-005 | governance | Skill/agent registry manifest | 2 | 2 | done | plan §5-D | Delivered 2026-09-24 (feat/rm-005, ADR-0009): repo-root `registry.json` — 33 entries (23 skills + 10 personas), each with owner (`@hierovision`), L1–L4 maturity (evidence-based promotion bar: evals green + real-loop use + independent review), status (`active`/`deferred`/`deprecated`), and a validator-resolved `boundary_ref`. Enforced by `validate_skill.py --all` cross-check (orphan/ghost/field/boundary-ref) inside `quality-gates`; loader `scripts/registry.py` is the single source of truth (no hand-parsing); `coverage_gaps` names declared deferrals in `deferred_skills` instead of `no_default_marker`. Canary markers stay in `evals.json`; model bindings stay in model-routing (registry references, never duplicates). Consumed by tooling; RM-008/009/011 gain their join table. |
| RM-006 | integration | Adoptable CI/CD templates | 3 | 2 | backlog | plan §5-D; `skills/designing-cicd`; 2026-09-24 triage | `templates/` YAML a consumer repo can copy to get the evaluate→build→deploy golden path (pairs with `designing-cicd`; deploy-step templates encode `deploying-with-supabase` / `deploying-to-azure-swa`; hardening encodes `securing-ci`). Volatility disposition (2026-09-24): templates are Layer-3 artifacts with their Layer-4 facts (action SHAs, versions, provider keys) isolated inside each file — SHA-pinned, dated, current-state only, no changelogs; skill bodies cite, never quote. Anti-rot mechanic is part of the acceptance: dated header per template ("validated against current docs <date>"), re-verified on touch (when a template is actually copied/used), and a CI drift alarm (actionlint/yamllint on `templates/**`). **Trigger**: fires with the consumer-repo pilot (RM-012) — templates are built from what a real consumer exercise proves is needed, not speculatively. |
| RM-007 | integration | PR annotations from eval + run logs | 3 | 3 | backlog | plan §5-D | PR checks annotate eval result + link run-log; regression blocks merge. |
| RM-008 | decision-boundaries | Encoded boundary manifest per agent | 3 | 3 | backlog | plan §5-E; repo audit (Boundaries L2) | Each agent has decide/escalate/never manifest in config; enforced where automatable. |
| RM-009 | roi-math | Cost/ROI tracker (4 numbers) | 4 | 3 | backlog | plan §5-F | Script reads run logs → hours×rate, error-rate Δ, cycle-time Δ, ramp-time avoided per project. |
| RM-010 | human-in-the-loop | Standardized escalation/override artifact | 4 | 3 | backlog | plan §5-G; repo audit (HITL L3) | Every handoff emits consistent escalation-context payload + recorded-override entry. |
| RM-011 | optimize | Drift detection + quarterly ALM reviews | 5 | 4 | backlog | plan §5-A/B; ALM | Behavioral drift score per skill tracked; quarterly stage-gate review held per owner. |
| RM-012 | integration | Consumer-repo pilot — full loop in one real project | 4 | 3 | backlog | 2026-09-24 triage (user) | Install the framework into one real consumer project, run the complete loop there (plan → implement → verify → review), and harvest the drift, gaps, and byproducts back into skills (the mechanism that produced `releasing-a-version`). Acceptance: a dated harvest record — what drifted, what was missing, which skills gained evals/body corrections — folded into the library; RM-006's templates are scoped from what the exercise proves is needed. **Trigger**: fires when a real-world consumer exercise happens — the row exists so the session that happens in knows the loop's output contract; nothing to build until then. Amended 2026-09-24: the harvest consumes RM-014's two artifacts (improvement candidates + the target-repo uplift ledger) rather than session memory. |
| RM-013 | governance | Skill retirement flow (registry deprecated → removed) | 5 | 3 | backlog | 2026-09-24 triage (user); ADR-0009 | A documented, gated path from `status: deprecated` (ADR-0009) to fully retired: uninstalled by `install.sh`, evals moved out of the gate population (not silently skipped), references updated, registry entry retained with the supersession pointer. Acceptance: a retiring skill demonstrably leaves every gate (validator, per-change mapping, weekly suite) without a red suite or a silent drop — asserted by a retirement checklist + CI green after the removal. **Trigger**: fires on the first real retirement candidate (none exists today; the registry's `deprecated` status is ready for it). |
| RM-014 | self-improvement | Two-way exercise loop — framework candidates + target-repo uplift | 2 | 2 | backlog | 2026-09-24 triage (user) | Any exercise of the framework on a target repo leaves BOTH repos better, via two artifacts defined in one contract: (1) upstream — a fixed-shape improvement candidate (observed behavior, implicated skill, proposed correction, evidence, date) captured mid-exercise in the target repo, promoted to a GitHub issue on this repo at session close (triaging-requirements already consumes live GitHub issues); (2) downstream — a target-repo uplift: the exercise converts its learnings into the target repo's own three-tier memory (its AGENTS.md standing rules, its ADRs, its ROADMAP) plus a dated uplift ledger, so the next exercise starts from the new baseline. Routing rules land in the decision tables (CONTRIBUTING + ADR); the orphaned handoff-proposal sentence in authoring-skills is re-anchored to the contract. Registry tie-in: exercises are the evidence source for the L2→L3 promotion bar (ADR-0009). |

## Sequencing rationale
Phase 1 (RM-001, RM-002, RM-003) is the fast win: observability + continuous
eval directly accelerate quality and speed, the stated goal. Phase 2 (RM-004,
RM-005, RM-006) converts prose rules into enforced artifacts and ships reusable
pipelines. Phase 3 (RM-007, RM-008, RM-009, RM-010) closes integration,
boundary-encoding, ROI, and HITL consistency. Phase 4 (RM-011) is the
optimizing loop.

RM-012 (consumer-repo pilot) is the standing trigger-gated row: it sits at
priority 4 not because it is unimportant but because its trigger — a real
consumer exercise — has not fired; when it fires it becomes the natural
scoping pass for RM-006. RM-013 keeps the library's lifecycle closed: what
can be born through the registry can also retire through it.
## Next-session entry

RM-001 through RM-005 are done. RM-005 delivered the registry: repo-root
`registry.json` (33 entries), loader `scripts/registry.py` as the single
source of truth, validator cross-check in `quality-gates` (ADR-0009),
and `deferred_skills` awareness in coverage gaps. Two RM-003 dated waits
remain tracked, not re-litigated: the first green-run record (AC4) waits
on the next qualifying weekly run — Monday 2026-09-28 10:30 UTC, then run
`python3 scripts/eval-report.py green-run-status --record --run-id <id>
--date <d> --duration-min <n> --all-pass --quarantine-flips 0
--artifact-url <url>`; the fail-fast flip-back waits on two consecutive
fully-green CI runs (the test flips with the flag). The next roadmap
item is RM-006 (adoptable CI/CD templates — `templates/` a consumer repo
can copy for the evaluate→build→deploy golden path; pairs with
`skills/designing-cicd`). Design artifacts belong in `.opencode/plans/`
via `architect` before `implementer` executes; decisions land in
`docs/ADRs/` (routing table: `docs/ADRs/README.md`, ADR-0008).
