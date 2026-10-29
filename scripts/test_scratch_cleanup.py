#!/usr/bin/env python3
"""Red-first tests for scripts/scratch_cleanup.py (F12 bounded scratch).

Run: python3 scripts/test_scratch_cleanup.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
DISPATCH = os.path.join(HERE, "dispatch_agent.py")
sys.path.insert(0, HERE)

import scratch_cleanup as cleanup  # noqa: E402


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _age(path, seconds):
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def test_prune_keeps_newest_and_caps_count():
    root = _tmp("scratch-prune-")
    try:
        dirs = []
        for i in range(8):
            path = os.path.join(root, f"run-{i}")
            os.makedirs(path)
            _age(path, 100 - i)  # run-7 is newest
            dirs.append(path)
        removed = cleanup.prune_run_configs(root, keep=3, max_age_seconds=10**9)
        remaining = sorted(os.listdir(root))
        assert remaining == ["run-5", "run-6", "run-7"], remaining
        assert len(removed) == 5, removed
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prune_removes_old_entries_even_below_count_cap():
    root = _tmp("scratch-prune-age-")
    try:
        old = os.path.join(root, "run-old")
        new = os.path.join(root, "run-new")
        os.makedirs(old)
        os.makedirs(new)
        _age(old, 8 * 86400)
        removed = cleanup.prune_run_configs(
            root, keep=10, max_age_seconds=7 * 86400)
        assert os.path.isdir(new), os.listdir(root)
        assert not os.path.exists(old), os.listdir(root)
        assert removed == [old], removed
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cleanup_run_config_removes_success_and_keeps_failure():
    root = _tmp("scratch-outcome-")
    try:
        ok = os.path.join(root, "ok")
        bad = os.path.join(root, "bad")
        os.makedirs(ok)
        os.makedirs(bad)
        cleanup.cleanup_run_config(ok, "success")
        cleanup.cleanup_run_config(bad, "failure")
        assert not os.path.exists(ok), os.listdir(root)
        assert os.path.isdir(bad), os.listdir(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _dispatch(mode, precreate):
    """Run dispatch_agent with an isolated config root; return (rc, entries)."""
    td = tempfile.mkdtemp(prefix="scratch-dispatch-")
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    stub = os.path.join(bin_dir, "opencode")
    with open(stub, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\n"
                 "if [ \"$1\" = \"api\" ]; then echo '{\"data\": {}}'; exit 0; fi\n"
                 "echo '{\"type\":\"step_start\",\"sessionID\":\"ses_scratch\"}'\n"
                 + ("" if mode == "valid" else "")
                 + "exit 0\n")
    os.chmod(stub, 0o755)
    prompt = os.path.join(td, "prompt.md")
    with open(prompt, "w", encoding="utf-8") as fh:
        fh.write("Do the thing.")
    cfg_root = os.path.join(td, "dispatch-config")
    os.makedirs(cfg_root)
    for i in range(precreate):
        os.makedirs(os.path.join(cfg_root, f"run-old-{i}"))
        _age(os.path.join(cfg_root, f"run-old-{i}"), 60 - i)
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["DISPATCH_CONFIG_ROOT"] = cfg_root
    env["OPENCODE_V2_NO_SERVICE"] = "1"
    env.pop("DISPATCH_KEEP_CONFIG", None)
    cmd = [sys.executable, DISPATCH, "--agent", "architect",
           "--prompt-file", prompt, "--out", os.path.join(td, "result.md"),
           "--logs-dir", os.path.join(td, "logs"), "--timeout", "10"]
    if mode == "failure":
        cmd += ["--contract", "implement-handoff"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              cwd=REPO, timeout=60)
        entries = sorted(os.listdir(cfg_root)) if os.path.isdir(cfg_root) else []
        return proc.returncode, entries
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_failed_dispatch_preserves_bounded_evidence():
    """A failure keeps its generated config for diagnosis, but the directory is
    pruned to the newest N: historical run-* dirs cannot grow without bound."""
    rc, entries = _dispatch("failure", precreate=8)
    assert rc != 0, rc
    assert len(entries) == 5, entries
    assert not any(name.startswith("run-old-0") for name in entries), entries
    assert any(name.startswith("run-old-") for name in entries), entries


def test_successful_dispatch_removes_its_run_config():
    rc, entries = _dispatch("valid", precreate=1)
    assert rc == 0, rc
    assert len(entries) == 1, entries
    assert entries[0].startswith("run-old-"), entries


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
