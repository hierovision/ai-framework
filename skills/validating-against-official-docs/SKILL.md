---
name: validating-against-official-docs
description: The meta-discipline of validating a skill, workflow, or config against authoritative vendor documentation (GitHub Actions, Supabase, Azure SWA, etc.) and emitting a cited adherence report — what adheres, what gaps exist, and the doc-backed fix for each. Use whenever the user says "check this against the official docs", "is this still correct per GitHub/Supabase/Azure", "validate our CI against the docs", "confirm this matches the vendor guidance", or surfaces a claim that needs a documented source — even without saying "validate". Consumed by the DevOps skills (designing-cicd, deploying-with-supabase, deploying-to-azure-swa, securing-ci) which say "verify against current docs via validating-against-official-docs". Not for writing the artifact (the producing skill does that), reviewing a diff against a plan (reviewing-code), or authoring tests (the test trio).
---

# Validating Against Official Docs

Validate a claim, skill, workflow, or config against the **authoritative
vendor documentation** and emit a cited adherence report a separate session
can trust cold. A validation pass is **done** when the report exists with:
every checked rule traced to a doc source (URL + section + retrieval date),
each gap named with its doc-backed fix, and a confidence note. The skill is
**read-only on the artifact** — it reports; it does not edit the thing it
validates. Edits route back to the producing skill (`designing-cicd`,
`securing-ci`, etc.).

This skill is the **meta-discipline** the other DevOps skills delegate their
"verify against current docs" step to. It formalizes the ad-hoc doc-checking
that scattered across those skills.

## The validation pass

Copy this checklist and check off items as you complete them.

```
Doc-Validation Progress:
- [ ] 1. Identify the artifact + the claim being checked
- [ ] 2. Identify the authoritative source(s) for that tech
- [ ] 3. Fetch the authoritative doc (note retrieval date + URL)
- [ ] 4. Extract the binding rules/limits from the doc (the "contract")
- [ ] 5. Compare the artifact against each rule -> adheres / gap / outdated
- [ ] 6. Cite every finding to the doc (URL + section)
- [ ] 7. Emit ADHERENCE.md (adheres / gaps-with-cited-fixes / confidence)
- [ ] 8. STOP (report only; route fixes to the producing skill)
```

### Step 1 — Artifact + claim

Name what is being validated (a workflow file, a skill's guidance, a config)
and the specific claim ("this CI is secure", "this is the correct Supabase
migrate-in-CI pattern"). A validation without a claim checks nothing.

### Step 2 — Authoritative source

Pick the **vendor's own docs**, not a blog or a StackOverflow answer. For
this library's stacks (see
[references/doc-sources.md](references/doc-sources.md)): GitHub *Events that
trigger workflows* / *Environments* / *Concurrency* / *Security hardening*;
Supabase *CLI Reference* / *Database Migrations* / *Branching*; Azure SWA
*Build configuration* / *Deploy to Azure Static Web Apps*. The skill cites
the doc URL so a reader can re-verify.

### Step 3 — Fetch + date

Fetch the doc (web fetch / vendor docs). Record the **retrieval date** —
vendor docs drift, and a citation without a date is not reproducible. If the
artifact is validated against a frozen doc copy in the repo, note that the
copy stands in for the live doc and date it.

### Step 4 — Extract the contract

From the doc, pull the **binding rules** the artifact must satisfy (triggers
that gate prod, forward-only migration semantics, action-pinning rules,
secret-handling rules). These are the checklines. A validation that quotes
the doc but extracts no testable rule proves nothing.

### Step 5 — Compare

For each rule: **adheres**, **gap** (artifact violates it), or **outdated**
(artifact predates a doc change). Map each gap to the exact rule it breaks.
A rule the artifact satisfies is "adheres" — record it too, so the report is
a full audit, not just a gripe list.

### Step 6 — Cite

Every finding carries the doc **URL + section** (and retrieval date). An
uncited finding is an opinion, not a validation. The report's value is the
trail back to authority.

### Step 7 — Emit ADHERENCE.md

Write `ADHERENCE.md` (or the project's report path) with three sections:

```
## Adheres
- <rule> — per <doc URL + section> (retrieved <date>)

## Gaps
- <artifact violation> — breaks <rule> (<doc URL + section>);
  fix: <doc-backed correction>

## Confidence
- <high|medium|low> — why (doc freshness, how directly the rule maps)
```

A report that only says "looks correct" with no rule mapping is not a
validation.

### Step 8 — STOP

Hand back the report. Do **not** edit the validated artifact — that is the
producing skill's job (route gaps to `designing-cicd` / `securing-ci` /
etc.). The validation is read-only on the artifact, diagnosis only.

## When not to use this skill

- **Writing the artifact** — the producing skill (`designing-cicd`,
  `deploying-with-supabase`, `deploying-to-azure-swa`, `securing-ci`).
- **Reviewing a diff against a plan** — `reviewing-code` (plan conformance,
  not doc conformance).
- **Authoring tests** — the test trio.
- **A claim with no citable vendor doc** — say so; confidence is `low` and
  the report says the rule is unverifiable, rather than guessing.

## References

- [references/doc-sources.md](references/doc-sources.md) — the authoritative
  doc URLs per stack this library covers, and what each validates. Read at
  Step 2 when picking the source.
- Vendor docs are the source of truth; skills in this library summarize
  them and must be re-validated against the live doc when a deprecation or
  version change is suspected (see `reference/model-routing.md` Deprecation
  watch for the cadence habit).
