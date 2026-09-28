# Threat model — converter (v1.4.0)

## §1 Header

- Project: converter, v1.4.0 (commit 9c2f0aa). Date: 2026-08-14.
- Status: **accepted**. Triage policy: **strict**.
- Provenance legend: *(documented, source)* stated by maintainers in public
  docs; *(maintainer, YYYY-MM)* answered in review; *(assumption, QN)* a safe
  default, still unratified; *(inferred, QN)* reasoned but open.
- Draft confidence: 14 documented / 0 maintainer / 0 assumption / 0 inferred.
- converter decodes uploaded image and document files into raw bytes. It runs
  in-process in the caller, or as a CLI, on a supported 64-bit platform.

**Triager quick-start**

> 1. Locate the sink in the §7 trust table (or §8 for output findings).
> 2. Check the component against §2/§3 and any build flag against §6.
> 3. If the root cause is in a dependency, apply §9.
> 4. Apply the §17 precedence; assign exactly one disposition.
> 5. Provenance gate: only a documented or maintainer claim may close a
>    report; an inferred claim escalates; an assumption escalates under the
>    strict policy. If nothing fits, assign MODEL-GAP and revise the model.

## §2 Scope and intended use

- Intended use: decode a file the caller already holds, in-process or via the
  `convert` CLI. Not a service; it opens no sockets.
- Component families: `core` (decoder), `cli` (argument handling). Both in
  scope. Caller: a developer integrating the library; trusted to pass
  well-formed paths and to manage its own process.

## §3 Out of scope

- `contrib/` and `examples/` are unsupported sample code; not shipped.
  Not applicable as supported surface.

## §4 Trust boundaries and data flow

- Single boundary: the caller feeds a file (bytes) and a path into the
  process. The bytes are untrusted; the path is trusted caller input.
- Reachability precondition: a finding in `core` is in-model only if it is
  reachable from the input file bytes.

## §5 Environment assumptions

- Supported: 64-bit Linux/macOS builds, default feature set.
- No side effects: the decoder opens no sockets, spawns no processes, and
  reads no environment variables beyond the CLI's own argument parsing.
  *(documented, README "Embedding")*
- Concurrency is not discussed here.

## §6 Build-time and configuration variants

- No compile-time flag changes which security properties hold.

## §7 Assumptions about inputs

| Entry point | Input operand | Attacker-controllable? | Control kind | Caller must enforce | Provenance |
|---|---|---|---|---|---|
| `convert` | file contents | **yes** | data, size | bound the decoded output size | *(documented, API reference: convert())* |
| `convert` | `path` | no — trusted caller string | resource-name | pass a trusted, sanitized path | *(documented, API reference: convert())* |
| `convert` | `options` | no — trusted caller object | data | none | *(documented, API reference: convert())* |

Contract-dimension matrix:

| Component | Dimension | Status | Conditions / boundary | Routes to | Provenance |
|---|---|---|---|---|---|
| core | numeric domain | claimed | supported sizes fail cleanly before integer wrap | §11 PP-MEMSAFE | *(documented, format spec)* |
| core | failure atomicity | disclaimed | a failed decode leaves the output buffer partially written | §12 DB-PARTIAL | *(documented, API reference)* |
| core | resource complexity | disclaimed | no cap on decoded output; caller bounds it | §12 DB-NO-CAP | *(documented, README FAQ "Import sizes")* |

## §8 Assumptions and guarantees about outputs

| Output channel | Component | Taint | Downstream must not assume | Provenance |
|---|---|---|---|---|
| decoded bytes | core | same-as-input | safe for HTML, SQL, shell, or a text grammar | *(documented, API reference)* |

## §9 Assumptions about dependencies

- `libdecode` is a direct runtime dependency; the project relies on its
  documented memory-safety contract. A violation inside `libdecode` with
  conformant usage routes upstream as `OUT-OF-MODEL: dependency-contract`.
  *(documented, build manifest)*

## §10 Adversary model

| Actor | In scope? | Capabilities held | Capabilities excluded | Goals | Provenance |
|---|---|---|---|---|---|
| input-file author | in | supply input bytes, choose input size | run code in the host process | crash, memory corruption, resource exhaustion | *(documented, SECURITY.md)* |
| in-process caller | out | choose paths, mutate process state, replace the allocator | none — already runs as the process | any | *(documented, SECURITY.md)* |

## §11 Security properties the project provides

- **PP-MEMSAFE** — memory safety on well-formed, size-bounded input.
  Violation symptom: crash / oob-read / oob-write. Tier: security-critical.
  Voided by: nothing; search `grep -rn 'UNSAFE\|NO_CHECK' src/` — 0 hits.
  *(documented, API reference: memory safety)*
- **PP-BOUNDED-WRITE** — writes never exceed the caller-supplied buffer.
  Violation symptom: oob-write. Tier: security-critical.
  Voided by: nothing; search `grep -rn 'RAW_WRITE' src/` — 0 hits.
  *(documented, API reference: convert())*

## §12 Security properties the project does *not* provide

| ID | The project does not provide | Conditions / boundary | Tier | False friend? | Provenance |
|---|---|---|---|---|---|
| DB-NO-CAP | a cap on total decoded output | applies to `core`; any input may expand without limit. README FAQ "Import sizes" states there is no row or size limit and callers must bound output. | security-critical | no | *(documented, README FAQ "Import sizes")* |
| DB-PARTIAL | failure atomicity | a failed decode may leave the output buffer partially written | correctness-only | no | *(documented, API reference)* |

## §13 Downstream responsibilities

- Bound the decoded output size before allocating (`core`).
- Treat decoded bytes as untrusted for any downstream grammar.

## §14 Known misuse patterns

- Rendering decoded bytes into HTML/terminal without escaping.

## §15 Known non-findings

Not applicable — no recurring false positive has been established.

## §16 Conditions that would change this model

- A new input format, a new supported platform, a new dependency, a
  concurrency guarantee, or any report that does not route to a §17
  disposition.

## §17 Triage dispositions

| Disposition | Meaning | Licensed by |
|---|---|---|
| `VALID` | Violates a claimed property, in-scope adversary and input | §11 |
| `VALID-HARDENING` | No property violated; an easy-to-prevent §14 misuse | §14 |
| `OUT-OF-MODEL: trusted-input` | Needs control of a parameter marked trusted | §7 |
| `OUT-OF-MODEL: adversary-not-in-scope` | Needs an excluded attacker capability | §10 |
| `OUT-OF-MODEL: unsupported-component` | Lands in out-of-scope code | §3 |
| `OUT-OF-MODEL: non-default-build` | Needs an unsupported configuration | §6 |
| `OUT-OF-MODEL: dependency-contract` | Root cause is a dependency failing its own contract | §9 |
| `BY-DESIGN: property-disclaimed` | Concerns a property explicitly not provided | §12 |
| `KNOWN-NON-FINDING` | Matches a documented recurring false positive | §15 |
| `MODEL-GAP` | Fits none of the above; revise the model | §16 |

Precedence (first match wins): KNOWN-NON-FINDING → unsupported-component →
non-default-build → dependency-contract → trusted-input →
adversary-not-in-scope → property-disclaimed → VALID → VALID-HARDENING →
MODEL-GAP.

Closure constraint: a disposition that closes a report (`OUT-OF-MODEL: *`,
`BY-DESIGN: *`, `KNOWN-NON-FINDING`) must be licensed by a documented or
maintainer claim. An inferred claim escalates; an assumption escalates under
the strict policy. Status is `closed`, `provisional`, or `escalated`.

## §18 Open questions for the maintainers

None — every claim above is documented and ratified.

## §19 Machine-readable companions

- `threat-model.yaml` — structured index, derived from this prose.
- `threat-model.json` — lossy export for external consumers; never a triage
  input. Authority order: prose > yaml > json.
