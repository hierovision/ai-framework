#!/usr/bin/env python3
"""Deterministic aggregation tests for query_runs.py (RM-001 AC3).

Run: python3 skills/observing-runs/scripts/test_query.py
Exit 0 = aggregates match the expected numbers embedded in the fixture.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "query_runs.py")

# Fixture records (two skills; alpha has 2 eval rows, beta 1 skill row).
FIXTURE_LINES = [
    {"ts": "2026-01-01T00:00:00Z", "run_id": "a1", "kind": "eval", "skill": "alpha",
     "model": "go", "tokens_in": 100, "tokens_out": 50, "duration_ms": 1000,
     "outcome": "success", "eval_pass": True, "detail": None},
    {"ts": "2026-01-01T00:01:00Z", "run_id": "a2", "kind": "eval", "skill": "alpha",
     "model": "go", "tokens_in": 100, "tokens_out": 50, "duration_ms": 2000,
     "outcome": "failure", "eval_pass": False, "detail": "boom"},
    {"ts": "2026-01-01T00:02:00Z", "run_id": "b1", "kind": "skill", "skill": "beta",
     "model": None, "tokens_in": 200, "tokens_out": 0, "duration_ms": 500,
     "outcome": "success", "eval_pass": None, "detail": None},
]

# Expected aggregates (computed by hand from the fixture above).
EXPECTED = {
    "alpha": {"runs": 2, "tokens_total": 300, "cost_per_task": 150.0, "mean_duration_ms": 1500.0},
    "beta": {"runs": 1, "tokens_total": 200, "cost_per_task": 200.0, "mean_duration_ms": 500.0},
    "eval_pass_rate": 0.5,
    "eval_rows": 2,
    "eval_passed": 1,
}


def _run_aggregate(logs_dir):
    r = subprocess.run(
        [sys.executable, SCRIPT, "aggregate", "--logs-dir", logs_dir],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip())


def main():
    d = tempfile.mkdtemp()
    failed = 0
    try:
        path = os.path.join(d, "run-2026-01-01.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for line in FIXTURE_LINES:
                fh.write(json.dumps(line) + "\n")

        result = _run_aggregate(d)
        by_skill = {s["skill"]: s for s in result["skills"]}

        for skill, exp in EXPECTED.items():
            if skill in ("eval_pass_rate", "eval_rows", "eval_passed"):
                continue
            got = by_skill[skill]
            for k, v in exp.items():
                if abs(got[k] - v) > 1e-9:
                    failed += 1
                    print(f"FAIL  skill {skill} {k}: expected {v}, got {got[k]}")
                else:
                    print(f"PASS  skill {skill} {k} = {v}")

        for k in ("eval_pass_rate", "eval_rows", "eval_passed"):
            if result[k] != EXPECTED[k]:
                failed += 1
                print(f"FAIL  {k}: expected {EXPECTED[k]}, got {result[k]}")
            else:
                print(f"PASS  {k} = {EXPECTED[k]}")
    finally:
        shutil.rmtree(d)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
