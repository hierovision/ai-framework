---
slug: rm-022-subagent-supervision
title: Subagent supervision — heartbeat protocol + progress watchdog promoted to scripts/
status: implemented
created: 2026-10-01
revised: 2026-10-01
---

## Goal / Approach

A long dispatched subagent must be observable while it runs. The D2 dispatch
(2026-09-28) authored 28 files in ~5 min, then spent 37 min inside three
11–13 min opaque blocking eval calls — invisible from outside, cancelled by
the user who could not tell progress from a hang. The tooling that fixed it
(`watch_agent.py`) and the protocol that frames it live only in gitignored
`.scratch/`. This plan promotes both into the tracked library — the reference
protocol and a tested `scripts/watch_agent.py` — and wires the protocol into
the skill that dispatches long work.

## Acceptance Criteria

1. **Verdict matrix is correct and tested.** A pure verdict function returns
   `OK` / `STALLED` / `DEAD` / `BLOCKING` / `UNKNOWN` for synthetic
   heartbeat + event inputs, including the STALLED (quiet > threshold) and DEAD
   (quiet > 2× threshold) boundaries. Verifier: `python3
   scripts/test_watch_agent.py`.
2. **Bad behavior is flagged.** Synthetic event streams containing
   `git commit`, a mutation under `~/.config/opencode`, `rm -rf /home/...`, and
   `curl … | sh` each produce their tag (`git-mutation`,
   `global-opencode-config`, `out-of-sandbox-rm`, `pipe-to-shell`). Verifier:
   the same test.
3. **Loop + blocking detection.** Repeated identical `bash`/`read` targets
   (≥ `--loop-repeats`) flag `LOOP`; a quiet gap > `--call-seconds` between
   events flags a blocking wait. Verifier: the same test.
4. **Exit codes are stable.** OK/WARN → 0, STALLED/BLOCKING → 2, DEAD → 3,
   UNKNOWN → 4, asserted by invoking `main([...])` against a temp heartbeat
   with no session (offline path). Verifier: the same test.
5. **Heartbeat parse is robust.** Timestamped `TAG rest` lines, untimestamped
   raw lines, an empty file, and a missing file all parse without crashing and
   report the expected age/entries. Verifier: the same test.
6. **The protocol is a tracked reference and is cited.** A new
   `reference/subagent-supervision.md` holds the heartbeat format, the ≤10 min
   checkpoint bound, the >180 s blocking-call prohibition, and the scope
   prohibitions; `skills/implementing-features/SKILL.md` cites it for long
   delegated workstreams. Verifier: `scripts/test_watch_agent.py` greps the
   reference and the skill for the citation, and asserts the four rule phrases.
7. **The read-only DB dependency is documented.** `reference/opencode-integration.md`
   records the read-only `opencode.db` access (`session` / `part` tables) as a
   dated, volatile fact. Verifier: the same test greps for it.
8. **Gates green.** `python3 -m py_compile` on both scripts; the quality-gates
   suite (`validate_skill.py --all`, `verify.mjs`,
   `check_typed_evals.py --base HEAD`, `yamllint`) exits 0; the new test is
   added to `.github/workflows/ci.yml`. Verifier: the listed commands.

## Files to Modify

- `scripts/watch_agent.py` (new) — promoted from
  `.scratch/skill-gap-analysis/tools/watch_agent.py`, refactored for testability:
  a pure `verdict(hb, an, thresholds)` function and a `verdict_exit_code()`;
  the SQLite read and `main()` stay thin. Behaviour preserved (same verdicts,
  same flags, same exit codes).
- `scripts/test_watch_agent.py` (new) — AC1–7, offline (no real DB, no network).
- `reference/subagent-supervision.md` (new) — the protocol, promoted from
  `.scratch/skill-gap-analysis/SUBAGENT-PROTOCOL.md`, watchdog path updated to
  `scripts/watch_agent.py`, dated.
- `skills/implementing-features/SKILL.md` — cite the protocol for a delegated
  workstream expected to exceed ~10 min (heartbeat + watchdog; detach long
  evals with a log and poll).
- `reference/opencode-integration.md` — document the read-only DB access as a
  dated volatile fact.
- `.github/workflows/ci.yml` — add `python3 scripts/test_watch_agent.py` to the
  offline unit suites.
- `.opencode/plans/rm-022-subagent-supervision.md` — this plan.

## Schema / Type Impacts

None. No database writes; the opencode DB is opened read-only (`mode=ro`).

## Verification

```
python3 scripts/test_watch_agent.py
python3 -m py_compile scripts/watch_agent.py scripts/test_watch_agent.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
node scripts/verify.mjs
python3 scripts/check_typed_evals.py --base HEAD
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

## Open Questions

- **Heartbeat path.** Proposed default: keep `.scratch/<program>/progress/<task>.log`
  (gitignored, per AGENTS.md rule 3). A tracked path would commit transient
  telemetry; not proposed.
- **Scratch copy.** Proposed default: mark
  `.scratch/skill-gap-analysis/tools/watch_agent.py` superseded in the scratch
  protocol but do not delete scratch files (gitignored, no duplication in
  tracked history).
- **DB dependency scope.** Proposed default: heartbeat-only mode is the
  supported offline path; the DB source is best-effort and its schema is a
  documented volatile fact. If the DB schema proves unstable, the verdict
  function still works from the heartbeat alone.
- **Enforcement.** Proposed default: the watchdog is orchestrator-invoked, not a
  daemon or hook; a hook cannot observe a subagent's session. Making the
  heartbeat automatic is a future skill-level change, not this plan.

## History

- 2026-10-01 — plan created from RM-022 (issue #53; D2 incident 2026-09-28).
  UX consult skipped: no user-facing UI (`no user-facing UI — council-ux
  consult skipped`).
- 2026-10-01 — implemented. `scripts/watch_agent.py` (promoted + refactored:
  pure `verdict()` and `verdict_exit_code()`; UNKNOWN now returns 4, matching
  the documented code that the scratch version never set);
  `scripts/test_watch_agent.py` (8 cases); `reference/subagent-supervision.md`;
  cited in `skills/implementing-features/SKILL.md` Step 8;
  `reference/opencode-integration.md` gained the read-only DB section; CI wiring.
  Verification green: the new test, `py_compile`, `validate_skill.py --all`,
  `verify.mjs`, `check_typed_evals.py --base HEAD`, `yamllint`. Runtime UI:
  none — `validating-ui` skipped explicitly. Coverage gate: added a `--json`
  output-shape test; no other high-value gap.
  - Follow-ups: the watchdog is orchestrator-invoked, not a daemon/hook; making
    the heartbeat automatic is a future skill-level change.
  - Mechanical note: `.scratch/.../watch_agent.py` is superseded by
    `scripts/watch_agent.py`; the scratch copy is left in place (gitignored).
  - User-requested addendum (2026-10-01): the `reasoning_effort` Go-gateway
    compat note added to `reference/opencode-integration.md` (same file this
    plan already edits) instead of a separate upstream issue.
