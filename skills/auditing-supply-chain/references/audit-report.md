# Report format — the `SUPPLY-CHAIN-AUDIT.md` contract

Single source of truth for the audit's output artifact. Write the report to
`SUPPLY-CHAIN-AUDIT.md` at the audited root unless the user names another path.
A consumer (a maintainer, a `securing-ci` pass, a fix session, an incident
handler) reads this shape; keep it stable.

## Contents

- Severity backbone
- Finding shape
- Triage record
- Report skeleton
- Clean report
- Accepted risks
- Evidence & limitations

## Severity backbone

The house blocker / major / minor / nit backbone, specialized for the supply
chain. Severity follows **reachability + integrity impact**, not the pattern
that matched:

| Severity | Meaning | Examples |
|---|---|---|
| **blocker** | A shipped/consumed artifact is or can be attacker-controlled, or the build executes unpinned unsigned code | a resolved package from an unverified registry, a known-malicious/tampered artifact, a production build running an unpinned unsigned base image, install-time code of unclear provenance in a runtime dependency |
| **major** | Reachable with a precondition a real attacker can meet, or restricted-reach high impact | lockfile drift on a production app, a typosquat-like runtime dependency with an unverified publisher, missing artifact verification in a deploy consumer |
| **minor** | Defense-in-depth gap with no demonstrated path | no SBOM, missing provenance on an internal artifact, an unpinned build-only tool |
| **nit** | Hardening suggestion; say plainly it is **not** a vulnerability | an unpinned dev-only linter, formatting an SBOM description |

Confidence is separate from severity and does not change it:

| Confidence | When |
|---|---|
| **Confirmed** | Every step of the path is visible in the material; no assumptions |
| **Likely** | The path holds but one step depends on registry/build state not visible offline |
| **Needs verification** | A step cannot be settled without a registry/advisory/build lookup the offline posture forbids — say exactly what would settle it; do **not** fetch it |

Never inflate (a hardening note into a blocker to look thorough) and never
deflate (a reachable unpinned runtime dependency into "minor" to keep the
report calm). If nothing is reachable, say so directly — a short honest report
beats a padded one.

## Finding shape

One block per confirmed finding, highest severity first:

```markdown
### [SEVERITY] Short title (signal-class)
- **Location:** path/to/manifest-or-lock:LINE and the package/artifact concerned
- **Evidence:** the line/tag/hash that shows it (e.g. `"lodash": "*"` with no
  lock entry), or the missing file (no `package-lock.json`, no `.intoto`).
- **Impact path:** <unpinned artifact> -> <resolution/integrity step> ->
  <trust boundary> -> <build/release>. Who can substitute/inject what, and
  where it lands.
- **Fix:** the concrete change (pin + commit the lock; add the digest; verify
  the signature before use); a short snippet when it isn't obvious.
- **Confidence:** Confirmed | Likely | Needs verification — <what is
  unverified and what would settle it>.
- **Route:** implementing-features | designing-architecture | securing-ci |
  handling-security-incidents
```

Rules:

- Name the **signal class** so the finding maps to `references/method.md`.
- Every finding needs a location and concrete evidence. "This dependency feels
  risky" is not a finding.
- The fix must be actionable; if the right fix is a control that needs design
  (a signing pipeline, an SBOM-emission stage, a registry-proxy policy), say
  so and route it to `designing-architecture`.
- Never paste registry tokens or credentials from a `.npmrc`/manifest. Cite
  the key name and the exposure; recommend rotation as the fix.

## Triage record

Below the findings, the Triage record section records every signal that did
**not** become a confirmed finding, with its disposition and reason. This is
what makes the audit auditable and separates it from pattern matching; the
section is required even on a clean chain. Use the fixed disposition words —
**confirmed** (belongs under Findings, not here), **downgraded**,
**needs-verification**, and **dropped** — so a reader can scan the columns
mechanically:

| Signal (class + location) | Disposition | Reason |
|---|---|---|
| `"left-pad": "*"` in `package.json:14` | dropped | a committed lockfile with integrity hashes pins the resolution (Step-6 Q2) |
| `postinstall` in `node_modules-listed dep` | downgraded | hook runs only a local pinned step, no network or shell-from-data; hardening note |
| private `@acme/infra` consumed unscoped | needs-verification | cannot tell offline whether the name is public; check the registry scope mapping |
| `FROM node:latest` in `Dockerfile:1` | confirmed | build-only but reachable; mutable tag → mutable build (major) |

A clean chain still carries this table — the dropped reasons are evidence the
sweep happened. A dropped signal gets a reason, never silence.

## Report skeleton

```markdown
# Supply-chain audit: <target> @ <ref> (<date>)

## Scope
What was audited (paths/ref), the surfaces covered, and the decision the audit
supports.

## Out of scope
Application-code vulnerability review (-> reviewing-security), active incident
handling (-> handling-security-incidents), CI token/secret hardening
(-> securing-ci), threat modeling (-> modeling-threats), fixes
(-> implementing-features), license/legal/compliance conclusions. List what
the user asked for but this discipline does not do, and where it routes.

## Chain inventory
The manifests, lockfiles, build/publish config, artifacts, SBOM, and vendored
trees found — with the declared-vs-resolved agreement noted per component.

## Summary
One paragraph: counts by severity, the top thing to fix first, and the overall
posture (reachable findings present / hardening only / clean).

## Findings
### Blockers
### Majors
### Minors
### Nits
(Hardening notes that are not findings live here or under a clearly marked
"Hardening notes" subsection; never disguise one as a finding.)

## Triage record
(the table above)

## Accepted risks
(only if the owner explicitly accepted one — see below)

## Evidence
- Files read: <list or globs; what was not read and why>
- Surfaces walked: <declared / resolved / build / artifacts / SBOM>
- References consulted: <method sections + external standards, by name>
- Limitations: <what could not be seen offline (registry state, build logs,
  advisory data); what would settle each needs-verification>
```

## Clean report

When the sweep finds nothing reachable, write the same skeleton with an empty
findings section that says so plainly (`No confirmed findings.`), the triage
record showing what was examined and dropped, and the limitations. Do not pad
with nits to look thorough. A clean chain gets a clean report — and it is
still a report, not a shrug.

## Accepted risks

Only when the user explicitly accepts a finding's risk: record it in the
report with the finding, the date, and who accepted it. The finding **stays**
in the report and counts in the summary. An accepted risk is a dated decision,
not a resolution, and never a silent removal — the cardinal rule (never green
an audit by weakening the net) applies here exactly as it does in the review
and test disciplines.

## Evidence & limitations

The evidence section is what lets a third party trust the audit: which files
were read, which surfaces were walked, which references were consulted, and
what could not be seen. State limitations honestly — offline, registry state
and advisory data are invisible; a report that claims certainty about a
resolution it never verified is a defect in the audit, not coverage.
