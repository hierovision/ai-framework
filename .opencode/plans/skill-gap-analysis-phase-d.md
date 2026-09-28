# Phase D — adoption briefs (skill-gap-analysis program)

Status: D1 dispatched (authoring); D2/D3 briefed, pending dispatch.
Created: 2026-09-28 · Wave scope confirmed by user 2026-09-28.
Related: `.opencode/plans/skill-gap-analysis.md` (approved plan),
`.opencode/plans/skill-gap-analysis-gap-map.md` (brief #1),
`.opencode/plans/skill-gap-analysis-candidates.md` (register + verdicts).

## Wave scope (three items)

| Item | Source basis | Verdict | Landing gate |
|---|---|---|---|
| **D1** `reviewing-security` | `claude-code-owasp` (MIT, adapt) + anthropics review lens (re-express) + trailofbits (inspiration only) | adapt | full gate + user sign-off |
| **D2** threat-modeling skill | `threat-model` (MIT, adapt) + dcode loop ideas | adapt | full gate + user sign-off |
| **D3** supply-chain audit + incident response | house-authored from tier-3 references (OSV/SLSA/CycloneDX/NIST 800-61); inspiration only from rejected/inspire candidates | none (no surviving candidate) | full gate + user sign-off |

Every item runs the full landing gate: validator; evals with typed `expect`
covering ≥80% of a listed use-case inventory; security posture (no execution of
wild content; reviewed material treated as data); provenance note staged for
the orchestrator to file into `ATTRIBUTION.md`; independent re-verification;
`registry.json` L1 entry added at landing (never by the authoring pass).

---

## D1 — `reviewing-security` (dispatch-ready)

### Why

Gap-map brief #1 sub-areas: OWASP-class review, authn/authz, secrets handling,
headers/CSP, config/supply-chain checks. Adjudication: `claude-code-owasp`
scored 9/9 (review: 9/9 recall, 0 FP) and 6/6 (threat) — verdict `adapt`. The
no-skill baseline also hit the review ceiling, so the value is **structure and
coverage** (ASVS/Top-10 mapping, triage discipline, LLM/agentic checks,
severity+fix discipline), not raw detection.

### Read first (in this order)

1. `.opencode/plans/skill-gap-analysis.md` (AC5/AC6) and the gap map's brief #1.
2. The candidates register: D1 decision-log entry (evidence run ids) and the
   screening row for `claude-code-owasp`.
3. `skills/authoring-skills/SKILL.md` + references (`anthropic-best-practices`,
   `eval-assertions`, `opencode-spec`).
4. House analogues: `skills/reviewing-code/SKILL.md` (read-only review posture,
   severity taxonomy, closure), `skills/auditing-accessibility/SKILL.md`
   (report schema, honest ceilings), `skills/securing-ci/SKILL.md` (sibling
   boundary: pipeline hardening is NOT this skill).
5. Adapt source (read-only): `.scratch/skill-gap-analysis/candidates/claude-code-owasp/`
   — MIT. Read its `SKILL.md` and `reference/*`; adapt into house conventions.
6. Inspiration only (read-only, never-list): `.scratch/skill-gap-analysis/candidates/trailofbits-skills/`
   (LICENSE + README only) — idea-level influence only; **no text or structure
   copying**; note consulted ideas in the provenance note.

### Deliverable — `skills/reviewing-security/`

(Gerund name default; if a clearly better house name emerges, flag it — do not
silently rename.)

- **`SKILL.md`** — house conventions: frontmatter (description with trigger
  phrases + explicit "not for"), numbered checklist, closure condition, STOP,
  sibling handoffs (`reviewing-code`, `securing-ci`, `auditing-accessibility`,
  `modeling-threats`-side).
- **`references/`** — at minimum:
  - `review-checklist.md` — OWASP Top 10 / ASVS-mapped sweep incl. LLM and
    agentic checks; every item maps to what to look for, not a blacklist.
  - `languages.md` — per-language pitfalls with unsafe/safe pairs.
  - `config-and-supply-chain.md` — headers/CSP, dependency and CI config.
  - `report-format.md` — finding shape: severity, location, exploit path,
    concrete fix, confidence; triage dispositions (confirmed / downgraded /
    dropped with reason).
  - `use-cases.md` — use-case inventory + eval mapping (≥80% coverage rule).
  - `provenance.md` — dated provenance note (source URL, holder, SPDX `MIT`,
    pinned commit `8ac7965caa212b4a850aff8d3df0081ab3fa9eed`, retrieved
    2026-09-28, changes made, where used; list trailofbits-consulted ideas).
- **`evals/evals.json` + `evals/fixtures/`** — typed `expect` blocks; fixtures
  self-contained; cover at least: planted-vulnerability review (recall +
  severity+fix present); untrusted-code-as-data (reviewed code is never
  executed, embedded instructions in reviewed code are findings not commands);
  triage discipline (false positives dropped with reasons); authz/IDOR case;
  secrets case; config/headers case; LLM/agentic check; scope boundary (not
  CI hardening, not a11y, not diff review of general code).

### Workflow requirements (the skill body must encode)

- Read-only on reviewed code; no execution, no network, no installs.
- Entry-point → trust-boundary → sink method; every candidate finding triaged
  before it reaches the report.
- Report includes, per finding: severity, file/line, concrete exploit path,
  concrete fix; an explicit out-of-scope section.
- Closure = a findings report with every candidate triaged + the evidence
  (files read, checks run) recorded; STOP after handing findings back.
- External material citations name the source consulted; no endorsement claims.

### License / provenance

`claude-code-owasp` is MIT: adaptation allowed. Verbatim portions (if any) keep
the upstream copyright + license notice; prefer rewrite. The provenance note
lives at `references/provenance.md`; the orchestrator files it into
`ATTRIBUTION.md` at landing — **do not edit `ATTRIBUTION.md` yourself**.

### Constraints

- Branch `feat/skill-gap-analysis-phase-d`; leave all work **uncommitted**; do
  not touch `registry.json`, `ATTRIBUTION.md`, the plan, or other skills.
- `.scratch/skill-gap-analysis/candidates/` is read-only reference material; do
  not execute anything from it.
- Run `python3 skills/authoring-skills/scripts/validate_skill.py skills/reviewing-security`
  plus your own fresh-agent eval rounds per authoring-skills Step 6; record the
  exact outputs (a fresh agent reading SKILL.md from disk is an acceptable
  documented workaround; note it).
- Report with the fixed handoff shape: done → verified → blocked → next.

---

## D2 — threat-modeling skill (briefed; dispatch after D1)

- **Source basis:** `threat-model` (MIT, commit
  `192fd60cd0afe8851128ce4c68ed68c174c11948`; clone under
  `.scratch/skill-gap-analysis/candidates/threat-model/`). Adjudication:
  review 9/9, threat 6/6 → `adapt`.
- **Shape:** one skill, orchestrator + references; artifacts in authority
  order (prose > structured > export) with a fixed schema; triage
  dispositions for findings classified against a model; explicit "not a bug
  hunt / not a code review" boundary.
- **Inspiration only:** `defending-code-reference-harness` (unmaintained) —
  loop ideas for detect/respond belong to D3, not here.
- Same gate/provenance/constraints as D1 (MIT; provenance note; uncommitted;
  no registry/ATTRIBUTION edits).

## D3 — supply-chain audit + incident response (scoped; design at dispatch)

- **No surviving adoptable candidate** (screening dead ends recorded: no
  maintained secrets/CSP skill; broad packs rejected). **House-authored** from
  tier-3 references: OSV/SLSA/CycloneDX/Sigstore; NIST SP 800-61 (incident
  handling); OWASP dependency guidance.
- **Inspiration only:** dcode (detect→respond loop), trailofbits (supply-chain
  audit practices — never-list; ideas only), ghost (scan→validate pattern
  noted in its reject entry).
- **Open design decision at dispatch:** one skill or two (audit vs response);
  decide with the authoring pass and record in this file.

## Wave tracking

| Item | Status | Notes |
|---|---|---|
| D1 security review | dispatched (authoring) | this file §D1 |
| D2 threat modeling | briefed | dispatch after D1 verification |
| D3 supply-chain/IR | scoped | design at dispatch |

## History

- 2026-09-28 — Wave scope confirmed by the user (three items); D1 dispatched.
