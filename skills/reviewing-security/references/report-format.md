# Report format — the `SECURITY-REVIEW.md` contract

Single source of truth for the review's output artifact. Write the report to
`SECURITY-REVIEW.md` at the repo root unless the user names another path. A
consumer (a developer, a `reviewing-code` pass, a fix session) reads this
shape; keep it stable.

## Contents

- Severity backbone
- Finding shape
- Triage record
- Report skeleton
- Clean report
- Accepted risks
- Evidence & limitations

## Severity backbone

The house blocker / major / minor / nit backbone, specialized for security.
Severity follows **exploitability + impact**, not the pattern that matched:

| Severity | Meaning | Examples |
|---|---|---|
| **blocker** | Directly exploitable across a trust boundary, or an exposed live secret | unauthenticated RCE/injection, auth bypass, cross-tenant read/write (IDOR/BOLA), committed production credential, command injection reachable from user input |
| **major** | Exploitable with a precondition a real attacker can meet, or restricted-reach high impact | stored XSS behind auth, IDOR into another user's data, missing role check on a sensitive action, weak password hashing on live accounts, SSRF limited to non-metadata internal hosts |
| **minor** | Defense-in-depth gap with no demonstrated exploit path | missing security header, permissive CORS without credentials, vulnerable dependency with no reachable call, verbose errors that leak no secret |
| **nit** | Hardening suggestion; say plainly it is **not** a vulnerability | cookie flag on a non-sensitive cookie, log-format tuning |

Confidence is separate from severity and does not change it:

| Confidence | When |
|---|---|
| **Confirmed** | Every step of the path is visible in the code; no assumptions |
| **Likely** | The path holds but one step depends on configuration/runtime not visible |
| **Needs runtime verification** | A step cannot be settled statically (a race, a framework default, middleware not in the target) — say exactly what would settle it; do **not** run it |

Never inflate (a hardening note into a blocker to look thorough) and never
deflate (a cross-boundary exploit into "minor" to keep the report calm). If
nothing is exploitable, say so directly — a short honest report beats a padded
one.

## Finding shape

One block per confirmed finding, highest severity first:

```markdown
### [SEVERITY] Short title (CWE-###, OWASP A##:2025 / LLM## Name / ASI## Name)
- **Location:** path/to/file.ext:LINE (and the function/route)
- **Exploit path:** <entry point> -> <hops/boundary> -> <sink>. Who can
  trigger it, what they get, which trust boundary is crossed.
- **Impact:** the concrete consequence (data class, scope, persistence).
- **Fix:** the concrete change; a short snippet when the fix is not obvious.
- **Confidence:** Confirmed | Likely | Needs runtime verification — <what is
  unverified and what would settle it>.
- **Route:** implementing-features | designing-architecture | debugging-test-failures
```

Rules:

- Write LLM/ASI IDs **with their names** (`LLM03 Excessive Agency`) — editions
  reuse the numbers, so a bare ID is ambiguous.
- Every finding needs a location and a concrete reason. "This feels risky" is
  not a finding.
- The fix must be actionable (the change, not "sanitize input"); if the right
  fix is a design change (tenancy model, authz layer, secret management),
  say so and route it to `designing-architecture`.
- Never paste secret values. Cite the variable/key name and the exposure;
  recommend rotation as the fix.

## Triage record

Below the findings, the Triage record section records every candidate that did
**not** become a confirmed finding, with its disposition and reason. This is
what makes the review auditable and separates it from pattern matching; the
section is required even on a clean target (in that case it is the only
substance in the report). Use the fixed disposition words — **confirmed**
(belongs under Findings, not here), **downgraded** (real but constrained:
defense-in-depth, needs runtime verification, attacker's-own-data only), and
**dropped** (a pattern match that fails a triage gate) — so a reader can scan
the columns mechanically:

| Candidate (pattern + location) | Disposition | Reason |
|---|---|---|
| `eval` in `src/plugins.js:44` | dropped | the argument is a constant string from the built-in registry, not attacker-controlled (Step-6 Q1) |
| `child_process.execFile` in `src/thumbs.js:12` | dropped | constant binary, argv array from a fixed enum; no shell, no user data (Q2) |
| `X-Forwarded-For` logged in `src/http.js:81` | downgraded | attacker-influenced but log is internal-only; log-injection hardening (minor), not an exploit |
| race on `src/wallet.js:30` | downgraded | plausible double-spend, but the transaction isolation level is not visible in the target; needs runtime verification |

A clean review still carries this table — the dropped reasons are evidence
the sweep happened. A dropped candidate gets a reason, never silence.

## Report skeleton

```markdown
# Security review: <target> (<date>)

## Scope
What was reviewed (paths/commit/PR), and the decision the review supports.

## Out of scope
CI/CD pipeline hardening (-> securing-ci), accessibility (-> auditing-
accessibility), general diff/plan review (-> reviewing-code), threat
modeling, fixes (-> implementing-features). List what the user asked for but
this discipline does not do, and where it routes.

## Summary
One paragraph: counts by severity, the top thing to fix first, and the
overall posture (exploitable findings present / hardening only / clean).

## Findings
### Blockers
### Majors
### Minors
### Nits
(Hardening notes that are not vulnerabilities live here or under a clearly
marked "Hardening notes" subsection; never disguise one as a finding.)

## Triage record
(the table above)

## Accepted risks
(only if the owner explicitly accepted one — see below)

## Evidence
- Files read: <list or globs; what was not read and why>
- Checks run: <checklist sections walked; language/config references loaded>
- References consulted: <this skill's references + external standards, by name>
- Limitations: <what could not be seen (runtime config, external services);
  what would settle each "needs runtime verification">
```

## Clean report

When the sweep finds nothing exploitable, write the same skeleton with an
empty findings section that says so plainly (`No confirmed findings.`), the
triage record showing what was examined and dropped, and the limitations.
Do not pad with nits to look thorough. A clean target gets a clean report —
and it is still a report, not a shrug.

## Accepted risks

Only when the user explicitly accepts a finding's risk: record it in the
report with the finding, the date, and who accepted it. The finding **stays**
in the report and counts in the summary. An accepted risk is a dated decision,
not a resolution, and never a silent removal — the cardinal rule (never green
a review by weakening the net) applies here exactly as it does in the audit
and test disciplines.

## Evidence & limitations

The evidence section is what lets a third party trust the review: which files
were read, which checklist sections were walked, which references were
consulted, and what could not be seen. State limitations honestly — a review
that claims certainty about code it never saw is a defect in the review, not
coverage.
