# AGENTS.md — standing rules

Cross-session imperatives only. Process knowledge lives in the skills
(`skills/*/SKILL.md`); current state and next actions live in
`docs/ROADMAP.md`; decisions live in `docs/ADRs/` (routing table:
`docs/ADRs/README.md`, ADR-0008). This file never carries per-session
state or process detail — propose an ADR instead of adding prose here.

## Rules

1. **Never `opencode run --continue` from a parent session that shares
   the session store.** Use fresh runs or an explicit `--session`; a
   continue from a shared-store parent resumes the wrong conversation.
2. **Per-question approval gates stay** until each stage has proven
   consistent success (routing passes, design approvals); a stage earns
   autonomy with evidence, never by assertion.
3. **Local agent scratch stays inside `.scratch/`** — never `/tmp`, never
   a consumer project's worktree.
4. **Plan lifecycle** (ADR-0008): plans and session handoffs are working
   artifacts in `.opencode/plans/` (tracked in this repo); extract their
   essence into ADRs / ROADMAP / skill bodies before merge, then delete
   them — git history is the recovery path, not a checked-in archive
   (ADR-0008 Amendment, 2026-10-02).
5. **The cardinal rule** (defined in `skills/debugging-test-failures/
   SKILL.md`, cited everywhere): never green a check by weakening the
   net; an override is honored only with a dated record.
6. **A merging PR carries its own doc updates.** Every documentation
   change that leaves the repo accurate the moment it merges rides the
   branch — never a follow-up commit on `main`: the ROADMAP row (status,
   date, evidence) **and** its horizon strip and counters, the per-ID
   detail file `docs/roadmap-detail/<ID>.md`, and plan-file retirement
   (rule 4). `reference/git-workflow.md` → *Roadmap closure* is the
   contract; `reviewing-code` gates it before merge. An orchestrator that
   owns the roadmap lands the closure on the branch **before** merging —
   deferring it to `main` is the failure this rule forbids.
