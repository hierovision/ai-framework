#!/usr/bin/env python3
"""Hermetic tests for the supported-path upgrade helper.

Covers: offline pin seams, prepare dry-run/real update, the plan matrix +
breaking notes, the supported topology, the canary evidence gate, apply
consent + post-smoke failure, the canary argv, resume, prune, and the official
PR body. The live `opencode upgrade` itself is owner-run.

Run: python3 scripts/test_opencode_upgrade.py
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

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
    _write(os.path.join(root, "migration-rehearsal.txt"),
           f"source_sessions_not_migrated={residual}\n")


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
    """A tiny executable that answers `--version` and `debug paths config`."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "#!/bin/sh",
        f'if [ "$1" = "--version" ]; then echo "opencode v{version}"; '
        "exit 0; fi",
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
    """Fake HOME before the V2 package exists: only the V1 default link."""
    home = os.path.join(root, "home")
    yarn_bin = os.path.join(home, ".yarn", "bin")
    link = os.path.join(yarn_bin, "opencode")
    _stub_binary(link, default_version)
    config = os.path.join(home, ".config", "opencode")
    os.makedirs(config, exist_ok=True)
    package_dir = os.path.join(home, ".config", "yarn", "global",
                               "node_modules", "@opencode", "cli")
    return {"home": home, "link": link,
            "link2": os.path.join(yarn_bin, "opencode2"), "config": config,
            "package_dir": package_dir,
            "package_bin": os.path.join(package_dir, "bin", "opencode.exe"),
            "yarn_bin": yarn_bin}


def _yarn_relink_stub(fixture, target, calls):
    """Official-install stub: installs V2, then Yarn links opencode2 to V2 but
    rewrites the default `opencode` to V1 (the observed dual-bin behavior)."""
    def install(_args, _target):
        calls.append("install")
        _stub_binary(fixture["package_bin"], target, fixture["config"])
        _write(os.path.join(fixture["package_dir"], "package.json"), json.dumps({
            "name": "@opencode/cli", "version": target}) + "\n")
        if os.path.lexists(fixture["link2"]):
            os.unlink(fixture["link2"])
        os.symlink(fixture["package_bin"], fixture["link2"])
        _stub_binary(fixture["link"], "1.19.4")
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
    upgrade.official_upgrade = install or (lambda a, t: 0)
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
    real_path = os.environ.get("PATH", "")
    real_test_config = os.environ.get("TEST_CONFIG")
    try:
        _fixture(root)
        home = os.path.join(root, "home")
        config = os.path.join(home, ".config", "opencode")
        os.makedirs(config)
        bin_dir = os.path.join(root, "bin")
        _write(os.path.join(bin_dir, "opencode"), (
            "#!/bin/sh\n"
            f"if [ \"$1\" = \"--version\" ]; then echo 'opencode v{v2.VERSION_PIN}'; exit 0; fi\n"
            "if [ \"$1\" = \"debug\" ]; then echo \"$TEST_CONFIG\"; exit 0; fi\n"
            "exit 1\n"))
        os.chmod(os.path.join(bin_dir, "opencode"), 0o755)
        os.environ["PATH"] = bin_dir + os.pathsep + real_path
        os.environ["TEST_CONFIG"] = config
        upgrade.write_state(root, v2.VERSION_PIN, "canaried")
        payload = upgrade.status_payload(_args(root, home=home))
        assert payload["pinned"] == v2.VERSION_PIN
        assert payload["live"] == v2.VERSION_PIN
        assert payload["install"]["supported"] is True
        assert payload["install"]["config_root"] == config
        assert payload["next"] == "up to date", payload["next"]
    finally:
        os.environ["PATH"] = real_path
        if real_test_config is None:
            os.environ.pop("TEST_CONFIG", None)
        else:
            os.environ["TEST_CONFIG"] = real_test_config
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
                        lambda a, t: calls.append("install") or 0)
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


def test_upgrade_repairs_when_default_is_v1():
    root = _tmp("upgrade-e2e-")
    target = v2.VERSION_PIN
    fixture = _shadow_home(root, target, package_version=target)
    calls = []
    backup = os.path.join(root, "backup")
    os.makedirs(backup)
    real = _patch_apply(backup, _smoke_recorder(calls),
                        lambda a, t: calls.append("install") or 0)
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
                            lambda a, t: calls.append("install") or 0)
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
                        lambda a, t: calls.append("install") or 0)
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
    try:
        upgrade.write_state(root, "2.3.0", "canaried")
        with _path_front(fixture["yarn_bin"]):
            payload = upgrade.status_payload(_args(root, home=fixture["home"]))
        assert payload["next"] == (
            "python3 scripts/opencode_upgrade.py upgrade --to 2.3.0 --resume")
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
    for text, name in ((readme, "README"), (reference, "reference"),
                       (adr, "ADR-0017")):
        assert "opencode2" in text, name
        assert "shadow" in text, name
        assert "upgrade --to" in text and "--apply" in text, name
    assert "both packages publish" in reference or "dual-bin" in reference
    assert "2026-11-09" in adr
    assert "not an automatic rollback" in adr or "no automatic" in adr


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
        args = _args(root, to=v2.VERSION_PIN, v1_bin=v1, default_bin="/tmp/live")
        argv = upgrade.canary_cmd(args, v2.VERSION_PIN)
        assert "--all" in argv and "--version" in argv, argv
        assert argv[argv.index("--version") + 1] == v2.VERSION_PIN
        assert argv[argv.index("--default-version") + 1] == v2.VERSION_PIN
        assert argv[argv.index("--default-bin") + 1] == "/tmp/live"
        assert "--skip-install" in argv
        assert f"v2-canary-{v2.VERSION_PIN}" in " ".join(argv)
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
                        lambda a, t: calls.append("install") or 0)
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
                        lambda a, t: calls.append("install") or 0)
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
    finally:
        _restore_apply(real)
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
