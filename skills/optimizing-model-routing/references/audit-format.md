# Model-Check Artifact Format

Read at Step 6 before writing the artifact, and at Step 8 for the
model-routing.md update marker. The artifact is the durable evidence
record the user reviews against; the presented table is its summary.

File: `reference/model-check-YYYY-MM-DD.md` (repo-relative; one per pass,
never overwrite a prior dated artifact).

## Sections (fixed order)

```markdown
# Model Check + Right-Sizing — YYYY-MM-DD

## Sources
- <catalog source> — retrieved YYYY-MM-DD (live fetch or snapshot path)
- <benchmark source> — retrieved YYYY-MM-DD, independence status
  (independently reproduced / cross-checked / vendor self-reported)

## Current bindings
<role → current free / Go / Zen + the agent file binding the free default>

## Per-role analysis
<per role: candidates considered, decisive evidence with source + date,
why the winner wins, what was rejected and why — including scores that
did NOT decide (vendor-only, capability-gated out, excluded)>

## Proposed bindings
<role → proposed free / Go / Zen, each marked changed or unchanged,
with the one-line bench basis>

## Questionable / uncertain
<vendor-only scores, unbenched new models, catalog-vs-binding mismatches,
reliability caveats, cost-tier changes, proposed structural changes —
each with what would resolve it>

## Applied
<"Not applied — awaiting approval." until Step 8 runs; then: what was
applied (including user modifications to the proposal), verifier result,
commit / PR refs>
```

## model-routing.md update marker

Append — never rewrite — a dated subsection directly under the bindings
table, and update the affected role rows in place:

```markdown
### Routing update — YYYY-MM-DD
- <role>: <old> → <new> (one-line bench basis; see model-check-YYYY-MM-DD.md)
```

The dated subsection plus the audit artifact preserve the decision trail;
clobbering either defeats it. Also update the deprecation watch rows for
any ID this pass retires, and bump the file's retrieved/reviewed dates.
