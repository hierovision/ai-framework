# Provenance note — auditing-supply-chain

Dated 2026-09-28. Authoring pass: D3 of the skill-gap-analysis Phase D wave
(`.opencode/plans/skill-gap-analysis-phase-d.md`). **House-authored**: no
surviving adoptable candidate was selected for this brief, so nothing was
adapted or copied from an upstream skill. This note is staged for the
orchestrator to consider at landing — the authoring pass does **not** edit
`ATTRIBUTION.md`.

## Contents

- Authorship and licence status
- Standards referenced (authority, names only)
- Inspiration consulted (ideas only — no text or structure copied)
- No-text-incorporated statement
- Orchestrator action

## Authorship and licence status

| Field | Value |
|---|---|
| Origin | House-authored for the ai-framework skill library (D3) |
| Adapted source | none |
| Upstream text | none incorporated |
| Upstream licence | n/a — no upstream work is reproduced or adapted |
| Attribution obligation | none asserted; the orchestrator may record a no-attribution entry |

The decision to house-author rather than adapt is the candidate register's:
no candidate passed the bar for this brief (screening dead ends recorded for a
maintained secrets/CSP skill; broad packs rejected), and the brief directs a
house-authored tier-3 build (`.opencode/plans/skill-gap-analysis-candidates.md`,
D3 row).

## Standards referenced (authority, names only)

The signal classes and the audit frame are informed by the standards below.
They are cited as authority for the *discipline*; no standard text or
requirement list is reproduced, and the editions move — re-verify a specific
version when a report cites one.

- OpenSSF **SLSA** — build levels and provenance.
- **CycloneDX** and **SPDX** — SBOM formats and coverage expectations.
- **Sigstore** (cosign / Fulcio / Rekor) — artifact signing and transparency.
- **OSV** — the vulnerability-database schema; cited as the format for reading
  advisories *as data offline*, never as an endpoint to fetch.
- **OpenSSF Scorecard** checks — pinned dependencies, provenance, dangerous
  workflows — used as an audit checklist frame, not a tool to run.
- **OWASP dependency guidance** — dependency-confusion and typosquat practices,
  expressed as signal classes.

No claim of endorsement by OpenSSF, OWASP, Sigstore, Google, the CycloneDX
project, or any cited body.

## Inspiration consulted (ideas only — no text or structure copied)

- **dcode "detect → respond" loop** — the idea that a chain audit is one half
  of a lifecycle. Consumed at idea level; the response half is the sibling
  `handling-security-incidents`. No dcode text or structure is used.
- **trailofbits supply-chain audit practices** (CC-BY-SA-4.0, ADR-0011
  never-list) — consulted read-only; the never-list forbids copy/adapt and
  close paraphrase. Idea-level influence only: the practice of enumerating
  resolved dependencies before judging, and of separating a scanner signal
  from a validated finding.
- **ghostsecurity "scan → validate → report"** (candidate rejected for failing
  standalone delivery) — the idea that a raw scan signal must be *validated*
  before it is reported, reflected in this skill's triage dispositions. No
  ghost content is used; the candidate's own workflow did not land.

No Trail of Bits, dcode, or ghostsecurity text, examples, structure, or wording
was copied or closely paraphrased.

## No-text-incorporated statement

This skill is original house work. Every sentence, table, checklist, and
fixture was written for this library. No upstream skill file (text, structure,
or example) is incorporated. The standards named above are cited for authority;
their text is not reproduced. There is therefore no licence notice to retain and
no attribution row owed — the orchestrator may treat this as a no-attribution
entry if the library records provenance uniformly.

## Orchestrator action

Consider whether `ATTRIBUTION.md` should carry a no-attribution entry for this
skill (origin: house-authored; standards referenced; inspiration-only sources).
No `ATTRIBUTION.md` edit was made by this pass.
