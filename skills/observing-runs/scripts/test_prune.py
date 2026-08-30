#!/usr/bin/env python3
"""Retention/prune tests for query_runs.py (RM-001 AC7).

Run: python3 skills/observing-runs/scripts/test_prune.py
Exit 0 = prune deletes only older daily files; --dry-run deletes nothing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPT = os.path.join(os.path.dirname(__file__), "query_runs.py")
DAY = 86400


def _run_prune(logs_dir, older_than, extra=None):
    cmd = [sys.executable, SCRIPT, "prune", "--older-than", older_than, "--logs-dir", logs_dir]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    d = tempfile.mkdtemp()
    failed = 0
    try:
        old = os.path.join(d, "run-2026-01-01.jsonl")
        new = os.path.join(d, "run-2026-12-31.jsonl")
        for p in (old, new):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": "x", "run_id": "y", "kind": "eval",
                                     "outcome": "success", "eval_pass": True}) + "\n")
        now = time.time()
        os.utime(old, (now - 40 * DAY, now - 40 * DAY))
        os.utime(new, (now, now))

        # --dry-run: keeps both
        r = _run_prune(d, "30d", ["--dry-run"])
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout.strip())
        assert out["removed"] == 0 and out["kept"] == 2, out
        assert os.path.exists(old) and os.path.exists(new)
        print("PASS  dry-run removes nothing")

        # real prune: removes only the old file
        r = _run_prune(d, "30d")
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout.strip())
        assert out["removed"] == 1 and out["kept"] == 1, out
        assert not os.path.exists(old), "old file should be deleted"
        assert os.path.exists(new), "new file must be kept"
        print("PASS  prune deletes only older file")

        # --archive: gzips the (remaining old) file instead of deleting
        old2 = os.path.join(d, "run-2026-02-01.jsonl")
        with open(old2, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "eval", "outcome": "success", "eval_pass": True}) + "\n")
        os.utime(old2, (now - 60 * DAY, now - 60 * DAY))
        r = _run_prune(d, "30d", ["--archive"])
        assert r.returncode == 0, r.stderr
        assert not os.path.exists(old2)
        assert os.path.exists(os.path.join(d, "archive", "run-2026-02-01.jsonl.gz"))
        print("PASS  --archive gzips to logs/archive/")
    except AssertionError as e:
        failed += 1
        print(f"FAIL  {e}")
    finally:
        shutil.rmtree(d)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
