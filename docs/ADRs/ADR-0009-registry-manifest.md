# ADR-0009: Machine-readable skill/agent registry, validator-enforced

## Status: accepted 2026-09-24

## Context

The library could not answer "what skills/personas exist, who owns each,
how mature is it, where are its boundaries" mechanically: the answers
lived in 23 SKILL.md frontmatters, eval-manifest markers, the
maturity-plan's axis-level prose, and session memory. RM-008 (encoded
boundaries), RM-009 (ROI per owner), and RM-011 (drift per skill) all
need a structured join table, and the contribution flow had no enforced
step for registering a new skill.

## Decision

Adopt a repo-root `registry.json` — one entry per skill directory and
per persona file, each with `name`, `type` (`skill`/`persona`), `owner`,
`maturity` (L1–L4), `status` (`active`/`deferred`/`deprecated`), and a
resolvable `boundary_ref`. Decisions embedded in this ADR:

- **Maturity is L1–L4 with an evidence-based promotion bar** — a skill
  moves L2 → L3 only on evidence: typed evals green + used in a real
  loop + independently reviewed. Never by assertion (consistent with
  how stages earn autonomy, `AGENTS.md` rule 2).
- **Single enforcement point** — `validate_skill.py --all` cross-checks
  registry ↔ repo reality (orphan / ghost / field / boundary_ref
  defects) inside the existing `quality-gates` CI job; the loader's
  `--check` CLI stays a local developer tool, not a second gate.
- **Single-source loading** — consumers import the loader
  (`scripts/registry.py`); nothing hand-parses the registry (the
  `query_runs.CORE_SKILLS` import precedent).
- **Declared deferrals are named, not hidden** — `coverage_gaps` keeps
  undeclared gaps in `no_default_marker`, moves registry-`deferred`
  skills into an explicit `deferred_skills` array (explicit negative by
  construction; no array invented when no registry is in play).
- **Eval canary markers and model bindings do NOT move** — `default`/
  `core` stay in `evals.json`, models stay in `reference/model-routing.md`
  and `agents/*.md` `model:` lines; the registry references, never
  duplicates.

## Consequences

- A new or renamed skill fails the pre-commit gate until registered —
  the contribution rule is enforced, not remembered.
- RM-008/009/011 gain their join table without further plumbing.
- The registry is a second structured artifact that can go stale — the
  validator cross-check is the compensating control.

## Sources

- `docs/ROADMAP.md` RM-005 acceptance cell (owner, maturity, boundary
  ref, consumed by tooling)
- `docs/maturity-plan.md` §3 (Governance L3 → "next: registry manifest")
- `.opencode/plans/archive/rm-005.md` (approved 2026-09-24; all four
  Open Questions resolved with the user)
