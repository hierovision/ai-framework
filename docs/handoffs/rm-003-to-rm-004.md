# Handoff: RM-003 eval-gating delivery → RM-004 governance

Created: 2026-09-21 (session spanning 09-18 → 09-22). Shape: done → verified →
blocked → next.

## Done

- **RM-001, RM-002, RM-003 all `done` on main** (ROADMAP reconciled 2026-09-21).
- RM-003 delivered and merged (PR #23, merge commit `20b4f06`): eval report +
  coverage-gap + green-run-status artifacts, per-change eval gating
  (changed-files → skill mapping, one-canary matrix), three-layer gating
  (pre-commit validators / advisory pre-push / required PR check),
  typed-assertion protocol (`action`/`artifact`/`text` over `opencode run
  --format json` event streams, Layer-1 enforced via
  `scripts/check_typed_evals.py`), retry + quarantine (+ rehabilitation
  pass-streaks) + deterministic continuation policy, and the consolidating
  cleanup pass per the 5-lens free council (`.opencode/plans/rm-003-cleanup.md`
  is the consolidated ledger — tracked follow-ups live there).
- Eval CI runs on the **direct-key lane** (`deepseek/deepseek-flash`, user
  directive 2026-09-21; model-routing.md records the amended policy + budget:
  ~$0.68/weekly run off-peak, cron 10:30 UTC). All canaries green in CI
  (authoring-skills #1→#2 migration with harvested fixtures;
  releasing-a-version approval handoff re-typed artifact-borne).
- Agents renamed to personas (architect/curator/implementer/planner, PR #22).
- New skill adopted: `releasing-a-version` (eval-agent byproduct, validated).

## Verified

- 76 tests green across 8 files; 23 skills validate; 23 manifests resolve;
  yamllint clean; typed-eval gate green vs main; CI quality-gates +
  pre-commit-check green on every push; per-change eval matrix 10/10 legs
  green across final runs.
- Known-truth records: per-attempt reliability annotations in run logs;
  failed-eval event streams persisted (key-redacted) under `logs/eval-streams/`.

## Blocked (nothing hard-blocked; dated waits)

- **First green-run record (AC4)**: next qualifying weekly run —
  **Monday 2026-09-28, 10:30 UTC** (direct-key lane, new cron). On a
  qualifying pass: `python3 scripts/eval-report.py green-run-status --record
  --run-id <id> --date <d> --duration-min <n> --all-pass --quarantine-flips 0
  --artifact-url <url>`.
- **fail-fast flip-back**: after two consecutive fully-green CI runs (tracked
  in the cleanup plan; the test flips with the flag).

## Next

1. **RM-004 — governance artifacts** (approved scope, design pass needed via
   `architect`): CONTRIBUTING/CODEOWNERS/SECURITY/docs/ADRs + the approved
   three-tier repo-memory structure (AGENTS.md standing rules · ADRs with
   accepted/superseded/reversed maturity · plan-lifecycle rule).
   **First act: back-fill the founding ADR set** from this session's tacit
   decisions — sonnet elimination, direct-key eval lane, typed-assertion
   protocol + nature rule, canary selection principle, three-layer gating,
   persona renames, eval-lane policy amendment. That is the memory layer
   every future session reads.
2. Deferred (tracked, do not re-litigate): runner split (seams documented in
   `.opencode/plans/rm-003-cleanup.md`), legacy-assertion migration of ~75
   evals (migrate-on-touch), multi-turn eval support if variance persists,
   `BEVAL_MAX_CONTINUATIONS` depth tuning.

Session mechanics worth carrying forward: per-question approval worked well
(routing pass); the free-council recovery path is documented in
`agents/council.md` (per-member CLI with `-m`, header verified); never use
`opencode run --continue` from a parent session that shares the session
store — use fresh runs or explicit `--session`.
