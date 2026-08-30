#!/usr/bin/env python3
"""RED/GREEN + symlink-safety tests for log_run.py (RM-001 AC1, AC2, AC6).

Run: python3 skills/observing-runs/scripts/test_log.py
Exit 0 = all assertions pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "log_run.py")
SCHEMA_FIELDS = [
    "ts", "run_id", "kind", "skill", "agent", "model",
    "tokens_in", "tokens_out", "duration_ms", "outcome", "eval_pass", "detail",
]


def _run(record, logs_dir, script_path=None):
    sp = script_path or SCRIPT
    cmd = [sys.executable, sp, "--record", json.dumps(record)]
    if logs_dir:
        cmd += ["--logs-dir", logs_dir]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_complete_record_writes_one_line():
    d = tempfile.mkdtemp()
    try:
        rec = {
            "kind": "eval", "skill": "x", "model": "go",
            "tokens_in": 10, "tokens_out": 20, "duration_ms": 500,
            "outcome": "success", "eval_pass": True, "detail": "ok",
        }
        r = _run(rec, d)
        assert r.returncode == 0, f"exit non-zero: {r.stderr}"
        files = os.listdir(d)
        assert len(files) == 1 and files[0].endswith(".jsonl"), files
        lines = [l for l in open(os.path.join(d, files[0]), encoding="utf-8").read().splitlines() if l]
        assert len(lines) == 1, f"expected exactly one line, got {len(lines)}"
        obj = json.loads(lines[0])
        for k in SCHEMA_FIELDS:
            assert k in obj, f"missing schema field {k}"
        # numeric defaults filled even when absent from input
        assert obj["tokens_in"] == 10 and obj["tokens_out"] == 20
    finally:
        shutil.rmtree(d)


def test_missing_required_field_exits_nonzero():
    d = tempfile.mkdtemp()
    try:
        rec = {"kind": "eval", "skill": "x"}  # missing required `outcome`
        r = _run(rec, d)
        assert r.returncode != 0, "should fail when a required field is omitted"
        assert not os.listdir(d), "must not write anything on validation failure"
    finally:
        shutil.rmtree(d)


def test_symlink_safe():
    real_skill = os.path.dirname(os.path.dirname(SCRIPT))  # skills/observing-runs
    d = tempfile.mkdtemp()
    link_dir = tempfile.mkdtemp()
    try:
        link = os.path.join(link_dir, "observing-runs")
        os.symlink(real_skill, link)
        link_script = os.path.join(link, "scripts", "log_run.py")
        rec = {"kind": "eval", "skill": "x", "outcome": "success", "eval_pass": True}
        r_real = _run(rec, d, script_path=SCRIPT)
        assert r_real.returncode == 0, r_real.stderr
        r_link = _run(rec, d, script_path=link_script)
        assert r_link.returncode == 0, r_link.stderr
        files = os.listdir(d)
        lines = [l for l in open(os.path.join(d, files[0]), encoding="utf-8").read().splitlines() if l]
        assert len(lines) == 2, f"expected 2 lines (real+symlink), got {len(lines)}"
        # realpath resolution means the symlinked run still wrote via the real script
        assert os.path.islink(link)
    finally:
        shutil.rmtree(d)
        shutil.rmtree(link_dir)


def test_append_only_no_readback():
    src = open(SCRIPT, encoding="utf-8").read()
    # append mode for the log file, and no read of the log path back
    assert 'open(path, "a"' in src, "log file must be opened append-only"
    assert '"r"' not in src, "log_run.py must not read the log file back (out-of-context guard)"


def main():
    tests = [
        test_complete_record_writes_one_line,
        test_missing_required_field_exits_nonzero,
        test_symlink_safe,
        test_append_only_no_readback,
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
