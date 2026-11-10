#!/usr/bin/env python3
"""Hermetic tests for the supported-path upgrade helper.

Covers: offline pin seams, prepare dry-run/real update, the plan matrix +
breaking notes, the supported topology, the canary evidence gate, apply
consent + post-smoke failure, the canary argv, resume, prune, and the official
PR body. The live `opencode upgrade` itself is owner-run.

Run: python3 scripts/test_opencode_upgrade.py
"""
import argparse
import builtins
import contextlib
import glob
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

import opencode_upgrade as upgrade  # noqa: E402
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


def _evidence(repo, version=None, residual=0, omit=()):
    version = version or v2.VERSION_PIN
    root = os.path.join(repo, ".scratch", "v2-canary-" + version)
    for name, filename in (("C1", "C1.txt"), ("C2", "C2.txt"),
                           ("C3", "C3-real.txt"), ("C4", "C4.txt"),
                           ("C5", "C5.txt"), ("C6", "C6.txt"),
                           ("C7", "C7.txt"), ("C8", "C8.txt")):
        if name in omit:
            continue
        _write(os.path.join(root, filename), f"{name}=PASS\n")
    _write(os.path.join(root, "migration-rehearsal.txt"), "\n".join([
        f"source_sessions_not_migrated={residual}",
        "target_only_ids=0",
        "zero_migration=False",
        "target_integrity_check=ok",
        "source_untouched=True",
        "migration=PASS" if residual == 0 else "migration=FAIL",
    ]) + "\n")


def _fixture(repo, version=None, opentui="0.8.1"):
    version = version or v2.VERSION_PIN
    _write(os.path.join(repo, "scripts", "opencode_v2.py"),
           f'VERSION_PIN = "{version}"\n')
    _write(os.path.join(repo, "README.md"), (
        f"Requires **OpenCode V2 `{version}`** (package "
        f"`@opencode/cli@{version}`; exact pin,\nno `latest`, no caret range). "
        f"`opencode --version` prints `opencode v{version}`.\n"))
    _write(os.path.join(repo, "reference", "opencode-integration.md"), (
        f"**Behavioral facts validated against opencode `2.1.4`; the\n"
        f"`{version}` upgrade passed the canary on 2026-11-02** (evidence "
        f"under\n`.scratch/v2-canary-{version}/`).\n\n"
        f"- Package: `@opencode/cli@{version}` (never `latest`).\n"
        f"- `opencode --version` prints `opencode v{version}` (the exact "
        f"string is\n  `opencode v{version}`).\n"
        f"- `@opencode/plugin@{version}` is the matching runtime package.\n"
        f"- **TUI plugin context.** `@opencode/plugin@2.1.4`'s `./tui`\n"))
    _write(os.path.join(repo, "plugins", "auto-compact-at-threshold",
                        "package.json"), json.dumps({
        "name": "auto-compact-at-threshold", "version": version,
        "dependencies": {"@opencode/plugin": version}}, indent=2) + "\n")
    for name in ("delegation-observer", "delegation-sentinel"):
        _write(os.path.join(repo, "plugins", name, "package.json"),
               json.dumps({
                   "name": name, "version": version,
                   "peerDependencies": {
                       "@opencode/plugin": version,
                       "@opentui/core": opentui,
                       "@opentui/solid": opentui,
                       "solid-js": "1.9.12"}}, indent=2) + "\n")
    _write(os.path.join(repo, "plugins", "delegation-observer", "README.md"), (
        f"1. `@opencode/plugin`\n   {version}, `solid-js` 1.9.12 and "
        f"`@opentui/core`/`solid` {opentui} are declared as\n"))
    _write(os.path.join(repo, "plugins", "delegation-sentinel", "README.md"), (
        f"(`@opencode/plugin` {version}, `solid-js` 1.9.12, "
        f"`@opentui/core`/`solid` {opentui})\n"))
    _write(os.path.join(repo, "docs", "ADRs",
                        "ADR-0014-opencode-v2-upgrade.md"), (
        f"**2026-11-02 amendment — version pin {version}.** canary C1–C8 "
        f"PASS; residual 0.\n"))
    _evidence(repo, version)


def _args(repo, **overrides):
    values = {
        "repo": repo, "home": None, "link": None, "to": None,
        "prefix": None, "v1_bin": None, "default_bin": None,
        "plugin_json": None, "releases_file": None, "opentui": None,
        "latest": None, "refresh": False, "remote": False, "pins_only": True,
        "pr": False, "json": False, "dry_run": False, "open_pr": False,
        "skip_install": False, "skip_canary": False,
        "allow_pending_canary": False, "stop_service": False,
        "tui_timeout": 20, "force": False, "resume": False, "apply": False,
        "keep": 1, "method": "yarn", "drain_acknowledged": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _stub_binary(path, version, config_root=None):
    """A tiny executable that answers `--version` and `debug paths config`.

    Models the real binaries: V1 (major 1) prints a bare `1.19.4`; V2 prints
    `opencode v2.2.6`.
    """
    output = (version if version.split(".", 1)[0] == "1"
              else f"opencode v{version}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "#!/bin/sh",
        f'if [ "$1" = "--version" ]; then echo "{output}"; exit 0; fi',
    ]
    if config_root:
        lines.append(
            'if [ "$1" = "debug" ] && [ "$2" = "paths" ] && '
            f'[ "$3" = "config" ]; then echo "{config_root}"; exit 0; fi')
    lines.append("exit 1")
    _write(path, "\n".join(lines) + "\n")
    os.chmod(path, 0o755)


def _shadow_home(root, target, *, default_version="1.19.4",
                 binary_version=None, package_version=None,
                 write_binary=True, opencode2=True, config_root=None,
                 default_config=None):
    """Fake HOME with the yarn-global V2 package, optional opencode2, and a
    default `opencode` link that reports `default_version`."""
    binary_version = binary_version or target
    home = os.path.join(root, "home")
    yarn_bin = os.path.join(home, ".yarn", "bin")
    config = config_root if config_root is not None else os.path.join(
        home, ".config", "opencode")
    os.makedirs(config, exist_ok=True)
    package_dir = os.path.join(home, ".config", "yarn", "global",
                               "node_modules", "@opencode", "cli")
    package_bin = os.path.join(package_dir, "bin", "opencode.exe")
    if write_binary:
        _stub_binary(package_bin, binary_version, config)
    if package_version is not None:
        _write(os.path.join(package_dir, "package.json"), json.dumps({
            "name": "@opencode/cli", "version": package_version}) + "\n")
    link2 = os.path.join(yarn_bin, "opencode2")
    if opencode2 and write_binary:
        os.makedirs(yarn_bin, exist_ok=True)
        if os.path.lexists(link2):
            os.unlink(link2)
        os.symlink(package_bin, link2)
    link = os.path.join(yarn_bin, "opencode")
    if default_version is not None:
        if default_config is None and default_version == binary_version:
            default_config = config
        _stub_binary(link, default_version, default_config)
    return {"home": home, "link": link, "link2": link2, "config": config,
            "package_dir": package_dir, "package_bin": package_bin,
            "yarn_bin": yarn_bin}


def _v1_only_home(root, default_version="1.19.4"):
    """Fake HOME before the V2 package exists: only the V1 package + link."""
    home = os.path.join(root, "home")
    yarn_bin = os.path.join(home, ".yarn", "bin")
    link = os.path.join(yarn_bin, "opencode")
    v1_dir = os.path.join(home, ".config", "yarn", "global", "node_modules",
                          "opencode-ai")
    v1_bin = os.path.join(v1_dir, "bin", "opencode.exe")
    _stub_binary(v1_bin, default_version)
    _write(os.path.join(v1_dir, "package.json"), json.dumps({
        "name": "opencode-ai", "version": default_version}) + "\n")
    os.makedirs(yarn_bin, exist_ok=True)
    if os.path.lexists(link):
        os.unlink(link)
    os.symlink(v1_bin, link)
    config = os.path.join(home, ".config", "opencode")
    os.makedirs(config, exist_ok=True)
    package_dir = os.path.join(home, ".config", "yarn", "global",
                               "node_modules", "@opencode", "cli")
    return {"home": home, "link": link, "v1_bin": v1_bin,
            "link2": os.path.join(yarn_bin, "opencode2"), "config": config,
            "package_dir": package_dir,
            "package_bin": os.path.join(package_dir, "bin", "opencode.exe"),
            "yarn_bin": yarn_bin}


def _yarn_relink_stub(fixture, target, calls):
    """Official-install stub: installs V2, then Yarn links opencode2 to V2 but
    leaves the default `opencode` on the retained V1 package."""
    def install(_args, _target, _command=None):
        calls.append("install")
        _stub_binary(fixture["package_bin"], target, fixture["config"])
        _write(os.path.join(fixture["package_dir"], "package.json"), json.dumps({
            "name": "@opencode/cli", "version": target}) + "\n")
        if os.path.lexists(fixture["link2"]):
            os.unlink(fixture["link2"])
        os.symlink(fixture["package_bin"], fixture["link2"])
        v1_bin = fixture.get("v1_bin") or os.path.join(
            fixture["home"], ".config", "yarn", "global", "node_modules",
            "opencode-ai", "bin", "opencode.exe")
        _stub_binary(v1_bin, "1.19.4")
        if os.path.lexists(fixture["link"]):
            os.unlink(fixture["link"])
        os.symlink(v1_bin, fixture["link"])
        return 0
    return install


def _smoke_recorder(calls, ok=True):
    def smoke(_args, _target, command=None):
        calls.append({"event": "smoke", "command": command,
                      "version": upgrade.version_of(command)
                      if command else None})
        return [("binary", ok, "ok" if ok else "forced failure")]
    return smoke


def _patch_apply(backup, smoke, install=None):
    real = (upgrade.pre_upgrade_backup, upgrade.official_upgrade,
            upgrade.post_upgrade_smoke, upgrade.stage_config.live_processes)
    upgrade.pre_upgrade_backup = lambda a, t: (
        backup, os.path.join(backup, "db"))
    upgrade.official_upgrade = install or (lambda a, t, command=None: 0)
    upgrade.post_upgrade_smoke = smoke
    upgrade.stage_config.live_processes = lambda: []
    return real


def _restore_apply(real):
    (upgrade.pre_upgrade_backup, upgrade.official_upgrade,
     upgrade.post_upgrade_smoke, upgrade.stage_config.live_processes) = real


@contextlib.contextmanager
def _path_front(directory):
    real = os.environ.get("PATH", "")
    os.environ["PATH"] = directory + os.pathsep + real
    try:
        yield
    finally:
        os.environ["PATH"] = real


def _artifact(root, target):
    return os.path.join(root, ".scratch", "opencode-v2",
                        f"upgrade-{target}-verify.json")


def test_check_pins_clean_and_stale():
    root = _tmp("upgrade-pins-")
    try:
        _fixture(root)
        results = upgrade.check_seams(root, v2.VERSION_PIN, "0.8.1")
        assert all(ok for _path, ok, _detail in results), results
        _write(os.path.join(root, "scripts", "opencode_v2.py"),
               'VERSION_PIN = "2.2.4"\n')
        results = upgrade.check_seams(root, v2.VERSION_PIN, "0.8.1")
        assert any(not ok and path.endswith("opencode_v2.py")
                   for path, ok, _detail in results), results
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _json_file(root, payload, name="fixture.json"):
    path = os.path.join(root, name)
    _write(path, json.dumps(payload))
    return path


def test_prepare_dry_run_and_update():
    root = _tmp("upgrade-prepare-")
    real_run = upgrade.run
    try:
        _fixture(root)
        _evidence(root, "2.3.0")
        before = open(os.path.join(root, "README.md")).read()
        upgrade.run = lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 0 if argv[:2] == ["npm", "install"] else 1, "", "")
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        args = _args(root, to="2.3.0", opentui="0.8.2", plugin_json=peers)
        with contextlib.redirect_stdout(io.StringIO()):
            assert upgrade.prepare(_args(**{**vars(args), "dry_run": True})) == 0
        assert open(os.path.join(root, "README.md")).read() == before
        with contextlib.redirect_stdout(io.StringIO()):
            assert upgrade.prepare(args) == 0
        text = open(os.path.join(root, "README.md")).read()
        assert "OpenCode V2 `2.3.0`" in text, text
        assert v2.VERSION_PIN not in text, text
        results = upgrade.check_seams(root, "2.3.0", "0.8.2")
        assert all(ok for _path, ok, _detail in results), results
        assert "version pin 2.3.0" in open(os.path.join(
            root, "docs", "ADRs", "ADR-0014-opencode-v2-upgrade.md")).read()
        assert upgrade.seam_changes(root, "2.3.0", "0.8.2") == []
    finally:
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_plan_matrix_and_breaking_notes():
    root = _tmp("upgrade-plan-")
    try:
        _fixture(root)
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        releases = _json_file(root, [{
            "tag_name": "v2.3.0",
            "body": "### Breaking changes\n#### Plugin API\n- change A\n"
                    "### Core\n- unrelated\n"}], "releases.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = upgrade.plan(_args(root, to="2.3.0", opentui="0.8.2",
                                    plugin_json=peers,
                                    releases_file=releases, json=True))
        assert rc == 0
        data = json.loads(out.getvalue())
        assert data["target"] == "2.3.0"
        matrix = {row[0]: row for row in data["matrix"]}
        assert matrix["CLI"][1:] == [v2.VERSION_PIN, "2.3.0"]
        assert matrix["@opentui/core"][2] == "0.8.2"
        assert data["breaking"][0][0] == "2.3.0"
        assert "change A" in data["breaking"][0][1]
        assert data["seams"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_status_supported_topology():
    root = _tmp("upgrade-status-")
    try:
        _fixture(root)
        home = os.path.join(root, "home")
        config = os.path.join(home, ".config", "opencode")
        os.makedirs(config)
        link = os.path.join(home, ".yarn", "bin", "opencode")
        _write(link, (
            "#!/bin/sh\n"
            f"if [ \"$1\" = \"--version\" ]; then echo 'opencode v{v2.VERSION_PIN}'; exit 0; fi\n"
            f"if [ \"$1\" = \"debug\" ]; then echo '{config}'; exit 0; fi\n"
            "exit 1\n"))
        os.chmod(link, 0o755)
        upgrade.write_state(root, v2.VERSION_PIN, "canaried")
        payload = upgrade.status_payload(_args(root, home=home))
        assert payload["pinned"] == v2.VERSION_PIN
        assert payload["live"] == v2.VERSION_PIN
        assert payload["install"]["supported"] is True
        assert payload["install"]["config_root"] == config
        assert payload["next"] == "up to date", payload["next"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_write_state_never_regresses():
    root = _tmp("upgrade-state-")
    try:
        upgrade.write_state(root, "2.2.5", "applied")
        upgrade.write_state(root, "2.2.5", "canaried")
        assert upgrade.read_state(root)["stage"] == "applied"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_pr_requires_canary():
    root = _tmp("upgrade-pr-")
    try:
        _fixture(root)
        with contextlib.redirect_stdout(io.StringIO()):
            assert upgrade.check(_args(root, pr=True)) == 0
        _write(os.path.join(root, ".scratch", f"v2-canary-{v2.VERSION_PIN}", "C4.txt"),
               "C4=FAIL\n")
        assert upgrade.check(_args(root, pr=True)) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_requires_consent_and_post_smoke_failure():
    root = _tmp("upgrade-apply-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, lambda a, t, command=None: [
        ("binary", False, "forced failure")])
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True)
        assert upgrade.apply_supported(args, target) == 2
        args.drain_acknowledged = True
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.apply_supported(args, target)
        assert rc == 1, out.getvalue()
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is False
        assert data["rolled_back"] is False
        assert "rollback:" in out.getvalue()
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_apply_repairs_yarn_relink_before_smoke():
    root = _tmp("upgrade-relink-")
    target = v2.VERSION_PIN
    fixture = _v1_only_home(root)
    calls = []
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, _smoke_recorder(calls),
                        _yarn_relink_stub(fixture, target, calls))
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = upgrade.apply_supported(args, target)
        assert rc == 0
        assert "install" in calls, calls
        smoke = [row for row in calls if isinstance(row, dict)]
        assert len(smoke) == 1, calls
        assert smoke[0]["version"] == target, smoke
        assert os.path.realpath(fixture["link"]) == os.path.realpath(
            fixture["package_bin"])
        assert json.load(open(_artifact(root, target)))["verified"] is True
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_apply_reuses_installed_target_and_repairs_default():
    root = _tmp("upgrade-reuse-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    calls = []
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t, command=None: calls.append("install") or 0)
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = upgrade.apply_supported(args, target)
        assert rc == 0
        assert "install" not in calls, calls
        smoke = [row for row in calls if isinstance(row, dict)]
        assert len(smoke) == 1, calls
        assert smoke[0]["version"] == target, smoke
        assert upgrade.read_state(root)["stage"] == "applied"
        assert os.path.realpath(fixture["link"]) == os.path.realpath(
            fixture["package_bin"])
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_apply_v1_default_failure_has_v1_rollback():
    root = _tmp("upgrade-v1-rollback-")
    target = v2.VERSION_PIN
    fixture = _v1_only_home(root)
    v1_backup = os.path.join(fixture["home"], ".config",
                             "opencode.v1-backup-20261101T000000Z")
    _write(os.path.join(v1_backup, "opencode.db"), "v1-db\n")
    calls = []
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, _smoke_recorder(calls, ok=False),
                        _yarn_relink_stub(fixture, target, calls))
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.apply_supported(args, target)
        assert rc == 1, out.getvalue()
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is False
        assert data["rolled_back"] is False
        assert data["failure_stage"] == "binary"
        prev = data["previous_default"]
        assert prev["path"] == fixture["link"]
        assert prev["target"] == fixture["v1_bin"]
        assert prev["resolved"] == os.path.realpath(fixture["v1_bin"])
        assert prev["version"] == "1.19.4"
        assert prev["kind"] == "v1"
        rollback = data["rollback"]
        assert rollback["kind"] == "v1"
        assert rollback["previous_default"] == prev
        assert any(fixture["v1_bin"] in command
                   for command in rollback["commands"]), rollback["commands"]
        assert "1.19.4" in rollback["guidance"]
        assert "opencode-ai" in rollback["guidance"]
        assert rollback["v1_backup"]["root"] == v1_backup
        assert v1_backup in rollback["guidance"]
        assert os.path.join(v1_backup, "opencode.db") in rollback["guidance"]
        assert "V2-era" in rollback["guidance"]
        assert "upgrade 1.19.4 --method yarn" not in json.dumps(data)
        assert "rollback: " in out.getvalue()
        v2_plan = upgrade.rollback_plan(
            fixture["link"], {"version": target, "kind": "v2"}, backup, "yarn")
        assert v2_plan["kind"] == "v2"
        assert v2_plan["commands"] == [
            f"{fixture['link']} upgrade {target} --method yarn"]
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_plan_unknown_previous():
    link = "/tmp/nowhere/.yarn/bin/opencode"
    backup = "/tmp/nowhere/backup"
    missing = {"path": link, "target": None, "resolved": None,
               "version": None, "kind": None, "exists": False}
    plan = upgrade.rollback_plan(link, missing, backup, "yarn")
    assert plan["kind"] == "unknown"
    assert plan["commands"] == []
    assert "missing or unclassifiable" in plan["guidance"]
    assert "V1" not in plan["guidance"]
    assert "V2" not in plan["guidance"]
    assert "upgrade " not in plan["guidance"]


def test_rollback_plan_v1_without_backup_is_truthful():
    root = _tmp("upgrade-v1-nobackup-")
    home = os.path.join(root, "home")
    link = os.path.join(home, ".yarn", "bin", "opencode")
    backup = os.path.join(root, "pre-upgrade")
    try:
        plan = upgrade.rollback_plan(
            link, {"version": "1.19.4", "kind": "v1", "target": None,
                   "resolved": None}, backup, "yarn", home=home)
        assert plan["kind"] == "v1"
        assert plan["v1_backup"] is None
        assert "no V1 config/DB backup" in plan["guidance"]
        assert "contains no config/DB copy" in plan["guidance"]
        assert "upgrade 1.19.4 --method yarn" not in plan["guidance"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_dry_run_text_truthful():
    target = v2.VERSION_PIN
    real_live = upgrade.stage_config.live_processes
    upgrade.stage_config.live_processes = lambda: []
    absent_root = _tmp("upgrade-dryrun-absent-")
    present_root = _tmp("upgrade-dryrun-present-")
    try:
        absent = _v1_only_home(absent_root)
        args = _args(absent_root, to=target, home=absent["home"],
                     skip_canary=True, drain_acknowledged=True, dry_run=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 0
        text = out.getvalue()
        assert f"would install {target} via the official command" in text, text
        assert "would run the post-upgrade smoke" in text, text
        assert f"would write {_artifact(absent_root, target)}" in text, text
        absent_order = [
            "would check the drain gate",
            "would back up any existing DB/config",
            f"would install {target} via the official command",
            f"would repair the default {absent['link']} shadow",
            "would run the post-upgrade smoke",
            f"would write {_artifact(absent_root, target)}",
        ]
        positions = [text.index(item) for item in absent_order]
        assert positions == sorted(positions), positions

        present = _shadow_home(present_root, target, package_version=target)
        args = _args(present_root, to=target, home=present["home"],
                     skip_canary=True, drain_acknowledged=True, dry_run=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 0
        text = out.getvalue()
        assert (f"would reuse the installed {target} V2 package") in text, text
        assert f"would repair the default {present['link']} shadow" in text, text
        assert "would run the post-upgrade smoke" in text, text
        assert f"would write {_artifact(present_root, target)}" in text, text
        present_order = [
            "would check the drain gate",
            "would back up any existing DB/config",
            f"would reuse the installed {target} V2 package",
            f"would repair the default {present['link']} shadow",
            "would run the post-upgrade smoke",
            f"would write {_artifact(present_root, target)}",
        ]
        positions = [text.index(item) for item in present_order]
        assert positions == sorted(positions), positions
    finally:
        upgrade.stage_config.live_processes = real_live
        shutil.rmtree(absent_root, ignore_errors=True)
        shutil.rmtree(present_root, ignore_errors=True)


def test_upgrade_repairs_when_default_is_v1():
    root = _tmp("upgrade-e2e-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    calls = []
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t, command=None: calls.append("install") or 0)
    try:
        args = _args(root, to=target, home=fixture["home"], apply=True,
                     skip_canary=True, drain_acknowledged=True)
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = upgrade.upgrade(args)
        assert rc == 0
        assert "install" not in calls, calls
        smoke = [row for row in calls if isinstance(row, dict)]
        assert len(smoke) == 1, calls
        assert upgrade.read_state(root)["stage"] == "applied"
        assert os.path.realpath(fixture["link"]) == os.path.realpath(
            fixture["package_bin"])
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_without_apply_prints_repair_for_v1_default():
    target = v2.VERSION_PIN
    repair_root = _tmp("upgrade-noapply-repair-")
    try:
        fixture = _shadow_home(repair_root, target, package_version=target)
        _evidence(repair_root, target)
        args = _args(repair_root, to=target, home=fixture["home"])
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.upgrade(args)
        assert rc == 0, out.getvalue()
        assert ("shadow repair needed: python3 scripts/opencode_upgrade.py "
                f"upgrade --to {target} --apply --drain-acknowledged"
                ) in out.getvalue(), out.getvalue()
        assert "stage_opencode_config.py" not in out.getvalue()
    finally:
        shutil.rmtree(repair_root, ignore_errors=True)

    migrate_root = _tmp("upgrade-noapply-migrate-")
    try:
        fixture = _shadow_home(migrate_root, target, write_binary=False,
                               package_version=None, opencode2=False)
        args = _args(migrate_root, to=target, home=fixture["home"])
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.upgrade(args)
        assert rc == 2, out.getvalue()
        assert "stage_opencode_config.py" in out.getvalue()
        assert "shadow repair needed" not in out.getvalue()
    finally:
        shutil.rmtree(migrate_root, ignore_errors=True)

    verify_root = _tmp("upgrade-noapply-verify-")
    try:
        fixture = _shadow_home(verify_root, target, default_version=target,
                               package_version=target)
        _evidence(verify_root, target)
        _write(_artifact(verify_root, target), json.dumps({
            "version": target, "verified": False, "rolled_back": False}) + "\n")
        args = _args(verify_root, to=target, home=fixture["home"])
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.upgrade(args)
        assert rc == 0, out.getvalue()
        assert ("verification needed: python3 scripts/opencode_upgrade.py "
                f"upgrade --to {target} --apply --drain-acknowledged"
                ) in out.getvalue(), out.getvalue()
        assert "shadow repair needed" not in out.getvalue()
    finally:
        shutil.rmtree(verify_root, ignore_errors=True)


def test_apply_failure_is_not_reported_as_rolled_back():
    root = _tmp("upgrade-truthful-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, lambda a, t, command=None: [
        ("binary", False, "forced failure")])
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.apply_supported(args, target)
        assert rc == 1, out.getvalue()
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is False
        assert data["rolled_back"] is False
        assert data["failure_stage"] == "binary"
        assert data["target_package"]["version"] == target
        assert data["target_package"]["path"].endswith(
            os.path.join("node_modules", "@opencode", "cli"))
        assert data["default_link"]["path"] == fixture["link"]
        assert data["default_link"]["version"] == target
        assert data["backup"] == backup
        assert upgrade.read_state(root)["stage"] == "prepared"
        assert "rollback:" in out.getvalue()
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_failed_reapply_regresses_applied_to_prepared():
    root = _tmp("upgrade-force-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, default_version=target,
                           package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, lambda a, t, command=None: [
        ("binary", False, "forced failure")])
    try:
        upgrade.write_state(root, target, "applied")
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = upgrade.apply_supported(args, target)
        assert rc == 1
        assert upgrade.read_state(root)["stage"] == "prepared"
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_shadow_repair_refuses_missing_or_wrong_target():
    target = v2.VERSION_PIN
    for case in ("missing", "wrong"):
        root = _tmp("upgrade-shadow-refuse-")
        if case == "missing":
            fixture = _shadow_home(root, target, write_binary=False,
                                   package_version=None, opencode2=False)
        else:
            fixture = _shadow_home(root, target, binary_version="2.2.5",
                                   package_version="2.2.5")
        backup = os.path.join(root, "backup")
        os.makedirs(backup)
        calls = []
        real = _patch_apply(backup, _smoke_recorder(calls),
                            lambda a, t, command=None: calls.append("install") or 0)
        try:
            args = _args(root, to=target, home=fixture["home"],
                         skip_canary=True, drain_acknowledged=True)
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                rc = upgrade.apply_supported(args, target)
            assert rc == 1, case
            assert not any(isinstance(row, dict) for row in calls), calls
            assert upgrade.version_of(fixture["link"]) != target, case
            data = json.load(open(_artifact(root, target)))
            assert data["verified"] is False, case
            assert data["failure_stage"] == "target-binary", case
            assert data["version"] == target, case
            assert data["target_package"]["requested"] == target, case
            if case == "missing":
                assert data["target_package"]["version"] is None, case
            else:
                assert data["target_package"]["version"] == "2.2.5", case
        finally:
            _restore_apply(real)
            shutil.rmtree(root, ignore_errors=True)


def test_shadow_repair_requires_supported_config_root():
    root = _tmp("upgrade-shadow-config-")
    target = v2.VERSION_PIN
    wrong_config = os.path.join(root, "elsewhere", "opencode")
    os.makedirs(wrong_config)
    fixture = _shadow_home(root, target, package_version=target,
                           config_root=wrong_config)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    calls = []
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t, command=None: calls.append("install") or 0)
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            rc = upgrade.apply_supported(args, target)
        assert rc == 1
        assert not any(isinstance(row, dict) for row in calls), calls
        assert upgrade.version_of(fixture["link"]) != target
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is False
        assert data["failure_stage"] == "config-root"
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_status_detects_shadow_mismatch_and_next_repair():
    root = _tmp("upgrade-status-shadow-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    _evidence(root, target)
    try:
        with _path_front(fixture["yarn_bin"]):
            payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["target_installed"] == target
        assert payload["default_version"] == "1.19.4"
        assert payload["shadow_ok"] is False
        assert payload["next"] == (
            "python3 scripts/opencode_upgrade.py upgrade --to " + target
            + " --apply --drain-acknowledged")
        assert "stage_opencode_config.py" not in payload["next"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_status_unsupported_config_uses_migration_guidance():
    root = _tmp("upgrade-status-config-")
    target = v2.VERSION_PIN
    wrong_config = os.path.join(root, "elsewhere", "opencode")
    os.makedirs(wrong_config)
    fixture = _shadow_home(root, target, package_version=target,
                           config_root=wrong_config)
    try:
        with _path_front(fixture["yarn_bin"]):
            payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["target_installed"] == target
        assert payload["shadow"]["supported_config"] is False
        assert payload["shadow_ok"] is False
        assert "stage_opencode_config.py" in payload["next"]
        assert "upgrade --to" not in payload["next"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_status_names_recorded_target_for_resume():
    root = _tmp("upgrade-status-resume-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, default_version=target,
                           package_version=target)
    _evidence(root, target)
    try:
        upgrade.write_state(root, "2.3.0", "canaried")
        with _path_front(fixture["yarn_bin"]):
            payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["next"] == (
            "python3 scripts/opencode_upgrade.py upgrade --to 2.3.0 --resume")
        # A legacy rolled-back stage is not resumable.
        upgrade.write_state(root, "2.3.0", "rolled-back")
        with _path_front(fixture["yarn_bin"]):
            payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["next"] == "up to date", payload["next"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_doctor_fails_on_shadow_mismatch():
    root = _tmp("upgrade-doctor-shadow-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out):
            rc = upgrade.doctor(_args(root, home=fixture["home"]))
        assert rc == 1
        assert "shadow: FAIL" in out.getvalue(), out.getvalue()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_docs_describe_supported_shadow():
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    reference = open(os.path.join(
        REPO, "reference", "opencode-integration.md"), encoding="utf-8").read()
    adr = open(os.path.join(
        REPO, "docs", "ADRs",
        "ADR-0017-supported-opencode-upgrade.md"), encoding="utf-8").read()
    adr14 = open(os.path.join(
        REPO, "docs", "ADRs",
        "ADR-0014-opencode-v2-upgrade.md"), encoding="utf-8").read()
    for text, name in ((readme, "README"), (reference, "reference"),
                       (adr, "ADR-0017")):
        assert "opencode2" in text, name
        assert "shadow" in text, name
        assert "upgrade --to <pin>" in text, name
        assert "--apply" in text, name
        assert "rolls back link + DB" not in text, name
    assert not re.search(r"upgrade --to \d+\.\d+\.\d+", readme)
    assert "verify.json.failed-" in readme
    assert "verify.json.previous-" in readme
    assert "both packages publish" in reference or "dual-bin" in reference
    assert "local/manual" in reference and "CI runs only" in reference
    assert "2026-11-09" in adr
    assert "not an automatic rollback" in adr or "no automatic" in adr
    assert "rolls back link + DB" not in adr14
    assert "opencode_upgrade.py apply" not in adr14
    assert "~/.scratch/opencode-v2" not in readme
    assert '"$PWD"/.scratch/opencode-v2' in readme


def test_prune_keeps_versions():
    root = _tmp("upgrade-prune-")
    try:
        for name in ("v2-1.0.0-prefix", "v2-canary-1.0.0",
                     "v2-2.0.0-prefix", "v2-canary-2.0.0",
                     "plugin-compat-2.0.0"):
            os.makedirs(os.path.join(root, ".scratch", name))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert upgrade.prune(_args(root, keep=1, dry_run=True)) == 0
        text = out.getvalue()
        assert "1.0.0" in text and "would remove" in text, text
        assert "v2-2.0.0-prefix" not in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gh_env_and_pr_body():
    env = upgrade.gh_env()
    assert env["GH_CONFIG_DIR"].endswith("/.config/gh"), env
    body = upgrade.pr_body("2.3.0", "0.8.2", {
        "gates": {"C1": "PASS", "C8": "PASS"}, "residual": 0},
        [("2.3.0", "- breaking")])
    assert "2.3.0" in body and "C1=PASS" in body
    assert "upgrade --to 2.3.0" in body


def test_canary_cmd_exact_args():
    root = _tmp("upgrade-canary-")
    try:
        _fixture(root)
        v1 = os.path.join(root, "v1", "opencode")
        _write(v1, "#!/bin/sh\necho 1.19.4\n")
        os.chmod(v1, 0o755)
        default = os.path.join(root, "default")
        _stub_binary(default, "2.2.5")
        args = _args(root, to=v2.VERSION_PIN, v1_bin=v1,
                     default_bin=default)
        argv = upgrade.canary_cmd(args, v2.VERSION_PIN)
        assert "--all" in argv and "--version" in argv, argv
        assert argv[argv.index("--version") + 1] == v2.VERSION_PIN
        assert argv[argv.index("--default-version") + 1] == "2.2.5"
        assert argv[argv.index("--default-bin") + 1] == default
        assert "--skip-install" in argv
        assert f"v2-canary-{v2.VERSION_PIN}" in " ".join(argv)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_cmd_measures_v1_default():
    root = _tmp("upgrade-canary-v1-")
    try:
        default = os.path.join(root, "default")
        _stub_binary(default, "1.19.4")
        args = _args(root, to=v2.VERSION_PIN, default_bin=default)
        argv = upgrade.canary_cmd(args, v2.VERSION_PIN)
        assert argv[argv.index("--default-version") + 1] == "1.19.4"
        assert argv[argv.index("--default-bin") + 1] == default
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_cmd_measures_prior_v2_default():
    root = _tmp("upgrade-canary-prior-v2-")
    try:
        default = os.path.join(root, "default")
        _stub_binary(default, "2.2.5")
        args = _args(root, to=v2.VERSION_PIN, default_bin=default)
        argv = upgrade.canary_cmd(args, v2.VERSION_PIN)
        assert argv[argv.index("--default-version") + 1] == "2.2.5"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_cmd_fails_closed_on_unmeasurable_default():
    root = _tmp("upgrade-canary-unmeasurable-")
    try:
        missing = os.path.join(root, "missing")
        args = _args(root, to=v2.VERSION_PIN, default_bin=missing)
        try:
            upgrade.canary_cmd(args, v2.VERSION_PIN)
            assert False, "missing default must fail closed"
        except RuntimeError as exc:
            assert "cannot measure default binary" in str(exc), exc
        garbage = os.path.join(root, "garbage")
        _write(garbage, "#!/bin/sh\necho 'not a version'\n")
        os.chmod(garbage, 0o755)
        args.default_bin = garbage
        try:
            upgrade.canary_cmd(args, v2.VERSION_PIN)
            assert False, "unparseable default must fail closed"
        except RuntimeError as exc:
            assert "cannot parse default binary version" in str(exc), exc
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_fails_closed_before_install_when_default_unmeasurable():
    root = _tmp("upgrade-canary-preinstall-")
    try:
        args = _args(root, to=v2.VERSION_PIN,
                     default_bin=os.path.join(root, "missing"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.canary(args) == 1
        assert "cannot measure default binary" in out.getvalue()
        assert not os.path.isdir(os.path.join(
            root, ".scratch", "v2-" + v2.VERSION_PIN + "-prefix"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_resume_skips_completed_stages():
    root = _tmp("upgrade-resume-")
    real = (upgrade.plan, upgrade.canary, upgrade.prepare,
            upgrade.topology, upgrade.version_of)
    calls = []
    try:
        _fixture(root)
        upgrade.write_state(root, "2.3.0", "canaried")
        upgrade.plan = lambda args: calls.append("plan") or 0
        upgrade.canary = lambda args: calls.append("canary") or 0
        upgrade.prepare = lambda args: calls.append("prepare") or 0
        upgrade.topology = lambda home, link: {
            "supported": True, "command": "opencode"}
        upgrade.version_of = lambda binary: "2.2.5"
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        args = _args(root, to="2.3.0", resume=True, opentui="0.8.2",
                     plugin_json=peers)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = upgrade.upgrade(args)
        assert rc == 0
        assert calls == ["prepare"], calls
    finally:
        (upgrade.plan, upgrade.canary, upgrade.prepare,
         upgrade.topology, upgrade.version_of) = real
        shutil.rmtree(root, ignore_errors=True)


def test_ci_pin_is_derived_from_adapter():
    for rel in (".github/workflows/eval-behavioral.yml",
                ".github/workflows/eval-per-change.yml"):
        text = open(os.path.join(REPO, rel), encoding="utf-8").read()
        assert "print(opencode_v2.VERSION_PIN)" in text, rel
        assert 'OPENCODE_VERSION: "' not in text, rel


def test_upgrade_reverifies_after_failed_apply():
    root = _tmp("upgrade-reverify-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, default_version=target,
                           package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    calls = []
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t, command=None: calls.append("install") or 0)
    try:
        _write(_artifact(root, target), json.dumps({
            "version": target, "verified": False, "rolled_back": False}) + "\n")
        args = _args(root, to=target, home=fixture["home"], apply=True,
                     skip_canary=True, drain_acknowledged=True)
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.upgrade(args)
        assert rc == 0, out.getvalue()
        assert "already current" not in out.getvalue()
        smoke = [row for row in calls if isinstance(row, dict)]
        assert len(smoke) == 1, calls
        assert json.load(open(_artifact(root, target)))["verified"] is True
        assert upgrade.read_state(root)["stage"] == "applied"
        calls.clear()
        out2 = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out2), \
                contextlib.redirect_stderr(out2):
            assert upgrade.upgrade(args) == 0
        assert "already current" in out2.getvalue()
        assert not [row for row in calls if isinstance(row, dict)], calls
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_reverifies_after_legacy_failed_artifact():
    root = _tmp("upgrade-legacy-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, default_version=target,
                           package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    calls = []
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t, command=None: calls.append("install") or 0)
    try:
        # Normalization: legacy artifacts have no `verified` field.
        passing = {"version": target, "rolled_back": False,
                   "checks": {"binary": {"ok": True, "detail": target}}}
        _write(_artifact(root, target), json.dumps(passing) + "\n")
        assert upgrade.last_verify_verified(root, target) is True
        # The live 2.2.6 legacy failure shape (no `verified`, rolled_back true).
        legacy = {
            "version": target,
            "checks": {
                "binary": {"ok": False, "detail": "1.19.4"},
                "api": {"ok": False, "detail": ""},
                "agents": {"ok": True, "detail": "framework=17 consumer=0"},
                "plugin": {"ok": False, "detail": "loader did not load"},
                "observer": {"ok": False, "detail": "api unavailable"},
            },
            "backup": backup,
            "rolled_back": True,
            "at": "2026-11-09T12:20:49Z",
        }
        _write(_artifact(root, target), json.dumps(legacy) + "\n")
        legacy_bytes = open(_artifact(root, target), "rb").read()
        assert upgrade.last_verify_verified(root, target) is False
        args = _args(root, to=target, home=fixture["home"], apply=True,
                     skip_canary=True, drain_acknowledged=True)
        out = io.StringIO()
        with _path_front(fixture["yarn_bin"]), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.upgrade(args)
        assert rc == 0, out.getvalue()
        assert "already current" not in out.getvalue()
        smoke = [row for row in calls if isinstance(row, dict)]
        assert len(smoke) == 1, calls
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is True
        assert data["rolled_back"] is False
        assert upgrade.read_state(root)["stage"] == "applied"
        artifact = _artifact(root, target)
        archives = sorted(glob.glob(artifact + ".failed-*"))
        assert len(archives) == 1, archives
        assert open(archives[0], "rb").read() == legacy_bytes
        # A verified predecessor is preserved under a neutral name.
        verified_bytes = open(artifact, "rb").read()
        previous = upgrade.archive_artifact(artifact)
        assert previous is not None
        assert ".previous-" in previous
        assert open(previous, "rb").read() == verified_bytes
        assert not os.path.isfile(artifact)
        assert sorted(glob.glob(artifact + ".previous-*")) == [previous]
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def _make_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
    con.execute("INSERT INTO session(id) VALUES ('ses_1')")
    con.commit()
    con.close()


def test_apply_dry_run_is_side_effect_free():
    root = _tmp("upgrade-dryrun-pure-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    calls = []
    real = (upgrade.run, upgrade.pre_upgrade_backup, upgrade.official_upgrade,
            upgrade.prepare_shadow, upgrade.stage_config.live_processes)
    before = open(fixture["link"], "rb").read()

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    upgrade.run = fake_run
    upgrade.pre_upgrade_backup = lambda a, t: calls.append("backup") or (
        os.path.join(root, "b"), None)
    upgrade.official_upgrade = lambda a, t, command=None: calls.append(
        "install") or 0
    upgrade.prepare_shadow = lambda h, l, t: calls.append("shadow") or {
        "failure_stage": None}
    upgrade.stage_config.live_processes = lambda: calls.append("drain") or []
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True, dry_run=True, stop_service=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.apply_supported(args, target) == 0
        for command in calls:
            if isinstance(command, list):
                assert not (command[1:3] == ["service", "stop"]), command
        assert "backup" not in calls and "install" not in calls
        assert "shadow" not in calls and "drain" not in calls
        assert not os.path.isfile(upgrade.state_path(root))
        assert open(fixture["link"], "rb").read() == before
    finally:
        (upgrade.run, upgrade.pre_upgrade_backup, upgrade.official_upgrade,
         upgrade.prepare_shadow,
         upgrade.stage_config.live_processes) = real
        shutil.rmtree(root, ignore_errors=True)


def test_apply_stops_service_before_drain_gate():
    root = _tmp("upgrade-stop-order-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    order = []
    stopped = {"done": False}
    real = (upgrade.run, upgrade.pre_upgrade_backup, upgrade.official_upgrade,
            upgrade.stage_config.live_processes, upgrade.post_upgrade_smoke)

    def fake_run(argv, **kwargs):
        order.append("run:" + " ".join(argv))
        if argv[1:3] == ["service", "stop"]:
            stopped["done"] = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:4] == ["debug", "paths", "config"]:
            return subprocess.CompletedProcess(argv, 0, fixture["config"], "")
        if len(argv) > 1 and argv[1] == "--version":
            return subprocess.CompletedProcess(
                argv, 0, f"opencode v{v2.VERSION_PIN}", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def live():
        order.append("drain")
        return [] if stopped["done"] else ["opencode running"]

    upgrade.run = fake_run
    upgrade.stage_config.live_processes = live
    upgrade.pre_upgrade_backup = lambda a, t: (
        os.path.join(root, "backup"), None)
    upgrade.official_upgrade = lambda a, t, command=None: 0
    upgrade.post_upgrade_smoke = lambda a, t, command=None: [
        ("binary", True, "ok")]
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True, stop_service=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.apply_supported(args, target) == 0, order
        stop_idx = next(i for i, item in enumerate(order)
                        if item.startswith("run:") and " service stop" in item)
        drain_idx = order.index("drain")
        assert stop_idx < drain_idx, order
    finally:
        (upgrade.run, upgrade.pre_upgrade_backup, upgrade.official_upgrade,
         upgrade.stage_config.live_processes,
         upgrade.post_upgrade_smoke) = real
        shutil.rmtree(root, ignore_errors=True)


def test_sqlite_backups_are_0600():
    root = _tmp("upgrade-dbperm-")
    try:
        src = os.path.join(root, "src.db")
        _make_db(src)
        dst = os.path.join(root, "dst.db")
        upgrade.sqlite_backup(src, dst)
        assert stat.S_IMODE(os.stat(dst).st_mode) == 0o600
        home = os.path.join(root, "home")
        home_db = os.path.join(home, ".local", "share", "opencode",
                               "opencode.db")
        _make_db(home_db)
        backup, db = upgrade.pre_upgrade_backup(
            _args(root, home=home, to=v2.VERSION_PIN), v2.VERSION_PIN)
        assert db and os.path.isfile(db)
        assert stat.S_IMODE(os.stat(db).st_mode) == 0o600
        assert backup.startswith(os.path.join(root, ".scratch"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_pre_upgrade_backup_uses_home_and_absent_db():
    root = _tmp("upgrade-dbhome-")
    try:
        home = os.path.join(root, "home")
        args = _args(root, home=home, to=v2.VERSION_PIN)
        _backup, db = upgrade.pre_upgrade_backup(args, v2.VERSION_PIN)
        assert db is None, db
        home_db = os.path.join(home, ".local", "share", "opencode",
                               "opencode.db")
        _make_db(home_db)
        assert upgrade.db_source_path(home) == home_db
        _backup, db = upgrade.pre_upgrade_backup(args, v2.VERSION_PIN)
        assert db and os.path.isfile(db), db
        override = os.path.join(root, "override.db")
        _make_db(override)
        real_env = os.environ.get("OPENCODE_DB")
        os.environ["OPENCODE_DB"] = override
        try:
            assert upgrade.db_source_path(home) == override
        finally:
            if real_env is None:
                os.environ.pop("OPENCODE_DB", None)
            else:
                os.environ["OPENCODE_DB"] = real_env
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_timeout_writes_failure_artifact():
    root = _tmp("upgrade-timeout-")
    target = v2.VERSION_PIN
    fixture = _v1_only_home(root)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, lambda a, t, command=None: [
        ("binary", True, "ok")])
    upgrade.pre_upgrade_backup = lambda a, t: (backup, None)

    def timeout(_args, _target, command=None):
        raise subprocess.TimeoutExpired(["opencode"], 900)

    upgrade.official_upgrade = timeout
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.apply_supported(args, target) == 1
        data = json.load(open(_artifact(root, target)))
        assert data["verified"] is False
        assert data["failure_stage"] == "exception:install", data
        assert "TimeoutExpired" in data["exception"]
        assert data["database_backup"] is None
        assert upgrade.read_state(root)["stage"] == "prepared"
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_apply_spawn_error_writes_failure_artifact():
    root = _tmp("upgrade-spawn-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, lambda a, t, command=None: [
        ("binary", True, "ok")])

    def spawn_error(_args, _target, command=None):
        raise FileNotFoundError("missing binary")

    upgrade.post_upgrade_smoke = spawn_error
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.apply_supported(args, target) == 1
        data = json.load(open(_artifact(root, target)))
        assert data["failure_stage"] == "exception:smoke", data
        assert "FileNotFoundError" in data["exception"]
        assert upgrade.read_state(root)["stage"] == "prepared"
    finally:
        _restore_apply(real)
        shutil.rmtree(root, ignore_errors=True)


def test_canary_residual_acceptance():
    root = _tmp("upgrade-residual-")
    target = v2.VERSION_PIN
    ev = os.path.join(root, ".scratch", "v2-canary-" + target)
    try:
        for name, filename in (("C1", "C1.txt"), ("C2", "C2.txt"),
                               ("C3", "C3-real.txt"), ("C4", "C4.txt"),
                               ("C5", "C5.txt"), ("C6", "C6.txt"),
                               ("C7", "C7.txt"), ("C8", "C8.txt")):
            _write(os.path.join(ev, filename), f"{name}=PASS\n")
        _write(os.path.join(ev, "migration-rehearsal.txt"), "\n".join([
            "source_sessions_not_migrated=3",
            "target_only_ids=0",
            "zero_migration=False",
            "target_integrity_check=ok",
            "source_untouched=True",
            "migration=PASS with fidelity residual 3",
        ]) + "\n")
        summary = upgrade.canary_summary(root, target)
        assert summary["ok"] is False
        assert summary["residual"] == 3
        assert summary["migration"]["verdict"] == "PASS"
        assert summary["residual_accepted"] is False
        _write(os.path.join(root, "docs",
                            "opencode-v2-migration-classification.json"),
               json.dumps({"version": target, "residual": 3,
                           "owner": "owner", "date": "2026-11-09"}) + "\n")
        summary = upgrade.canary_summary(root, target)
        assert summary["ok"] is True
        assert summary["residual_accepted"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_summary_migration_failures_block():
    root = _tmp("upgrade-migration-block-")
    target = v2.VERSION_PIN
    ev = os.path.join(root, ".scratch", "v2-canary-" + target)
    try:
        for name, filename in (("C1", "C1.txt"), ("C2", "C2.txt"),
                               ("C3", "C3-real.txt"), ("C4", "C4.txt"),
                               ("C5", "C5.txt"), ("C6", "C6.txt"),
                               ("C7", "C7.txt"), ("C8", "C8.txt")):
            _write(os.path.join(ev, filename), f"{name}=PASS\n")

        def migration(verdict, residual, target_only, zero, integrity,
                      untouched="True"):
            _write(os.path.join(ev, "migration-rehearsal.txt"), "\n".join([
                f"source_sessions_not_migrated={residual}",
                f"target_only_ids={target_only}",
                f"zero_migration={zero}",
                f"target_integrity_check={integrity}",
                f"source_untouched={untouched}",
                f"migration={verdict}",
            ]) + "\n")

        migration("FAIL", 0, 2, "False", "ok")
        assert upgrade.canary_summary(root, target)["ok"] is False
        migration("FAIL", 0, 0, "False", "corrupt")
        assert upgrade.canary_summary(root, target)["ok"] is False
        migration("PASS", 0, 0, "True", "ok")
        assert upgrade.canary_summary(root, target)["ok"] is False
        migration("PASS", 0, 0, "False", "ok")
        assert upgrade.canary_summary(root, target)["ok"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_missing_canary_names_prerequisite():
    root = _tmp("upgrade-nocanary-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        args = _args(root, to=target, home=fixture["home"],
                     drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 2
        text = out.getvalue()
        assert "no canary evidence" in text
        assert f"canary --to {target}" in text
        assert "--skip-canary" not in text
        assert not os.path.isfile(upgrade.state_path(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_version_parsing_rejects_substrings():
    root = _tmp("upgrade-versions-")
    try:
        # Real binaries: V1 prints bare 1.19.4; V2 prints opencode v2.2.6.
        v1 = os.path.join(root, "v1")
        _stub_binary(v1, "1.19.4")
        assert upgrade.version_of(v1) == "1.19.4"
        long_version = os.path.join(root, "long")
        _stub_binary(long_version, "2.2.60")
        assert upgrade.version_of(long_version) == "2.2.60"
        assert upgrade.version_of(long_version) != v2.VERSION_PIN
        v1_long = os.path.join(root, "v1long")
        _stub_binary(v1_long, "1.19.40")
        assert upgrade.version_of(v1_long) == "1.19.40"
        assert upgrade.version_of(v1_long) != "1.19.4"
        prerelease = os.path.join(root, "rc")
        _stub_binary(prerelease, "2.2.6-rc")
        assert upgrade.version_of(prerelease) is None
        cases = (
            ("opencode v2.2.6", "2.2.6"),
            ("v2.2.6", "2.2.6"),
            ("2.2.6", "2.2.6"),
            ("opencode v1.19.4", "1.19.4"),
            ("v1.19.4", "1.19.4"),
            ("1.19.4", "1.19.4"),
            ("1.19.40", "1.19.40"),
            ("opencode v2.2.6-rc", None),
            ("build 2.2.6", None),
            ("2.2", None),
            ("", None),
        )
        for text, expected in cases:
            assert v2.parse_opencode_version(text) == expected, (text, expected)
        assert upgrade.api_version('{"version":"2.2.60"}',
                                   v2.VERSION_PIN)[0] is False
        assert upgrade.api_version('{"version":"2.2.6"}',
                                   v2.VERSION_PIN)[0] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_shared_version_parser_is_single_source():
    import opencode_v2_canary as canary
    import opencode_v2_post_smoke as post_smoke
    samples = ("opencode v2.2.6", "v2.2.6", "2.2.6", "1.19.4",
               "1.19.40", "opencode v2.2.6-rc", "build 2.2.6", "")
    for text in samples:
        expected = v2.parse_opencode_version(text)
        assert upgrade.parse_version(text) == expected, text
        assert canary.exact_version(text) == expected, text
        assert post_smoke.parsed_version(text) == expected, text


def test_prepare_gate_precedes_writes():
    root = _tmp("upgrade-prepare-gate-")
    try:
        _fixture(root)
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        before = {
            "readme": open(os.path.join(root, "README.md")).read(),
            "adapter": open(os.path.join(root, "scripts",
                                         "opencode_v2.py")).read(),
            "plugin": open(os.path.join(
                root, "plugins", "delegation-observer",
                "package.json")).read(),
        }
        args = _args(root, to="2.3.0", opentui="0.8.2", plugin_json=peers)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.prepare(args) == 2
        assert open(os.path.join(root, "README.md")).read() == before["readme"]
        assert open(os.path.join(root, "scripts",
                                 "opencode_v2.py")).read() == before["adapter"]
        assert open(os.path.join(
            root, "plugins", "delegation-observer",
            "package.json")).read() == before["plugin"]
        assert "2.3.0" not in open(os.path.join(
            root, "docs", "ADRs", "ADR-0014-opencode-v2-upgrade.md")).read()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_allow_pending_canary_is_explicit_bypass():
    root = _tmp("upgrade-prepare-bypass-")
    real_run = upgrade.run
    try:
        _fixture(root)
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        upgrade.run = lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 0 if argv[:2] == ["npm", "install"] else 1, "", "")
        args = _args(root, to="2.3.0", opentui="0.8.2", plugin_json=peers,
                     allow_pending_canary=True)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.prepare(args) == 0
        assert "2.3.0" in open(os.path.join(root, "README.md")).read()
    finally:
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_topology_uses_explicit_link_not_path():
    root = _tmp("upgrade-path-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, default_version=target,
                           package_version=target)
    path_dir = os.path.join(root, "pathbin")
    _stub_binary(os.path.join(path_dir, "opencode"), "1.19.4")
    real_path = os.environ.get("PATH", "")
    real_run = upgrade.run
    os.environ["PATH"] = path_dir + os.pathsep + real_path
    try:
        install = upgrade.topology(fixture["home"], fixture["link"])
        assert install["command"] == fixture["link"]
        assert install["supported"] is True
        assert upgrade.version_of(install["command"]) == target
        recorded = []
        upgrade.run = lambda argv, **kwargs: recorded.append(list(argv)) or \
            subprocess.CompletedProcess(argv, 0, "", "")
        try:
            upgrade.official_upgrade(_args(root, method="yarn"), target,
                                     fixture["link"])
        finally:
            upgrade.run = real_run
        assert recorded and recorded[0][0] == fixture["link"], recorded
    finally:
        os.environ["PATH"] = real_path
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_cli_docstring_truthful():
    doc = upgrade.__doc__ or ""
    assert "rollback  manual" not in doc
    assert "apply     drained" not in doc
    assert "upgrade --apply --drain-acknowledged" in doc
    assert "not require or check a TTY" in doc
    parser = upgrade.build_parser()
    sub = next(action for action in parser._actions
               if isinstance(action, argparse._SubParsersAction))
    assert "rollback" not in sub.choices
    assert "apply" not in sub.choices


def test_satisfies_semver_ranges():
    cases = [
        ("0.8.1", "^0.8.0", True),
        ("0.9.0", "^0.8.0", False),
        ("1.2.5", "~1.2.3", True),
        ("1.3.0", "~1.2.3", False),
        ("1.9.0", ">=1.2.3 <2.0.0", True),
        ("2.0.0", ">=1.2.3 <2.0.0", False),
        ("1.5.0", "1.x", True),
        ("2.0.0", "1.x", False),
        ("1.0.0", "next", False),
    ]
    for current, spec, expected in cases:
        assert upgrade.satisfies(current, spec) is expected, (current, spec)


def test_state_contract_has_no_unused_stage():
    assert upgrade.STAGE_ORDER == ("planned", "canaried", "prepared", "applied")
    assert "checked" not in upgrade.STAGE_ORDER
    assert upgrade.RESUMABLE_STAGES == ("planned", "canaried", "prepared")
    root = _tmp("upgrade-stages-")
    try:
        for stage in upgrade.STAGE_ORDER:
            upgrade.write_state(root, v2.VERSION_PIN, stage)
        state = upgrade.read_state(root)
        assert state["stage"] == "applied"
        assert upgrade.completed_stages(state) == set(upgrade.STAGE_ORDER)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_write_json_atomic_under_concurrency():
    root = _tmp("upgrade-atomic-")
    path = os.path.join(root, "state.json")
    payloads = [{"n": i, "blob": "x" * 10000} for i in range(4)]
    upgrade.write_json(path, payloads[0])
    errors = []

    def writer(payload):
        for _ in range(20):
            upgrade.write_json(path, payload)

    def reader():
        for _ in range(200):
            try:
                json.load(open(path))
            except ValueError as exc:  # torn JSON is the defect under test
                errors.append(exc)

    threads = [threading.Thread(target=writer, args=(p,)) for p in payloads]
    read_thread = threading.Thread(target=reader)
    read_thread.start()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    read_thread.join()
    try:
        assert not errors, errors
        assert not glob.glob(path + ".tmp.*")
        assert json.load(open(path)) in payloads
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_file_lock_is_bounded():
    root = _tmp("upgrade-lock-")
    path = os.path.join(root, "state.json")
    try:
        with upgrade.file_lock(path):
            try:
                with upgrade.file_lock(path, timeout=0.1):
                    assert False, "second lock should time out"
            except TimeoutError:
                pass
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_tui_smoke_missing_script_is_named_failure():
    root = _tmp("upgrade-tui-")
    real_which = upgrade.shutil.which
    upgrade.shutil.which = lambda name: None if name == "script" else real_which(name)
    try:
        ok, detail = upgrade.tui_smoke(
            _args(root, prefix=os.path.join(root, "prefix")),
            v2.VERSION_PIN, "0.8.1")
        assert ok is False
        assert "script-not-available" in detail
        evidence = os.path.join(root, ".scratch", "v2-canary-" + v2.VERSION_PIN,
                                "tui-smoke.txt")
        assert os.path.isfile(evidence)
    finally:
        upgrade.shutil.which = real_which
        shutil.rmtree(root, ignore_errors=True)


def test_diagnostics_do_not_write_state():
    root = _tmp("upgrade-diag-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            upgrade.status_payload(_args(root, home=fixture["home"]))
            upgrade.doctor(_args(root, home=fixture["home"]))
            upgrade.upgrade(_args(root, to=target, home=fixture["home"]))
        assert not os.path.isfile(upgrade.state_path(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_plan_range_action_uses_peer_spec():
    root = _tmp("upgrade-plan-range-")
    try:
        _fixture(root)
        peers = _json_file(root, {
            "@opencode/plugin": "2.3.0",
            "@opentui/core": ">=0.8.0",
            "@opentui/solid": ">=0.8.0",
            "solid-js": ">=1.9.0"}, "peers.json")
        releases = _json_file(root, [], "releases.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert upgrade.plan(_args(root, to="2.3.0", opentui="0.8.2",
                                    plugin_json=peers,
                                    releases_file=releases)) == 0
        text = out.getvalue()
        core = next(line for line in text.splitlines()
                    if "@opentui/core" in line)
        assert core.rstrip().endswith("none"), core
        solid = next(line for line in text.splitlines() if "solid-js" in line)
        assert solid.rstrip().endswith("none"), solid
        cli = next(line for line in text.splitlines()
                   if line.strip().startswith("CLI"))
        assert cli.rstrip().endswith("bump"), cli
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_dry_run_lists_all_actions():
    root = _tmp("upgrade-dryrun-upgrade-")
    target = "2.3.0"
    fixture = _shadow_home(root, v2.VERSION_PIN,
                           default_version=v2.VERSION_PIN,
                           package_version=v2.VERSION_PIN)
    real_plan = upgrade.plan
    upgrade.plan = lambda args: 0
    try:
        args = _args(root, to=target, home=fixture["home"], dry_run=True,
                     stop_service=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.upgrade(args) == 0
        text = out.getvalue()
        assert "would back up any existing DB/config" in text, text
        assert "would stop the service before the drain check" in text, text
        assert (f"would run: {fixture['link']} upgrade {target} --method yarn"
                ) in text, text
        assert (f"would repair the default {fixture['link']} shadow"
                ) in text, text
        assert "would run the post-upgrade smoke" in text, text
        assert f"would write {_artifact(root, target)}" in text, text
        order = [
            "would stop the service before the drain check",
            "would check the drain gate",
            "would back up any existing DB/config",
            f"would run: {fixture['link']} upgrade {target} --method yarn",
            f"would repair the default {fixture['link']} shadow",
            "would run the post-upgrade smoke",
            f"would write {_artifact(root, target)}",
        ]
        positions = [text.index(item) for item in order]
        assert positions == sorted(positions), positions
    finally:
        upgrade.plan = real_plan
        shutil.rmtree(root, ignore_errors=True)


def test_pre_upgrade_backup_absent_config_not_cited():
    root = _tmp("upgrade-noconfig-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    _make_db(os.path.join(fixture["home"], ".local", "share", "opencode",
                          "opencode.db"))
    shutil.rmtree(fixture["config"])
    real = (upgrade.official_upgrade, upgrade.post_upgrade_smoke,
            upgrade.stage_config.live_processes)
    upgrade.official_upgrade = lambda a, t, command=None: 0
    upgrade.post_upgrade_smoke = lambda a, t, command=None: [
        ("binary", False, "forced failure")]
    upgrade.stage_config.live_processes = lambda: []
    try:
        args = _args(root, to=target, home=fixture["home"], skip_canary=True,
                     drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 1
        data = json.load(open(_artifact(root, target)))
        assert data["config_backup"] is None, data["config_backup"]
        assert data["database_backup"] and os.path.isfile(
            data["database_backup"])
        assert os.path.join(data["backup"], "config") not in data[
            "rollback"]["guidance"]
        restore_tail = out.getvalue().split("restore:")[-1]
        assert "config:" not in restore_tail
        assert "DB:" in restore_tail
    finally:
        (upgrade.official_upgrade, upgrade.post_upgrade_smoke,
         upgrade.stage_config.live_processes) = real
        shutil.rmtree(root, ignore_errors=True)


def test_doctor_survives_spawn_timeout():
    root = _tmp("upgrade-doctor-timeout-")
    fixture = _shadow_home(root, v2.VERSION_PIN,
                           default_version=v2.VERSION_PIN,
                           package_version=v2.VERSION_PIN)
    real_run = upgrade.run
    real_observer = upgrade.observer_plugin

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(["opencode"], 30)

    upgrade.run = timeout
    upgrade.observer_plugin = timeout
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.doctor(_args(root, home=fixture["home"])) == 1
        text = out.getvalue()
        assert "service: FAIL TimeoutExpired" in text, text
        assert "observer: FAIL TimeoutExpired" in text, text
    finally:
        upgrade.run = real_run
        upgrade.observer_plugin = real_observer
        shutil.rmtree(root, ignore_errors=True)


def test_cli_dry_run_and_consent_do_not_write_state():
    root = _tmp("upgrade-cli-purity-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    before = open(fixture["link"], "rb").read()
    real_backup = upgrade.pre_upgrade_backup
    real_smoke = upgrade.post_upgrade_smoke
    upgrade.pre_upgrade_backup = lambda a, t: (
        os.path.join(root, "backup"), None)
    upgrade.post_upgrade_smoke = lambda a, t, command=None: [
        ("binary", True, "ok")]
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.main([
                "upgrade", "--to", target, "--apply", "--dry-run",
                "--skip-canary", "--drain-acknowledged",
                "--home", fixture["home"], "--repo", root,
            ])
        assert rc == 0, out.getvalue()
        assert not os.path.isfile(upgrade.state_path(root))
        assert not os.path.exists(_artifact(root, target))
        assert open(fixture["link"], "rb").read() == before

        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.main([
                "upgrade", "--to", target, "--apply", "--skip-canary",
                "--home", fixture["home"], "--repo", root,
            ])
        assert rc == 2, out.getvalue()
        assert not os.path.isfile(upgrade.state_path(root))
        assert not os.path.exists(_artifact(root, target))
    finally:
        upgrade.pre_upgrade_backup = real_backup
        upgrade.post_upgrade_smoke = real_smoke
        shutil.rmtree(root, ignore_errors=True)


def test_cli_successful_apply_records_state():
    root = _tmp("upgrade-cli-state-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    real = (upgrade.pre_upgrade_backup, upgrade.post_upgrade_smoke,
            upgrade.stage_config.live_processes)
    upgrade.pre_upgrade_backup = lambda a, t: (
        os.path.join(root, "backup"), None)
    upgrade.post_upgrade_smoke = lambda a, t, command=None: [
        ("binary", True, "ok")]
    upgrade.stage_config.live_processes = lambda: []
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.main([
                "upgrade", "--to", target, "--apply", "--skip-canary",
                "--drain-acknowledged", "--home", fixture["home"],
                "--repo", root,
            ])
        assert rc == 0, out.getvalue()
        assert upgrade.read_state(root)["stage"] == "applied"
        assert json.load(open(_artifact(root, target)))["verified"] is True
    finally:
        (upgrade.pre_upgrade_backup, upgrade.post_upgrade_smoke,
         upgrade.stage_config.live_processes) = real
        shutil.rmtree(root, ignore_errors=True)


def _legacy_canary(repo, version):
    """The actual pre-hardening 2.2.6 migration evidence shape."""
    ev = os.path.join(repo, ".scratch", "v2-canary-" + version)
    for name, filename in (("C1", "C1.txt"), ("C2", "C2.txt"),
                           ("C3", "C3-real.txt"), ("C4", "C4.txt"),
                           ("C5", "C5.txt"), ("C6", "C6.txt"),
                           ("C7", "C7.txt"), ("C8", "C8.txt")):
        _write(os.path.join(ev, filename), f"{name}=PASS\n")
    _write(os.path.join(ev, "migration-rehearsal.txt"), "\n".join([
        "source_session_rows=12",
        "source_sessions_not_migrated=0",
        "target_integrity_check=ok",
        "source_untouched=True",
        "migration=PASS with fidelity residual 0 "
        "(requires classification or owner acceptance)",
    ]) + "\n")


def test_canary_summary_legacy_evidence_fails_actionably():
    root = _tmp("upgrade-legacy-canary-")
    target = v2.VERSION_PIN
    try:
        _legacy_canary(root, target)
        summary = upgrade.canary_summary(root, target)
        assert summary["ok"] is False
        assert summary["schema_complete"] is False
        assert "zero_migration" in summary["missing_fields"]
        assert "target_only_ids" in summary["missing_fields"]
        assert f"canary --to {target}" in summary["reason"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_summary_fresh_schema_passes():
    root = _tmp("upgrade-fresh-canary-")
    target = v2.VERSION_PIN
    try:
        _evidence(root, target)
        summary = upgrade.canary_summary(root, target)
        assert summary["ok"] is True
        assert summary["schema_complete"] is True
        assert summary["reason"] is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_refuses_legacy_canary_actionably():
    root = _tmp("upgrade-legacy-apply-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        _legacy_canary(root, target)
        args = _args(root, to=target, home=fixture["home"],
                     drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 2
        text = out.getvalue()
        assert "zero_migration" in text and "target_only_ids" in text, text
        assert f"canary --to {target}" in text, text
        assert "--skip-canary" not in text, text
        assert not os.path.isfile(upgrade.state_path(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_status_shows_canary_prerequisite_for_legacy_evidence():
    root = _tmp("upgrade-legacy-status-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        _legacy_canary(root, target)
        payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["next"] == upgrade.canary_command(target)
        assert payload["canary_blocker"] is True
        assert "zero_migration" in (payload["canary_reason"] or "")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_no_apply_shows_canary_prerequisite():
    root = _tmp("upgrade-legacy-guidance-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    try:
        _legacy_canary(root, target)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.upgrade(_args(root, to=target,
                                         home=fixture["home"])) == 0
        text = out.getvalue()
        assert "canary prerequisite" in text, text
        assert f"canary --to {target}" in text, text
        assert "shadow repair needed" not in text, text
        assert not os.path.isfile(upgrade.state_path(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_canary_cmd_uses_explicit_link_not_path():
    root = _tmp("upgrade-canary-link-")
    target = v2.VERSION_PIN
    home = os.path.join(root, "home")
    link = os.path.join(home, ".yarn", "bin", "opencode")
    _stub_binary(link, target)
    path_dir = os.path.join(root, "pathbin")
    _stub_binary(os.path.join(path_dir, "opencode"), "1.19.4")
    real_path = os.environ.get("PATH", "")
    os.environ["PATH"] = path_dir + os.pathsep + real_path
    try:
        args = _args(root, home=home, link=link,
                     v1_bin=os.path.join(root, "v1"))
        argv = upgrade.canary_cmd(args, target)
        default_bin = argv[argv.index("--default-bin") + 1]
        assert default_bin == link
        assert argv[argv.index("--default-version") + 1] == target
        args.link = None
        argv = upgrade.canary_cmd(args, target)
        default_bin = argv[argv.index("--default-bin") + 1]
        assert default_bin == os.path.join(home, ".yarn", "bin", "opencode")
        assert argv[argv.index("--default-version") + 1] == target
    finally:
        os.environ["PATH"] = real_path
        shutil.rmtree(root, ignore_errors=True)


def test_topology_does_not_read_large_binary():
    root = _tmp("upgrade-large-binary-")
    home = os.path.join(root, "home")
    link = os.path.join(home, ".yarn", "bin", "opencode")
    config = os.path.join(home, ".config", "opencode")
    os.makedirs(config)
    big = os.path.join(root, "big-opencode")
    with open(big, "wb") as fh:
        fh.truncate(200 * 1024 * 1024)
    os.chmod(big, 0o755)
    os.makedirs(os.path.dirname(link), exist_ok=True)
    os.symlink(big, link)
    real_run = upgrade.run
    real_open = builtins.open
    upgrade.run = lambda argv, **kwargs: subprocess.CompletedProcess(
        argv, 0, config, "")

    def guarded(path, *args, **kwargs):
        if os.path.abspath(str(path)) == os.path.abspath(big):
            raise AssertionError("topology read the executable")
        return real_open(path, *args, **kwargs)

    builtins.open = guarded
    try:
        install = upgrade.topology(home, link)
        assert install["command"] == link
        assert install["supported"] is True
        assert install["wrapper"] is None
    finally:
        builtins.open = real_open
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_apply_paths_use_explicit_link_not_path():
    root = _tmp("upgrade-command-link-")
    target = v2.VERSION_PIN
    home = os.path.join(root, "home")
    link = os.path.join(home, ".yarn", "bin", "opencode")
    _stub_binary(link, target)
    path_dir = os.path.join(root, "pathbin")
    _stub_binary(os.path.join(path_dir, "opencode"), "1.19.4")
    real_path = os.environ.get("PATH", "")
    real_run = upgrade.run
    real_agents = upgrade.post_smoke.check_agents_live
    real_plugin = upgrade.post_smoke.check_plugin
    real_observer = upgrade.observer_plugin
    recorded = []
    os.environ["PATH"] = path_dir + os.pathsep + real_path
    upgrade.run = lambda argv, **kwargs: recorded.append(list(argv)) or \
        subprocess.CompletedProcess(argv, 0, "", "")
    upgrade.post_smoke.check_agents_live = lambda binary, framework: (
        recorded.append(["agents", binary]) or (True, "ok"))
    upgrade.post_smoke.check_plugin = lambda **kwargs: (
        recorded.append(["plugin", kwargs.get("binary")]) or (True, "ok"))
    upgrade.observer_plugin = lambda command: (
        recorded.append(["observer", command]) or (None, "tui=True"))
    try:
        args = _args(root, home=home, link=link)
        upgrade.official_upgrade(args, target)
        assert recorded and recorded[0][0] == link, recorded
        recorded.clear()
        upgrade.post_upgrade_smoke(args, target)
        commands = [
            row[1] if row[0] in ("agents", "plugin", "observer") else row[0]
            for row in recorded if isinstance(row, list)
        ]
        assert commands, recorded
        assert all(command == link for command in commands), commands
    finally:
        os.environ["PATH"] = real_path
        upgrade.run = real_run
        upgrade.post_smoke.check_agents_live = real_agents
        upgrade.post_smoke.check_plugin = real_plugin
        upgrade.observer_plugin = real_observer
        shutil.rmtree(root, ignore_errors=True)


def _prepare_peers(root):
    return _json_file(root, {
        "@opencode/plugin": "2.3.0",
        "@opentui/core": ">=0.8.0",
        "@opentui/solid": ">=0.8.0",
        "solid-js": ">=1.9.0"}, "peers.json")


def _prepare_originals(root):
    return {
        "readme": open(os.path.join(root, "README.md")).read(),
        "adapter": open(os.path.join(root, "scripts",
                                     "opencode_v2.py")).read(),
        "plugin": open(os.path.join(root, "plugins", "delegation-observer",
                                    "package.json")).read(),
        "adr": open(os.path.join(root, "docs", "ADRs",
                                 "ADR-0014-opencode-v2-upgrade.md")).read(),
    }


def _assert_prepare_restored(root, originals):
    assert open(os.path.join(root, "README.md")).read() == originals["readme"]
    assert open(os.path.join(root, "scripts",
                             "opencode_v2.py")).read() == originals["adapter"]
    assert open(os.path.join(root, "plugins", "delegation-observer",
                             "package.json")).read() == originals["plugin"]
    assert open(os.path.join(root, "docs", "ADRs",
                             "ADR-0014-opencode-v2-upgrade.md")).read() == \
        originals["adr"]


def test_prepare_npm_timeout_writes_failure_artifact_and_restores():
    root = _tmp("upgrade-prepare-timeout-")
    real_run = upgrade.run
    try:
        _fixture(root)
        _evidence(root, "2.3.0")
        peers = _prepare_peers(root)
        originals = _prepare_originals(root)

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 300)

        upgrade.run = timeout
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.prepare(_args(root, to="2.3.0", opentui="0.8.2",
                                         plugin_json=peers)) == 1
        artifact = os.path.join(root, ".scratch", "opencode-v2",
                                "prepare-2.3.0-failure.json")
        data = json.load(open(artifact))
        assert data["stage"] == "npm-install"
        assert "TimeoutExpired" in data["exception"]
        assert data["restored"], data
        assert data["completed"], data
        _assert_prepare_restored(root, originals)
        assert not os.path.isfile(upgrade.state_path(root)) or \
            upgrade.read_state(root).get("stage") != "prepared"
    finally:
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_adr_failure_restores_written_files():
    root = _tmp("upgrade-prepare-adr-")
    real_run = upgrade.run
    real_adr = upgrade.append_adr_amendment
    try:
        _fixture(root)
        _evidence(root, "2.3.0")
        peers = _prepare_peers(root)
        originals = _prepare_originals(root)
        upgrade.run = lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 0, "", "")

        def fail(*args, **kwargs):
            raise OSError("adr write failed")

        upgrade.append_adr_amendment = fail
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.prepare(_args(root, to="2.3.0", opentui="0.8.2",
                                         plugin_json=peers)) == 1
        artifact = os.path.join(root, ".scratch", "opencode-v2",
                                "prepare-2.3.0-failure.json")
        data = json.load(open(artifact))
        assert data["stage"] == "adr-amendment"
        assert "OSError" in data["exception"]
        assert data["restored"], data
        _assert_prepare_restored(root, originals)
    finally:
        upgrade.run = real_run
        upgrade.append_adr_amendment = real_adr
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_failure_preserves_prior_state():
    root = _tmp("upgrade-prepare-state-")
    real_run = upgrade.run
    try:
        _fixture(root)
        _evidence(root, "2.3.0")
        peers = _prepare_peers(root)
        upgrade.write_state(root, "2.3.0", "planned")

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 300)

        upgrade.run = timeout
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            assert upgrade.prepare(_args(root, to="2.3.0", opentui="0.8.2",
                                         plugin_json=peers)) == 1
        assert upgrade.read_state(root)["stage"] == "planned"
    finally:
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_pre_upgrade_backup_config_failure_reports_db():
    root = _tmp("upgrade-backup-config-")
    real_copytree = upgrade.shutil.copytree
    try:
        home = os.path.join(root, "home")
        _make_db(os.path.join(home, ".local", "share", "opencode",
                              "opencode.db"))
        os.makedirs(os.path.join(home, ".config", "opencode"))
        _write(os.path.join(home, ".config", "opencode", "opencode.jsonc"),
               "{}\n")

        def fail(source, dest, *args, **kwargs):
            os.makedirs(dest, exist_ok=True)
            _write(os.path.join(dest, "opencode.jsonc"), "{}\n")
            raise OSError("copy failed after partial")

        upgrade.shutil.copytree = fail
        backup, db = upgrade.pre_upgrade_backup(
            _args(root, home=home), v2.VERSION_PIN)
        assert db and os.path.isfile(db)
        # A partial config dir exists, but metadata says it is not a restore
        # source.
        assert os.path.isdir(os.path.join(backup, "config"))
        meta = json.load(open(os.path.join(backup, "backup.json")))
        assert meta["db"] == db
        assert meta["config"] is None
        assert "OSError" in meta["config_error"]
        link = os.path.join(home, ".yarn", "bin", "opencode")
        payload = upgrade.apply_artifact(
            _args(root, home=home), v2.VERSION_PIN, home, link, backup,
            {"kind": "v2", "version": "2.2.5"}, "smoke", [], db=db)
        assert payload["config_backup"] is None
        assert payload["backup_metadata"]["config"] is None
        assert "OSError" in payload["config_backup_error"]
        assert payload["database_backup"] == db
        assert os.path.join(backup, "config") not in payload["rollback"][
            "guidance"]
    finally:
        upgrade.shutil.copytree = real_copytree
        shutil.rmtree(root, ignore_errors=True)


def test_apply_partial_config_backup_not_cited_as_restore():
    root = _tmp("upgrade-partial-config-apply-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    _make_db(os.path.join(fixture["home"], ".local", "share", "opencode",
                          "opencode.db"))
    real_copytree = upgrade.shutil.copytree
    real = (upgrade.official_upgrade, upgrade.post_upgrade_smoke,
            upgrade.stage_config.live_processes)

    def fail(source, dest, *args, **kwargs):
        os.makedirs(dest, exist_ok=True)
        _write(os.path.join(dest, "opencode.jsonc"), "{}\n")
        raise OSError("partial copy")

    upgrade.shutil.copytree = fail
    upgrade.official_upgrade = lambda a, t, command=None: 0
    upgrade.post_upgrade_smoke = lambda a, t, command=None: [
        ("binary", False, "forced failure")]
    upgrade.stage_config.live_processes = lambda: []
    try:
        args = _args(root, to=target, home=fixture["home"],
                     skip_canary=True, drain_acknowledged=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.apply_supported(args, target) == 1
        data = json.load(open(_artifact(root, target)))
        assert data["config_backup"] is None
        assert data["backup_metadata"]["config"] is None
        assert "OSError" in data["config_backup_error"]
        assert data["database_backup"] and os.path.isfile(
            data["database_backup"])
        assert os.path.join(data["backup"], "config") not in data["rollback"][
            "guidance"]
        restore_tail = out.getvalue().split("restore:")[-1]
        assert "config:" not in restore_tail, restore_tail
        assert "DB:" in restore_tail, restore_tail
    finally:
        upgrade.shutil.copytree = real_copytree
        (upgrade.official_upgrade, upgrade.post_upgrade_smoke,
         upgrade.stage_config.live_processes) = real
        shutil.rmtree(root, ignore_errors=True)


def test_pre_upgrade_backup_missing_db_reports_none():
    root = _tmp("upgrade-backup-nodb-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(home)
        backup, db = upgrade.pre_upgrade_backup(
            _args(root, home=home), v2.VERSION_PIN)
        assert db is None
        meta = json.load(open(os.path.join(backup, "backup.json")))
        assert meta["db"] is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_write_state_preserves_first_same_stage_record():
    root = _tmp("upgrade-state-record-")
    try:
        upgrade.write_state(root, v2.VERSION_PIN, "planned", {"n": 1})
        first = upgrade.read_state(root)["stages"]["planned"]
        upgrade.write_state(root, v2.VERSION_PIN, "planned", {"n": 2})
        assert upgrade.read_state(root)["stages"]["planned"] == first
        upgrade.write_state(root, v2.VERSION_PIN, "planned", {"n": 3},
                            force=True)
        assert upgrade.read_state(root)["stages"]["planned"]["detail"] == {
            "n": 3}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_registry_probe_timeout_returns_none():
    root = _tmp("upgrade-registry-timeout-")
    real_run = upgrade.run
    try:
        _fixture(root)

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 60)

        upgrade.run = timeout
        assert upgrade.latest_version(root, refresh=True) is None
        assert upgrade.plugin_peers("2.3.0") is None
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            assert upgrade.check(_args(root, remote=True)) == 2
        assert "registry" in out.getvalue()
    finally:
        upgrade.run = real_run
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
