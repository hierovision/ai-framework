# ADR-0011: License and ingest policy

## Status: accepted 2026-09-27

## Context

The skill-gap analysis plan (`.opencode/plans/skill-gap-analysis.md`) introduces a
disciplined workflow for sourcing and ingesting external skills. Before any wild
content is touched, the repo needs a binding license and an ingest policy that
defines what may be copied, adapted, or only used as inspiration — and how
provenance is recorded.

## Decision

### Repo license

- **MIT**, `Copyright (c) 2026 Zack Nichols`.

### Copy / adapt allow-list (SPDX identifiers)

- `MIT`
- `BSD-2-Clause`, `BSD-3-Clause`
- `ISC`
- `Apache-2.0` — preserve `NOTICE` file and state modifications
- `0BSD`
- `Unlicense`
- `CC0-1.0` (code)
- `CC-BY-4.0` (prose only)

### Never copy / adapt (never-list)

- `GPL-*`, `AGPL-*`, `LGPL-*` (any version)
- `CC-BY-SA-*`, `CC-BY-ND-*` (any version)
- Proprietary / paywalled content
- Anything without an explicit license at the pinned commit

### Missing or unclear license

- **Inspiration only** — clean-room rewrite, no close paraphrase.
- Pin the commit; verify the license at that commit.
- Record the decision in the candidate register with status `inspire`.

### Provenance

- Every ingested item gets a row in `ATTRIBUTION.md` (schema: source URL | author/holder | SPDX id | pinned commit | retrieved date | changes | where used).
- Verbatim portions keep upstream notices and license text appended in `ATTRIBUTION.md`.
- No trademark or implied-endorsement claims.
- In doubt → don't copy.

## Consequences

- The allow-list is intentionally narrow; any license not listed is treated as
  `inspire` at best.
- `ATTRIBUTION.md` becomes the single source of truth for all external
  provenance; the skill's `references/` directory carries a dated provenance
  note per ADR-0009.
- The new `sourcing-external-skills` skill (Phase 0.5) encodes these rules as
  executable gates.

## Sources

- `.opencode/plans/skill-gap-analysis.md` — Phase 0 policy decisions, user-approved 2026-09-27