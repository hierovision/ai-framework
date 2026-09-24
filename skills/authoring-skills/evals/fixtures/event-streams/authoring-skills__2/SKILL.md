---
name: build
description: Execute coding tasks from an approved plan. Use when asked to build a planned feature, implement a task from .opencode/plans, or hand off an approved plan for implementation.
---

# Build a planned task

1. Read the plan at `.opencode/plans/pending-task.md` first. Implement only
   what the plan contains — no scope additions.
2. Establish the baseline: the skill's evals run green against the current
   behavior before any rewrite lands.
3. Run the verification feedback loop: type-check, lint, unit tests, e2e —
   fix and re-run each until it passes; only proceed when all are green.
4. Present manual validation steps to the user; never self-certify the
   checks that need human eyes.
