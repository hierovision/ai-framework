---
slug: facilitating-product-vision-skill
title: Author the facilitating-product-vision skill (owner vision session → outcome-based slice roadmap)
status: approved
created: 2026-10-09
related: []
---

# Plan: facilitating-product-vision-skill

## Goal / Approach

The library gains a facilitation skill — `facilitating-product-vision` — that
turns an owner's product ambition into a vision artifact plus an
outcome-based roadmap of concrete, testable slices, closing the verified gap
upstream of `triaging-requirements` and unblocking the consumer item
`review-vision-roadmap-refresh` (Paragon Learning Network, owner directive
2026-10-08, handoff `~/repos/temp/ai-framework-handoff-vision-roadmap-skill.md`).

Strategy: author through the meta-loop (`authoring-skills`, evals-first,
fresh-agent testing, `validate_skill.py` gates), register in `registry.json`
(L1/active per ADR-0009), install via `./install.sh`, and record the consumer
pointer in `docs/ROADMAP.md`. Execution shape: **one** `skill-author`
workstream — evals drive the body, so the authoring core loop is inherently
sequential and is deliberately NOT split across parallel agents; independent
verification runs after authoring (`skill-reviewer`, never self-graded).
Parallel subagents were appropriate and used at design time (the three-lane
validation wave, recorded in History), not during implementation.

Process content = the handoff's 11 pieces, amended by the product-lens
consult (see History): add **non-goals / anti-vision** capture, **capacity /
envelope realism** (a throughput ceiling applied to Now/Next/Later), a
**per-slice success measure** (not just build-ACs), and **slice dependency
(blocked-by) mapping**; owner checkpoints are **batched into ~3 decision
points** (strategy batch: pieces 2–6; roadmap batch: themes → slices;
compliance/phase-gate confirm woven in) to avoid ~7 pauses and late-session
rubber-stamping. Every judgment call stays owner-owned and recorded with
rationale; the agent never invents strategy.

## Acceptance Criteria

1. **Skill artifact + structure gates.** `skills/facilitating-product-vision/SKILL.md`
   exists (name matches dir); the description states the one-line purpose,
   the use-when triggers ("define/refresh the vision", "our roadmap is too
   lean", "turn the vision into slices", "run a vision/strategy session"),
   the not-for list naming all five siblings (`triaging-requirements`,
   `designing-architecture`, `managing-github-issues`,
   `refining-issue-acceptance`, `council-product`), and says "product
   vision" explicitly (collision guard vs the `vision-critic-*` agents);
   the body carries the boundary routing table (~10 rows: request → route)
   and the ownership contract. — Verifier: `python3
   skills/authoring-skills/scripts/validate_skill.py
   skills/facilitating-product-vision` exits 0; `grep -c
   "triaging-requirements" skills/facilitating-product-vision/SKILL.md` ≥ 1;
   the description contains "product vision".
2. **Process content present.** The body's process checklist covers all 11
   handoff pieces plus the four consult additions (non-goals/anti-vision;
   capacity envelope; per-slice success measure; blocked-by mapping) and the
   batched-checkpoint discipline (~3 owner decision points, stop-and-ask,
   recorded rationale). — Verifier: `grep -n` for "anti-vision" (or
   "non-goals"), "capacity", "success measure", "blocked-by", and the
   checkpoint batch structure in `SKILL.md` each hit ≥ 1 (behavior itself is
   covered by ACs 4–5).
3. **Roadmap conformance + ownership contract.** The skill instructs emitted
   `ROADMAP.md` rows to conform to the item-row schema of
   `../triaging-requirements/references/roadmap-format.md` (cited by exact
   sibling-relative path), carries outcome/Now-Next-Later semantics via the
   roadmap's recorded `rubric:` frontmatter + Notes (not a private table
   shape), and never rebuilds an existing ROADMAP.md from scratch — it emits
   themes + provisional slices; `triaging-requirements` owns scoring,
   ranking, and durable merge (established-once rule). — Verifier:
   `grep -n "roadmap-format.md" skills/facilitating-product-vision/SKILL.md`
   ≥ 1; the merge-not-rebuild rule greps ≥ 1.
4. **Eval suite (5 typed evals).** `evals/evals.json` with 5 evals, top-level
   `default_model_tier: "free"`: (1) `vision-roadmap-artifact` — lean-roadmap
   consumer input → vision artifact with section-vocabulary phrases (artifact
   class, `timeout: 600`; count thresholds live in `expected_behavior` as
   intent only — the closed schema has no counting class); (2)
   `route-rank-backlog` — text `["triaging-requirements"]` with a bait
   backlog fixture; (3) `route-plan-single-item` — text
   `["designing-architecture"]`; (4) `owner-checkpoint-one-shot` —
   one-shot-declared prompt → artifact `["Open Questions"]` on the draft +
   asking-the-owner text; (5) `owner-checkpoint-two-turn` — the Step 6
   two-turn harness (turn 1 stop+ask; turn 2 answers recorded as design
   decisions), marked `deferred: true`. Notes carry the honest limits: no
   negative assertion class exists, so "instead of inventing strategy" is
   hand-review-enveloped; Go/Zen cross-tier validation is a documented
   deferral. Fixture data may be project-flavored; instructions must not
   mirror eval scenarios. — Verifier: `python3
   scripts/check_typed_evals.py --base main` exits 0; the validator (AC1)
   confirms fixture paths resolve.
5. **Behavioral eval runs (honest outcomes).** Ids 1–4 run on the free tier
   (CI default) and id 5 locally with `--include-deferred` on the Go lane;
   one `kind=eval` run-log record per eval; any failure is iterated per
   authoring Step 7 — never greened by weakening an assertion (cardinal
   rule). — Verifier: `python3 skills/authoring-skills/scripts/
   run_behavioral_eval.py --skill facilitating-product-vision` completes with
   per-eval pass/fail recorded in `logs/run-*.jsonl` (`rg -c '"kind":
   "eval"'` on the fresh log); the `evals.json` notes state the tier
   deferral.
6. **Registration + install.** `registry.json` gains the entry (type skill,
   owner `@hierovision`, maturity `L1`, status `active`, boundary_ref
   `skills/facilitating-product-vision/SKILL.md`); `./install.sh` re-run;
   the symlink resolves. — Verifier: `python3 scripts/registry.py --check`
   exits 0; `readlink ~/.config/opencode/skills/facilitating-product-vision`
   resolves into this repo; the validator is green through the symlinked
   path.
7. **Consumer guidance (generic) + PLNA pointer.** The skill's handoff
   section points at `triaging-requirements` (ranking) →
   `designing-architecture` (top slice → plan); a
   `references/consumer-session.md` documents the consumer adoption flow
   (run against a named roadmap item; artifacts returned: vision artifact
   stored per the consumer's decision-doc convention, `ROADMAP.md` rows, a
   session record as a working artifact per the consumer's plan convention).
   PLNA-specific instructions stay OUT of the skill body (instructions are
   project-neutral; fixture data may be project-flavored) — the PLNA
   instance lives in this repo's `docs/ROADMAP.md` row. — Verifier:
   `references/consumer-session.md` exists and `SKILL.md` links it;
   `grep -n "review-vision-roadmap-refresh" docs/ROADMAP.md` hits the new
   row and `grep -rn "review-vision-roadmap-refresh"
   skills/facilitating-product-vision/` is empty.
8. **Roles, not model IDs.** The skill references roles/lanes only; no new
   `reference/model-routing.md` row is needed (skills are lane-agnostic;
   personas own bindings). — Verifier: `grep -rn
   "opencode-\|kimi-\|gpt-\|glm-\|deepseek\|mimo-\|minimax\|qwen\|nemotron"
   skills/facilitating-product-vision/` → no hits.
9. **Boundary pointer in the sibling.** `skills/triaging-requirements/SKILL.md`
   gains one line in its not-for/boundary list: creating a vision or outcome
   themes from scratch → `facilitating-product-vision` (the trigger-phrase
   collision fix — it currently claims "build/update our roadmap"). —
   Verifier: `grep -n "facilitating-product-vision"
   skills/triaging-requirements/SKILL.md` ≥ 1.

## Files to Modify

- `skills/facilitating-product-vision/SKILL.md` — new; frontmatter (name,
  description with use/not-use + five siblings + "product vision"), process
  checklist (11 amended pieces + batched checkpoints), boundary routing
  table, ownership contract, artifact/eval/handoff pointers
- `skills/facilitating-product-vision/references/artifact-format.md` — new;
  the vision artifact's fixed section vocabulary (Inputs & constraints,
  Vision statement, Segments & JTBD, Alternatives & non-goals/anti-vision,
  Value & business model, North Star + guardrails, Outcome themes
  Now/Next/Later, Slices (AC + success measure + blocked-by + sizing),
  Compliance & phase gates, Open Questions) — the contract the eval phrases
  pin
- `skills/facilitating-product-vision/references/consumer-session.md` — new;
  generic consumer adoption flow + artifact returns (AC7)
- `skills/facilitating-product-vision/evals/evals.json` — new; 5 typed evals
  per AC4
- `skills/facilitating-product-vision/evals/fixtures/` — new; lean-roadmap
  consumer fixture (a `ROADMAP.md` + owner notes), bait backlog
  (`fixtures/backlog/…`), bait single-item fixture; self-contained, verifiers
  able to fail
- `registry.json` — add the entry (AC6)
- `docs/ROADMAP.md` — add the delivery row (RM-046) with the PLNA pointer +
  consumer next step (AC7)
- `skills/triaging-requirements/SKILL.md` — one-line boundary pointer (AC9)

## Scope

**Included**

- The complete skill directory (SKILL.md + 2 references + evals + fixtures),
  authored through the `authoring-skills` loop (evals first, fresh-agent
  testing, Step 5/8 validator runs, Step 8 install)
- Registry registration (L1) + install + ROADMAP.md delivery row
- The one-line sibling boundary pointer (AC9)
- Implementation on branch `feat/facilitating-product-vision-skill` (slug
  derivation per `reference/git-workflow.md`), landing as a PR per the
  push/PR contract (RM-036: the pass lands branch + PR without prompting)

**Excluded**

- Running the PLNA vision session itself — consumer-side work, starts after
  this skill lands (the handoff's "Consumer next step")
- Any `roadmap-format.md` schema extension (first-class Now/Next/Later
  sections or outcome columns) — ADR-gated (OQ2); v1 conforms to the
  existing schema
- `reference/model-routing.md` changes (no new role/binding; AC8)
- Council persona / runner changes; the skill merely *cites* the council
  consult path (`agents/council.md` + the delegated-result contract) at its
  defined consult points
- All consumer-repo edits (paragon-learning-network or otherwise)
- The `sourcing-external-skills` gates (ADR-0011/0012) — N/A: from-scratch
  authoring, not external-skill ingest

## Schema / Type Impacts

None.

## Verification

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/check_typed_evals.py --base main`
- `python3 scripts/registry.py --check`
- `bash -n install.sh`
- `./install.sh && readlink ~/.config/opencode/skills/facilitating-product-vision`
- `python3 skills/authoring-skills/scripts/run_behavioral_eval.py --skill facilitating-product-vision`  # ids 1–4, free tier
- `python3 skills/authoring-skills/scripts/run_behavioral_eval.py --skill facilitating-product-vision --include-deferred`  # id 5, Go lane, local
- The grep verifiers of ACs 1–4, 7–9

## Open Questions

- **OQ1 — Vision-artifact canonical home (consumer side).** Vision document
  vs ADR addendum is the consumer repo's own decision-doc call.
  *Proposed default:* the skill's inputs step asks the owner and stores per
  the consumer's convention (PLNA → `docs/ADRs/`). Does not block this
  plan; blocks nothing in the skill body, which stays convention-agnostic.
- **OQ2 — First-class Now/Next/Later in ROADMAP.md.** Schema extension
  (new sections/columns) vs conform-with-rubric. *Proposed default:* v1
  conforms to the existing item-row schema and records the outcome rubric
  in frontmatter + Notes; any schema extension is a separate ADR.

## History

- 2026-10-09 — **Approved by the user** (turn 2 of the design conversation).
  Implementation proceeds on `feat/facilitating-product-vision-skill` in a
  fresh implementer session at this plan path, sequenced AFTER the
  `session-guard-task-child-lifecycle` fix lands (the guard's false abort
  verdict on in-session-Task children would misclassify the implement pass's
  dispatch waves — see that plan).
- 2026-10-09 — Design pass opened from the PLNA handoff (owner directive
  2026-10-08, `~/repos/temp/ai-framework-handoff-vision-roadmap-skill.md`).
  Gap independently verified: 28 skills in `skills/` + the installed
  `~/.config/opencode/skills/` mirror — nothing covering vision / roadmap /
  strategy / product / discovery / market facilitation. Validation wave
  (3 parallel lanes, in-session Tasks on the Go lane, results validated
  against `reference/delegated-result-contract.md`): Lane A (explore)
  confirmed all five sibling insufficiency claims — nuance:
  `triaging-requirements`' vision-exclusion is implicit, not literal, and it
  claims the trigger phrase "build/update our roadmap" (collision → AC9);
  sourced the roadmap format of record
  (`skills/triaging-requirements/references/roadmap-format.md`, item-row
  schema + rubric frontmatter). Lane B (general) mapped the three handoff
  evals to the typed protocol: counts (≥3 themes, ≥5 slices) are
  unassertable (no counting class → structure phrases instead);
  "instead of inventing strategy" has no negative class (hand-review
  envelope); the checkpoint-pressure case ships as a one-shot-declared
  default eval + a deferred two-turn eval (precedents: authoring-skills id 1,
  optimizing-model-routing ids 1–3); free-tier CI default + Go/Zen deferral
  notes. Lane C (council-product) verdict: "proceed with named adjustments"
  — folded: ROADMAP ownership/merge contract with `triaging-requirements`
  (the single most important adjustment), +4 process pieces (non-goals,
  capacity envelope, per-slice success measure, blocked-by), batched
  checkpoints (~3, not ~7), artifact canonical homes, structure-over-counts
  eval assertions. Handoff corrections recorded: AC4-as-written (PLNA-specific
  guidance in the skill) would inject project-flavored instructions into a
  portable skill — generic consumer guidance in the skill, PLNA instance in
  this repo's ROADMAP row; "docs/changelog" does not exist — the
  registration surface is `registry.json` + `./install.sh` + the ROADMAP
  row. UX consult skipped — no user-facing UI (the product-lens consult ran
  in its place; explicit skip recorded here per the skill's Step 5b rule).
  Framework-defect candidate captured (RM-027 convention): `session_guard.py`
  flagged `empty-result` / `wave-failure` (3/3) mid-wave and `stalled`/`DEAD`
  after completion for the in-session-Task children whose results were
  received, non-empty, and marker-valid (result texts verified present in
  `opencode.db`) — the guard's node classifier does not model the
  in-session-Task child lifecycle (it was built and verified against
  run-vehicle dispatches); log as an issue at session close. Attribution:
  3 × `kind=agent` records emitted (explore, general → glm-5.3-flash;
  council-product → mimo-v2.6-flash), guard abort record emitted
  mechanically (`agent=session-guard, outcome=stopped`).
- 2026-10-09 — **AC5 lane correction (D6, skill-author; mechanical
  plan-vs-reality adjustment per implementing-features Step 10).** The
  plan's "free tier (CI default)" premise came from stale marker-doc prose
  in `skills/authoring-skills/SKILL.md`; verified both CI workflows pin
  `--model opencode-go/deepseek-v4.1-flash` (`.github/workflows/eval-behavioral.yml`
  line ~163; `.github/workflows/eval-per-change.yml` line ~283) and the
  runner honors the flag over the manifest — `run_behavioral_eval.py`
  resolves `model or e["model_tier"]` at lines 592/644/678/719/1149, so the
  manifest's `default_model_tier: "free"` marker is CI-INERT. The two
  free-lane rounds (D3 manifest-only 0/4, D5 post-D4-fixes 0/4 with
  identical signatures; free-tier records in `logs/run-2026-10-09.jsonl`,
  full per-eval streams under `logs/eval-streams/`) are recorded in the
  `evals.json` notes as the honest tier-gap finding (free agents did not
  complete the artifact/route behaviors reliably) — never greened, never
  deleted. The re-run (D6) uses the CI lane with
  `--model opencode-go/deepseek-v4.1-flash`, ids 1–4 only (deferred id 5
  stays excluded per `filter_evals`); `default_model_tier: "free"` is
  retained (five sibling skills carry it; it is a tier-intent tag, not a
  CI override) and the dated `evals.json` notes block documents exactly
  what the marker does and does not steer.
