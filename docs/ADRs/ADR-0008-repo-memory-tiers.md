# ADR-0008: Three-tier repo memory; plans as the tracked working-artifact tier; handoffs retired

## Status: accepted 2026-09-23

## Context

Session-boundary knowledge (what landed, what is verified, what is blocked,
what is next) had no durable home. The first attempt was a `docs/handoffs/`
directory: handoff docs were committed in July, deleted on 2026-07-27 when
their essence was folded into skill bodies (commit `12c8297`), gitignored as
"removed from the repo — never track", then revived on 2026-09-21
(`fa8af03`). The revival immediately re-demonstrated the original problem:
the handoff duplicated the ROADMAP's next-session entry and carried
standing-rule candidates that belong in `AGENTS.md` — two staleable copies
of truth. Separately, `rm-003.md` flagged that `.opencode/plans/` is
gitignored, leaving the consolidated follow-up ledger untracked. The
user-approved RM-004 scope (2026-09-18) already defined the three-tier
repo-memory structure this decision formalizes.

## Decision

Adopt three memory tiers, and one working-artifact tier:

1. **Standing rules** — repo-root `AGENTS.md`: auto-loaded, cross-session
   imperatives only (never process knowledge, never per-session state).
2. **Decision record** — `docs/ADRs/`: one file per decision with maturity
   `accepted` / `superseded` / `reversed`; a decision that stops being true
   is superseded or reversed *in place*, never silently rewritten.
3. **Plan lifecycle** — plans are working artifacts whose essence is
   extracted into tracked docs (ADRs, ROADMAP, skill bodies) before merge;
   the files then move to `.opencode/plans/archive/`. There is no
   archive-as-memory tier — the archive preserves the audit trail, it is
   not read as current truth.

Working-artifact tier: `.opencode/plans/` holds the in-flight plans and
session-boundary handoffs, and **is tracked in this repo only** (the
plan-format default — runtime artifacts, not committed — stays in force for
consumer repos; this is the opt-in the plan-format contract anticipates).
`docs/handoffs/` is retired; the fixed handoff shape (done → verified →
blocked → next) remains defined in `docs/CONCEPTS.md` Choice 11, and a
session handoff lives in `.opencode/plans/` until its essence is extracted,
then joins the archive.

## Consequences

- Every artifact has exactly one authoritative home: decisions in ADRs,
  imperatives in AGENTS.md, state/next in ROADMAP, in-flight contracts in
  `.opencode/plans/`.
- The construction record (how the library was built, plan-by-plan) is
  versioned — the untracked-ledger problem is closed.
- Consumer repos keep ignoring `.opencode/`; this exception is repo-local
  and recorded in `.gitignore`.

## Sources

- ROADMAP RM-004 acceptance cell (three-tier structure, user-approved
  2026-09-18)
- `docs/CONCEPTS.md` Choice 11 (handoff shape) and Choice 4 (artifacts as
  contracts); Choice 6 (layer by rate of change)
- `.opencode/plans/handoff-rm-003-to-rm-004.md` (the retiring artifact)
- `.gitignore` history: deletion `12c8297` (2026-07-27), revival `fa8af03`
  (2026-09-22), this retirement (2026-09-23)
