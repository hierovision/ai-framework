# Candidate register — skill-gap-analysis (Phase B)

Status: **brief #1 adjudication complete — verdicts recorded; Phase D
adoption design next (per-item user sign-off required)**
Created: 2026-09-28
Scope of this pass: gap brief #1 — **application security engineering beyond
CI** (threat modeling, authn/authz review, secrets, OWASP-class review,
security headers, dependency/supply-chain audit, incident response).
Related: `.opencode/plans/skill-gap-analysis.md`,
`.opencode/plans/skill-gap-analysis-gap-map.md` (brief #1).

Method: candidates located by a public-source sweep (web + GitHub metadata,
2026-09-28); each fetched candidate cloned into
`.scratch/skill-gap-analysis/candidates/` for read-only vetting; ADR-0012
pre-scan run by a read-only class scanner over every fetched file; flagged
files reviewed by hand to classify (attack examples/docs are not hostile
instructions); license verified at the pinned commit. No candidate content
was executed.

## Candidate register

| Candidate | Tier | License | Commit | Rubric | Pre-scan | Status | Reason |
|---|---|---|---|---|---|---|---|
| claude-code-owasp — OWASP Top 10 / ASVS review workflow | 1 | MIT | 8ac7965caa212b4a850aff8d3df0081ab3fa9eed | 9/9 (3×3) | clean | shortlist | Allow-list license; review checklist + triage rubric + report format + evals; direct fit for the OWASP-class review gap |
| threat-model (alpha-omega-security) — threat-model orchestration | 1 | MIT | 192fd60cd0afe8851128ce4c68ed68c174c11948 | 9/9 (3×3) | clean (test-fixture URL reviewed) | shortlist | Allow-list license; dedicated threat-modeling workflow with machine-readable artifacts and specialist split; fills the named threat-modeling gap |
| ghostsecurity/skills — scan → validate → report | 1 | Apache-2.0 | 25fdf068760723b85b40e0224a3b8533e4aab31f | 6/9 (3×2) | clean | shortlist | Allow-list license (no NOTICE file at pinned commit); code/deps/secrets scanning with multi-stage verification; heavier vendor-integration surface (scripts, `~/.ghost` paths) raises adaptation cost |
| defending-code-reference-harness (anthropics) — threat-model → scan → triage → patch → IR | 1 | Apache-2.0 | d3bea6b5793b5f3d59a75ebe69a58efa88383145 | 6/9 (3×2) | destructive commands in build files/tests (reviewed — standard Dockerfile cleanup and untrusted-content tests) | shortlist | Allow-list license (no NOTICE file at pinned commit); official reference loop covering the brief end-to-end; upstream declares the repo unmaintained |
| vbsec (tanviet12) — 21-class security scanner | 1 | MIT | 1b86c27936d350d1a9ca67f044341262d4219d4e | 6/9 (3×2) | destructive commands, credential patterns, injection URLs in rule examples (reviewed — training/documentation data) | shortlist | Allow-list license; authz/IDOR/JWT/secrets classes + optional OSV dependency scan; Vietnamese-first authoring plus a sloppy license note ("will confirm when public") raise adaptation cost |
| trailofbits/skills — audit workflows (semgrep/CodeQL, triage, supply chain) | 1 | CC-BY-SA-4.0 | 0cc1c73a5e96749ab32d7ea5e14892fafa6972ae | n/a — license gate | clean (fetched files only: LICENSE, README) | inspire | ADR-0011 never-list (share-alike) — no copy/adapt; strong audit workflows usable as clean-room inspiration only, no close paraphrase |
| claude-code-security-review (anthropics) — PR security-review Action + prompt | 2 | MIT | 0c6a49f1fa56a1d472575da86a94dbc1edb78eda | 3/9 (3×1) | clean | inspire | Tier-2 primitive (GitHub Action + prompt, no SKILL.md) — re-express as a house review lens, never copy |
| appsec-skills (EresusSecurity) — SAST + manual audit + threat modeler | 1 | Apache-2.0 | 249fa52348f7e2dca7f06d2fb9075dfcb7fbbce0 | 4/9 (2×2) | injection/URL examples in reference docs (reviewed) | reject | Offensive-persona skew and weak maintenance signal (7★, 5 months stale); below the finalist bar |
| devops-security-agent-skills (BagelHole) — 163-skill devops/security pack | 1 | MIT | 0365f57a079b1332f95cf26e31dd2d5332a8399f | 4/9 (2×2) | injection/exfil examples in documentation (reviewed) | reject | Breadth-over-depth pack; each slice is shallower than a finalist; cherry-pick pattern source at most |
| cybersecurity-skill (Masriyan) — security ops/testing pack | 1 | MIT | 42e150160396a2e0e9e9ef7caf07bcefa2731212 | 4/9 (2×2) | hidden Unicode + injection patterns in test fixtures (reviewed — intentional obfuscation payloads); exfil example URLs in docs | reject | Pentest-flavored breadth below the finalist bar for a defensive-engineering brief |
| wshobson/agents — 183-skill multi-harness aggregator | 1 | MIT | 9b15b34b0bfc13a815cbfc2366e14ea549e09422 | 4/9 (2×2) | destructive/injection patterns in docs/tests (reviewed) | reject | Aggregator with variable quality; targeted slices covered better by finalists |
| sail-skill (pillar-labs) — agentic-security lifecycle assessment | 1 | CC-BY-NC-SA-4.0 | 67e1691ac64586b0abea96c74f511ea5628f62ed | n/a — license gate | clean (fetched files only) | reject | Never-list license (non-commercial share-alike) and adjacent agentic-security scope, not brief #1; cite-only at most |

## Gate notes

- **License gate.** MIT and Apache-2.0 rows are allow-list (ADR-0011). None of
  the Apache-2.0 candidates ships a `NOTICE` file at the pinned commit; if any
  portion is adapted later, the NOTICE obligation is vacuous today but the
  license text must be preserved and modifications stated. The two
  gate-terminal rows are never-list (share-alike variants) — no copy/adapt,
  inspiration or citation only.
- **Security gate.** The pre-scan walked every fetched file for hidden
  Unicode, prompt-injection patterns, exfiltration URLs, destructive commands,
  credential access, covert network, and dependency risk. All flagged files
  were reviewed by hand: they are attack examples in security documentation,
  intentional obfuscation test payloads, or build/test fixtures — none is an
  embedded hostile instruction chain aimed at the consuming agent; no
  credential egress or destructive command is executed by any workflow under
  screening. Raw scan outputs: `.scratch/skill-gap-analysis/scans/` (ephemeral).
- **No execution.** No candidate script, test, or tool was run; clones served
  read-only inspection only.

## Closure (screening pass)

```
Screened:      12 candidates (5 shortlist, 2 inspire, 5 reject)
Unreachable:   none
Provenance:    none staged — nothing copied or adapted in this pass
```

## Phase C — head-to-head adjudication

Method: each shortlisted candidate ran under the fresh-agent protocol on two
shared tasks (security review of a planted-issue fixture; threat model of a
design brief) plus no-skill baselines; vetted content staged read-only in
isolated workdirs on the direct-key lane; artifacts machine-graded against a
planted ground truth and hand-verified (`ground truth` + streams under
`.scratch/skill-gap-analysis/phase-c/`). One run-log record per run
(`logs/run-2026-09-28.jsonl`, ids cited below).

| Candidate | Review (recall/9, FP) | Threat (criteria/6) | Artifact delivery | Cost |
|---|---|---|---|---|
| claude-code-owasp | 9, 0 | 6 | both | $0.032 |
| threat-model | 9, 0 | 6 | both | $0.033 |
| defending-code | 9, 0 | 6 | both | $0.035 |
| ghostsecurity | **FAIL — none** | 6 | review failed | $0.030 |
| vbsec | **FAIL — none** | 6 | review failed | $0.028 |
| baseline (no skill) | 9, 0 | 5 | both | $0.009 |

**Fixture note (honest limit):** the no-skill baseline hit the review ceiling
(9/9, 0 FP) — recall does not discriminate on this fixture. Verdicts below rest
on discipline (entry-point→sink tracing, triage, severity+fix), coverage breadth
(ASVS/Top 10/LLM/agentic mapping), artifact rigor (machine-readable threat
outputs), and standalone robustness. A deeper multi-file adversarial fixture
belongs in the adapted skill's own eval net at Phase D.

## Decision log

### 2026-09-28 — claude-code-owasp — adapt

- Gates: license MIT (allow-list); security clean
- Rubric: fit 3/3 × quality 3/3 → 9/9
- Evidence: run `aa82c9bf-9052-4a7b-b844-65f93d3e9b2a` (review 9/9, FP 0);
  run `efcec53b-352e-4261-8073-8e38720071f9` (threat 6/6); scan
  `.scratch/skill-gap-analysis/scans/claude-code-owasp.json`
- Reason: strongest review workflow — OWASP/ASVS + LLM/agentic coverage,
  explicit triage rubric, severity+fix per finding; adapt into the house
  security-review capability under Phase D conventions.
- Decided by: orchestrator recommendation (Phase C record); adoption requires
  per-item user sign-off (Phase D).

### 2026-09-28 — threat-model (alpha-omega-security) — adapt

- Gates: license MIT (allow-list); security clean
- Rubric: fit 3/3 × quality 3/3 → 9/9
- Evidence: run `caf8c0e0-7ae2-4820-89f2-1248d64e30af` (review 9/9, FP 0);
  run `5420627c-df0c-4f1c-b714-19a1730bb6d1` (threat 6/6); scan
  `.scratch/skill-gap-analysis/scans/threat-model.json`
- Reason: dedicated threat-modeling procedure with contract-style
  machine-readable artifacts and triage dispositions; adapt as the house
  threat-modeling workflow.
- Decided by: orchestrator recommendation (Phase C record); adoption requires
  per-item user sign-off (Phase D).

### 2026-09-28 — defending-code-reference-harness (anthropics) — inspire

- Gates: license Apache-2.0 (no NOTICE file at pin); security clean
- Rubric: fit 3/3 × quality 2/3 → 6/9
- Evidence: run `0fd1a3d0-ddc6-42da-adab-dd20692fa4e5` (review 9/9, FP 0);
  run `405ebeea-205f-42ad-9ffb-0ecadc897ce6` (threat 6/6); scan
  `.scratch/skill-gap-analysis/scans/defending-code-reference-harness.json`
- Reason: unmaintained upstream — no direct integration; the loop structure
  (threat-model → scan → triage → patch → detect/respond) informs the adapted
  design as ideas only.
- Decided by: orchestrator recommendation (Phase C record).

### 2026-09-28 — ghostsecurity/skills — reject

- Gates: license Apache-2.0 (no NOTICE file at pin); security clean
- Rubric: fit 3/3 × quality 2/3 → 6/9
- Evidence: run `1a967f13-14cc-48e5-89cc-d6a186d379bc` (review FAIL — no
  artifact; workflow wrote to `$HOME/.ghost` outside the workdir and its
  CLI-ecosystem coupling stalled the pass); run
  `3648f001-5828-469e-8915-d8a58f108198` (threat 6/6); scan
  `.scratch/skill-gap-analysis/scans/ghostsecurity-skills.json`
- Reason: fails standalone delivery under isolation; its multi-stage
  validate→report pattern is noted as a possible input to the adapted design,
  but the candidate itself does not land.
- Decided by: orchestrator recommendation (Phase C record).

### 2026-09-28 — vbsec — reject

- Gates: license MIT (allow-list); security clean
- Rubric: fit 3/3 × quality 2/3 → 6/9
- Evidence: run `c1f9032e-4139-438a-be1e-12a351d3ea3d` (review FAIL — no
  artifact; helper script ran, the pass stalled on out-of-workdir scratch and
  ended with an empty result); run `831500b8-1af0-4d76-bef8-2c8395a61ee7`
  (threat 6/6); scan `.scratch/skill-gap-analysis/scans/vbsec.json`
- Reason: review workflow not robust under isolation; Vietnamese-first
  authoring raises adaptation cost; threat coverage already selected via
  `threat-model`.
- Decided by: orchestrator recommendation (Phase C record).

## History

- 2026-09-28 — Brief #1 screening pass complete: 12 candidates sourced,
  pre-scanned, license-gated, and rubric-screened; 5 shortlisted. Next: Phase C
  adjudication (head-to-head fresh-agent evals) — **requires explicit user
  sign-off to load candidate skills under the eval harness** (ADR-0012:
  wild content executes only with recorded sign-off).
- 2026-09-28 — **User signed off** Phase C execution (session, 2026-09-28).
  Head-to-head runs started for the 5 shortlisted candidates × 2 tasks
  (security review of a planted-issue fixture; threat model of a design
  brief) plus no-skill baselines; runs on the direct-key lane, isolated
  workdirs, no external network from candidate content.
- 2026-09-28 — Phase C complete for brief #1: 12 head-to-head runs recorded
  (`logs/run-2026-09-28.jsonl`; ids in the decision log below). Verdicts —
  adapt: `claude-code-owasp`, `threat-model`; inspire:
  `defending-code-reference-harness`; reject: `ghostsecurity/skills`, `vbsec`.
  Baseline saturation noted (the review fixture does not discriminate recall).
  Next: Phase D adoption design for the two adapts (per-item user sign-off).
- 2026-09-28 — **Phase D confirmed** by the user: three-item wave — D1
  security review (adapt `claude-code-owasp`; re-expressed review lens;
  trailofbits inspiration-only), D2 threat modeling (adapt `threat-model`),
  D3 supply-chain/IR (house-authored). Inspiration items are consumed
  explicitly per the phase-d briefs (`.opencode/plans/skill-gap-analysis-phase-d.md`).
  D1 dispatched for authoring.
- 2026-09-28 — D1 `reviewing-security` authored and independently verified
  (official runner 8/8; adversarial transcript clean); landing PR open,
  awaiting user sign-off.
- 2026-09-28 — **D1 landed**: sign-off given; PR #40 squash-merged as
  `e0baae9`. D2 (`threat-modeling`) next.
