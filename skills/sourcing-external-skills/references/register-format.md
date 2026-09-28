# Register format — candidate register + decision log

Resolved against this skill's own directory — not the project's.

## Contents

- The candidate row schema
- Column rules
- Worked example register
- Decision log shape

## The candidate row schema

Fixed columns, copied from the sourcing plan:

```
| Candidate | Tier | License | Commit | Rubric | Pre-scan | Status | Reason |
```

- **Candidate** — short name + one-line what (e.g.
  `trace-triage — test-failure triage skill`).
- **Tier** — the source-tier classification (1–4, from Step 2).
- **License** — SPDX id at the pinned commit, or `unlicensed`.
- **Commit** — pinned commit SHA you reviewed, or
  `local snapshot <date>`.
- **Rubric** — fit × quality score (e.g. `6/9`), stating the axis
  scores (fit × quality).
- **Pre-scan** — `clean` or a comma-list of finding classes.
- **Status** — terminal: `shortlist` / `adopt` / `adapt` / `inspire` /
  `reject`.
- **Reason** — one sentence naming the gate or rubric result that
  decided the status.

Every field is mandatory for every row, including rejects — a failed
screen is a record, not a deletion.

## Column rules

- License is evaluated **at the pinned commit**, not the repo's
  current default branch (a repo can add or change a license later).
- When the candidate has no repo (a local bundle), the commit cell
  records `local snapshot <date>`.
- Status vocabulary is terminal and capped: screening produces
  `shortlist` or `inspire` (the user may also hand down `reject`
  directly); `adopt`/`adapt` enter only after user approval at the
  adjudication/adoption phases.
- `open` is the sanctioned NON-terminal status for a row whose gate
  inputs are not yet in hand (files not provided, scan not run,
  license not readable). An `open` row is never a closure claim: the
  pass summary lists open rows with what unblocks each, and the pass
  stays incomplete until they resolve.
- A critical security finding (credential egress, destructive command,
  embedded hostile instructions) forces `reject`/`security-gate`; a
  never-list or missing license forces out of copy/adapt candidacy
  (inspire at most).

## Worked example register

```markdown
## Candidate register — 2026-09-27 screen

| Candidate | Tier | License | Commit | Rubric | Pre-scan | Status | Reason |
|---|---|---|---|---|---|---|---|
| changelog-scribe — commit-log → release notes skill | 1 | BSD-2-Clause | b1c2d3e | 7/9 (3×3) | clean | shortlist | Allow-list license; closure on objective signals; advances to adjudication |
| release-captain — version-bump + tag checklist skill | 1 | GPL-3.0-only | f4a5b6c | 6/9 (2×3) | clean | reject | Never-list license — no copy/adapt (ADR-0011) |
| standup-summarizer — digest + blocker extractor | 1 | unlicensed | local snapshot 2026-09-27 | 5/9 (2×2) | clean | inspire | No explicit license at pinned copy → clean-room rewrite only (ADR-0011) |
| queue-ticketer — ticket-triage skill package | 1 | MIT | c9d8e7f | 4/9 (2×2) | credential access, covert callback | reject | Script reads a token and POSTs to an external endpoint — critical finding overrides the allow-list license (ADR-0012) |
```

The last row is the priority lesson: an allow-list license never launders
a critical security finding. The security gate runs first (Step 3),
and its `reject` verdict stands even when the license column is clean.

## Decision log shape

For every candidate that reaches adjudication (or later lands), one
entry per decision, appended (never rewritten):

```markdown
### <date> — <candidate> — <status>

- Gates: license <allow-list id|never-list id|unlicensed>;
  security <clean|finding classes>
- Rubric: fit <n>/3 × quality <n>/3 → <n>/9
- Evidence: scan artifact path, eval run IDs (Phase C), PR path
- Reason: <one sentence>
- Decided by: <user session/orchestrator record>
```

The decision log is append-only; supersede a prior entry with a new
dated one, never by editing history.
