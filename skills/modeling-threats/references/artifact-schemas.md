# Machine-readable artifact schemas

The structured index (`threat-model.yaml`) and the export
(`threat-model.json`) are **derived** from the prose. This file is the fixed
schema contract: registered keys, required fields, and the enums. Extend with
project-specific keys only under an `x-` prefix. When a derived artifact
disagrees with the prose, the derived artifact is wrong.

## Contents

- Provenance object
- `threat-model.yaml` — annotated schema
- Required and optional keys
- `threat-model.json` — export shape and limits

## Provenance object

Every claim, row, and field that carries authority uses the same provenance
object:

```yaml
provenance:
  kind: documented      # documented | maintainer | assumption | inferred
  source: "README FAQ: import sizes"   # required for documented; a locator
  # date: "2026-03"     # required for maintainer
  # question_id: Q4     # required for assumption and inferred
  # rationale: "..."    # optional, for assumption
```

A closing route may be licensed by a documented or maintainer claim under any
policy; by an assumption only under `triage_policy: relaxed`, only for a
low-blast-radius route, and never for a security-critical disclaimer, a known
non-finding, or a dependency-contract route; inferred never closes. See
[triage.md](triage.md).

## `threat-model.yaml` — annotated schema

```yaml
schema: threat-model/v1          # fixed
project: zlib
version: "1.3.1 @ 04f42cec"      # release tag or merged commit
date: 2026-09-28
prose:                           # binding to the canonical prose
  path: threat-model.md
  sha256: "<64 hex chars of the prose bytes>"
model_status: unratified         # draft | unratified | accepted
triage_policy: strict            # strict (default) | relaxed
confidence: {documented: 29, maintainer: 4, assumption: 0, inferred: 6}

components:                      # from §2/§3
  - name: core-inflate
    scope: in                    # in | out
    reachability_precondition: "reachable from the compressed input bytes"
    provenance: {kind: documented, source: "zlib manual"}

entry_points:                    # from §7; id is a function, route, or message
  - id: inflate
    component: core-inflate
    parameters:
      - name: input-bytes
        attacker_controllable: true
        control_kinds: [data, size]   # data | size/rate | type/class | callback/code
                                      # | object-graph-topology | collaborator-implementation
                                      # | resource-name | serialized-state | x-*
        caller_must_enforce: "bound the output buffer"
        provenance: {kind: documented, source: "inflate API contract"}

contract_dimensions:             # from the §7 matrix; no blank cells
  - component: core-inflate
    dimension: resource-complexity   # numeric-domain | failure-atomicity
                                     # | recursive-topology | callback-execution
                                     # | serialization | lifecycle | concurrency
                                     # | resource-complexity | x-*
    status: disclaimed           # claimed | disclaimed | not-applicable | unresolved
    conditions: "no cap on decompressed output; caller bounds it"
    routes_to: "§12 DB-BOMB"
    provenance: {kind: documented, source: "README FAQ: output size"}

properties_provided:             # from §11
  - id: PP-MEMSAFE
    components: [core-inflate]
    tier: security-critical      # security-critical | correctness-only
    conditions: "well-formed, size-bounded input on a supported platform"
    violation_symptoms: [crash, oob-read, oob-write]
    voids: []                    # or entries: {what: "...", ref: "inflate.c:1393"}
    provenance: {kind: documented, source: "zlib manual"}

properties_disclaimed:           # from §12
  - id: DB-BOMB
    components: [core-inflate]
    conditions: "no output budget is enforced by the library"
    tier: security-critical      # worst impact of a report this would close
    false_friend: false
    provenance: {kind: documented, source: "README FAQ: output size"}

adversaries:                     # from §10
  - name: compressed-input-author
    scope: in                    # in | out
    capabilities: [supply-input-bytes, choose-input-size]
    excluded_capabilities: [execute-in-host-process]
    goals: [memory-corruption, resource-exhaustion]
    provenance: {kind: documented, source: "SECURITY.md"}

dependencies:                    # from §9
  - name: caller-supplied-allocator
    relied_on_for: "standard allocator contract"
    covered_here: false
    violation_disposition: "OUT-OF-MODEL: dependency-contract"
    provenance: {kind: documented, source: "allocator API contract"}

build_flags:                     # from §6; [] when none change the properties
  - name: ZLIB_INSECURE
    default: "off"
    maintainer_stance: discouraged    # supported | dev-only | discouraged | unsupported
    affects_properties: [PP-MEMSAFE]
    provenance: {kind: documented, source: "zlib build documentation"}

known_misuses:                   # from §14
  - id: KM-CRC
    components: [core-inflate]
    pattern: "using the checksum to authenticate attacker-controlled data"
    safer_alternative: "authenticate the framed data with a MAC"
    provenance: {kind: maintainer, date: "2026-03"}

known_non_findings:              # from §15; only by-design / established KNFs
  - id: KNF-FUZZ-OOM
    components: [core-inflate]   # non-empty; `all-in-scope` is NOT allowed here
    symptom: unbounded-allocation   # symptom or attack class, never a location
    conditions: "input expands without bound; no library cap is promised"
    discharged_by: [DB-BOMB]     # stable claim IDs in this model
    provenance: {kind: documented, source: "README FAQ: output size"}

downstream_responsibilities:     # from §13
  - id: DR-CAP
    statement: "cap total decompressed output before allocating"
    provenance: {kind: documented, source: "README FAQ: output size"}

dispositions:                    # fixed, verbatim, in this order
  - VALID
  - VALID-HARDENING
  - "OUT-OF-MODEL: trusted-input"
  - "OUT-OF-MODEL: adversary-not-in-scope"
  - "OUT-OF-MODEL: unsupported-component"
  - "OUT-OF-MODEL: non-default-build"
  - "OUT-OF-MODEL: dependency-contract"
  - "BY-DESIGN: property-disclaimed"
  - KNOWN-NON-FINDING
  - MODEL-GAP

disposition_precedence:          # fixed, first match wins
  - KNOWN-NON-FINDING
  - "OUT-OF-MODEL: unsupported-component"
  - "OUT-OF-MODEL: non-default-build"
  - "OUT-OF-MODEL: dependency-contract"
  - "OUT-OF-MODEL: trusted-input"
  - "OUT-OF-MODEL: adversary-not-in-scope"
  - "BY-DESIGN: property-disclaimed"
  - VALID
  - VALID-HARDENING
  - MODEL-GAP

open_questions:                  # from §18
  - id: Q1
    question: "Is contrib/ supported for production use?"
    proposed_answer: "No; it is unsupported example code."
    lands_in: "§3"
```

Optional top-level keys (same provenance discipline when present):
`host_side_effects` (from §5), `outputs` (from §8), `generation` (producing
model/agent and effort, or `human-authored`). Project-specific keys use an
`x-` prefix.

## Required and optional keys

Required: `schema`, `project`, `version`, `date`, `prose`, `model_status`,
`triage_policy`, `confidence`, `components`, `entry_points`,
`contract_dimensions`, `properties_provided`, `properties_disclaimed`,
`adversaries`, `dependencies`, `build_flags`, `known_misuses`,
`known_non_findings`, `downstream_responsibilities`, `dispositions`,
`disposition_precedence`, `open_questions`.

Optional: `host_side_effects`, `outputs`, `generation`, `x-*`.

Lists may be empty (`[]`) only when the prose section is N/A with a reason.
Every item that carries authority has a `provenance` object with one of the
four kinds. The two disposition lists are **closed enums** — emit them
verbatim; do not add, rename, or reorder members.

## `threat-model.json` — export shape and limits

The JSON is a flat, lossy projection for external consumers — inventories,
dashboards, policy tooling. It is **never a triage input**.

```json
{
  "schema": "threat-model-export/v1",
  "project": "zlib",
  "version": "1.3.1 @ 04f42cec",
  "date": "2026-09-28",
  "prose": {"path": "threat-model.md", "sha256": "<64 hex chars>"},
  "confidence": {"documented": 29, "maintainer": 4, "assumption": 0, "inferred": 6},
  "components": [
    {"name": "core-inflate", "scope": "in"}
  ],
  "entry_points": [
    {"id": "inflate", "component": "core-inflate", "parameters": [
      {"name": "input-bytes", "attacker_controllable": true, "control_kinds": ["data", "size"]}
    ]}
  ],
  "properties_provided": [
    {"id": "PP-MEMSAFE", "components": ["core-inflate"], "tier": "security-critical",
     "violation_symptoms": ["crash", "oob-read", "oob-write"]}
  ],
  "properties_disclaimed": [
    {"id": "DB-BOMB", "components": ["core-inflate"], "tier": "security-critical"}
  ],
  "known_non_findings": [
    {"id": "KNF-FUZZ-OOM", "components": ["core-inflate"],
     "symptom": "unbounded-allocation",
     "why_safe": "input expansion is disclaimed by DB-BOMB; callers cap output",
     "cites": ["DB-BOMB"]}
  ],
  "dispositions": ["VALID", "VALID-HARDENING", "OUT-OF-MODEL: trusted-input",
    "OUT-OF-MODEL: adversary-not-in-scope", "OUT-OF-MODEL: unsupported-component",
    "OUT-OF-MODEL: non-default-build", "OUT-OF-MODEL: dependency-contract",
    "BY-DESIGN: property-disclaimed", "KNOWN-NON-FINDING", "MODEL-GAP"]
}
```

Rules and limits:

- The export carries no `triage_policy`, no disposition **precedence**, no
  disclaimer **tiers**, and no open questions. It can say what the contract
  is; it cannot route a report against it.
- A provenance kind is never upgraded in the export: nothing whose YAML
  provenance is inferred or assumption may surface as documented.
- Each `known_non_findings` entry carries its component scope in `why_safe`
  (or equivalent) and a `cites` list resolving to claim IDs in the same
  export; the flat form drops the YAML scoping fields, so an entry without
  scope can suppress everything.
- Regenerate the export whenever the prose or YAML changes. The `prose.sha256`
  is the binding: if it does not match the current prose, the export is stale.
