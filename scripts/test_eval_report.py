#!/usr/bin/env python3
"""Deterministic tests for eval-report.py + query_runs.py coverage-gaps
(RM-003 AC1, AC3, AC4, AC11).

Run: python3 scripts/test_eval_report.py
Exit 0 = aggregate per-run scores, the four coverage-gap arrays, the green-run
status shape, and the quota projection are correct.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
QUERY = os.path.join(REPO_ROOT, "skills", "observing-runs", "scripts", "query_runs.py")
_SPEC = importlib.util.spec_from_file_location(
    "eval_report", os.path.join(HERE, "eval-report.py"))
report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(report)

_QS = importlib.util.spec_from_file_location("query_runs", QUERY)
query_runs = importlib.util.module_from_spec(_QS)
_QS.loader.exec_module(query_runs)

FIXTURE_LINES = [
    {"ts": "2026-09-17T06:00:00Z", "run_id": "r1", "kind": "eval",
     "skill": "writing-unit-tests", "model": "free", "tokens_in": 800,
     "tokens_out": 300, "duration_ms": 142000, "outcome": "success",
     "eval_pass": True, "detail": None},
    {"ts": "2026-09-17T06:01:00Z", "run_id": "r2", "kind": "eval",
     "skill": "observing-runs", "model": "free", "tokens_in": 700,
     "tokens_out": 250, "duration_ms": 120000, "outcome": "failure",
     "eval_pass": False, "detail": "missing x"},
    {"ts": "2026-09-17T06:02:00Z", "run_id": "r3", "kind": "skill",
     "skill": "writing-unit-tests", "model": None, "tokens_in": None,
     "tokens_out": None, "duration_ms": None, "outcome": "success",
     "eval_pass": None, "detail": None},
]


def _seed_logs(d):
    with open(os.path.join(d, "run-2026-09-17.jsonl"), "w", encoding="utf-8") as fh:
        for line in FIXTURE_LINES:
            fh.write(json.dumps(line) + "\n")


def test_aggregate_report_per_run_scores():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        out = report.aggregate_report(d)
        assert out["aggregate"]["eval_rows"] == 2, out["aggregate"]
        assert out["aggregate"]["eval_passed"] == 1, out["aggregate"]
        assert "writing-unit-tests" in out["per_skill"]
        runs = out["per_skill"]["writing-unit-tests"]
        assert len(runs) == 1 and runs[0]["run_id"] == "r1"
        assert runs[0]["duration_ms"] == 142000 and runs[0]["eval_pass"] is True
        assert len(out["per_skill"]["observing-runs"]) == 1
    finally:
        shutil.rmtree(d)


def test_coverage_gaps_shape_and_quarantine():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        with open(os.path.join(d, "quarantine.json"), "w", encoding="utf-8") as fh:
            json.dump({"writing-unit-tests#3": {
                "fail_count": 3, "first_fail": "2026-09-15",
                "last_fail": "2026-09-17", "status": "quarantined"}}, fh)
        gaps = report.coverage_gaps(d)
        assert set(gaps) == {"zero_eval_skills", "deferred_evals",
                             "free_tier_excluded_evals", "quarantined_evals",
                             "no_default_marker", "core_covered", "core_uncovered",
                             "smoke_uncovered"}, gaps
        # writing-unit-tests + observing-runs have eval records -> not zero.
        assert "writing-unit-tests" not in gaps["zero_eval_skills"]
        assert "observing-runs" not in gaps["zero_eval_skills"]
        assert "authoring-skills" in gaps["zero_eval_skills"]
        # deferred evals (optimizing-model-routing + validating-against-official-docs).
        deferred_skills = {x["skill"] for x in gaps["deferred_evals"]}
        assert {"optimizing-model-routing", "validating-against-official-docs"} <= deferred_skills
        assert gaps["free_tier_excluded_evals"] == []
        assert gaps["quarantined_evals"][0]["key"] == "writing-unit-tests#3"
    finally:
        shutil.rmtree(d)


def test_query_runs_coverage_gaps_cli():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        r = subprocess.run([sys.executable, QUERY, "coverage-gaps",
                            "--logs-dir", d], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        gaps = json.loads(r.stdout)
        assert "zero_eval_skills" in gaps and "deferred_evals" in gaps
    finally:
        shutil.rmtree(d)


def test_green_run_status_not_achieved_and_recorded():
    not_achieved = report.green_run_status()
    assert not_achieved["achieved"] is False
    assert "2026-09-21" in not_achieved["reason"]
    assert "35108912831" in not_achieved["reason"]

    achieved = report.green_run_status(
        achieved=True, run_id="123", date="2026-09-21", branch="main",
        duration_min=18.5, all_pass=True, quarantine_flips=0,
        artifact_url="https://example/actions/runs/123")
    assert achieved["achieved"] is True and achieved["run_id"] == "123"
    assert achieved["duration_min"] == 18.5


def test_quota_projection_under_guardrail():
    q = report.quota_projection()
    assert q["guardrail_limit"] == 1800
    assert q["projected_monthly"] == round(
        q["weekly_min_used"] + q["per_change_min_used"], 1)
    assert q["projected_monthly"] < q["guardrail_limit"], q


def test_coverage_gaps_default_and_core_arrays():
    """RM-003 pass 4 / AC3: no_default_marker + core coverage arrays.

    Additive to the three required arrays. The six core skills must resolve a
    core-marked canary; only the two pass-4 canaries carry `default`.
    """
    d = tempfile.mkdtemp()
    try:
        gaps = report.coverage_gaps(d)
        for key in ("no_default_marker", "core_covered",
                    "core_uncovered", "smoke_uncovered"):
            assert key in gaps, (key, gaps)
        covered = {x["skill"] for x in gaps["core_covered"]}
        assert covered == set(query_runs.CORE_SKILLS), covered
        assert gaps["core_uncovered"] == [], gaps["core_uncovered"]
        # default marker rollout: only authoring-skills + observing-runs this pass
        assert "authoring-skills" not in gaps["no_default_marker"]
        assert "observing-runs" not in gaps["no_default_marker"]
        assert "designing-architecture" in gaps["no_default_marker"]
        # core_covered entries name the canary eval id
        for item in gaps["core_covered"]:
            assert item["eval_id"] == 1, item
    finally:
        shutil.rmtree(d)


def main():
    tests = [
        test_aggregate_report_per_run_scores,
        test_coverage_gaps_shape_and_quarantine,
        test_coverage_gaps_default_and_core_arrays,
        test_query_runs_coverage_gaps_cli,
        test_green_run_status_not_achieved_and_recorded,
        test_quota_projection_under_guardrail,
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
