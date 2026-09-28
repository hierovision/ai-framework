# Record format — the `INCIDENT-RECORD.md` contract

Single source of truth for the incident pass's output artifact. Write the record
to `INCIDENT-RECORD.md` at the working root unless the user names another path.
One record per incident (the incident id in the header is what later evidence
attaches to). A consumer (a responder, an auditor, a fix session) reads this
shape; keep it stable.

## Contents

- Record skeleton
- Disposition and severity vocabulary
- Tag vocabulary
- Plan shape
- Post-incident section
- Evidence & limitations

## Record skeleton

```markdown
# Incident record: <short title> (INC-<id>)

- **Status:** open | contained | eradicated | recovered | closed
- **Disposition:** confirmed-incident | suspected | not-an-incident
- **Severity:** sev1 | sev2 | sev3 | sev4 — <one-line basis>
- **Opened:** <UTC timestamp>   **Last updated:** <UTC timestamp>
- **Owner-role:** <role, not a name>
- **Detection source:** <scanner | advisory | report | log | person> + locator

## Summary
Three to five sentences: what is claimed, what the evidence currently shows,
what is decided, and the single most important next action.

## Timeline
| Timestamp (UTC) | Event | Evidence (source + locator) | Tag |
|---|---|---|---|
| ... | ... | ... | fact/assumption/inferred/open-question |

## Facts, assumptions, and open questions
### Facts
- <statement> — *evidence:* <locator>
### Assumptions
- <statement> — *confirm/refute by:* <check>
### Inferred
- <conclusion> — *from:* <facts + reasoning>
### Open questions
- <question> — *settled by:* <who/what>

## Scope & impact
- **Affected:** components / environments / tenants / data classes /
  credentials / artifacts.
- **Not affected (and why):** <explicit list>
- **Exposure:** who can trigger/exploit, ongoing?, trust boundaries crossed.
- **Unaffected-so-far but unassessed:** <name what analysis has not covered>

## Response plan
### Short-term containment
| Action | Owner-role | Depends on | Verification |
|---|---|---|---|
### Eradication
| Action | Owner-role | Depends on | Verification |
|---|---|---|---|
### Recovery
| Action | Owner-role | Depends on | Verification (negative + positive) |
|---|---|---|---|
### Long-term control
| Action | Owner-role | Route (designing-architecture / implementing-features) |
|---|---|---|

## Communications
| Audience | Trigger | Owner-role | Timing | Message category |
|---|---|---|---|---|

## Routed fixes
- <fix> -> implementing-features
- <control design> -> designing-architecture
- <pipeline hardening> -> securing-ci
- <vulnerability hunt> -> reviewing-security
- <static chain audit> -> auditing-supply-chain
- <runtime reproduction> -> debugging-test-failures

## Post-incident
- **What worked / what didn't:**
- **Root cause (as far as facts support):**
- **Detection/response gaps:**
- **Actions to prevent recurrence (routed):**

## Evidence
- Material read: <list or globs; what was not read and why>
- Checks run: <what was inspected; what was explicitly NOT executed>
- References consulted: <this skill's references + standards, by name>
- Limitations: <what could not be seen offline; what would settle each
  needs-verification>
```

## Disposition and severity vocabulary

Fixed words so a reader can scan mechanically. One disposition per record:

- **confirmed-incident** — evidence establishes a security event.
- **suspected** — plausible, evidence insufficient; the next check is named.
- **not-an-incident** — evidence establishes a benign explanation; the reason
  and the ruling-out evidence are recorded.

One severity per record (vocabulary in `references/method.md`): **sev1**
(critical, ongoing, cross-boundary/production-wide), **sev2** (confirmed,
significant, not production-wide), **sev3** (confirmed, limited), **sev4**
(informational / near-miss / hardening). Severity never overrides the
disposition: a `not-an-incident` has no severity.

## Tag vocabulary

Every statement in Timeline and Facts/Assumptions is tagged exactly one of
**fact** (with locator), **assumption** (with the check), **inferred** (with
the reasoning), **open-question** (with who/what settles it). No untagged
claim; no hedge-tags. A tag is not decoration — it tells the reader where the
certainty ends.

## Plan shape

An action is `action | owner-role | depends-on | verification`. The plan names
roles, not people. A plan step with no verification is not a plan step. The
recovery section pairs a **negative** verification (the exploited path is
dead) with a **positive** one (the service works), plus the rollback. This
skill writes the plan and does not execute it; the record notes actions as
*reported by the operator*, not as performed here.

## Post-incident section

Written even for a `not-an-incident` (as a short note, because the near-miss is
useful) and required for a confirmed incident. It records what worked, what did
not, the root cause to the extent facts support it, detection/response gaps,
and the routed preventive actions. It never asserts a root cause the facts do
not support — an unresolved cause is an open question.

## Evidence & limitations

The evidence section lets a third party trust the record: what was read, what
was inspected, what was explicitly **not** executed or fetched, which
references were consulted, and what could not be seen offline. A record that
claims a fact it never verified is a defect in the record, not coverage. State
limitations; a reader relies on knowing them.
