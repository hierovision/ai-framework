---
slug: agent-persona-expansion
title: Expand the persona cast so every standing loop role has a session identity
status: approved
created: 2026-10-02
related: [agent-teams-dispatch]
---

# Plan: agent-persona-expansion

## Goal / Approach

Every standing loop role has a dispatchable session identity — role lens,
skill pointer, model binding, authority surface, and dispatch policy —
instead of the current 4 (plus council/curator subset): 7 new thin personas
(`agents/reviewer.md`, `agents/test-writer.md`, `agents/debugger.md`,
`agents/vision-critic-fast.md`, `agents/vision-critic-final.md`,
`agents/skill-author.md`, `agents/skill-reviewer.md`), registered at
maturity L1, dispatch policy per `reference/agent-teams.md` (judgment-led;
leaf deny only where genuinely single-shot). Approach: thin bindings only
(ADR-0006, `docs/CONCEPTS.md` Choice 3) — each new file carries frontmatter
(`name`, `description`, `model`, `mode: all`, `permission`), a role lens, a
pointer to the owning skill(s), the communication pointer, and a dispatch-policy
citation. Model values cite `reference/model-routing.md` role rows; the agent
`model:` line is the sanctioned concrete-ID home for the persona's default
binding (routing table stays the single role map — nothing duplicated).
The `test_agent_dispatch.py` contract from PR #86 is extended for the
new cast.

## Acceptance Criteria

1. Seven persona files exist at `agents/<name>.md`, named per routing
   roles (never skill names), each thin (no process text — the SKILL.md is
   cited, not restated), each carrying `mode: all` and the role's routing
   default as its `model:` line: reviewer/test-writer/debugger/skill-author/
   skill-reviewer → `opencode/nemotron-3-ultra-free`;
   vision-critic-fast → `opencode-go/minimax-m3`;
   vision-critic-final → `deepseek/deepseek-flash`.
   — files parse as YAML frontmatter; `python3 scripts/test_agent_dispatch.py`
   `test_all_personas_dispatchable` passes (already asserts `mode: all` over
   every registry persona); a new assertion checks the frontmatter `model`
   value against the per-role table in this plan's Files section.

2. `registry.json` gains 7 persona entries — `type: persona`,
   `owner: @hierovision`, `maturity: L1`, `status: active`, resolvable
   `boundary_ref: agents/<name>.md` — and set-equality holds both ways
   (every `agents/*.md` ↔ one entry).
   — `python3 scripts/test_registry.py` exits 0
   (its completeness assertions enforce both directions; no stale count).

3. Authoritative surfaces encoded in frontmatter, per authority class:
   - **read-only + bash deny** (lens-like, single advisory pass):
     `vision-critic-fast`, `vision-critic-final` →
     `permission: {edit: deny, write: deny, bash: deny, task: deny}`
     (screenshot/image reads travel the Read tool, not bash).
   - **read-only with a read-only bash map** (single verdict):
     `reviewer`, `skill-reviewer` →
     `edit: deny, write: deny, task: deny`, bash reusing the planner's
     read-only allow map shape (`"ls *": allow`, `git diff*`… with a
     `"*": ask` catch-all first and the deny-list `rm*/git commit*/…`
     after — per `scripts/test_registry.py`
     `test_agent_bash_permission_maps_have_catch_all`).
   - **judgment-led workers** (delegatable, no task deny, no task
     allowlist): `test-writer` (writes tests only), `debugger`
     (read-first, minimal edits), `skill-author` (writes skill files)
     → `mode: all`, no `permission.task` key; `edit` left at default.
   — `python3 scripts/test_agent_dispatch.py` extended:
   `DENY_ALL_PERSONAS` gains the four leaves; a new
   `test_workers_judgment_led` asserts the three workers carry
   `permission.task is None`; a permission-shape check asserts each leaf's
   `edit`/`write`/`bash` deny posture per class above.

4. `reference/agent-teams.md` states the expanded leaf set and adds the
   new roles to its composition examples (still examples, not gates —
   judgment-led preserved; no per-persona allow-list introduced).
   — extended phrase assertions pass in
   `test_agent_teams_doc_contract` (leaf roster names all four leaves;
   at least one example sentence names a new role).

5. `docs/CONCEPTS.md` role vocabulary reflects the expanded cast
   (Choice 3 / Choice 6 role-vocabulary lines name the standup roles; no
   model IDs, no skill-name-personas).
   — grep: persona names appear in `docs/CONCEPTS.md`; no model IDs added
     to `docs/CONCEPTS.md` (diff check).

6. Full static gate green:
   — `python3 scripts/test_registry.py`
   — `python3 scripts/test_agent_dispatch.py`
   — `python3 skills/authoring-skills/scripts/validate_skill.py --all`
   — `python3 scripts/check_typed_evals.py --base HEAD`
   — `node scripts/verify.mjs`
   — `bash -n install.sh`
   Exit 0 each; yamllint clean as CI runs it.

7. Harness/live check: personas discoverable.
   — bash `scripts/install.sh` links the new agents into the global
     config (`install.sh` links `agents/*.md` wholesale); `opencode agent
     list` lists all seven new names. Recorded as a manual line in the
     handoff (live harness, not hermetic — proceeds only with a live
     session; an honest `DEFERRED` note replaces it if offline).

8. Roadmap tracked: `docs/ROADMAP.md` gains one row `RM-033`
   (self-improvement, priority 1–2, status `done` at implementation),
   source = this plan slug; no other row edited.
   — RM-033 row present at close; the registry trio (7 files + JSON +
     tests) and the row land in the same PR.

## Files to Modify

- `agents/reviewer.md` — new; reviews diffs against a plan (owning skill
  `reviewing-code`); read-only leaf (rule 3 above). No `reviewing-security`
  ownership — security review stays with `council-security` / audit skills.
- `agents/test-writer.md` — new; one persona binding the test trio
  (`writing-unit-tests` / `writing-integration-tests` /
  `writing-e2e-tests`), routes by layer per the trio's routing table;
  writes tests only (authority surface).
- `agents/debugger.md` — new; owns `debugging-test-failures`; read-first,
  minimal edits (edit allowed; the cardinal rule is cited, not restated).
- `agents/vision-critic-fast.md` — new; owns `correcting-ui` /
  `validating-ui` (advisory pass) / `capturing-ui-evidence`; Go lane
  (`opencode-go/minimax-m3` — no free multimodal exists, native
  multimodal is a hard gate per routing §Vision capability strategy).
  Read-only leaf.
- `agents/vision-critic-final.md` — new; vision sign-off, direct-key lane
  (`deepseek/deepseek-flash`). Read-only leaf.
- `agents/skill-author.md` — new; owns `authoring-skills` and
  `sourcing-external-skills`; writes skill files.
- `agents/skill-reviewer.md` — new; owns `validating-against-official-docs`
  plus independent skill-review (the "author never grades itself" pair with
  `skill-author`, `docs/CONCEPTS.md` 9b); read-only leaf.
- `registry.json` — 7 persona entries, maturity L1.
- `reference/agent-teams.md` — leaf rule names the four new leaves;
  composition examples include the new roles.
- `docs/CONCEPTS.md` — role vocabulary (Choices 3/6) lists the expanded cast.
- `scripts/test_agent_dispatch.py` — extended leaf set + workers + doc phrases.
- `docs/ROADMAP.md` — RM-033 allocated at implementation (source = this plan).
- Not modified: `reference/model-routing.md` — all seven roles already
  exist as table rows with exactly the bindings above; nothing to add.
- Not modified: `install.sh` — symlinks `agents/*.md` generically.

## Schema / Type Impacts

None. No database schema, generated types, or shared API contract — the
touched "contract" surfaces (`registry.json`, frontmatter YAML) are
validated by existing scripts, not regenerated.

## Scope

**Included**

- The seven thin persona files, registry entries (L1), dispatch-policy and
  permission frontmatter per rule 3.
- `test_agent_dispatch.py` extension (leaf roster, worker check, doc phrases).
- `reference/agent-teams.md` leaf-rule + composition-example updates.
- `docs/CONCEPTS.md` role-vocabulary update.
- `docs/ROADMAP.md` RM-033 allocation at implementation.

**Excluded**

- Changing `reference/model-routing.md` (role rows and bindings already
  exist; never duplicate IDs).
- Skills themselves — no `skills/*/SKILL.md` bodies change; personas are
  bindings, not process text (ADR-0006).
- Dispatcher/allow-list changes — composition stays judgment-led
  (2026-10-02 directive); planner and council-* keep their leaf deny.
- Consumer-repo behavior — no overrides/RM-015 work, no eval wiring for
  the new personas (behavioral evals for personas is future scope if a
  gap is proven).
- Model-routing optimization (`optimizing-model-routing` is the skill that
  changes bindings, not this plan).

## Verification

```bash
python3 scripts/test_registry.py
python3 scripts/test_agent_dispatch.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/check_typed_evals.py --base HEAD
node scripts/verify.mjs
bash -n install.sh
yamllint .github/workflows/*.yml
```

Plus (live, manual line in handoff): `bash scripts/install.sh && opencode agent list`

## Open Questions

1. **Vision shape** — propose **two personas** (fast/final), matching the
   routing table's two role rows; a single vision persona with explicit
   `--model` escalation would collapse the fast/sign-off authority
   distinction. Confirm two.
2. **Leaf roster** — propose the four leaves (reviewer, skill-reviewer,
   vision-critic-fast, vision-critic-final) deny `task`; test-writer,
   debugger,    skill-author stay judgment-led. Basis: single advisory pass /
   single verdict = genuinely single-shot; debugger and skill-author
   structurally loop with other agents (the debug→implement handoff;
   author→reviewer within the authoring-skill flow). Confirm.
3. **Names** — `reviewer` reads ambiguous against `skill-reviewer` in the
   registry; alternative `code-reviewer`. Propose keeping `reviewer` (the
   routing-table role name is canonical, ADR-0006 rule: role names).
   Confirm.
4. **Bootstrapping the cast at L1 vs L3** — registry maturity stays L1 for
   all seven (user decision); promotion evidence per ADR-0009 bar: a
   real-loop use (persona actually dispatched in a plan/implement/skill
   pass) + independent review, recorded in ROADMAP. Confirm L1 start.

## History

- 2026-10-02 — plan created from the user's design brief (7 personas;
  source PR #86's dispatch contract; user directive 2026-10-02 to expand
  the cast). Implement branch: `feat/agent-persona-expansion`.
  council-ux consult skipped — no user-facing UI; internal persona
  configuration (agent-teams scope).
- 2026-10-02 — approved per user directive (conditional pre-approval:
  proceed to implementation without waiting when the plan holds on its
  proposed defaults; no confounding questions found). All four Open
  Questions resolved on their defaults: two vision personas
  (fast/final); four-leaf roster (reviewer, skill-reviewer,
  vision-critic-fast, vision-critic-final) with test-writer / debugger /
  skill-author judgment-led; `reviewer` name kept; all seven at L1.
- 2026-10-02 — implemented (implement pass on `feat/agent-persona-expansion`).
  Delivered: 7 thin personas with `mode: all`, routing-role default
  bindings, and authority frontmatter (reviewer / skill-reviewer /
  vision-critic-* deny `task`; vision critics deny edit/write/bash;
  reviewers carry the planner's read-only bash map); registry entries at L1;
  `reference/agent-teams.md` leaf roster + composition examples;
  `docs/CONCEPTS.md` role vocabulary; RM-033 row; `scripts/test_agent_dispatch.py`
  extended (bindings, L1 entries, worker/leaf postures, owning-skill
  pointers, doc phrases, CONCEPTS vocabulary, RM-033).
  Red evidence (pre-implementation): `test_new_personas_files_and_bindings`
  / `test_new_personas_registered_l1` / `test_new_leaf_permission_posture` /
  `test_new_workers_judgment_led` failed on `agents/<name>.md missing` and
  `no registry persona entry`; `test_concepts_role_vocabulary` on the
  missing cast; `test_roadmap_rm033_row` on the missing row;
  `test_agent_teams_doc_contract` on the missing persona names.
  Verification: all 7 commands exit 0 (the canonical yamllint form
  `python3 -m yamllint -c .yamllint.yaml .github/workflows/` replaces the
  plan's `yamllint .github/workflows/*.yml`). Live check: `bash install.sh`
  linked 17 agents (0 skipped) and `opencode agent list` shows all seven
  `(all)` — the plan's `bash scripts/install.sh` path was corrected
  (install.sh is repo-root).
  Coverage gate: no layer rebalance (offline structural/unit is the right
  layer; the live harness is manual by design); expansion — the owning-skill
  pointer (ADR-0006) was uncovered, so
  `test_new_personas_cite_owning_skills` was added and proven
  break → red → restore → green. Runtime UI: no user-facing UI —
  council-ux consult skipped.
  Mechanical deviation: RM-033 lands `in-progress` with the PR link at push
  (the repo's closure convention — flips to `done` at merge), not `done` as
  AC8 worded it.

- 2026-10-02 — PR opened:
  [PR #88](https://github.com/hierovision/ai-framework/pull/88) on branch
  `feat/agent-persona-expansion`; RM-033 row carries the link (in-progress;
  flips to `done` at merge).

### Follow-ups

- `scripts/test_registry.py`'s PASS line still prints the frozen "10
  personas" (cosmetic, pre-existing; the assertions are derived) — fix on
  touch.
