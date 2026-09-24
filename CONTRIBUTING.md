# Contributing to ai-framework

This library is a portable, versioned set of agent skills and thin agent
personas; every change to it is made by the same discipline it enforces.
`docs/CONCEPTS.md` is the design rationale; this file is the contribution
flow.

## All work happens on a branch

Branch names derive from the plan slug: `<type>/<name>`
(`reference/git-workflow.md`). main is protected; merges are PRs,
user-initiated. Trivial edits skip the plan, never the branch.

## The contribution flow (skill authoring)

1. **Evals first.** Draft 2–3 realistic prompts with observable expected
   behavior and self-contained fixtures before the skill body exists
   (`skills/authoring-skills/SKILL.md` owns the process).
2. **Typed assertions.** Every eval carries a closed-shape `expect` block
   (action / artifact / text — the nature rule, ADR-0003). A new or
   changed eval must carry `expect` in the same change (migrate-on-touch).
3. **Fresh-agent testing.** Run the evals with a fresh agent session that
   has the skill installed — the author never grades itself.
4. **Independent re-verification.** A separate session re-runs the evals
   from a fresh copy and tries to break the verifier before commit.
5. **Review.** `reviewing-code` verdicts on the diff against the plan;
   the verdict follows the mechanical severity table.

## The gates every PR passes

These match `.github/workflows/ci.yml` exactly (three-layer gating,
ADR-0005 — the full details live in `reference/three-layer-gating.md`):

```
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/check_typed_evals.py --base main
python3 scripts/test_changed_files.py && python3 scripts/test_eval_report.py \
  && python3 scripts/test_eval_workflows.py && python3 scripts/test_quarantine.py \
  && python3 scripts/test_stall_timeout.py && python3 scripts/test_typed_evals.py
node skills/managing-github-issues/evals/fixtures/unit.test.mjs
node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs
bash -n install.sh
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

The required PR eval check additionally runs the changed skills' canaries
(`eval-per-change.yml`); the weekly full suite
(`eval-behavioral.yml`) is the coverage backstop.

## Where does a decision go?

The three-tier repo memory (ADR-0008; routing table in
`docs/ADRs/README.md`):

| You are about to record… | It belongs in |
|---|---|
| A cross-session imperative | `AGENTS.md` |
| A binding or structure decision | `docs/ADRs/` (with maturity status) |
| An in-flight plan or session handoff | `.opencode/plans/` (tracked here; archived after essence-extraction) |
| Current state and next action | `docs/ROADMAP.md` |
| A volatile fact (models, pricing, catalog) | `reference/*.md` (current-state only, dated) |

## Communication baseline

Engineering artifacts follow `reference/technical-english.md`: plain
words, the shared vocabulary verbatim, exact numbers, uncertainty labeled
(`unverified` / `vendor-stated` / `assumed`), and the fixed handoff shape
done → verified → blocked → next.
