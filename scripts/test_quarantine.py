#!/usr/bin/env python3
"""Deterministic tests for quarantine.py + the runner retry/quarantine wiring
(RM-003 AC9).

Run: python3 scripts/test_quarantine.py
Exit 0 = 3-strike quarantine works, success clears, retry fires on transient
failures only, and the runner excludes quarantined evals by default.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import quarantine  # noqa: E402

RUNNER = os.path.join(
    os.path.dirname(HERE), "skills", "authoring-skills", "scripts",
    "run_behavioral_eval.py")
_SPEC = importlib.util.spec_from_file_location("run_behavioral_eval", RUNNER)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def test_three_strike_quarantine():
    d = tempfile.mkdtemp(prefix="quarantine-test-")
    try:
        path = os.path.join(d, "quarantine.json")
        key = "writing-unit-tests#3"
        e1 = quarantine.record_failure(path, key, today="2026-09-15")
        assert e1["fail_count"] == 1 and e1["status"] == "watching", e1
        e2 = quarantine.record_failure(path, key, today="2026-09-17")
        assert e2["fail_count"] == 2 and e2["status"] == "watching", e2
        e3 = quarantine.record_failure(path, key, today="2026-09-18")
        assert e3["fail_count"] == 3 and e3["status"] == "quarantined", e3
        assert e3["first_fail"] == "2026-09-15" and e3["last_fail"] == "2026-09-18", e3
        assert key in quarantine.quarantined_keys(path)
    finally:
        shutil.rmtree(d)


def test_success_clears_consecutive():
    d = tempfile.mkdtemp(prefix="quarantine-test-")
    try:
        path = os.path.join(d, "quarantine.json")
        key = "observing-runs#1"
        quarantine.record_failure(path, key)
        quarantine.record_failure(path, key)
        assert quarantine.load(path)[key]["fail_count"] == 2
        assert quarantine.record_success(path, key) is True
        assert key not in quarantine.load(path)


    finally:
        shutil.rmtree(d)


def test_runner_retries_transient_only():
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A", "B"],
         "model_tier": "free"}
    calls = {"n": 0}

    def flaky(_e):
        calls["n"] += 1
        if calls["n"] == 1:
            return "error: connection timeout (transient)"
        return "A\nB"

    d = tempfile.mkdtemp()
    try:
        passed, missing, _ = runner.run_eval(
            e, flaky, logs_dir=d, sleep=lambda _s: None)
        assert passed and not missing, (passed, missing)
        assert calls["n"] == 2, f"expected one retry, got {calls['n']} calls"
    finally:
        shutil.rmtree(d)

    # A non-transient failure must NOT be retried.
    calls2 = {"n": 0}

    def miss(_e):
        calls2["n"] += 1
        return "only A"

    d = tempfile.mkdtemp()
    try:
        passed, missing, _ = runner.run_eval(
            e, miss, logs_dir=d, sleep=lambda _s: None)
        assert not passed and missing == ["B"], (passed, missing)
        assert calls2["n"] == 1, f"non-transient must not retry, got {calls2['n']}"
    finally:
        shutil.rmtree(d)


def test_runner_no_quarantine_when_disabled():
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"],
         "model_tier": "free"}
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "quarantine.json")
        runner.run_eval(e, lambda _e: "", logs_dir=d, sleep=lambda _s: None,
                        quarantine_path=path)
        assert os.path.isfile(path), "quarantine_path must record a failure"
        assert quarantine.load(path)[runner.eval_key(e)]["fail_count"] == 1
    finally:
        shutil.rmtree(d)


def test_filter_excludes_quarantined():
    evals = [
        {"skill": "a", "eval_id": 1, "deferred": False, "model_tier": "free"},
        {"skill": "a", "eval_id": 2, "deferred": False, "model_tier": "free"},
    ]
    excluded = runner.filter_evals(evals, quarantined={"a#2"})
    assert [e["eval_id"] for e in excluded] == [1], excluded
    included = runner.filter_evals(evals, quarantined={"a#2"}, include_quarantine=True)
    assert [e["eval_id"] for e in included] == [1, 2], included


def test_cli_check_and_mark_count():
    import json as _json
    import subprocess
    d = tempfile.mkdtemp(prefix="quarantine-cli-")
    try:
        qpath = os.path.join(d, "quarantine.json")
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "quarantine.py"),
             "--quarantine-file", qpath, "mark", "a#1", "--count", "3"],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert _json.loads(r.stdout)["status"] == "quarantined", r.stdout
        # check exits 0 when quarantined, 1 when not.
        r0 = subprocess.run(
            [sys.executable, os.path.join(HERE, "quarantine.py"),
             "--quarantine-file", qpath, "check", "a#1"],
            capture_output=True, text=True)
        assert r0.returncode == 0, r0.stdout + r0.stderr
        r1 = subprocess.run(
            [sys.executable, os.path.join(HERE, "quarantine.py"),
             "--quarantine-file", qpath, "check", "a#2"],
            capture_output=True, text=True)
        assert r1.returncode == 1, r1.stdout + r1.stderr
    finally:
        shutil.rmtree(d)


def main():
    tests = [
        test_three_strike_quarantine,
        test_success_clears_consecutive,
        test_runner_retries_transient_only,
        test_runner_no_quarantine_when_disabled,
        test_filter_excludes_quarantined,
        test_cli_check_and_mark_count,
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
