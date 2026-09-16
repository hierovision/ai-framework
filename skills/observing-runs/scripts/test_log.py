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


def test_missing_tokens_default_null_not_zero():
    d = tempfile.mkdtemp()
    try:
        rec = {"kind": "skill", "skill": "x", "outcome": "success"}
        r = _run(rec, d)
        assert r.returncode == 0, f"exit non-zero: {r.stderr}"
        files = os.listdir(d)
        obj = json.loads(open(os.path.join(d, files[0]), encoding="utf-8").read().splitlines()[0])
        assert obj["tokens_in"] is None, f"missing tokens_in must be None, got {obj['tokens_in']!r}"
        assert obj["tokens_out"] is None, f"missing tokens_out must be None, got {obj['tokens_out']!r}"
        assert obj["duration_ms"] is None, f"missing duration_ms must be None, got {obj['duration_ms']!r}"
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


def test_default_logs_dir_when_imported_as_module():
    """RM-002 seam (found by the AC5 live gate, 2026-09-16): the eval runner
    IMPORTS log_run as a module (single source of truth — the runner must not
    redefine the schema), so the default logs dir must resolve from
    log_run.py's OWN location, never from sys.argv[0] of the importing
    process. In CI the importer is run_behavioral_eval.py, so the old
    argv[0]-based computation landed records in skills/logs/ instead of
    repo-root logs/ and the workflow artifact upload found nothing.
    """
    expected = os.path.abspath(
        os.path.join(os.path.dirname(SCRIPT), os.pardir, os.pardir, os.pardir, "logs")
    )
    importer_dir = tempfile.mkdtemp(prefix="logrun-importer-")
    importer = os.path.join(importer_dir, "some_other_script.py")
    try:
        with open(importer, "w", encoding="utf-8") as fh:
            fh.write(
                "import sys\n"
                f"sys.path.insert(0, {os.path.dirname(SCRIPT)!r})\n"
                "import log_run\n"
                "print(log_run.DEFAULT_LOGS_DIR)\n"
            )
        r = subprocess.run([sys.executable, importer], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        got = r.stdout.strip().splitlines()[-1]
        assert got == expected, (
            "imported default logs dir is argv[0]-dependent: "
            f"got {got!r}, expected {expected!r}"
        )
        # In-process import from THIS test file (argv[0] = test_log.py, another
        # script) must resolve the same default — the repo-root computation
        # itself must be right, not just symlink-safe.
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import log_run
        assert log_run.DEFAULT_LOGS_DIR == expected, (
            f"log_run.DEFAULT_LOGS_DIR is {log_run.DEFAULT_LOGS_DIR!r}, expected {expected!r} "
            "(repo-root logs/ per SKILL.md/schema.md/.gitignore/CI artifact path)"
        )
    finally:
        shutil.rmtree(importer_dir)


def main():
    tests = [
        test_complete_record_writes_one_line,
        test_missing_tokens_default_null_not_zero,
        test_missing_required_field_exits_nonzero,
        test_symlink_safe,
        test_default_logs_dir_when_imported_as_module,
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
