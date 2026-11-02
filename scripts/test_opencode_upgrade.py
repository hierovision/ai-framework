#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_upgrade.py (fail closed).

Proves the offline pin seams, the prepare dry-run/real update, the plan
compatibility matrix + breaking notes, status topology, the commit-visible
canary gate, apply consent + auto-rollback, drain waiting, pruning, and the
generated PR/gh environment.

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


def _evidence(repo, version="2.2.5", residual=0, omit=()):
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


def _fixture(repo, version="2.2.5", opentui="0.8.1"):
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
    for name, has_tui in (("delegation-observer", True),
                          ("delegation-sentinel", True)):
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
        "prefix": None, "source_prefix": None, "source_db": None,
        "scratch_root": None, "processes_file": None, "final_backup": None,
        "config_source": None, "manifest": None, "v1_bin": None,
        "plugin_json": None, "releases_file": None, "opentui": None,
        "latest": None, "refresh": False, "remote": False, "pins_only": True,
        "pr": False, "json": False, "dry_run": False, "open_pr": False,
        "skip_install": False, "skip_canary": False,
        "allow_pending_canary": False, "wait_for_drain": False,
        "stop_service": False, "timeout": 1, "interval": 0,
        "force": False, "resume": False, "apply": False, "keep": 1,
        "drain_acknowledged": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_check_pins_clean_and_stale():
    root = _tmp("upgrade-pins-")
    try:
        _fixture(root)
        results = upgrade.check_seams(root, "2.2.5", "0.8.1")
        assert all(ok for _path, ok, _detail in results), results
        _write(os.path.join(root, "scripts", "opencode_v2.py"),
               'VERSION_PIN = "2.2.4"\n')
        results = upgrade.check_seams(root, "2.2.5", "0.8.1")
        assert any(not ok and path.endswith("opencode_v2.py")
                   for path, ok, _detail in results), results
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_dry_run_and_update():
    root = _tmp("upgrade-prepare-")
    real_run = upgrade.run
    try:
        _fixture(root)
        _evidence(root, "2.3.0")
        before = open(os.path.join(root, "README.md")).read()
        upgrade.run = lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 0 if argv[:2] == ["npm", "install"] else 1, "", "")
        args = _args(root, to="2.3.0", opentui="0.8.2", plugin_json=_json_file(
            root, {"@opencode/plugin": "2.3.0",
                   "@opentui/core": ">=0.8.0",
                   "@opentui/solid": ">=0.8.0",
                   "solid-js": ">=1.9.0"}))
        with contextlib.redirect_stdout(io.StringIO()):
            assert upgrade.prepare(_args(**{**vars(args), "dry_run": True})) == 0
        assert open(os.path.join(root, "README.md")).read() == before
        with contextlib.redirect_stdout(io.StringIO()):
            assert upgrade.prepare(args) == 0
        text = open(os.path.join(root, "README.md")).read()
        assert "OpenCode V2 `2.3.0`" in text, text
        assert "2.2.5" not in text, text
        results = upgrade.check_seams(root, "2.3.0", "0.8.2")
        assert all(ok for _path, ok, _detail in results), results
        assert "version pin 2.3.0" in open(os.path.join(
            root, "docs", "ADRs", "ADR-0014-opencode-v2-upgrade.md")).read()
        # A second prepare is a no-op: no seam changes remain.
        assert upgrade.seam_changes(root, "2.3.0", "0.8.2") == []
    finally:
        upgrade.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def _json_file(root, payload, name="fixture.json"):
    path = os.path.join(root, name)
    _write(path, json.dumps(payload))
    return path


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
        assert matrix["CLI"][1:] == ["2.2.5", "2.3.0"]
        assert matrix["@opentui/core"][2] == "0.8.2"
        assert data["breaking"][0][0] == "2.3.0"
        assert "change A" in data["breaking"][0][1]
        assert data["seams"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_status_topology():
    root = _tmp("upgrade-status-")
    try:
        _fixture(root)
        home = os.path.join(root, "home")
        config = os.path.join(home, ".local", "lib", "opencode", "2.1.4",
                              "config")
        os.makedirs(config)
        wrapper = os.path.join(home, ".local", "lib", "opencode", "2.1.4",
                               "opencode-wrapper")
        _write(wrapper, f'#!/bin/sh\nexport XDG_CONFIG_HOME="{config}"\n'
                        f'exec /bin/echo "opencode v2.1.4"\n')
        os.chmod(wrapper, 0o755)
        link = os.path.join(home, ".yarn", "bin", "opencode")
        os.makedirs(os.path.dirname(link))
        os.symlink(wrapper, link)
        v1 = os.path.join(home, ".config", "yarn", "global", "node_modules",
                          "opencode-ai", "package.json")
        _write(v1, '{"version": "1.19.4"}\n')
        payload = upgrade.status_payload(_args(root, home=home, link=link))
        assert payload["pinned"] == "2.2.5"
        assert payload["live"] == "2.1.4"
        assert payload["install"]["config_root"] == config
        assert payload["install"]["v1_rollback"] == "1.19.4"
        assert payload["canary"]["ok"] is True
        assert "apply" in payload["next"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_pr_requires_canary():
    root = _tmp("upgrade-pr-")
    try:
        _fixture(root)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert upgrade.check(_args(root, pr=True)) == 0
        _write(os.path.join(root, ".scratch", "v2-canary-2.2.5", "C4.txt"),
               "C4=FAIL\n")
        assert upgrade.check(_args(root, pr=True)) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_requires_consent_and_rolls_back():
    root = _tmp("upgrade-apply-")
    real_checks = upgrade.cutover.upgrade_checks
    real_execute = upgrade.cutover.upgrade_execute
    real_rollback = upgrade.cutover.rollback
    real_verify = upgrade.verify_live
    calls = []
    try:
        _fixture(root)
        home, link = upgrade.live_paths(_args(root))
        args = _args(root, to="2.2.5", skip_canary=True,
                     manifest=os.path.join(root, "manifest.json"),
                     drain_acknowledged=False)
        assert upgrade.apply(args) == 2
        args.drain_acknowledged = True
        upgrade.cutover.upgrade_checks = lambda ns: (
            [("drain", True, "drained"), ("tty", True, "interactive")],
            ns.home, ns.link, "2.1.4")

        def fake_execute(ns):
            upgrade.write_json(ns.manifest, {
                "switched": True, "from_version": "2.1.4",
                "version": "2.2.5",
                "versioned": {"config_root": os.path.join(root, "cfg")}})
            calls.append("execute")
            return 0

        upgrade.cutover.upgrade_execute = fake_execute
        upgrade.cutover.rollback = lambda ns: calls.append(("rollback",
                                                           ns.manifest)) or 0
        upgrade.verify_live = lambda *a, **k: [
            ("binary", False, "forced failure")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            rc = upgrade.apply(args)
        assert rc == 1, out.getvalue()
        assert "execute" in calls and any(
            isinstance(c, tuple) and c[0] == "rollback" for c in calls), calls
        assert "ROLLED BACK" in out.getvalue()
    finally:
        upgrade.cutover.upgrade_checks = real_checks
        upgrade.cutover.upgrade_execute = real_execute
        upgrade.cutover.rollback = real_rollback
        upgrade.verify_live = real_verify
        shutil.rmtree(root, ignore_errors=True)


def test_wait_for_drain():
    root = _tmp("upgrade-drain-")
    real_check = upgrade.cutover.check_drain
    real_busy = upgrade.busy_sessions
    try:
        seq = [(False, "live"), (False, "live"), (True, "drained")]

        def fake_check(_args):
            return seq.pop(0) if seq else (True, "drained")

        upgrade.cutover.check_drain = fake_check
        upgrade.busy_sessions = lambda _link: []
        ok, detail = upgrade.wait_for_drain(
            _args(root, timeout=2, interval=0), "opencode")
        assert ok and detail == "drained"
    finally:
        upgrade.cutover.check_drain = real_check
        upgrade.busy_sessions = real_busy
        shutil.rmtree(root, ignore_errors=True)


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
        assert "v2-canary-2.0.0" not in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_upgrade_resume_skips_completed_stages():
    root = _tmp("upgrade-resume-")
    real = (upgrade.plan, upgrade.canary, upgrade.prepare)
    calls = []
    try:
        _fixture(root)
        upgrade.write_state(root, "2.3.0", "canaried")
        upgrade.plan = lambda args: calls.append("plan") or 0
        upgrade.canary = lambda args: calls.append("canary") or 0
        upgrade.prepare = lambda args: calls.append("prepare") or 0
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
        upgrade.plan, upgrade.canary, upgrade.prepare = real
        shutil.rmtree(root, ignore_errors=True)


def test_ci_pin_is_derived_from_adapter():
    for rel in (".github/workflows/eval-behavioral.yml",
                ".github/workflows/eval-per-change.yml"):
        text = open(os.path.join(REPO, rel), encoding="utf-8").read()
        assert "print(opencode_v2.VERSION_PIN)" in text, rel
        assert 'OPENCODE_VERSION: "' not in text, rel


def test_gh_env_and_pr_body():
    env = upgrade.gh_env()
    assert env["GH_CONFIG_DIR"].endswith("/.config/gh"), env
    body = upgrade.pr_body("2.3.0", "0.8.2", {
        "gates": {"C1": "PASS", "C8": "PASS"}, "residual": 0},
        [("2.3.0", "- breaking")])
    assert "2.3.0" in body and "C1=PASS" in body
    assert "opencode_upgrade.py apply --to 2.3.0" in body


def test_canary_cmd_exact_args():
    root = _tmp("upgrade-canary-")
    try:
        _fixture(root)
        v1 = os.path.join(root, "v1", "opencode")
        _write(v1, "#!/bin/sh\necho 1.19.4\n")
        os.chmod(v1, 0o755)
        argv = upgrade.canary_cmd(_args(root, to="2.2.5", v1_bin=v1), "2.2.5")
        text = " ".join(argv)
        assert "--all" in argv and "--version" in argv, argv
        assert argv[argv.index("--version") + 1] == "2.2.5"
        assert "--skip-install" in argv
        assert "--prefix" in argv and "--scratch-root" in argv
        assert "v2-canary-2.2.5" in text
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
