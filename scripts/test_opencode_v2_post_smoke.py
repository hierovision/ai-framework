#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_v2_post_smoke.py (fail closed).

Proves: partial evidence refuses to pass, pre-merge/post-merge ordering is
explicit, a missing consumer readiness artifact fails, a failure routes to
rollback, and the post-merge SHA/corpus check is exact.

Run: python3 scripts/test_opencode_v2_post_smoke.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "opencode_v2_post_smoke.py")


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True, text=True)


def _framework(root, with_plugin=True):
    path = os.path.join(root, "framework")
    os.makedirs(os.path.join(path, "agents"))
    for i in range(17):
        with open(os.path.join(path, "agents", f"agent-{i}.md"), "w") as fh:
            fh.write("---\ndescription: d\nmodel: m\npermissions:\n"
                     "  - action: shell\n    resource: '*'\n    effect: allow\n"
                     "---\n")
    config_root = os.path.join(path, ".scratch", "versioned", "config")
    cfg_dir = os.path.join(config_root, "opencode")
    os.makedirs(cfg_dir, exist_ok=True)
    if with_plugin:
        d = os.path.join(cfg_dir, "plugins", "auto-compact-at-threshold")
        shutil.copytree(os.path.join(REPO, "plugins",
                                     "auto-compact-at-threshold"), d)
        cfg = {"plugins": ["plugins/auto-compact-at-threshold/index.js"]}
    else:
        cfg = {}
    with open(os.path.join(cfg_dir, "opencode.jsonc"), "w") as fh:
        json.dump(cfg, fh)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


def _config_root(path):
    return os.path.join(path, ".scratch", "versioned", "config")


def _fake_bin(root, version="opencode v2.1.4"):
    d = os.path.join(root, "bin")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "opencode")
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n"
                 "if [ \"$1\" = \"plugin\" ]; then\n"
                 "  echo \"auto-compact-at-threshold local "
                 "$XDG_CONFIG_HOME/opencode/plugins/auto-compact-at-threshold/index.js\"\n"
                 "  exit 0\n"
                 "fi\n"
                 f"echo '{version}'\n")
    os.chmod(path, 0o755)
    return path


def _db(root):
    path = os.path.join(root, "sessions.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY)")
    con.execute("INSERT INTO session_v2(id) VALUES ('ses_1')")
    con.commit()
    con.close()
    return path


def _run(args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, SCRIPT] + args, capture_output=True,
                          text=True, env=env)


def test_partial_evidence_refused():
    root = _tmp("smoke-partial-")
    try:
        fw = _framework(root, with_plugin=False)
        binary = _fake_bin(root)
        db = _db(root)
        out = os.path.join(root, "post.json")
        r = _run(["--framework", fw, "--config-root", _config_root(fw),
                  "--default-bin", binary, "--skip-live", "--artifact", out],
                 {"OPENCODE_DB": db})
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "plugin: FAIL" in r.stdout, r.stdout
        data = json.load(open(out))
        assert data["passed"] is False
        assert "rollback" in r.stderr, r.stderr
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_passing_pre_merge_writes_artifact():
    root = _tmp("smoke-pass-")
    try:
        fw = _framework(root)
        binary = _fake_bin(root)
        db = _db(root)
        out = os.path.join(root, "post.json")
        r = _run(["--framework", fw, "--config-root", _config_root(fw),
                  "--default-bin", binary, "--skip-live", "--artifact", out],
                 {"OPENCODE_DB": db})
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        data = json.load(open(out))
        assert data["passed"] is True
        assert data["framework_sha"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_consumer_required_fails_without_artifact():
    root = _tmp("smoke-consumer-")
    try:
        fw = _framework(root)
        binary = _fake_bin(root)
        db = _db(root)
        cs = os.path.join(root, "consumer")
        os.makedirs(cs)
        out = os.path.join(root, "post.json")
        r = _run(["--framework", fw, "--config-root", _config_root(fw),
                  "--consumer", cs, "--default-bin", binary,
                  "--skip-live", "--require-consumer",
                  "--artifact", out,
                  "--consumer-artifact", os.path.join(root, "missing.json")],
                 {"OPENCODE_DB": db})
        assert r.returncode == 1, (r.returncode, r.stdout)
        assert "consumer: FAIL" in r.stdout, r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_post_merge_requires_manifest_and_exact_sha():
    root = _tmp("smoke-postmerge-")
    try:
        fw = _framework(root)
        sha = subprocess.run(["git", "-C", fw, "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        r = _run(["--post-merge", "--framework", fw])
        assert r.returncode == 2, (r.returncode, r.stdout)
        manifest = os.path.join(root, "manifest.json")
        config = os.path.join(root, "config")
        os.makedirs(os.path.join(config, "opencode", "agents"))
        with open(os.path.join(config, "opencode", "agents", "a.md"), "w") as fh:
            fh.write("x")
        with open(manifest, "w") as fh:
            json.dump({"readiness": {"framework_sha": sha},
                       "versioned": {"config_root": config}}, fh)
        r2 = _run(["--post-merge", "--framework", fw, "--manifest", manifest])
        assert r2.returncode == 0, (r2.returncode, r2.stdout, r2.stderr)
        with open(manifest, "w") as fh:
            json.dump({"readiness": {"framework_sha": "0" * 40},
                       "versioned": {"config_root": config}}, fh)
        r3 = _run(["--post-merge", "--framework", fw, "--manifest", manifest])
        assert r3.returncode == 1, (r3.returncode, r3.stdout)
        assert "framework-sha: FAIL" in r3.stdout, r3.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_check_verifies_db_and_agents():
    root = _tmp("smoke-rollback-")
    try:
        binary = _fake_bin(root, version="1.19.4")
        backup = os.path.join(root, "final.db")
        con = sqlite3.connect(backup)
        con.execute("CREATE TABLE session (id TEXT)")
        con.commit()
        con.close()
        snapshot = os.path.join(root, "snapshot")
        os.makedirs(snapshot)
        with open(os.path.join(snapshot, "a.md"), "w") as fh:
            fh.write("agent\n")
        import hashlib
        digest = hashlib.sha256(b"agent\n").hexdigest()
        with open(os.path.join(snapshot, "hashes.json"), "w") as fh:
            json.dump({"a.md": digest}, fh)
        agents = os.path.join(root, "agents")
        os.makedirs(agents)
        with open(os.path.join(agents, "a.md"), "w") as fh:
            fh.write("agent\n")
        manifest = os.path.join(root, "manifest.json")
        with open(manifest, "w") as fh:
            json.dump({"backup": {"path": backup}}, fh)
        r = _run(["--rollback-check", "--manifest", manifest,
                  "--default-bin", binary, "--agent-snapshot", snapshot,
                  "--agents-dir", agents])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "v1-version: PASS" in r.stdout
        assert "db-integrity: PASS" in r.stdout
        assert "v1-agent-hashes: PASS" in r.stdout
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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
