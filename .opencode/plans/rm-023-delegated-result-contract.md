---
slug: rm-023-delegated-result-contract
title: Delegated-result contract — empty/malformed result = failed, never clean
status: implemented
created: 2026-10-01
revised: 2026-10-01
---

## Goal / Approach

A parent that delegates work to a Task subagent (a council lens, an implement
workstream, a design consult) must never read a dead or malformed result as a
clean one. Today a provider death returns `state=completed` with an EMPTY
result; in a review loop, silence reads as "the lens found nothing" — a
false-green hole (issue #52). This plan gives every delegation a declared
**report contract**, checks the result against it mechanically, classifies the
failure from the host log, and requires the outcome to be recorded.

## Acceptance Criteria

1. **Empty is invalid.** `python3 scripts/validate_delegated_result.py
   --contract council-lens --file <empty>` exits non-zero and prints
   `empty result`. Verifier: `scripts/test_validate_delegated_result.py`
   (case `empty`).
2. **Malformed is invalid.** A result missing one declared marker exits
   non-zero and names the missing marker. Verifier: the same test's
   `missing-marker` case.
3. **Valid passes.** A result carrying every declared marker exits 0.
   Verifier: the same test's `valid` case.
4. **Named contracts exist.** The validator ships at least `council-lens`,
   `implement-handoff`, and `design-consult` marker sets, each documented in
   `reference/delegated-result-contract.md`. Verifier:
   `validate_delegated_result.py --list-contracts` lists all three, asserted by
   `test_validate_delegated_result.py`.
5. **Every delegating surface cites the contract.** `agents/council.md`,
   `docs/COUNCIL.md`, and the four skills cite
   `reference/delegated-result-contract.md`. Verifier: a structural test
   (`scripts/test_delegated_result_contract.py`) greps the six files for the
   citation and fails if one is missing.
6. **The rule text is present and stable.** The contract doc and each citing
   surface state: (a) empty/malformed = failed run, never clean; (b) transient
   failure → retry, deterministic failure → retry once then switch vehicle or
   take over inline; (c) the delegation outcome (clean / retried / fallback /
   inline) is recorded in the artifact. Verifier:
   `scripts/test_delegated_result_contract.py` asserts the three phrases per
   surface.
7. **CI stays green.** `scripts/test_validate_delegated_result.py` and
   `scripts/test_delegated_result_contract.py` are added to the `quality-gates`
   step in `.github/workflows/ci.yml`; `python3
   skills/authoring-skills/scripts/validate_skill.py --all`, `node
   scripts/verify.mjs`, and `python3 scripts/check_typed_evals.py --base HEAD`
   all exit 0. Verifier: the listed commands locally + the CI job.

## Files to Modify

- `reference/delegated-result-contract.md` (new) — the contract: declared
  report shape per delegation type, the validity rule (non-empty + all markers),
  the failure-classification table, the recorder requirement.
- `scripts/validate_delegated_result.py` (new) — mechanical validator;
  `--contract <name>` or `--markers a,b,c`; `--list-contracts`; non-zero on
  empty/malformed.
- `scripts/test_validate_delegated_result.py` (new) — cases valid / empty /
  missing-marker / unknown-contract / `--list-contracts`.
- `scripts/test_delegated_result_contract.py` (new) — structural citation +
  rule-text check across the six surfaces.
- `.github/workflows/ci.yml` — add the two tests to `quality-gates` (lines
  68-78 block).
- `agents/council.md` — Process step 3 and Guardrails cite the contract.
- `docs/COUNCIL.md` — Procedure step 3 cites the contract.
- `skills/designing-architecture/SKILL.md` — Step 5b replaces the ad-hoc
  empty-result paragraph with the contract + outcome recorder.
- `skills/validating-ui/SKILL.md` — Step 5 cites the contract; Step 7 records
  the outcome.
- `skills/reviewing-code/SKILL.md` — the council/delegation relationship
  section cites the contract.
- `skills/implementing-features/SKILL.md` — Step 8 item 4 cites the contract
  for the `council-ux` consult and any Task workstream.

## Scope

**Included:** a written delegated-result contract; a mechanical validator with
tests; citation + rule text in the six delegating surfaces; CI wiring for the
new tests.

**Excluded:**

- Model bindings (council is already Go-bound, PR #78) and the free-tier gate.
- The heartbeat/watchdog supervision protocol and `watch_agent.py` promotion
  (RM-022) — adjacent, separate.
- Run-log schema changes (owned by `observing-runs`); no new `delegated` field.
- Automatic retry/orchestration tooling — the contract states the rule; the
  parent agent applies it. No new orchestrator process.
- Any consumer-repo change (paragon mirrors later if the contract proves useful).

## Schema / Type Impacts

None. No database, no generated types.

## Verification

```
python3 scripts/test_validate_delegated_result.py
python3 scripts/test_delegated_result_contract.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
node scripts/verify.mjs
python3 scripts/check_typed_evals.py --base HEAD
python3 scripts/model-liveness-check.py
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

## Open Questions

- **Marker sets.** Proposed defaults — `council-lens`: `Findings`,
  `Recommendation`; `implement-handoff`: `Verification`, `Handoff`;
  `design-consult`: `Consult outcome`. Resolve at implementation by reading the
  existing output contracts (`agents/council.md`, the handoff template) so the
  markers match real outputs, not guesses.
- **Enforcement point.** Proposed default: the validator is parent-invoked and
  cited, not wired into a git hook (a hook cannot see a subagent result). A
  future eval could simulate an empty Task result; proposed to defer it with a
  recorded reason unless the eval harness can seed it.
- **Recording home.** Proposed default: plan `## History` for design consults,
  the review report for review lenses, and the handoff for implement
  workstreams. Resolve while editing each skill.

## History

- 2026-10-01 — plan created from RM-023 (issue #52). UX consult skipped: no
  user-facing UI (`no user-facing UI — council-ux consult skipped`).
- 2026-10-01 — implemented. New `reference/delegated-result-contract.md`;
  `scripts/validate_delegated_result.py` (+ `test_validate_delegated_result.py`);
  `scripts/test_delegated_result_contract.py`; CI wiring; rule text + citation in
  the six surfaces. Verification green: both new tests, `validate_skill.py
  --all`, `verify.mjs`, `check_typed_evals.py --base HEAD`,
  `model-liveness-check.py`, `yamllint`. Mechanical correction: `reviewing-code`'s
  council note said "defaulting to free models" — corrected to the Go lane
  (rebind in PR #78). Runtime UI validation: no visible UI — `validating-ui`
  skipped explicitly. Coverage gate: no high-value gap beyond the AC set; added
  one test for the documented `--markers` path.
  - Follow-ups: marker sets (`council-lens`, `implement-handoff`,
    `design-consult`) are provisional defaults; revisit if a real delegated
    result is rejected as malformed.
