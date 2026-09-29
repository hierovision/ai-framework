---
name: build
description: Execute coding tasks from an approved plan artifact.
---

## Build Skill — Portable Implementation Loop

This skill is self-contained. It does **not** depend on any agent files. Follow these steps exactly.

---

### 1. Locate & Read the Plan

The plan lives at `.opencode/plans/pending-task.md`. Read it in full before writing any code.

```bash
cat .opencode/plans/pending-task.md
```

If the file does not exist, **stop** and tell the user: "No plan found at .opencode/plans/pending-task.md".

The plan contains:
- **Goal** — one-sentence objective
- **Scope** — files/directories you may touch
- **Excluded** — files/directories you must NOT touch
- **Acceptance Criteria** — observable behaviors a test could assert
- **Verification** — exact commands to run (type-check, lint, unit, e2e)
- **Manual Validation** — steps for the user to run after automated checks pass

---

### 2. Implement Strictly Within Scope

- Write code **only** inside the `Scope` paths.
- Do **not** modify anything in `Excluded`.
- Do **not** add features, refactor, or fix bugs outside the plan.
- If you discover a conflict (plan vs. reality), **stop** and report the mismatch; do not improvise.

---

### 3. Run Automated Verification (All Must Pass)

Execute the commands listed in the plan's **Verification** section **in order**. Typical sequence:

```bash
# Type-check (example)
npm run typecheck   # or: pnpm tsc --noEmit, cargo check, etc.

# Lint
npm run lint        # or: pnpm lint, ruff check, etc.

# Unit tests
npm run test:unit   # or: pnpm vitest run, cargo test --lib, etc.

# E2E tests
npm run test:e2e    # or: pnpm playwright test, etc.
```

**If any command fails**: stop, diagnose, fix the root cause, then re-run **the full sequence from the start**. Do not skip or weaken checks.

---

### 4. Present Manual Validation Steps

Only after **all** automated verification commands exit `0`, print the **Manual Validation** steps from the plan verbatim. Do not summarize or rephrase.

Example output:

```
✅ All automated checks passed.

=== MANUAL VALIDATION (from plan) ===
1. Start the dev server: npm run dev
2. Open http://localhost:3000/dashboard
3. Verify the new "Export CSV" button appears in the toolbar
4. Click it and confirm a CSV downloads with correct columns
5. Confirm no console errors or warnings
===============================
```

Then stop. The user performs manual validation.

---

### 5. Portability Notes

- **No agent files required**: This skill contains the complete loop.
- **Commands are plan-defined**: The plan's `Verification` section holds the exact commands for the project's toolchain (npm, pnpm, cargo, make, etc.). Do not assume a specific stack.
- **Plan path is fixed**: Always `.opencode/plans/pending-task.md`.
- **No git operations**: Do not commit, push, or tag. The user decides when to commit.

---

### Quick Reference Checklist

- [ ] Read `.opencode/plans/pending-task.md`
- [ ] Implement only within `Scope`, respecting `Excluded`
- [ ] Run **every** verification command in order, full sequence on any failure
- [ ] All automated checks exit `0`
- [ ] Print `Manual Validation` steps exactly as written in the plan
- [ ] Stop