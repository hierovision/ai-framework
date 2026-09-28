# Triage — classifying a finding against a model

Single source of truth for the triage contract: the closed disposition set,
the precedence order, the closure constraint, and the triage record shape.
The prose model's §17 states the same set; when the two disagree, fix the
model.

Read the **prose** and the **YAML index** — never the JSON export. The JSON
drops the triage policy, the precedence, and disclaimer tiers by design, so a
consumer holding only the JSON cannot route a report against the model.

## Contents

- Routing algorithm
- The closed disposition set
- Precedence (first match wins)
- Dispositions vs statuses
- The closure constraint
- Known non-findings — the four rules
- Output — the triage record

## Routing algorithm

Given one inbound finding — a report, scanner hit, fuzzer artifact, or AI
finding — and a finished (or drafted) model:

1. **Read the triage policy** declared in §1 (`strict` or `relaxed`). It
   controls only what an **assumption** may close.
2. **Locate the sink** in the §7 input-trust table (or the §8 output
   statement, for "downstream may assume X" findings).
3. **Locate the contract dimension** for state corruption, overflow,
   recursion, callback execution, serialization, lifecycle, concurrency, or
   complexity findings; follow the matrix row to its owning claim in
   §11/§12/§3/§18. Do not infer failure semantics from the parameter row
   alone.
4. **Check the required attacker capability and control kind** against
   §7/§10 — distinguish control of data from control of size, type, callback
   code, object topology, collaborator implementation, or serialized state.
5. **Check the affected component** against §2/§3, and any required build flag
   against §6.
6. **Apply the precedence below**, beginning with an exact §15 known
   non-finding match. Assign **exactly one** disposition, citing the section
   that licenses it.
7. **Pass the provenance gate** (the closure constraint): decide whether the
   licensing claim may close this report. Record the status.
8. If no rule fits, assign `MODEL-GAP` and trigger a revision — **do not
   improvise** a disposition. `MODEL-GAP` is not "other": it means the model
   is incomplete.

## The closed disposition set

| Disposition | Meaning | Licensed by |
|---|---|---|
| `VALID` | Violates a claimed property, via an in-scope adversary and input. | §11, §7, §10 |
| `VALID-HARDENING` | No claimed property violated, but an API misuse is easy enough to harden. Maintainer discretion; usually no CVE. | §14 |
| `OUT-OF-MODEL: trusted-input` | Requires attacker control of a parameter marked trusted. | §7 |
| `OUT-OF-MODEL: adversary-not-in-scope` | Requires an excluded attacker capability. | §10 |
| `OUT-OF-MODEL: unsupported-component` | Lands in code outside the model's scope. | §3 |
| `OUT-OF-MODEL: non-default-build` | Requires a configuration explicitly marked dev-only, discouraged, or unsupported. Non-default alone is insufficient. | §6 |
| `OUT-OF-MODEL: dependency-contract` | Root cause is a dependency failing its own contract, with conformant usage here. Forward upstream. | §9 |
| `BY-DESIGN: property-disclaimed` | Concerns a property the project explicitly does not provide. | §12 |
| `KNOWN-NON-FINDING` | Matches a documented recurring false positive exactly. | §15 |
| `MODEL-GAP` | Fits none of the above. Triggers a model revision; not a verdict on the report. | §16 |

## Precedence (first match wins)

1. An exact §15 pattern → `KNOWN-NON-FINDING`.
2. Unsupported component → `OUT-OF-MODEL: unsupported-component`.
3. Unsupported configuration → `OUT-OF-MODEL: non-default-build`.
4. Conformant use of a dependency that broke its own contract →
   `OUT-OF-MODEL: dependency-contract`.
5. Required control of a trusted input → `OUT-OF-MODEL: trusted-input`.
6. Required excluded attacker capability →
   `OUT-OF-MODEL: adversary-not-in-scope`.
7. Explicitly disclaimed property → `BY-DESIGN: property-disclaimed`.
8. Violated claimed property → `VALID`; otherwise an easy-to-prevent §14
   misuse may be `VALID-HARDENING`.
9. No supported conclusion → `MODEL-GAP`.

Multiple failed preconditions do not create a `MODEL-GAP`; this order resolves
them. `MODEL-GAP` is for a model that is silent or genuinely contradictory.

## Dispositions vs statuses

The disposition says which route the facts point at. The status says what the
triager may **do** about it today. A closing disposition always carries a
status; `VALID`, `VALID-HARDENING`, and `MODEL-GAP` are not closes and take no
status qualifier.

| Status | Meaning |
|---|---|
| `closed` | Licensed by a documented or maintainer claim. The report is answered. |
| `provisional` | A `relaxed`-policy assumption close. Cite the licensing QN; keep the §18 item open; re-open on a reporter challenge without new evidence. |
| `escalated` | The route is right but its licensing claim cannot close the report. Hand to the maintainer with the intended disposition and the blocking QN. |

Report both, as `DISPOSITION (status)` — for example
`OUT-OF-MODEL: trusted-input (escalated)`.

**An escalated finding is not a `MODEL-GAP`.** Escalation means the route is
right and the authority to use it is missing; `MODEL-GAP` means no route
exists. Keep the disposition, mark it `escalated`, and name the §18 question
that would unblock it. Do not feed an escalation into the revision loop — that
loop is for genuine gaps, and filling it with escalations manufactures phantom
model defects.

## The closure constraint

Any disposition that closes a report against the reporter (`OUT-OF-MODEL: *`,
`BY-DESIGN: *`, `KNOWN-NON-FINDING`) must be licensed by a **documented** or
**maintainer** claim, except as the declared triage policy permits for
**assumption** claims:

- **Inferred** licensing claims can only **escalate** the report, under every
  policy.
- Under **`strict`** (default), an assumption behaves like inferred: escalate
  only.
- Under **`relaxed`**, an assumption may license the **low-blast-radius**
  closes — `trusted-input`, `adversary-not-in-scope`,
  `unsupported-component`, `non-default-build`, and a *non*-security-critical
  `property-disclaimed` — as a **provisional** close (cite the QN, keep the
  §18 item open, re-open on challenge).
- **Security-critical floor (both policies).** An assumption never licenses
  `KNOWN-NON-FINDING`, a `security-critical` property disclaimer, or
  `dependency-contract`; those need documented or maintainer authority or
  they escalate.
- **Silence floor (both policies).** A §12 disclaimer resting on the
  *absence* of a statement rather than on a stated limit never closes a
  security-critical report, a known non-finding, or a dependency-contract
  route — even when tagged documented. Keep the documented tag (the absence
  really is verifiable) and escalate. A disclaimer with no tier is treated as
  security-critical: do not read a blank as permission.

`VALID` and `MODEL-GAP` are fail-safe under every policy. A model marked
`accepted` while retaining inferred or assumption claims is invalid — return
it for status correction.

## Known non-findings — the four rules

`KNOWN-NON-FINDING` is first in the precedence, so a loose entry suppresses a
whole class of reports ahead of every other safeguard. An "exact" match
satisfies every field of the §15 entry *and* the current discharging claim:

1. **Discharge only by a claim in the model.** The discharge reference is a
   stable claim ID from §3/§7/§11/§12. A process statement about reporting
   etiquette never discharges a finding.
2. **Match on the behaviour of the code, never on the quality of the
   report.** `no reproducer`, `no proof-of-concept`, or `scanner could not
   prove exploitability` are forbidden as match conditions; an unreproduced
   report stays open pending a reproducer.
3. **Name a symptom or attack class, not just a location.** An entry whose
   conditions reduce to "out of scope", "unsupported build", or "dependency
   root cause" is not a known non-finding — it keeps its `OUT-OF-MODEL`
   label.
4. **The discharging claim must cover the component.** A disclaimer written
   for one component does not discharge a report against another.

## Output — the triage record

Write the record as markdown (default `THREAT-TRIAGE.md` at the modeled root
or the path the user names; a short pass may state it inline instead):

```markdown
# Threat triage: <target> (<date>)

Model: threat-model.md @ <version/commit> — status <draft|unratified|accepted>,
policy <strict|relaxed>

| # | Finding | Sink / component | Disposition | Status | Licensed by | Provenance |
|---|---|---|---|---|---|---|
| 1 | Unbounded expansion (f-101) | decode / core | BY-DESIGN: property-disclaimed | closed | §12 DB-NO-CAP | documented (README FAQ) |
| 2 | Path traversal (f-102) | convert(path) / core | OUT-OF-MODEL: trusted-input | closed | §7 path row | documented (API reference) |
| 3 | Cache race (f-103) | warmup / core | MODEL-GAP | — | none | — |

## Follow-ups

- `MODEL-GAP` #3: add an `unresolved` concurrency matrix row + open question
  (proposed answer) and revise the model before re-routing.
- Escalated: none.
```

Every closing row cites the licensing section and the provenance kind of the
claim. A `MODEL-GAP` names the proposed revision; an escalation names the
blocking question. Then **STOP**: a `VALID` finding routes to
`reviewing-security` and/or `implementing-features`; a model revision routes
to the modeling pass; the triage pass does not fix, scan, or edit anything.
