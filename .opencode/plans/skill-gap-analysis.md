---
slug: skill-gap-analysis
title: Skill-pool gap audit + gated external-skill ingest
status: approved
created: 2026-09-27
revised: [2026-09-27]
related: [adr-0008, adr-0009]
---

# Plan: skill-gap-analysis

## Goal / Approach

Make the library earn its stated future state — turn an idea into a finished,
deployable product across work types and sizes (small business, non-profit,
education, medical, SaaS, turnkey, location-aware; one-line fix → greenfield) —
by closing the gaps between the current 23 skills / 10 personas and what that
work actually needs. Finish line (user-frozen 2026-09-27): **existing skills
improved with the research findings where applicable + new skills ingested
through a disciplined workflow**; every approved gap landed or explicitly
deferred with a dated reason.

Approach, four phases plus a policy prerequisite:

- **Phase 0 — policy artifacts.** `LICENSE` (MIT), `ATTRIBUTION.md`, and two
  ADRs (license/ingest policy; untrusted-content security gate) land before any
  wild content is touched.
- **Phase A — gap map (read-only).** Audit the current pool (trigger boundary,
  closure, use-case coverage baseline per skill) against a work-type × lifecycle
  matrix; inspect `pt`, `pln`, `choredomino`, `clcnext` read-only as evidence;
  produce a ranked candidate-search brief per gap.
- **Phase B — sourcing + screening.** Sweep the agreed source tiers (official
  and community Agent Skills, adjacent agent-framework primitives, authoritative
  references); every candidate gets provenance, license, and injection
  pre-scan; rubric screen → shortlist.
- **Phase C — adjudication.** Finalists get a head-to-head eval record
  (fresh-agent protocol, typed assertions, pass/fail + cost) against the
  incumbent or a baseline; verdicts (adopt/adapt/inspire/reject) with reasons.
- **Phase D — adoption waves.** Per approved item: adapt into house conventions
  by default; full landing gate (validator, evals ≥80% use-case coverage,
  security scan, provenance, orchestrator re-verification, registry); branch +
  PR + per-item sign-off. Amended existing skills hold the same bar.

A discipline workflow for sourcing/ingesting lands as the new
`sourcing-external-skills` skill (Open Question 1, decided) **authored
immediately after Phase 0** — it encodes the license/security/ingest rules and
drives Phases B–D; it is the first landing under its own gate (Phase 0.5).

## Acceptance Criteria

1. **Policy prereqs land before the first ingest** — `LICENSE` (MIT,
   `Copyright (c) 2026 Zack Nichols`), `ATTRIBUTION.md` (row schema below), and
   two accepted ADRs (license/ingest policy; untrusted-content security gate)
   exist with index rows in `docs/ADRs/README.md`. —
   `test -s LICENSE && test -s ATTRIBUTION.md`; both ADR files exist with
   `accepted` status; `grep -c` finds each ADR row in the index.
2. **Gap map complete and approved** — `.opencode/plans/skill-gap-analysis-gap-map.md`
   has one populated cell per work type (7) × lifecycle phase (7) = 49 cells,
   each verdict (covered / weak / absent) citing evidence (skill name + file, or
   sample-repo path); ranked candidate brief per gap; user approval recorded in
   `## History`. — row count 49 with zero blank verdict cells; approval entry
   present.
3. **Candidate register complete** — `.opencode/plans/skill-gap-analysis-candidates.md`
   carries for every sourced candidate: URL, SPDX id (or `unlicensed`), pinned
   commit, retrieved date, rubric score, injection pre-scan result, terminal
   status. Never-list licenses are never marked adoptable; unlicensed items are
   never marked copyable. — field-completeness sweep with no missing fields;
   no adopt/adapt status on never-list or unlicensed rows.
4. **Finalists adjudicated with recorded evidence** — every shortlisted
   candidate has a head-to-head record (eval run IDs, pass/fail, cost) against
   the incumbent or a baseline, and a verdict (adopt/adapt/inspire/reject) with
   reason in the decision log. — each recorded run ID resolves in
   `logs/run-*.jsonl`; one decision-log entry per shortlisted candidate.
5. **Landed items pass the full gate** — per item: validator green; evals
   covering ≥80% of a listed use-case inventory and demonstrably failable;
   security scan recorded; provenance recorded; independent orchestrator
   re-verification recorded; `registry.json` entry. — repo gates green on the
   landing branch; per-item evidence present in the PR body.
6. **Amended skills hold the same bar** — every finding that changes an
   existing skill updates that skill's evals/coverage for the amended surface
   (same gate as AC5). — amended skill's gates green on the amending branch.
7. **Nothing silently dropped** — every gap on the approved map reaches a
   terminal state (landed or dated-deferred); deferrals appear as ROADMAP rows.
   — map rows cross-checked against the decision log and `docs/ROADMAP.md`.
8. **Closing lifecycle per ADR-0008** — essence extracted into ROADMAP / ADRs /
   skill bodies; this plan and its companions move to
   `.opencode/plans/archive/`. — `ls .opencode/plans/*.md` prints nothing.

## Files to Modify

- `LICENSE` — new; MIT, `Copyright (c) 2026 Zack Nichols` (AC1)
- `ATTRIBUTION.md` — new; provenance rows + upstream notices for any verbatim
  portion (AC1, AC5)
- `docs/ADRs/ADR-0011-license-and-ingest-policy.md` + index — new (number is
  the next free at time of writing) (AC1)
- `docs/ADRs/ADR-0012-untrusted-content-security-gate.md` + index — new (AC1)
- `.opencode/plans/skill-gap-analysis.md` — this plan
- `.opencode/plans/skill-gap-analysis-gap-map.md` — new companion; 7×7 matrix +
  candidate brief per gap (AC2)
- `.opencode/plans/skill-gap-analysis-candidates.md` — new companion; candidate
  register + decision log (AC3, AC4)
- `docs/ROADMAP.md` — new rows per adoption wave / dated deferrals; essence
  extraction (AC7, AC8)
- `registry.json` — one entry per landed skill (AC5)
- `skills/<new-skill>/**` — TBD by the gap map; SKILL.md + references/ +
  evals/ + scripts/ per house conventions; names flagged in Open Questions (AC5)
- `skills/<incumbent>/**` — TBD amendments per findings (AC6)
- `CONTRIBUTING.md` — ingest-workflow row + decision-routing updates if the
  sourcing workflow lands as a skill (AC5, AC8)

### Revised 2026-09-27 — Phase 0 policy decisions (cold-execution detail)

The implementing session transcribes these user-approved decisions; they are
not re-opened:

- **LICENSE:** MIT text, `Copyright (c) 2026 Zack Nichols`.
- **ATTRIBUTION.md:** provenance table (header cites ADR-0011/0012); row schema
  `source URL | author/holder | SPDX id | pinned commit | retrieved date |
  changes | where used`; upstream notices + license text appended for any
  verbatim portion.
- **ADR-0011 — license and ingest policy (accepted 2026-09-27):**
  - Repo license: MIT (`Copyright (c) 2026 Zack Nichols`).
  - Copy/adapt allow-list: MIT, BSD-2/3, ISC, Apache-2.0 (preserve NOTICE +
    state modifications), 0BSD, Unlicense, CC0 (code); CC-BY-4.0 (prose).
  - Never copy/adapt: GPL/AGPL/LGPL, CC-BY-SA/ND, proprietary/paywalled, or
    anything without an explicit license at the pinned commit.
  - Missing/unclear license = inspiration only; clean rewrite, no close
    paraphrase. Pin the commit; verify the license at that commit.
  - Provenance for every ingested item; verbatim portions keep upstream
    notices; no trademark or implied-endorsement claims; in doubt → don't copy.
- **ADR-0012 — untrusted-content security gate (accepted 2026-09-27):**
  - All wild content is untrusted pure data; it must not be possible to
    interpret it as instructions.
  - Formal injection/vulnerability pre-scan per candidate (hidden Unicode,
    prompt-injection patterns, exfiltration URLs, destructive commands,
    credential access, covert network calls, dependency risk).
  - Every script fully security-reviewed; execution only after user sign-off;
    candidates that cannot be evaluated safely are rejected.

## Scope

**Included**

- Policy artifacts (Phase 0) as AC1
- Gap map + candidate register + adjudication records as AC2–AC4
- Adoption waves through the full gate, including eval-coverage audits and
  amendments to existing skills, as AC5–AC6
- ROADMAP reflection for deferrals; lifecycle close as AC7–AC8
- The new sourcing/ingest skill itself (name per Open Question 1)

**Excluded**

- Full field exercises on `pln` / `choredomino` — user-frozen as a follow-on
  program that consumes this effort's output (they need bringing up to speed
  first)
- Building product work in the sample repos (`pt`, `pln`, `choredomino`,
  `clcnext`) — read-only evidence sources here
- Executing any unreviewed third-party code; any ingest under a never-list or
  unclear license (inspiration-only rewrite at most)
- Paid-model spend beyond the cheap direct-key lane without an explicit flag
  first
- RM-006 templates, RM-015 consumer overrides, RM-012 pilot — separate rows;
  revisit only if the gap map proves a dependency
- Retaining the raw interview log as a durable artifact — `.scratch/` is
  ephemeral by design

## Schema / Type Impacts

No DB, no generated types.

- `registry.json` — additive entries per landed skill; ADR-0009 shape
  unchanged. Provenance lives in `ATTRIBUTION.md` + per-skill references
  (decided 2026-09-27).
- `ATTRIBUTION.md` row shape: source URL | author/holder | SPDX id | pinned
  commit | retrieved date | changes | where used.
- Candidate register row shape: candidate | source tier | license | commit |
  rubric score | injection pre-scan | status | decision reason.

## Verification

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/check_typed_evals.py --base main`
- `python3 scripts/test_changed_files.py && python3 scripts/test_eval_report.py && python3 scripts/test_eval_workflows.py && python3 scripts/test_quarantine.py && python3 scripts/test_stall_timeout.py && python3 scripts/test_typed_evals.py`
- `python3 skills/observing-runs/scripts/test_query.py && python3 skills/observing-runs/scripts/test_log.py && python3 skills/observing-runs/scripts/test_prune.py`
- `node skills/managing-github-issues/evals/fixtures/unit.test.mjs && node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs`
- `python3 -m yamllint -c .yamllint.yaml .github/workflows/`
- `bash -n install.sh`
- Per-change skill canaries via `eval-per-change.yml`; weekly
  `eval-behavioral.yml` backstop.
- Phase checks: `test -s LICENSE && test -s ATTRIBUTION.md`; gap-map cell count
  = 49 with no blank verdicts; register field-completeness sweep; each recorded
  head-to-head run ID resolves in `logs/run-*.jsonl`.

## Open Questions

- **New sourcing/ingest skill name** — **DECIDED 2026-09-27** (with plan
  approval): `sourcing-external-skills` (gerund-first per house convention;
  owns sweep → screen → adjudicate → ingest gate).
- **Provenance storage** — **DECIDED 2026-09-27**: `ATTRIBUTION.md` + a dated
  provenance note in each ingested skill's references; `registry.json` shape
  unchanged.
- **Companion artifact home** — **DECIDED 2026-09-27**: `.opencode/plans/`
  (working tier; essence extracted to ROADMAP at close).
- **Adoption-wave priority order** — **DECIDED 2026-09-27**: (1) cross-cutting
  app-security / a11y / PWA gaps that hit most work types; (2)
  sample-repo-driven gaps (pt / pln / choredomino / clcnext); (3) remaining
  types by frequency.
- **ADR numbers** — **DECIDED 2026-09-27**: ADR-0011 (license/ingest policy)
  and ADR-0012 (untrusted-content security gate).

## History

- 2026-09-27 — Draft created from the 7-question interview (frozen spec; raw
  log at `.scratch/skill-gap-analysis/NOTES.md`, ephemeral by design). Filed to
  the plans tier after the user challenged the scratch-only placement: the
  frozen spec + execution plan is a durable in-flight contract and belongs in
  `.opencode/plans/` per ADR-0008. Status `draft` pending user approval.
- 2026-09-27 — User approved the plan as drafted; status → `approved`. All
  five Open Questions resolved with their proposed defaults (sourcing skill
  name; provenance storage; companion home; adoption-wave order; ADR numbers).
- 2026-09-27 — Sequencing clarification recorded: `sourcing-external-skills`
  is authored immediately after Phase 0 (Phase 0.5) so it drives Phases B–D
  and is the first landing under the new gate.
- 2026-09-27 — Revision: Phase 0 policy decisions inlined into Files to Modify
  for cold execution (previously only in ephemeral scratch); no approach
  change. Gap captured as an improvement candidate: a program plan whose
  Phase 0 encodes interview-frozen policy needs that detail in the plan body,
  not hand-carried in the dispatch prompt.
- 2026-09-27 — Phase 0 executed by `implementer` on `feat/skill-gap-analysis`
  (commit a9e6f32): `LICENSE`, `ATTRIBUTION.md`, ADR-0011/0012, ADR index rows.
  Gates green (validator ×23, `bash -n install.sh`, yamllint, pre-commit
  Layer 1). Orchestrator verification passed on all five artifacts;
  orchestrator corrections applied: ADR-0011 source-citation fix and this
  entry. Five improvement candidates captured in
  `.scratch/skill-gap-analysis/subagent-issues.md` (one pre-dispatch, four
  from the run).
- 2026-09-28 — Phase 0.5 landed: `sourcing-external-skills` (SKILL.md + 3
  references + 7-eval manifest, typed `expect`, 7/7 use-case coverage) authored
  under `authoring-skills`, then independently re-verified by a fresh session
  under runner-real isolation (`deepseek/deepseek-flash`, CI continuation
  policy): 7/7 evals pass, no wild-content execution, no network egress,
  fixture hashes intact. Pre-landing fixes: eval-1 `expect` aligned to the
  skill's own register schema; stale use-case-1 wording; residual fixture-name
  leak; ADR-0011 allow/never lists restated in
  `references/license-policy.md` (runner-reachable execution; ADR stays the
  authority). Review: `approve-with-nits` (indent + handoff-template nits
  fixed). Registry: L1 entry added. Deferred framework debt: the tested agent
  can read the skill's `evals/` answer key under the installed layout —
  sanitized staging belongs in `run_behavioral_eval.py`, tracked separately.
- 2026-09-28 — Phase A produced: `.opencode/plans/skill-gap-analysis-gap-map.md`
  — 24-skill pool audit (trigger boundary / closure / coverage baseline),
  49-cell work-type × phase matrix with cited evidence, 13 ranked
  candidate-search briefs. Status in the companion: awaiting user approval
  (AC2). Phase B sourcing starts on approval.
- 2026-09-28 — Gap map approved by the user; AC2 satisfied. Phase B sourcing
  authorized — begins on the ranked briefs (brief #1: application security).
