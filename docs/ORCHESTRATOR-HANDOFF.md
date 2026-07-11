# Orchestrator / Reviewer Handoff

Purpose: let a fresh high-tier session (Opus 4.8 or Fable 5) resume the
**reviewer/orchestrator** role for this skill library cold, without the
prior conversation. Read this + PLAN.md, then you are current.

## Your role (you are NOT the author)

Skills are authored by *separate* fresh mid-tier sessions (GLM 5.2 /
MiniMax M3) driven by a detailed **handoff prompt** you write. Those
sessions build the skill, run its eval loop, and leave it UNCOMMITTED in
the working tree. **You then review it independently and commit it.** You
do not author skills yourself — your value is the second-pass review with
cross-session context, and writing the next handoff.

The workflow loop, every skill:
1. You write a handoff prompt (see the template pattern in git log +
   the examples the user has pasted). The user runs it in a fresh
   author session.
2. Author returns a summary; the skill sits untracked in the tree.
3. **You run the review protocol below**, fix what review-scope allows,
   fold learnings into `authoring-skills`, then commit + push.
4. You propose/write the next handoff.

## Review protocol (run this every time, in order)

1. `python3 skills/authoring-skills/scripts/validate_skill.py --all`
   — frontmatter/strict-YAML, name regex, desc caps, evals present +
   fixture paths resolve, TOC on long refs. Must be green.
2. Leak scan: `grep -rniE 'phasetimer|HIERPT|hierovision|<real project
   terms>' <skill>/SKILL.md <skill>/references/` — instructions must be
   generic; fixtures may be project-flavored.
3. Read the SKILL.md fully + its references + evals.json (esp. the
   `notes` field — the durable loop log, since /tmp reports get cleaned).
4. **Exercise the bundled scripts/gates YOURSELF.** Do not trust the
   author's report. Copy a fixture to /tmp, run the verifier in all
   states: pristine baseline (must FAIL/exit 1), correct fix (must PASS),
   wrong fix (must be REJECTED). A gate that can't fail proves nothing.
   For loop skills this is the single most important review step.
5. Confirm: roles-not-model-IDs in the body; cross-skill contracts
   LINKED not duplicated; description <=900 chars & strict-YAML-safe
   (no unquoted ': '); body <500 lines.
6. Fix only review-scope items (typos, doc gaps, truncations, a
   sibling-propagation the author missed). Do NOT blind-edit large
   bundled scripts you can't re-verify — document the finding and defer
   the code fix to an authoring pass instead (precedent: the
   capturing-ui-evidence playwright-resolution finding).
7. Fold any new durable learning into `skills/authoring-skills/SKILL.md`
   (and its references) so every future skill inherits it.
8. `git add -A && git commit` with a detailed message recording what was
   independently verified + any review fix + learnings. `git push`.
   Never commit without the user's standing go-ahead — they have it for
   these skill commits, but never for anything outside the library.

## Durable conventions the library enforces (learned across 11 rounds)

- **Gerund skill names**; must match directory; regex
  `^[a-z0-9]+(-[a-z0-9]+)*$`.
- **Evals mandatory + self-contained**: fixtures under `evals/fixtures/`,
  `files[]` populated, never `/tmp` or a live repo.
- **Failable verifiers**: a loop eval whose verification cannot fail
  proves nothing. Fixtures ship BASELINE (problem present) so the
  verifier fails until the fix is applied.
- **Fixes → `[fix-verified]` assertions**: every eval-loop fix becomes a
  regression assertion before "stable"; /tmp reports are ephemeral, the
  evals.json `notes` + assertions are the durable net.
- **Roles, not model IDs**, in skill bodies. IDs live only in
  `reference/model-routing.md`.
- **No volatile facts** (prices, model names, dates) in skill bodies.
- **Cross-skill contracts have ONE source of truth**, linked via relative
  sibling path (e.g. `../designing-architecture/references/plan-format.md`),
  never duplicated. Library installs as a set so siblings resolve.
- **Stack plugin axis** `references/stacks/` (framework); the UI loop adds
  a second axis `references/systems/` (CSS methodology).
- **Skill-relative paths stated explicitly** ("resolved against this
  skill's own directory — not the project's") — a fresh agent in a
  project defaults to project-relative reading.
- **Description headroom**: target <=900 chars (hard cap 1024); pushy
  descriptions crowd the cap.
- **Two-turn harness** for stop-and-ask skills; **document deferrals**
  (e.g. no-browser, single-model-tier) in evals.json notes, never
  silently skip.
- **Loops close on objective signals** (exit codes, geometry, computed
  CSS, source-mapped rules), never "looks done." Vision is last-resort
  perceptual residue only.
- **Leak scan**: instructions generic, fixtures may be project-flavored;
  and scan for eval-answer leaks (instructions mirroring eval scenarios).

## Model strategy (see reference/model-routing.md, evidence-backed 2026-07-06)

- **Reviewer (you)**: `claude-opus-4-8` (88.6 SWE-Verified / 69.2 Pro —
  highest buyable). `claude-fable-5` only for peak architecture (2x cost,
  export-suspended intermittently).
- **Skill author**: `minimax-m3` default (existing-code parity w/ GLM,
  3.7x cheaper + 3.7x more Go requests — fixes Go-limit exhaustion),
  `glm-5.2` escalation for subtle/greenfield-ish/contract-consuming
  skills (use it for the capstone-class ones), `qwen3.7-max` for
  instruction-following escalation.
- **Vision critic (UI loop)**: tiered — `vision-critic-fast`
  (gemini-3-flash / gpt-5.4-mini, or evaluate minimax-m3 native-multimodal
  on Go flat rate), `vision-critic-final` (gemini-3.1-pro / sonnet-5).

## Current state (2026-07-10, HEAD after this review's commit)

**Both core loops complete + first Phase 3 follow-on landed. 12 skills,
all eval-backed + reviewed + pushed.**

Core loop: triaging-requirements, designing-architecture,
implementing-features, debugging-test-failures, writing-unit-tests,
writing-integration-tests, writing-e2e-tests, reviewing-code.
UI loop: capturing-ui-evidence, correcting-ui, auditing-accessibility
(proactive a11y auditor — axe-core + Playwright, WCAG 2.2 AA/AAA,
read-only, routes fixes to correcting-ui/implementing-features/
designing-architecture).
Meta: authoring-skills (+ bundled scripts/validate_skill.py).

`auditing-accessibility` review (this round): validator green across all
12 skills; leak scan clean (`phasewave` confirmed as the library's
sanctioned fictional-fixture convention, not a real-project leak); all 4
eval scenarios independently re-run from fresh /tmp copies against the
real `audit.mjs` (not the author's report) — violations-present,
clean-page, suppression-trap (both refusal + dated-acceptance legs), and
automation-ceiling all green; failable property proven by hand (deleted a
planted violation from the canned axe-results → verifier correctly went
red; tampered a harness file → zero-edit guard correctly went red;
restored → green again). `buildReport` in audit.mjs inspected directly:
violations are never filtered by `acceptedRisks`, only annotated — the
cardinal rule is structurally guaranteed, not just test-fitted.

Defect found by the author + independently reproduced by review: a
symlinked-install no-op in `audit.mjs`'s "run as main" gate (real
`import.meta.url` vs. un-realpath'd `argv[1]` never match under
`~/.config/opencode/skills/...`, so `main()` silently never runs). Fixed
in both `audit.mjs` and the same latent defect in the sibling
`capturing-ui-evidence/scripts/capture.mjs`; sibling's 3 fixtures
re-verified green post-fix (no regression). Learning folded into
`authoring-skills/SKILL.md`'s Library conventions (symlink-safe
"run-as-main" gate requirement for any bundled script).

## Remaining backlog

- **NEXT (not optional — a real gap, not a nice-to-have):** TDD-aware
  implement sequencing. `implementing-features` currently runs the plan's
  Verification commands and fixes code until green, with no requirement
  that a test exist — let alone fail — before the code does; test
  authoring (the trio) is invoked "separately," unordered. Decisions
  locked in `PLAN.md` under "Core Loop Refinement — TDD-Aware Implement
  Sequencing"; handoff prompt ready in
  `docs/handoffs/tdd-sequencing.md` — dispatch to a fresh GLM 5.2 author
  session. Touches `implementing-features` (two new steps: red-first AC
  capture, coverage-and-quality gate), all three test-trio skills (a
  meaningfulness-proof mode branch), and a small additive cross-reference
  in `reviewing-code`. Review this one especially carefully at Step 4 of
  the review protocol — a red-first proof that's secretly fabricated (the
  agent claims a test went red pre-implementation but never actually ran
  it that way) is exactly the kind of claim this library's review
  discipline exists to catch, not take on faith.
- `auditing-visual-design` (proactive visual audit) — Phase 3 follow-on.
- Phase 4: `running-councils`, `releasing-changes`, agent templates, and
  the **pt migration** (pt consumes the library; refresh its stale
  `qwen3.6-plus` binding; reconcile pt's single `.opencode/plans/
  pending-task.md` with the library's slug-based plan artifacts).
- Phase 5: benchmark harness to empirically confirm model-routing bindings.

## Known open items carried forward

- `capturing-ui-evidence/scripts/capture.mjs` does bare
  `await import('playwright')` resolved from its symlinked location — a
  project-local playwright may not resolve. Documented workaround in that
  SKILL.md; a robust in-harness fix (createRequire from cwd) is deferred
  to an authoring pass with re-verification.
- pt's build agent expects one `pending-task.md`; the library emits
  slug-based plans. Reconcile during the Phase 4 pt migration.
