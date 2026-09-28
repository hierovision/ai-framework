# Provenance note — reviewing-security

Dated 2026-09-28. Authoring pass: D1 of the skill-gap-analysis Phase D wave
(`.opencode/plans/skill-gap-analysis-phase-d.md`). This note is staged for the
orchestrator to file into `ATTRIBUTION.md` at landing — the authoring pass
does **not** edit `ATTRIBUTION.md`.

Status 2026-09-28: **filed** — the orchestrator added the provenance row and
the upstream MIT notice to `ATTRIBUTION.md` in the landing pass.

## Contents

- Adapted source (MIT)
- Inspiration consulted (no text or structure copied)
- Standards referenced
- Orchestrator action

## Adapted source (MIT)

| Field | Value |
|---|---|
| Source | `agamm/claude-code-owasp` — "OWASP Security Skill for Claude Code" (`owasp-security` skill) |
| URL | https://github.com/agamm/claude-code-owasp |
| Author / holder | agamm (upstream `LICENSE` carries `Copyright (c) 2026` with no named holder) |
| SPDX | MIT |
| Pinned commit | `8ac7965caa212b4a850aff8d3df0081ab3fa9eed` |
| Retrieved | 2026-09-28 |
| License status | ADR-0011 allow-list; verified at the pinned commit |

### Changes made

Adapted into ai-framework house conventions; every section was rewritten in
house voice and restructured around this library's read-only review pass,
triage dispositions, evidence logging, and sibling boundaries. Specifically:

- **Workflow**: re-expressed as the eight-step review pass with the
  entry-point → trust-boundary → sink method, the four-question reachability
  rubric, and confirmed/downgraded/dropped dispositions recorded in the
  report (`SKILL.md`, `references/report-format.md`).
- **Severity**: converted from the source's Critical/High/Medium/Low/Info
  scale to the house blocker/major/minor/nit backbone, specialized with
  security definitions.
- **New house material**: the read-only/untrusted-data posture (no execution,
  no network, no installs, no secret values in the report), the cardinal-rule
  and false-positive discipline, the out-of-scope/evidence/limitations report
  sections, the use-case inventory with eval mapping, sibling handoff
  routing, and the LLM/agentic sections' framing.
- **Trimmed**: the source's ~1100-line per-item deep-dive reference
  (`owasp-report.md`) was not carried; its per-category facts were folded
  into the compact checklist.
- **Rewritten**: `references/languages.md` pairs and
  `references/config-and-supply-chain.md` tables were re-derived and
  restructured (pinned digests, lockfile table, CI patterns).
- No claim of endorsement by upstream, OWASP, or any cited body.

### Where used

- `SKILL.md` — workflow, triage rubric, severity framing, LLM/agentic
  coverage pointers.
- `references/review-checklist.md` — OWASP Top 10 / ASVS / LLM / Agentic
  sweep structure and item coverage.
- `references/languages.md` — per-language pitfall pairs.
- `references/config-and-supply-chain.md` — config/supply-chain surfaces,
  lockfile table, security-header table, CI patterns.
- `references/report-format.md` — severity-by-exploitability framing, finding
  fields, triage dispositions.

### Upstream notice (retained per MIT)

```
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Inspiration consulted (no text or structure copied)

`trailofbits/skills` (https://github.com/trailofbits/skills) — CC-BY-SA-4.0,
ADR-0011 never-list. Consulted read-only at the pinned commit
`0cc1c73a5e96749ab32d7ea5e14892fafa6972ae` (`LICENSE` + `README` only; the
candidate register records it as `inspire`). Idea-level influences only:

- `entry-point-analyzer` — the discipline of enumerating state-changing entry
  points before analysis (reflected in Step 3).
- `fp-check` — systematic false-positive verification as a first-class review
  stage (reflected in the Step-6 triage rubric and dropped-candidate record).
- `vulnerability-triage-brocards` — triage dispositions for reports (reflected
  in confirmed/downgraded/dropped).
- `insecure-defaults` — fail-open defaults as a named review class (reflected
  in the A06 checklist section).

No Trail of Bits text, examples, structure, or wording was copied or closely
paraphrased.

## Standards referenced

The checklist maps to the editions below, as named by the adapted source at
the pinned commit. Standards editions move; re-verify the current edition
when a review's output cites a specific requirement ID.

- OWASP Top 10:2025 — https://owasp.org/Top10/2025/
- OWASP ASVS 5.0 — https://github.com/OWASP/ASVS (5.0 branch)
- OWASP Top 10 for LLM Applications 2026 — https://genai.owasp.org/
- OWASP Top 10 for Agentic Applications 2026 — https://genai.owasp.org/
- OWASP Cheat Sheet Series — https://cheatsheetseries.owasp.org/

## Orchestrator action

File the adapted-source row and the retained notice into `ATTRIBUTION.md`
using the row schema: source URL | author/holder | SPDX id | pinned commit |
retrieved date | changes | where used. No `ATTRIBUTION.md` edit was made by
this pass.
