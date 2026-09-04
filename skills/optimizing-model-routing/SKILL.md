---
name: optimizing-model-routing
description: Re-derive the library's model bindings from objective evidence — gather the live opencode catalogs (or a local snapshot), identify and verify the most objective benchmarks available (independently reproduced first; vendor self-reported numbers are a tier filter and never decide a binding), rank the best free and escalation model per workflow role, and present a table (current vs proposed free/Go/Zen with bench basis) plus a mandatory Questionable/Uncertain section for review — then apply the approved updates to reference/model-routing.md and agents/*.md on a branch + PR. Use when the user says "optimize model routing", "rebind the models", "find the best model for each skill or role", "the bindings are stale", "catalog check", or "right-size the models". Not for one-off model config edits in a consumer project, changing agent prompts, or price-only lookups.
---

# Optimizing Model Routing

Re-derive the library's role → model bindings from objective evidence: the
opencode catalogs plus the most objective benchmark data available.
**Coverage is skill-level** — the approval table lists every skill against
its role, so nothing hides behind indirection. **Mutation is role-level** —
updates land on `reference/model-routing.md` role rows and `agents/*.md`
model lines, keeping the roles-not-model-IDs single source of truth. The
pass stops at user approval; no binding is edited before it.

## The routing pass

Copy this checklist and check off items as you complete them.

```
Routing Progress:
- [ ] 1. Scope the pass (all roles, or one named role)
- [ ] 2. Read current state
- [ ] 3. Gather catalogs + liveness (live fetch; docs + routing probe)
- [ ] 4. Identify + verify objective benchmarks
- [ ] 5. Rank candidates per role (free first; Go/Zen escalation — live candidates only)
- [ ] 6. Write the dated audit artifact
- [ ] 7. Present table + evidence + Questionable/Uncertain; STOP for approval
- [ ] 8. On approval: apply, verify, commit, PR
```

### Step 1 — Scope the pass

Default: every role in `reference/model-routing.md`. A named role (or a
skill named by the user) scopes the pass to that role only — analyze it,
present it, touch nothing else, and say so explicitly so a scoped pass is
never mistaken for a clean bill of health on the rest.

### Step 2 — Read current state

Read `reference/model-routing.md` in full — the bindings table, **hard
exclusions**, and the deprecation watch — and every `model:` line in
`agents/*.md`. Two absolute rules from this step:

- **Hard exclusions win over any score.** An excluded family is dropped
  from candidacy regardless of benchmark results, even the best ever
  reported.
- **A bound ID missing from the catalog OR failing liveness is a stale binding.** A stale binding is any ID that is not catalog-listed, not docs-listed (free tier), or fails to route in a live opencode session (see Step 3). It can only be flagged and rebound, never re-proposed.

### Step 3 — Gather catalogs + liveness

Production default: fetch both live catalogs **and** the docs free list
(`https://opencode.ai/docs/zen/#endpoints` — authoritative for free-tier;
see `reference/model-routing.md` Update procedure). Cross-check catalog
vs docs; any divergence is a catalog-vs-availability mismatch → record in
Questionable/Uncertain and exclude the ID from candidacy. Then
liveness-probe every remaining candidate (minimal routing test in a live
opencode session: select an agent bound to that model / send a trivial
prompt and verify no routing error). **Only live-verified IDs are
candidates** — catalog membership alone never makes a model a candidate.

**Go/Zen escalation gate:** for any model proposed for a Go or Zen
escalation row, run a live routing probe on its tier (select an agent
bound to that model on Go/Zen, invoke with a trivial prompt, confirm no
routing error). Record the probe date + result in the routing update
note. Non-live escalation IDs are excluded from the row.

Offline / snapshot mode: a local snapshot directory containing
`zen-catalog.json`, `go-catalog.json`, and `benchmarks.md` — use it when
the user points at one or fetching fails. State which mode ran; never
silently mix snapshot and live data. Every candidate must be
catalog-verified **and** live-verified before ranking; record the
retrieval date for the artifact.

### Step 4 — Identify + verify objective benchmarks

Read [references/benchmarks.md](references/benchmarks.md) now — the
objectivity hierarchy and the role → dominant-trait map. Core discipline:
every cited score carries source + date + independence status, and
**vendor self-reported numbers never decide a binding** — they are a tier
filter and belong in Questionable/Uncertain. Search for the most
objective evidence available before settling for less; if the best
evidence for a candidate is vendor-only, say so instead of laundering it
into a decision.

### Step 5 — Rank candidates per role

Per role in scope, rank **only over live candidates** (Step 3) on the
role's dominant trait per the reference map, deciding on the most
objective evidence available and tie-breaking upward in objectivity (an
independent result beats a cross-checked one beats a vendor claim).
Free-first: propose a free model wherever a live, docs-listed free model
qualifies; Go and Zen rows are escalation picks. **Liveness is a hard
gate, like capability** — a non-live ID is not a candidate at any
benchmark score and never enters ranking. Capability requirements (e.g.
native image input for vision seats) are hard gates, not scores — a
text-only model cannot hold a vision seat at any benchmark number.

### Step 6 — Write the dated audit artifact

Write `reference/model-check-YYYY-MM-DD.md` per
[references/audit-format.md](references/audit-format.md) — read it now.
The artifact is the durable evidence record; what you present to the user
is a summary of it. It is the only file written before approval.

### Step 7 — Present; STOP

Present three things:

- a simple table: role → used-by skills → current → proposed
  (free / Go / Zen) → bench basis (the one decisive number + its source);
- a brief evidence summary — one line per decisive benchmark, with source
  and independence status;
- a **Questionable / Uncertain** section — mandatory, never omitted:
  vendor-only scores, unbenched new models, catalog-vs-binding
  mismatches, reliability caveats, cost-tier changes, and any proposed
  structural change (e.g. a new role row). Each entry says what would
  resolve it.

End with the explicit approval question. Make zero changes to
`agents/*.md` and `reference/model-routing.md` before approval.

### Step 8 — Apply on approval

Apply exactly the approved table — a user modification to the proposal is
part of the approval, not an argument to relitigate:

1. Update `agents/*.md` `model:` lines (free defaults) and the role rows
   in `reference/model-routing.md` (escalations), appending the dated
   `### Routing update — YYYY-MM-DD` section per the audit format.
   Revise-don't-clobber: never rewrite history; update the deprecation
   watch rows for any ID this pass retires; fill the artifact's Applied
   section with what actually landed (including user modifications).
2. Generate the expectation JSON from the **approved** table
   (`bindings` + `forbidden` ids: excluded families and removed catalog
   ids) and run, resolved against this skill's own directory — not the
   project's:
   `python3 scripts/verify_rebind.py --repo <repo-root> --expect <file>`.
   Exit 0 is required; fix and re-run on failure.
3. On a git checkout: branch `chore/model-rebind-<date>`, one commit
   (artifact + updates), push, open the PR, report the URL — the user
   merges. In a non-git working copy (eval / fixture): apply + verify
   only.
4. On rejection: discard the audit artifact, change no binding, report
   what the user should reconsider.

## When not to use this skill

- **One-off model choice in a consumer project's config** → just edit it;
  this skill maintains the library's own routing architecture.
- **Changing an agent's prompt or persona** → that is authoring work, not
  routing.
- **Price / deprecation lookup only** → read model-routing.md's watch
  tables.
- **Adding a new role or agent** → author it first; route it in a later
  pass.

## References

- [references/benchmarks.md](references/benchmarks.md) — the objectivity
  hierarchy (independently reproduced > multi-source cross-checked >
  vendor self-reported), the role → dominant-trait map, capability gates,
  and how to derive the skill → role map. Read at Step 4.
- [references/audit-format.md](references/audit-format.md) — the dated
  model-check artifact contract and the model-routing.md update marker.
  Read at Step 6.
- [scripts/verify_rebind.py](scripts/verify_rebind.py) — execute at
  Step 8 with a generated expectation JSON; exit 0 gates the pass.
