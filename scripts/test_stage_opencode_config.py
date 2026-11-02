#!/usr/bin/env python3
"""Hermetic tests for scripts/stage_opencode_config.py.

Run: python3 scripts/test_stage_opencode_config.py
"""
import argparse
import json
import os
import shutil
import sqlite3
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
