#!/usr/bin/env python3
"""Deterministic tests for changed-files-to-skills.py (RM-003 AC7).

Run: python3 scripts/test_changed_files.py
Exit 0 = the mapping table is deterministic, first-match-wins, and classifies
all three classes (evaluable / smoke / non-evaluable) correctly.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "changed_files_to_skills", os.path.join(HERE, "changed-files-to-skills.py"))
cfs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cfs)


def test_evaluable_skills():
    assert cfs.analyze(["skills/writing-unit-tests/SKILL.md"])["skills"] == ["writing-unit-tests"]
    assert cfs.analyze(["skills/authoring-skills/evals/evals.json"])["skills"] == ["authoring-skills"]
    # skill-internal scripts are covered by skills/<name>/** (no per-file row)
    assert cfs.analyze(["skills/authoring-skills/scripts/run_behavioral_eval.py"])["skills"] == ["authoring-skills"]
    assert cfs.analyze(["skills/observing-runs/scripts/query_runs.py"])["skills"] == ["observing-runs"]
    assert cfs.analyze(["skills/writing-unit-tests/evals/fixtures/x/README.md"])["skills"] == ["writing-unit-tests"]


def test_optimizing_model_routing():
    assert cfs.analyze(["reference/model-routing.md"])["skills"] == ["optimizing-model-routing"]
    assert cfs.analyze(["agents/council.md"])["skills"] == ["optimizing-model-routing"]


def test_non_evaluable():
    for path in ("docs/architecture.md", "reference/git-workflow.md",
                 ".opencode/plans/rm-003.md", "README.md", "LICENSE",
                 ".gitignore", "CONTRIBUTING.md"):
        r = cfs.analyze([path])
        assert r["skills"] == [], (path, r)
        assert r["class"] == "non_evaluable", (path, r)
        assert r["harness"] is False, (path, r)


def test_harness():
    """RM-003 pass 4: CI-infra/unmatched paths are the `harness` class, whose
    action is the fixed six-core-default set (no relevance list / alphabetical
    fallback)."""
    expected_core = ["authoring-skills", "designing-architecture",
                     "implementing-features", "reviewing-code",
                     "triaging-requirements", "writing-unit-tests"]
    for path in ("scripts/changed-files-to-skills.py", "scripts/eval-report.py",
                 ".github/workflows/eval-behavioral.yml", "Makefile"):
        r = cfs.analyze([path])
        assert r["skills"] == [], (path, r)
        assert r["class"] == "harness", (path, r)
        assert r["harness"] is True, (path, r)
        assert r["core_skills"] == expected_core, (path, r)


def test_harness_has_no_relevance_list_or_alphabetical_fallback():
    """RM-003 AC7: a harness change never guesses skills alphabetically."""
    r = cfs.analyze(["scripts/unknown-new-script.py"])
    assert r["class"] == "harness" and r["skills"] == [], r
    # the fixed core set is the harness target, independent of the changed name
    assert r["core_skills"] == list(cfs.CORE_SKILLS), r


def test_first_match_wins_and_dedupe():
    r = cfs.analyze([
        "skills/writing-unit-tests/SKILL.md",
        "skills/writing-unit-tests/evals/evals.json",
        "skills/authoring-skills/scripts/run_behavioral_eval.py",
    ])
    # first-seen order, deduped
    assert r["skills"] == ["writing-unit-tests", "authoring-skills"], r


def test_class_precedence_evaluable_wins():
    # A PR touching a skill + a workflow is evaluable (run the skill evals),
    # while still reporting that smoke/non-evaluable paths changed.
    r = cfs.analyze(["skills/observing-runs/SKILL.md",
                     ".github/workflows/ci.yml", "docs/x.md"])
    assert r["class"] == "evaluable", r
    assert r["skills"] == ["observing-runs"], r
    assert r["harness"] is True and r["non_evaluable"] is True, r


def test_docs_only_runs_zero_evals():
    r = cfs.analyze(["docs/architecture.md", "README.md"])
    assert r["class"] == "non_evaluable"
    assert r["skills"] == []


def main():
    tests = [
        test_evaluable_skills,
        test_optimizing_model_routing,
        test_non_evaluable,
        test_harness,
        test_harness_has_no_relevance_list_or_alphabetical_fallback,
        test_first_match_wins_and_dedupe,
        test_class_precedence_evaluable_wins,
        test_docs_only_runs_zero_evals,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
