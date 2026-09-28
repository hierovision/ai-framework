# Threat model — raster-import (v2.1.0)

## §1 Header

- Project: raster-import, v2.1.0 (commit e7d41b9). Date: 2026-08-20.
- Status: **accepted**. Triage policy: **strict**.
- Provenance legend: *(documented, source)* / *(maintainer, YYYY-MM)* /
  *(assumption, QN)* / *(inferred, QN)*.
- Draft confidence: 11 documented / 0 maintainer / 0 assumption / 0 inferred.
- raster-import parses layered raster documents into a scene tree.

**Triager quick-start**: locate the sink in §7; check §2/§3 and §6; apply
§17 precedence to exactly one disposition; then the provenance gate (only a
documented/maintainer claim closes; inferred escalates; assumption escalates
under strict). Nothing fits → MODEL-GAP and revise.

## §2 Scope and intended use

- In-process library parsing an untrusted raster document from the caller.
- Component families: `parser`, `scene` — both in scope.

## §3 Out of scope

- `tools/` (debug viewers) is unsupported developer tooling, not shipped.

## §4 Trust boundaries and data flow

- Boundary: the document bytes. Precondition for a `parser` finding: reachable
  from the document bytes.

## §5 Environment assumptions

- Single-threaded parse. No sockets, no subprocesses.
  *(documented, README "Embedding")*

## §6 Build-time and configuration variants

- `RASTER_FAST` disables layer-count validation; discouraged, unsupported for
  production parsing. *(maintainer, 2026-07)*

## §7 Assumptions about inputs

| Entry point | Input operand | Attacker-controllable? | Control kind | Caller must enforce | Provenance |
|---|---|---|---|---|---|
| `parse` | document bytes | **yes** | data, size | bound input size | *(documented, API reference)* |
| `parse` | `path` | no — trusted caller string | resource-name | pass a trusted path | *(documented, API reference)* |

| Component | Dimension | Status | Conditions / boundary | Routes to | Provenance |
|---|---|---|---|---|---|
| parser | recursive topology | claimed | nesting depth is bounded by the format cap (256 levels); deeper documents are rejected cleanly | §11 PP-RECURSION | *(documented, format spec "nesting")* |
| parser | numeric domain | claimed | supported sizes fail cleanly before integer wrap | §11 PP-MEMSAFE | *(documented, format spec)* |
| parser | resource complexity | disclaimed | no wall-clock timeout; caller may cap elapsed time | §12 DB-NO-TIMEOUT | *(documented, README FAQ)* |

## §8 Assumptions and guarantees about outputs

| Output channel | Component | Taint | Downstream must not assume | Provenance |
|---|---|---|---|---|
| scene tree | scene | same-as-input | safe for direct rendering | *(documented, API reference)* |

## §9 Assumptions about dependencies

- None beyond the C runtime. *(documented, build manifest)*

## §10 Adversary model

| Actor | In scope? | Capabilities held | Capabilities excluded | Goals | Provenance |
|---|---|---|---|---|---|
| document author | in | supply bytes, choose nesting depth | run code in the host | crash, resource exhaustion | *(documented, SECURITY.md)* |

## §11 Security properties the project provides

- **PP-RECURSION** — parsed nesting depth never exceeds the format cap of 256;
  deeper documents are rejected before recursion proceeds. Violation symptom:
  crash / stack-exhaustion. Tier: security-critical. Voided by: `RASTER_FAST`
  (see §6). *(documented, format spec "nesting")*
- **PP-MEMSAFE** — memory safety on well-formed input. Violation symptom:
  crash / oob-read / oob-write. Tier: security-critical. Voided by: nothing;
  search `grep -rn 'NO_CHECK' src/` — 0 hits.
  *(documented, API reference)*

## §12 Security properties the project does *not* provide

| ID | The project does not provide | Conditions / boundary | Tier | False friend? | Provenance |
|---|---|---|---|---|---|
| DB-NO-TIMEOUT | a wall-clock bound on parsing | any document; callers cap elapsed time | correctness-only | no | *(documented, README FAQ)* |

## §13 Downstream responsibilities

- Bound input size and elapsed time; treat the scene tree as untrusted.

## §14 Known misuse patterns

- Parsing with `RASTER_FAST` in a service exposed to untrusted documents.

## §15 Known non-findings

Not applicable — none established.

## §16 Conditions that would change this model

- A new format version, a new supported build flag, a new public entry point.

## §17 Triage dispositions

| Disposition | Licensed by |
|---|---|
| `VALID` | §11 |
| `VALID-HARDENING` | §14 |
| `OUT-OF-MODEL: trusted-input` | §7 |
| `OUT-OF-MODEL: adversary-not-in-scope` | §10 |
| `OUT-OF-MODEL: unsupported-component` | §3 |
| `OUT-OF-MODEL: non-default-build` | §6 |
| `OUT-OF-MODEL: dependency-contract` | §9 |
| `BY-DESIGN: property-disclaimed` | §12 |
| `KNOWN-NON-FINDING` | §15 |
| `MODEL-GAP` | §16 (revise) |

Precedence: KNOWN-NON-FINDING → unsupported-component → non-default-build →
dependency-contract → trusted-input → adversary-not-in-scope →
property-disclaimed → VALID → VALID-HARDENING → MODEL-GAP.

Closure constraint: closes need a documented or maintainer claim; inferred
escalates; assumption escalates under strict.

## §18 Open questions for the maintainers

None — every claim is documented and ratified.

## §19 Machine-readable companions

`threat-model.yaml` (structured index; derived) and `threat-model.json`
(lossy export; never a triage input). Authority: prose > yaml > json.
