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
   essence into ADRs / ROADMAP / skill bodies before merge, then archive
   them in `.opencode/plans/archive/` — the archive is an audit trail,
   not current truth.
5. **The cardinal rule** (defined in `skills/debugging-test-failures/
   SKILL.md`, cited everywhere): never green a check by weakening the
   net; an override is honored only with a dated record.
