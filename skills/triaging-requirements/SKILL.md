---
name: triaging-requirements
description: Triage a backlog of product requirements, feature requests, bugs, and tech debt into a single prioritized ROADMAP.md that is established once and updated each session. Detects from multiple sources (pasted text, local repo files, live issue trackers like Jira or GitHub). Use whenever the user says "triage these", "sort through this backlog", "go through these issues", "build/update our roadmap", "what should we work on first", "organize these requirements", or pastes/describes a mess of issues and wants them ranked and reconciled against a roadmap — even if they don't say the word "triage" or "roadmap". Not for writing a single new spec, opening one issue, or estimating one task in isolation.
---

# Triaging Requirements

Triage a backlog into a single, durable ROADMAP.md. The roadmap is
**established once** and **updated each session** — never regenerated from
scratch when one already exists. A pass succeeds when every item from
every *resolvable* source has been resolved against the roadmap (added,
merged, or deliberately skipped with a reason). An unreachable source is
surfaced, not papered over. "I think that's everything" is not success.

## The triage pass

Copy this checklist and check off items as you complete them.

```
Triage Progress:
- [ ] 1. Resolve sources
- [ ] 2. Detect stack & fetch live items
- [ ] 3. Collected item set (deduped across sources)
- [ ] 4. Load existing ROADMAP.md (or initialize)
- [ ] 5. Categorize every item
- [ ] 6. Score & rank (default rubric unless user overrides)
- [ ] 7. Merge into ROADMAP.md (preserve history; never blow away)
- [ ] 8. Summarize changes; confirm cuts
- [ ] 9. Close the loop: every source item resolved (or report why open)
```

### Step 1 — Resolve sources

Items come from up to three places; gather all the user actually provided:

- **Pasted text** in the conversation (the common case — backtick blocks,
  bullet lists, prose). Parse it; don't ignore it.
- **Local files** the user names by path (e.g. `docs/feature-ideas.md`,
  `todo.md`). Read each fully. Markdown with `✅`/`⏳`/`- [x]`/`- [ ]` markers
  carries status — preserve it.
- **Live tracker** the user names by project key (e.g. `PROJ` on Jira,
  `owner/repo` on GitHub). See Step 2.

If the user names a source you cannot access (tracker auth missing, repo
path doesn't resolve), surface the gap explicitly and list which items
were *not* fetched. Do not silently proceed as if there were nothing there.

### Step 2 — Detect stack & fetch live items

Identify the project's tracker from its rules file (`AGENTS.md` /
`.opencode/agents.md`) and the user's phrasing:

- User says "Jira" / gives a project key like `PROJ` → Jira.
- User gives `owner/repo` or says "GitHub issues" → GitHub via `gh`.
- User names only local files → no live fetch needed.
- User names a tracker *but supplies an export file* (CSV/JSON pulled
  manually) instead of pointing at a live API → load the matching stack
  reference for its issue → item mapping, but skip the auth/fetch sections.
  The export file is the tracker source; treat its rows as tracker items,
  not generic local-file content.

Load the matching stack reference when a live fetch is required *or* when
you need the issue → item mapping for an export file:

- Jira → [references/stacks/jira.md](references/stacks/jira.md)
- GitHub → [references/stacks/github.md](references/stacks/github.md)

If no stack reference exists for the user's tracker, proceed generically,
fetch what you can with available tools, and flag the gap. Do not
hallucinate tracker data — an unfetched issue is a finding, not a guess.

### Step 3 — Collect & dedupe

One item may appear in several sources (a `Planned Features` section and a
Jira epic for the same thing; a feature spec and the unwired schema
scaffold for it in a tech-debt note are the *same* item). Merge into a
single item that keeps the richest description and notes every source.

Already-done items (`✅`, `- [x]`, closed tickets) are not work to do. They
become history, kept in the roadmap as Done so the record stays complete.

### Step 4 — Load or initialize ROADMAP.md

- **No `ROADMAP.md` at repo root** → initialize. See
  [references/roadmap-format.md](references/roadmap-format.md) for the
  section structure and frontmatter.
- **Existing `ROADMAP.md`** → read it. This is a *merge* pass, not a
  rebuild. Keep prior categories, priorities, and history for still-open
  items unless the item's status moved (now closed, now blocked, now
  unblocked). A new priority label or signal from a source (e.g. a Jira
  `High` priority where there was none) is recorded in Notes but does not
  trigger a re-score — status moves are the only re-score trigger, so
  scores stay comparable across passes. See Step 7 for the one exception
  (rubric change).

### Step 5 — Categorize every item

Fixed set — every item gets exactly one:

| Category | Use for |
|---|---|
| `feature` | New or enhanced user-facing capability |
| `bug` | Incorrect behavior against existing intent |
| `debt` | Internal cleanup that improves future velocity (refactors, schema consistency, dead code) |
| `chore` | Non-feature maintenance (CI thresholds, icon assets, version bumps, manifest dedup) |

If an item genuinely doesn't fit (an "Intentionally Excluded" note, a
research spike with no committed outcome, a scaffolded-but-unwired field
that's both feature and debt), flag it with `category: review` and explain
the ambiguity inline rather than forcing a bucket. The roadmap has a real
`## Review (category: review)` section (see roadmap-format.md) where these
live — but items there are awaiting a user decision on how to recategorize,
not permanently parked. The skill surfaces the ambiguity and asks; it does
not silently absorb it into one of the four buckets above.

### Step 6 — Score & rank

**Default rubric: impact × urgency.** Two axes, each 1–3, multiplied for a
1–9 score. Show both axes per item so the user can sanity-check the
ranking, not just a flat priority.

- **Impact** — how many users / how much it hurts not to have it.
- **Urgency** — time-sensitivity now vs later (a broken core flow this week
  is urgent; a nice-to-have for Q4 is not).

The user may supply a different rubric (e.g. RICE: reach × confidence /
effort, MoSCoW buckets, or their own scoring). When they do, switch
entirely and **state which rubric is in effect** so they can catch a
misread. Record the rubric and any threshold in the roadmap so a future
pass is reproducible.

A rubric change changes the scoring unit, so prior scores are no longer
comparable. This is the **one exception** to Step 7's "don't re-score"
rule: when the rubric changes, re-score every still-open item under the
new rubric, and preserve the prior score in the Notes cell (e.g.
`prev: 9 (impact×urgency)`) so the history survives the unit change.
Status moves and rubric changes are the only two re-score triggers.

If a threshold is given (e.g. "don't add anything below 0.4 unless I say
so"), enforce it: items below are *proposed cuts*, listed separately, and
**not written into the roadmap without confirmation**. The threshold
applies uniformly across categories — chores and debt get no automatic
exemption, because low reach is a real signal that the work may not be
worth it now. But when a rubric switch causes existing chores or debt to
fall below threshold, surface it explicitly in the change summary as a
category-level prompt (e.g. "3 chores/debt now below 0.4 under RICE — say
the word if you want chores/debt exempt from the threshold") so the user
decides intentionally rather than losing maintenance work by accident.

When scoring is ambiguous (e.g. "reach x confidence / effort" could be
RICE without the Impact term), do not guess silently — one question costs
far less than a roadmap built on the wrong formula. Two situations:

- **The user is interactive and the pass can pause** → ask the one
  clarifying question before scoring.
- **The pass must produce the file this turn** (the user asked for the
  roadmap now, or is not answering) → proceed under the most reasonable
  reading, mark it provisional in frontmatter
  (`rubric: reach-confidence-effort  # provisional`), and surface the
  question at the top of the change summary. A provisional rubric is
  re-confirmed or corrected on the next pass; a silent guess is
  indistinguishable from a decision.

### Step 7 — Merge into ROADMAP.md

Merge rules — see [references/roadmap-format.md](references/roadmap-format.md)
for the full format and the field-by-field merge table. Essentials:

- New items append as `proposed`.
- Items the user's rubric cut sit in a `## Proposed (cut)` section, not the
  main list, until confirmed.
- Done items (shipped/closed since last pass) move to `Done`; keep them, do
  not delete. Maintaining done history is the point of a durable roadmap.
- Don't re-score already-ranked open items unless their status moved — or
  unless the rubric changed this pass (see Step 6: re-score all, preserve
  prior score in Notes).
- One row per logical item — never two rows for the same feature.

### Step 8 — Summarize & confirm

Before declaring the pass complete, give the user a short change log:

```
Added (new):       3 — feat-export-csv (6), feat-offline-sync (4), chore-ci-cache (2)
Newly done:        1 — feat-onboarding-flow (closed 2026-06-28)
Re-ranked:         1 — bug-session-expiry ↑ (status moved: now blocking release)
Proposed cuts:     2 — feat-widget-embed (0.2), chore-icon-dedup (0.1)
Unresolved:        0 — or: ≥1 source (Jira PROJ unreachable — auth missing)
Category cuts:     2 chores/debt below 0.4 under new rubric — exempt? (say the word)
```

Surfacing cuts and re-ranks is non-negotiable: a silent edit is what makes
users stop trusting the roadmap. `Unresolved` reports the count of items
that were neither added, merged, nor deliberately skipped — go back and
resolve each. An unreachable source is reported as `≥1 source (<reason>)`
rather than a number, since the count is unknowable when the fetch never
returned; the pass is then honestly marked incomplete pending that source,
not silently closed.

### Step 9 — Close the loop (or report why it stays open)

The pass is complete when every item from every *resolvable* source has
been added, merged into an existing row, or marked `skipped` with a
one-line reason recorded in the roadmap. "I think that's everything" is not
success; a counted, empty unresolved list across resolvable sources is.

An unreachable source (failed auth, repo not found, network) is not
"resolved" — it stays in `Unresolved` as `≥1 source (<reason>)`. Finish
the resolvable sources, still write ROADMAP.md, still surface the change
summary, but do **not** mark Step 9 closed while a named source is
unreached. The honest terminal state is "pass incomplete, pending that
source"; a rerun with the source reachable closes the loop. This is the
reconciliation between the closure bar and the stack-ref guidance to
"proceed with resolvable sources": you proceed, you don't overclaim.

An unfetched source from a prior pass is carried forward in frontmatter
but does not block a later pass that does not name it — it only blocks
closure if the user names it again this pass and it is still unreachable.
The carry-forward note is a reminder to re-attempt when the user next
names that source, not a permanent open issue.

## When not to use this skill

- Writing a spec for one feature → just write it.
- Estimating one task → estimate it.
- Grooming a single issue's description → edit that issue.
- Pure backlog export with no ranking intent → user wants a list, not a
  roadmap pass.

## References

- [references/roadmap-format.md](references/roadmap-format.md) — ROADMAP.md
  schema, section order, and the merge table. Read when initializing or
  before any merge that isn't a trivial append.
- [references/stacks/jira.md](references/stacks/jira.md) — fetching Jira
  issues by project key. Read only when a live Jira fetch is required.
- [references/stacks/github.md](references/stacks/github.md) — fetching
  GitHub issues via `gh`. Read only when a live GitHub fetch is required.