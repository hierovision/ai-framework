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
sys.path.insert(0, HERE)

import scratch_cleanup  # noqa: E402
import opencode_v2 as v2  # noqa: E402
import opencode_v2_post_smoke as post_smoke  # noqa: E402


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    scratch_cleanup.prune_test_scratch(base)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True, text=True)


def _framework(root, with_plugin=True,
               plugin_spec="./plugins/auto-compact-at-threshold"):
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
        cfg = {"plugins": [plugin_spec]}
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


def _fake_bin(root, version=None):
    """Stub the V2 CLI: --version plus a standalone loader log on `run`.

    The stubbed version tracks `VERSION_PIN` so a pin bump cannot silently
    leave this fixture asserting the previous version.

    STUB_LOADER selects the loader evidence shape: pass (default), absent,
    failed, wrong, or untagged (right id, marker without this probe's token).
    All shapes exit non-zero after the plugin phase because the probe uses an
    unavailable model; only the captured stderr is asserted.
    """
    version = version or f"opencode v{v2.VERSION_PIN}"
    d = os.path.join(root, "bin")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "opencode")
    agent_rows = ",".join(f'{{"id":"agent-{i}"}}' for i in range(17))
    with open(path, "w") as fh:
        fh.write(f"""#!/bin/sh
if [ "$1" = "--version" ]; then
  echo '{version}'
  exit 0
fi
if [ "$1" = "api" ] && [ "$2" = "GET" ] && [ "$3" = "/api/agent" ]; then
  echo '{{"data":[{agent_rows},{{"id":"builtin"}}]}}'
  exit 0
fi
if [ "$1" = "run" ]; then
  cfg="$XDG_CONFIG_HOME/opencode/plugins/auto-compact-at-threshold"
  case "$STUB_LOADER" in
    absent)
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=INFO msg="loading plugin" id=/other/plugin entrypoint=file:///other/plugin/index.js' >&2
      ;;
    failed)
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=INFO msg="loading plugin" id='"$cfg"' entrypoint=file://'"$cfg"'/index.js' >&2
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=WARN message="failed to load plugin" target=plugins/auto-compact-at-threshold cause=NpmInstallFailedError' >&2
      ;;
    wrong)
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=INFO msg="loading plugin" id=/tmp/not-the-plugin entrypoint=file:///tmp/not-the-plugin/index.js' >&2
      printf '%s\\n' '{{"service":"auto-compact-at-threshold","level":"info","message":"auto-compact-at-threshold initialized","extra":{{"version":"2.2.5"}}}}' >&2
      ;;
    untagged)
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=INFO msg="loading plugin" id='"$cfg"' entrypoint=file://'"$cfg"'/index.js' >&2
      printf '%s\\n' '{{"service":"auto-compact-at-threshold","level":"info","message":"auto-compact-at-threshold initialized","extra":{{"version":"2.2.5"}}}}' >&2
      ;;
    *)
      printf '%s\\n' 'timestamp=2026-10-29T00:00:00.000Z level=INFO msg="loading plugin" id='"$cfg"' entrypoint=file://'"$cfg"'/index.js' >&2
      printf '%s\\n' '{{"service":"auto-compact-at-threshold","level":"info","message":"auto-compact-at-threshold initialized","extra":{{"version":"2.2.5","probe":"'"$OPENCODE_LOADER_PROBE_TOKEN"'"}}}}' >&2
      ;;
  esac
  exit 1
fi
echo '{version}'
""")
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


def _plugin_failure(loader, plugin_spec="./plugins/auto-compact-at-threshold"):
    """Run a pre-merge smoke whose loader evidence is `loader`; return the run."""
    root = _tmp(f"smoke-loader-{loader}-")
    try:
        fw = _framework(root, plugin_spec=plugin_spec)
        binary = _fake_bin(root)
        db = _db(root)
        out = os.path.join(root, "post.json")
        r = _run(["--framework", fw, "--config-root", _config_root(fw),
                  "--default-bin", binary, "--skip-live", "--artifact", out],
                 {"OPENCODE_DB": db, "STUB_LOADER": loader})
        return r, json.load(open(out)) if os.path.isfile(out) else None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_loader_log_without_marker_fails():
    """N1: the runtime probe alone is insufficient — V2's loader log must
    name this plugin and carry its startup marker."""
    r, data = _plugin_failure("absent")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "plugin: FAIL" in r.stdout, r.stdout
    assert "loader" in r.stdout.lower(), r.stdout
    assert data and data["passed"] is False, data


def test_loader_failure_line_fails():
    """N1: a `failed to load plugin` line is a hard failure even when a
    loading line is present."""
    r, _ = _plugin_failure("failed")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "plugin: FAIL" in r.stdout, r.stdout
    assert "failed to load" in r.stdout.lower(), r.stdout


def test_loader_marker_for_wrong_plugin_fails():
    """N1: a marker is not enough; the loaded id must be the versioned plugin."""
    r, _ = _plugin_failure("wrong")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "plugin: FAIL" in r.stdout, r.stdout
    assert "wrong plugin" in r.stdout.lower() or "did not load" in r.stdout.lower(), \
        r.stdout


def test_loader_marker_from_untagged_copy_fails():
    """N1: the marker must be attributed to this probe. A correctly named
    loader line plus the static marker text from a different plugin copy
    (no per-run token) must fail."""
    r, _ = _plugin_failure("untagged")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "plugin: FAIL" in r.stdout, r.stdout
    assert "not attributed" in r.stdout.lower(), r.stdout


def test_bare_plugin_wiring_is_rejected():
    """N1: a bare `plugins/...` spec is an npm package spec in V2, not a local
    directory; the versioned config must wire `./plugins/...`."""
    r, _ = _plugin_failure("pass", plugin_spec="plugins/auto-compact-at-threshold")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "plugin: FAIL" in r.stdout, r.stdout
    assert "./plugins/" in r.stdout or "local" in r.stdout.lower(), r.stdout


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


def _stub(root, name, output):
    path = os.path.join(root, "bin", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\nprintf '%s\\n' " + json.dumps(output) + "\n")
    os.chmod(path, 0o755)
    return path


def test_check_agents_live_tolerates_extras_and_flags_missing():
    root = _tmp("postsmoke-agents-live-")
    try:
        expected = sorted(name[:-3] for name in os.listdir(
            os.path.join(REPO, "agents")) if name.endswith(".md"))
        ids = expected + ["builtin", "new-agent"]
        binary = _stub(root, "opencode",
                       json.dumps({"data": [{"id": i} for i in ids]}))
        ok, detail = post_smoke.check_agents_live(binary, REPO)
        assert ok is True, detail
        assert "missing=[]" in detail
        missing = expected[0]
        ids = expected[1:] + ["builtin"]
        binary = _stub(root, "opencode2",
                       json.dumps({"data": [{"id": i} for i in ids]}))
        ok, detail = post_smoke.check_agents_live(binary, REPO)
        assert ok is False
        assert missing in detail
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_version_is_exact():
    root = _tmp("postsmoke-version-")
    try:
        long_version = _stub(root, "long", f"opencode v{v2.VERSION_PIN}0")
        ok, detail = post_smoke.check_version(long_version)
        assert ok is False, detail
        assert detail != v2.VERSION_PIN
        exact = _stub(root, "exact", f"opencode v{v2.VERSION_PIN}")
        ok, detail = post_smoke.check_version(exact)
        assert ok is True, detail
        assert detail == v2.VERSION_PIN
        bare = _stub(root, "bare", v2.VERSION_PIN)
        assert post_smoke.check_version(bare)[0] is True
        v_form = _stub(root, "vform", f"v{v2.VERSION_PIN}")
        assert post_smoke.check_version(v_form)[0] is True
        embedded = _stub(root, "embedded", f"build {v2.VERSION_PIN}")
        assert post_smoke.check_version(embedded)[0] is False
        prerelease = _stub(root, "rc", f"opencode v{v2.VERSION_PIN}-rc")
        assert post_smoke.check_version(prerelease)[0] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_run_spawn_error_returns_completed_process():
    result = post_smoke.run(["definitely-not-a-real-binary-xyz"])
    assert hasattr(result, "returncode")
    assert result.returncode != 0
    assert "FileNotFoundError" in (result.stderr or "")


def test_check_agents_corpus_derived_live():
    root = _tmp("postsmoke-agents-corpus-")
    try:
        fw = os.path.join(root, "framework")
        os.makedirs(os.path.join(fw, "agents"))
        for name in ("alpha", "beta"):
            with open(os.path.join(fw, "agents", name + ".md"), "w") as fh:
                fh.write("---\ndescription: d\nmodel: m\npermissions: []\n---\n")
        cs = os.path.join(root, "consumer")
        os.makedirs(os.path.join(cs, ".opencode", "agents"))
        with open(os.path.join(cs, ".opencode", "agents", "gamma.md"),
                  "w") as fh:
            fh.write("---\ndescription: d\nmodel: m\npermissions: []\n---\n")
        live = _stub(root, "live", json.dumps({"data": [
            {"id": "alpha"}, {"id": "beta"}, {"id": "gamma"},
            {"id": "builtin"}]}))
        ok, detail = post_smoke.check_agents(fw, cs, live)
        assert ok is True, detail
        assert "missing=[]" in detail
        missing = _stub(root, "missing", json.dumps({"data": [
            {"id": "alpha"}, {"id": "builtin"}]}))
        ok, detail = post_smoke.check_agents(fw, cs, missing)
        assert ok is False
        assert "beta" in detail and "gamma" in detail
        ok, detail = post_smoke.check_agents(fw, cs)
        assert ok is True
        assert "framework=2" in detail and "consumer=1" in detail
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_check_rejects_v1_superstring():
    root = _tmp("smoke-rollback-super-")
    try:
        binary = _fake_bin(root, version="1.19.40")
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
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "v1-version: FAIL" in r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_check_handles_spawn_error():
    root = _tmp("smoke-rollback-spawn-")
    try:
        snapshot = os.path.join(root, "snapshot")
        os.makedirs(snapshot)
        agents = os.path.join(root, "agents")
        os.makedirs(agents)
        manifest = os.path.join(root, "manifest.json")
        with open(manifest, "w") as fh:
            json.dump({"backup": {"path": os.path.join(root, "missing.db")}},
                      fh)
        r = _run(["--rollback-check", "--manifest", manifest,
                  "--default-bin", "/definitely/not/opencode",
                  "--agent-snapshot", snapshot, "--agents-dir", agents])
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "v1-version: FAIL FileNotFoundError" in r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_version_spawn_error_is_named():
    ok, detail = post_smoke.check_version("/definitely/not/opencode")
    assert ok is False
    assert "FileNotFoundError" in detail


def test_default_bin_path_is_explicit_link():
    root = _tmp("postsmoke-default-link-")
    fake_home = os.path.join(root, "home")
    link = os.path.join(fake_home, ".yarn", "bin", "opencode")
    _stub(os.path.join(fake_home, ".yarn"), "opencode",
          f"opencode v{v2.VERSION_PIN}")
    path_dir = os.path.join(root, "pathbin")
    _stub(path_dir, "opencode", "1.19.4")
    real_home = os.environ.get("HOME")
    real_path = os.environ.get("PATH", "")
    os.environ["HOME"] = fake_home
    os.environ["PATH"] = path_dir + os.pathsep + real_path
    try:
        assert post_smoke.default_bin_path() == link
        ok, detail = post_smoke.check_version(link)
        assert ok is True, detail
    finally:
        if real_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = real_home
        os.environ["PATH"] = real_path
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
