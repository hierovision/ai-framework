#!/usr/bin/env python3
"""Hermetic tests for scripts/stage_opencode_config.py.

Run: python3 scripts/test_stage_opencode_config.py
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import stage_opencode_config as stage  # noqa: E402
import scratch_cleanup  # noqa: E402


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    scratch_cleanup.prune_test_scratch(base)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _args(root, home, source, **overrides):
    values = {"home": home, "config_root": None, "source": source,
              "repo": REPO, "dry_run": False, "force": True,
              "no_backup": False}
    values.update(overrides)
    return argparse.Namespace(**values)


def test_stage_moves_v1_and_links_v2():
    root = _tmp("stage-config-")
    try:
        home = os.path.join(root, "home")
        target = os.path.join(home, ".config", "opencode")
        _write(os.path.join(target, "opencode.jsonc"), '{"v1": true}\n')
        _write(os.path.join(target, "service.json"), "v1-service\n")
        db_path = os.path.join(home, ".local", "share", "opencode",
                               "opencode.db")
        os.makedirs(os.path.dirname(db_path))
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
        con.execute("INSERT INTO session(id) VALUES ('ses_1')")
        con.commit()
        con.close()
        source = os.path.join(root, "source")
        _write(os.path.join(source, "opencode.jsonc"), json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["/tmp/ref/cross-repo-isolation.md"],
            "agents": {"title": {"model": {"providerID": "p",
                                           "model": "m"}}},
        }, indent=2) + "\n")
        _write(os.path.join(source, "cli.json"), '{"theme":"x"}\n')
        _write(os.path.join(source, "service.json"), "v2-service\n")
        assert stage.stage(_args(root, home, source)) == 0
        config = json.load(open(os.path.join(target, "opencode.jsonc")))
        assert config["plugins"] == [
            "./plugins/auto-compact-at-threshold",
            "./plugins/delegation-observer",
            "./plugins/delegation-sentinel",
        ], config
        assert os.path.isfile(os.path.join(target, "plugins",
                                           "delegation-observer", "model.ts"))
        assert len(os.listdir(os.path.join(target, "agents"))) == 17
        assert os.path.islink(os.path.join(target, "reference"))
        assert os.path.isdir(os.path.join(target, "skills"))
        assert open(os.path.join(target, "service.json")).read() == "v2-service\n"
        assert open(os.path.join(target, "cli.json")).read() == '{"theme":"x"}\n'
        backups = [name for name in os.listdir(os.path.join(home, ".config"))
                   if name.startswith("opencode.v1-backup-")]
        assert len(backups) == 1, backups
        backup = os.path.join(home, ".config", backups[0])
        assert json.load(open(os.path.join(backup, "opencode.jsonc")))["v1"]
        assert open(os.path.join(backup, "service.json")).read() == "v1-service\n"
        assert stat.S_IMODE(os.stat(os.path.join(
            backup, "opencode.db")).st_mode) == 0o600
        con = sqlite3.connect(os.path.join(backup, "opencode.db"))
        assert con.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1
        con.close()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stage_dry_run_is_read_only():
    root = _tmp("stage-dry-")
    try:
        home = os.path.join(root, "home")
        target = os.path.join(home, ".config", "opencode")
        _write(os.path.join(target, "opencode.jsonc"), '{"v1": true}\n')
        db_path = os.path.join(home, ".local", "share", "opencode",
                               "opencode.db")
        os.makedirs(os.path.dirname(db_path))
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
        con.execute("INSERT INTO session(id) VALUES ('ses_1')")
        con.commit()
        con.close()
        source = os.path.join(root, "source")
        _write(os.path.join(source, "opencode.jsonc"), "{}\n")
        assert stage.stage(_args(root, home, source, dry_run=True)) == 0
        assert json.load(open(os.path.join(target, "opencode.jsonc")))["v1"]
        assert not any(name.startswith("opencode.v1-backup-")
                       for name in os.listdir(os.path.join(home, ".config")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_backup_flag_is_documented_noop():
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            stage.main(["--help"])
    except SystemExit:
        pass
    assert "no-op" in out.getvalue()
    assert "--backup" in out.getvalue()


def _fake_ps(text):
    real = stage.subprocess.run
    stage.subprocess.run = lambda argv, **kwargs: subprocess.CompletedProcess(
        argv, 0, text, "")
    return real


def test_live_processes_ignores_wrapper_tee_and_orchestrator():
    """The drain gate must match process identity, not paths/arguments.

    The upgrade wrapper, its `tee` log path, and the orchestrator all contain
    the substring `opencode`; none of them is a live OpenCode session.
    """
    text = "\n".join([
        "82895 bash bash .scratch/opencode-v2/apply-2.2.7.sh",
        "83066 tee tee -a /repo/.scratch/opencode-v2/apply-2.2.7.log",
        "83067 python3 python3 scripts/opencode_upgrade.py upgrade --to 2.2.7",
        "83068 ps ps -eo pid=,comm=,args=",
    ]) + "\n"
    real = _fake_ps(text)
    try:
        assert stage.live_processes() == []
    finally:
        stage.subprocess.run = real


def test_live_processes_ignores_script_names_in_shell_arguments():
    """A grep/bash command naming a supervision script is not that script."""
    text = "\n".join([
        "84000 bash bash -c 'grep dispatch_agent.py scripts/foo'",
        "84001 grep grep -R dispatch_agent.py scripts",
        "84002 tee tee -a /tmp/opencode.log",
    ]) + "\n"
    real = _fake_ps(text)
    try:
        assert stage.live_processes() == []
    finally:
        stage.subprocess.run = real


def test_live_processes_flags_real_opencode_and_supervision():
    text = "\n".join([
        "83202 opencode.exe /repo/opencode.exe serve --service",
        "83429 opencode opencode",
        "83500 python3 python3 /repo/scripts/dispatch_agent.py --agent x",
        "83501 python3 python3 /repo/scripts/observe_completion.py",
        "83502 python3 python3 /repo/scripts/watch_agent.py",
        "83503 python3 python3 /repo/scripts/session_guard.py",
    ]) + "\n"
    real = _fake_ps(text)
    try:
        hits = stage.live_processes()
        assert len(hits) == 6, hits
        assert any("opencode.exe" in hit for hit in hits), hits
        assert any("dispatch_agent.py" in hit for hit in hits), hits
    finally:
        stage.subprocess.run = real


def test_tui_processes_excludes_service_and_supervision():
    """The supervisor waits for the TUI only: serve/--service is not a TUI."""
    text = "\n".join([
        "83202 opencode.exe /repo/opencode.exe serve --service",
        "83429 opencode opencode",
        "83430 opencode opencode --standalone",
        "83431 opencode opencode serve",
        "83500 python3 python3 /repo/scripts/dispatch_agent.py --agent x",
    ]) + "\n"
    hits = stage.parse_tui_processes(text)
    assert len(hits) == 2, hits
    assert any("83429" in hit for hit in hits), hits
    assert any("83430" in hit for hit in hits), hits
    assert not any("serve" in hit or "dispatch_agent" in hit
                   for hit in hits), hits


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
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
