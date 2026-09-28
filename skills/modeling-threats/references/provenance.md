# Provenance note — modeling-threats

Dated 2026-09-28. Authoring pass: D2 of the skill-gap-analysis Phase D wave
(`.opencode/plans/skill-gap-analysis-phase-d.md`). This note is staged for the
orchestrator to file into `ATTRIBUTION.md` at landing — the authoring pass
does **not** edit `ATTRIBUTION.md`.

Status 2026-09-28: **staged** — awaiting the orchestrator's landing pass.

## Contents

- Adapted source (MIT)
- Changes made
- Where used
- Upstream notice (retained per MIT)
- Inspiration consulted (no text or structure copied)
- Orchestrator action

## Adapted source (MIT)

| Field | Value |
|---|---|
| Source | `alpha-omega-security/threat-model` — "Threat Model Generator" (an orchestrator plus `threat-model-*` specialists) |
| URL | https://github.com/alpha-omega-security/threat-model |
| Author / holder | Alpha-Omega (upstream `LICENSE` carries `Copyright (c) 2026 Alpha-Omega`) |
| SPDX | MIT |
| Pinned commit | `192fd60cd0afe8851128ce4c68ed68c174c11948` |
| Retrieved | 2026-09-28 |
| License status | ADR-0011 allow-list; verified at the pinned commit (register verdict `adapt`) |

## Changes made

Adapted into ai-framework house conventions as **one skill** with references
(the source ships an orchestrator plus seven specialists):

- **Structure**: the orchestrator's seven-phase workflow (orient, mine,
  surface, interview, author, backtest, sign-off) and the standalone triage
  specialist were folded into one nine-step modeling pass plus a five-step
  triage pass in `SKILL.md`, with the specialists' procedures condensed into
  `references/`.
- **Cut**: the specialist roster and delegation map, the `threat-model.yaml`
  sidecar's full v2 field set, the JSON export's ten-label mapping, the
  glossary, the worked zlib sketch, and the batch/CI automation scripts
  (`new_threat_model.py`, `batch_threat_models.py`, the test harness). The
  house schema (`references/artifact-schemas.md`) is a reduced, fixed contract
  that keeps the triage-relevant facts and the authority order.
- **Re-expressed**: the prose section spec (§1–§19) compressed from ~840 lines
  to the artifact contract reference; the four-question framework, provenance
  tags, the closure constraint, disposition precedence, known-non-finding
  rules, and the backtest fail-safe kept as the discipline's backbone.
- **House material added**: the untrusted-data + read-only posture, the
  cardinal-rule closure-safety section, sibling handoff routing, the
  use-case inventory with eval mapping, the triage record shape,
  `THREAT-TRIAGE.md` as the triage output default, and the `accepted` status
  requiring zero unratified claims.
- No claim of endorsement by Alpha-Omega or any cited body.

## Where used

- `SKILL.md` — the modeling and triage passes, closure conditions, sibling
  boundaries.
- `references/principles.md` — is/is-not, four questions, writing bar,
  split rule, leave-out list.
- `references/artifact-contract.md` — §1–§19 prose spec, provenance tags,
  self-check gates.
- `references/artifact-schemas.md` — the reduced fixed YAML schema and JSON
  export shape.
- `references/triage.md` — routing algorithm, closed set, precedence,
  closure constraint, known-non-finding rules.
- `evals/` — fixtures and typed evals authored fresh for the house skill.

## Upstream notice (retained per MIT)

```
MIT License

Copyright (c) 2026 Alpha-Omega

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## Inspiration consulted (no text or structure copied)

`anthropics/defending-code-reference-harness` — Apache-2.0 (no `NOTICE` file
at the pinned commit), unmaintained upstream, register verdict `inspire`.
Consulted read-only at the pinned commit
`d3bea6b5793b5f3d59a75ebe69a58efa88383145`. Per the D2 brief, its
detect/respond loop ideas belong to the D3 supply-chain/IR item and are **not**
used in this skill; the only idea-level influence considered was the phase
shape of model → triage → backtest, which is also present in the adapted
source. No text, examples, structure, or wording was copied or closely
paraphrased.

## Orchestrator action

File the adapted-source row and the retained notice into `ATTRIBUTION.md`
using the row schema: source URL | author/holder | SPDX id | pinned commit |
retrieved date | changes | where used. No `ATTRIBUTION.md` edit was made by
this pass.
