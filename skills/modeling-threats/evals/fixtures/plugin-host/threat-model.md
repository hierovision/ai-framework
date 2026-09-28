# Threat model — plugin-host (v3.0.2)

## §1 Header

- Project: plugin-host, v3.0.2 (commit c9a1f02). Date: 2026-08-05.
- Status: **accepted**. Triage policy: **strict**.
- Provenance legend: *(documented, source)* / *(maintainer, YYYY-MM)* /
  *(assumption, QN)* / *(inferred, QN)*.
- Draft confidence: 12 documented / 0 maintainer / 0 assumption / 0 inferred.
- plugin-host embeds third-party plugin code into a host application.

**Triager quick-start**: §7 sink → §2/§3 component → §6 build → §9 dependency
→ §17 precedence → one disposition → provenance gate (documented/maintainer
closes; inferred escalates; assumption escalates under strict).

## §2 Scope and intended use

- In-process host that loads plugins shipped in the host's own plugin
  directory. Components: `loader`, `config-loader` — in scope.

## §3 Out of scope

- `contrib/` contains sample and example plugins. It is unsupported, not
  shipped, and not part of the supported surface. *(documented, README
  "contrib")*

## §4 Trust boundaries and data flow

- Boundary: the plugin directory is trusted (operator-controlled); plugin
  config files are parsed by the host.

## §5 Environment assumptions

- Loader reads the plugin directory; no network. *(documented, README)*

## §6 Build-time and configuration variants

- `PLUGIN_DEV` disables signature checks; dev-only, unsupported for
  production. *(maintainer, 2026-06)*

## §7 Assumptions about inputs

| Entry point | Input operand | Attacker-controllable? | Control kind | Caller must enforce | Provenance |
|---|---|---|---|---|---|
| `loadPlugin` | `name` | no — from operator config | resource-name | keep the plugin directory trusted | *(documented, API reference)* |
| `parseConfig` | config text | no — operator-supplied | data | pass trusted config text | *(documented, API reference)* |

| Component | Dimension | Status | Conditions / boundary | Routes to | Provenance |
|---|---|---|---|---|---|
| config-loader | numeric domain | claimed | `parseConfig` truncates fractional digits to two decimals; this rounding is intentional | §11 CFG-ROUNDING | *(documented, API reference: parseConfig)* |
| loader | resource complexity | disclaimed | no cap on plugin count; operator controls the directory | §12 DB-NO-COUNT | *(documented, README)* |

## §8 Assumptions and guarantees about outputs

| Output channel | Component | Taint | Downstream must not assume | Provenance |
|---|---|---|---|---|
| loaded plugin handles | loader | trusted | nothing | *(documented, API reference)* |

## §9 Assumptions about dependencies

- No runtime dependencies beyond the host runtime. *(documented, build
  manifest)*

## §10 Adversary model

| Actor | In scope? | Capabilities held | Capabilities excluded | Goals | Provenance |
|---|---|---|---|---|---|
| operator | in | choose plugin directory contents, config text | — | misconfiguration, not attack | *(documented, SECURITY.md)* |
| network attacker | out | none — no network surface | send input to the host | any | *(documented, SECURITY.md)* |

## §11 Security properties the project provides

- **CFG-ROUNDING** — `parseConfig` truncates fractional values to two
  decimals; callers get a stable, rounded number. Violation symptom:
  wrong-output for the precision contract only. Tier: correctness-only.
  *(documented, API reference: parseConfig)*
- **LOADER-TRUST** — `loadPlugin` only loads from the host's plugin
  directory. Violation symptom: load an arbitrary path. Tier:
  security-critical. *(documented, API reference: loadPlugin)*

## §12 Security properties the project does *not* provide

| ID | The project does not provide | Conditions / boundary | Tier | False friend? | Provenance |
|---|---|---|---|---|---|
| DB-NO-COUNT | a cap on the number of plugins loaded | operator controls the directory | correctness-only | no | *(documented, README)* |

## §13 Downstream responsibilities

- Keep the plugin directory operator-controlled.

## §14 Known misuse patterns

- Shipping a plugin that reads its own config with floating-point precision
  expectations.

## §15 Known non-findings

| ID | Components | Symptom / attack class | What gets reported | Conditions for an exact match | Discharged by | Provenance |
|---|---|---|---|---|---|---|
| KNF-ROUND | config-loader | wrong-output (precision) | "parseConfig loses precision on decimals (e.g. 1.005 → 1.00)" | component `config-loader`; symptom float-rounding; behavior of `parseConfig` only | CFG-ROUNDING | *(documented, API reference: parseConfig)* |

## §16 Conditions that would change this model

- New entry points, a network surface, a change to `parseConfig` rounding.

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

Closure constraint: closes need documented/maintainer; inferred escalates;
assumption escalates under strict.

## §18 Open questions for the maintainers

None — every claim is documented and ratified.

## §19 Machine-readable companions

`threat-model.yaml` (derived index) and `threat-model.json` (lossy export;
never a triage input). Authority: prose > yaml > json.
