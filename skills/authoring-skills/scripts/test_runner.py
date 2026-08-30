#!/usr/bin/env python3
"""Offline (no-model) tests for run_behavioral_eval.py (RM-002 AC1, AC2, AC4, AC7).

Run: python3 skills/authoring-skills/scripts/test_runner.py
Exit 0 = the gate fails-when-wrong and passes-when-right, and uses RM-001's
log_run.py (single source of truth).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_behavioral_eval.py")

spec = importlib.util.spec_from_file_location("run_behavioral_eval", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)  # also imports RM-001's log_run (AC2)


def _make_skills_root():
    root = tempfile.mkdtemp(prefix="beval-skills-")
    # alpha: one normal eval + one deferred eval
    alpha = os.path.join(root, "alpha", "evals")
    os.makedirs(alpha)
    json.dump({
        "default_model_tier": "go",
        "evals": [
            {"id": 1, "prompt": "p", "expected_behavior": ["alpha does X", "alpha does Y"]},
            {"id": 2, "prompt": "p", "expected_behavior": ["alpha deferred Z"], "deferred": True},
        ],
    }, open(os.path.join(alpha, "evals.json"), "w"))
    # beta: one normal eval
    beta = os.path.join(root, "beta", "evals")
    os.makedirs(beta)
    json.dump({
        "evals": [{"id": 1, "prompt": "p", "expected_behavior": ["beta does W"]}],
    }, open(os.path.join(beta, "evals.json"), "w"))
    return root


def _read_logs(logs_dir):
    recs = []
    if not os.path.isdir(logs_dir):
        return recs
    for fn in os.listdir(logs_dir):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(logs_dir, fn), encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def test_assert_behavior():
    exp = ["A", "B"]
    assert runner.assert_behavior(exp, "A\nB") == []
    assert runner.assert_behavior(exp, "a and b here") == []  # case-insensitive
    miss = runner.assert_behavior(exp, "only A present")
    assert miss == ["B"], miss


def test_run_eval_pass_and_fail():
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A", "B"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    try:
        passed, missing, path = runner.run_eval(e, lambda _e: "A\nB", logs_dir=d)
        assert passed and not missing
        recs = _read_logs(d)
        assert len(recs) == 1 and recs[0]["eval_pass"] is True
        assert recs[0]["outcome"] == "success"

        passed, missing, path = runner.run_eval(e, lambda _e: "only A", logs_dir=d)
        assert not passed and missing == ["B"]
        recs = _read_logs(d)
        assert recs[-1]["eval_pass"] is False
        assert recs[-1]["outcome"] == "failure"
        assert "B" in (recs[-1]["detail"] or "")
    finally:
        shutil.rmtree(d)


def test_cli_pass_branch():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--skills-root", root,
                            "--logs-dir", logs, "--stub-output", "ALL"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        recs = _read_logs(logs)
        assert len(recs) == 2, f"expected 2 non-deferred records, got {len(recs)}"
        assert all(x["eval_pass"] is True for x in recs)
        print("PASS  stub ALL -> exit 0, eval_pass=true for every included eval")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_cli_fail_branch():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--skills-root", root,
                            "--logs-dir", logs, "--stub-output", ":MISS:"],
                           capture_output=True, text=True)
        assert r.returncode != 0, "omitting an expected behavior must fail the gate"
        recs = _read_logs(logs)
        assert recs and all(x["eval_pass"] is False for x in recs)
        print("PASS  stub :MISS: -> exit non-zero, eval_pass=false")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_deferred_excluded():
    root = _make_skills_root()
    try:
        evals = runner.load_skill_evals(root)
        included = runner.filter_evals(evals, include_deferred=False)
        ids = [(e["skill"], e["eval_id"]) for e in included]
        assert ("alpha", 2) not in ids, "deferred eval must be excluded by default"
        assert ("alpha", 1) in ids and ("beta", 1) in ids

        # --list also omits the deferred eval
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root],
                           capture_output=True, text=True)
        assert r.returncode == 0
        assert "included evals: 2" in r.stdout, r.stdout
        assert "deferred" not in r.stdout, "deferred must not appear in default --list"
        print("PASS  deferred eval excluded from default run + --list")
    finally:
        shutil.rmtree(root)


def test_subset_sharding():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        # --limit 1 runs only the first included eval
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root,
                            "--limit", "1"], capture_output=True, text=True)
        assert "included evals: 1" in r.stdout, r.stdout
        r2 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
                             "--limit", "1", "--stub-output", "ALL"],
                            capture_output=True, text=True)
        assert r2.returncode == 0, r2.stderr
        recs = _read_logs(logs)
        assert len(recs) == 1, f"--limit 1 must run exactly one eval, got {len(recs)}"

        # --skill beta runs only beta
        logs2 = tempfile.mkdtemp()
        try:
            r3 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs2,
                                 "--skill", "beta", "--stub-output", "ALL"],
                                capture_output=True, text=True)
            assert r3.returncode == 0, r3.stderr
            recs2 = _read_logs(logs2)
            assert len(recs2) == 1 and recs2[0]["skill"] == "beta"
        finally:
            shutil.rmtree(logs2)
        print("PASS  --limit / --skill shard the run (subset skips the rest)")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_ci_free_only():
    root = tempfile.mkdtemp(prefix="beval-ci-")
    try:
        s = os.path.join(root, "s", "evals"); os.makedirs(s)
        json.dump({"evals": [
            {"id": 1, "prompt": "p", "expected_behavior": ["free ok"], "default_model_tier": "free"},
            {"id": 2, "prompt": "p", "expected_behavior": ["go skip"], "default_model_tier": "go"},
            {"id": 3, "prompt": "p", "expected_behavior": ["zen skip"], "default_model_tier": "zen"},
        ]}, open(os.path.join(s, "evals.json"), "w"))
        env = {**os.environ, "AI_FRAMEWORK_FREE_TIER": "1"}
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root],
                           capture_output=True, text=True, env=env)
        assert "tier=free" in r.stdout and "tier=go" not in r.stdout and "tier=zen" not in r.stdout, r.stdout
        logs = tempfile.mkdtemp()
        r2 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
                             "--stub-output", "ALL"], capture_output=True, text=True, env=env)
        assert r2.returncode == 0, r2.stderr
        recs = _read_logs(logs)
        assert len(recs) == 1 and recs[0]["model"] == "free", recs
        print("PASS  CI mode (AI_FRAMEWORK_FREE_TIER=1) skips go/zen, runs free only")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    tests = [
        test_assert_behavior,
        test_run_eval_pass_and_fail,
        test_cli_pass_branch,
        test_cli_fail_branch,
        test_deferred_excluded,
        test_subset_sharding,
        test_ci_free_only,
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
