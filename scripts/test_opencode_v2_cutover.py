#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_v2_cutover.py (fail closed).

Proves: drain failures refuse to switch, a non-TTY invocation without
`--execute`/`--drain-acknowledged` cannot switch, the temp-HOME switch is one
atomic link that selects the versioned runtime+config with V1 untouched, an
injected switch failure leaves no partial state, and rollback restores the
V1 link/DB/agent files.

Run: python3 scripts/test_opencode_v2_cutover.py
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
SCRIPT = os.path.join(HERE, "opencode_v2_cutover.py")
sys.path.insert(0, HERE)

import opencode_v2_cutover as cutover  # noqa: E402


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True, text=True)


def _repo(root, name):
    path = os.path.join(root, name)
    os.makedirs(path)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    with open(os.path.join(path, "README.md"), "w") as fh:
        fh.write("x\n")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


def _worktree(root, primary):
    work = os.path.join(root, "work")
    _git(primary, "worktree", "add", "-q", "-b", "feat/x", work)
    with open(os.path.join(work, "file.txt"), "w") as fh:
        fh.write("x\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "x")
    return work


def _sha(path):
    return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def _artifact(root, framework, consumer):
    path = os.path.join(root, "ready.json")
    with open(path, "w") as fh:
        json.dump({"framework_sha": _sha(framework),
                   "consumer_sha": _sha(consumer),
                   "framework_pr_url": "https://example.test/fw/pull/1",
                   "consumer_pr_url": "https://example.test/cs/pull/2"}, fh)
    return path


def _setup(root):
    framework = _repo(root, "framework")
    consumer = _repo(root, "consumer")
    artifact = _artifact(root, framework, consumer)
    home = os.path.join(root, "home")
    os.makedirs(os.path.join(home, ".yarn", "bin"))
    v1_bin = os.path.join(root, "v1", "opencode")
    os.makedirs(os.path.dirname(v1_bin))
    with open(v1_bin, "w") as fh:
        fh.write("#!/bin/sh\necho 1.19.4\n")
    os.chmod(v1_bin, 0o755)
    link = os.path.join(home, ".yarn", "bin", "opencode")
    os.symlink(v1_bin, link)

    prefix = os.path.join(root, "prefix")
    os.makedirs(os.path.join(prefix, "bin"))
    fake = os.path.join(prefix, "bin", "opencode2")
    with open(fake, "w") as fh:
        fh.write("#!/bin/sh\necho 'opencode v2.1.4'\n")
    os.chmod(fake, 0o755)

    config = os.path.join(root, "config")
    os.makedirs(os.path.join(config, "agents"))
    os.makedirs(os.path.join(config, "plugins", "auto-compact-at-threshold"))
    with open(os.path.join(config, "agents", "architect.md"), "w") as fh:
        fh.write("---\nmodel: m\npermissions: []\n---\n")
    with open(os.path.join(config, "plugins", "auto-compact-at-threshold",
                           "index.js"), "w") as fh:
        fh.write("Plugin.define({id:'auto-compact-at-threshold'})\n")
    with open(os.path.join(config, "opencode.jsonc"), "w") as fh:
        json.dump({"agents": {"title": {"model": "m"}}}, fh)

    source_db = os.path.join(root, "source.db")
    con = sqlite3.connect(source_db)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
    con.execute("INSERT INTO session(id) VALUES ('ses_1')")
    con.commit()
    con.close()

    empty = os.path.join(root, "procs.json")
    with open(empty, "w") as fh:
        json.dump([], fh)

    migration = os.path.join(root, "migration-rehearsal.txt")
    with open(migration, "w") as fh:
        fh.write("source_sessions_not_migrated=0\n")

    scratch = os.path.join(root, "scratch")
    os.makedirs(scratch)
    return {
        "framework": framework, "consumer": consumer, "artifact": artifact,
        "home": home, "link": link, "v1_bin": v1_bin, "prefix": prefix,
        "config": config, "source_db": source_db, "procs": empty,
        "scratch": scratch, "migration": migration,
    }


def _args(ctx, manifest, extra=()):
    return [
        "--execute", "--drain-acknowledged",
        "--framework", ctx["framework"], "--consumer", ctx["consumer"],
        "--artifact", ctx["artifact"],
        "--processes-file", ctx["procs"],
        "--source-db", ctx["source_db"],
        "--source-prefix", ctx["prefix"], "--config-source", ctx["config"],
        "--scratch-root", ctx["scratch"], "--home", ctx["home"],
        "--link", ctx["link"], "--manifest", manifest,
        "--migration-evidence", ctx["migration"],
    ] + list(extra)


def _run(argv, use_tty=True):
    if use_tty:
        quoted = " ".join(_q(a) for a in [sys.executable, SCRIPT] + argv)
        return subprocess.run(["script", "-qec", quoted, "/dev/null"],
                              capture_output=True, text=True)
    return subprocess.run([sys.executable, SCRIPT] + argv,
                          capture_output=True, text=True)


def _q(arg):
    return "'" + arg.replace("'", "'\\''") + "'"


def test_drain_failure_refuses_switch():
    root = _tmp("cutover-drain-")
    try:
        ctx = _setup(root)
        procs = os.path.join(root, "live.json")
        with open(procs, "w") as fh:
            json.dump(["12345 opencode.exe serve --service",
                       "12 python3 scripts/dispatch_agent.py"], fh)
        ctx["procs"] = procs
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "drain gate failed" in (r.stdout + r.stderr), (r.stdout, r.stderr)
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
        assert not os.path.exists(manifest)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_non_tty_cannot_switch():
    root = _tmp("cutover-tty-")
    try:
        ctx = _setup(root)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest), use_tty=False)
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "TTY" in (r.stdout + r.stderr), (r.stdout, r.stderr)
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
        # Without --execute/--drain-acknowledged, preflight cannot switch.
        r2 = subprocess.run(
            [sys.executable, SCRIPT, "--preflight",
             "--framework", ctx["framework"], "--consumer", ctx["consumer"],
             "--artifact", ctx["artifact"], "--processes-file", ctx["procs"],
             "--source-db", ctx["source_db"]],
            capture_output=True, text=True)
        assert r2.returncode != 0  # non-TTY preflight is honest
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_atomic_switch_temp_home():
    root = _tmp("cutover-switch-")
    try:
        ctx = _setup(root)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        target = os.readlink(ctx["link"])
        assert target.endswith("opencode-wrapper"), target
        wrapper = open(target).read()
        assert "XDG_CONFIG_HOME=" in wrapper
        assert "2.1.4" in target
        data = json.load(open(manifest))
        assert data["switched"] is True
        assert data["original_link"]["target"] == ctx["v1_bin"]
        # V1 files are byte-identical.
        assert open(ctx["v1_bin"]).read().startswith("#!/bin/sh")
        assert data["config_hashes"], data
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_sha_mismatch_refused():
    root = _tmp("cutover-sha-")
    try:
        ctx = _setup(root)
        with open(ctx["artifact"], "w") as fh:
            json.dump({"framework_sha": "0" * 40,
                       "consumer_sha": "0" * 40,
                       "framework_pr_url": "https://x/fw/1",
                       "consumer_pr_url": "https://x/cs/2"}, fh)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "readiness gate failed" in (r.stdout + r.stderr), (r.stdout, r.stderr)
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_injected_failure_leaves_no_partial_switch():
    root = _tmp("cutover-fail-")
    try:
        ctx = _setup(root)
        # A directory at the link path makes the atomic rename fail.
        os.unlink(ctx["link"])
        os.makedirs(ctx["link"])
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert os.path.isdir(ctx["link"])
        if os.path.exists(manifest):
            data = json.load(open(manifest))
            assert data["switched"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_restores_v1():
    root = _tmp("cutover-rollback-")
    try:
        ctx = _setup(root)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        # Simulate a failed V2 DB and an agent drifted from the snapshot.
        real_db = os.path.join(ctx["home"], ".local", "share", "opencode",
                               "opencode.db")
        os.makedirs(os.path.dirname(real_db))
        with open(real_db, "w") as fh:
            fh.write("failed-v2")
        snapshot = os.path.join(root, "snapshot")
        os.makedirs(snapshot)
        with open(os.path.join(snapshot, "architect.md"), "w") as fh:
            fh.write("original\n")
        with open(os.path.join(snapshot, "hashes.json"), "w") as fh:
            json.dump({"architect.md":
                       cutover.sha256(os.path.join(snapshot, "architect.md"))},
                      fh)
        agents_dir = os.path.join(ctx["home"], ".config", "opencode", "agents")
        os.makedirs(agents_dir)
        with open(os.path.join(agents_dir, "architect.md"), "w") as fh:
            fh.write("drifted\n")
        rb = subprocess.run(
            [sys.executable, SCRIPT, "--rollback", "--manifest", manifest,
             "--home", ctx["home"],
             "--agent-snapshot", snapshot, "--agents-dir", agents_dir],
            capture_output=True, text=True)
        assert rb.returncode == 0, (rb.returncode, rb.stdout, rb.stderr)
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
        assert open(os.path.join(agents_dir, "architect.md")).read() == \
            "original\n"
        con = sqlite3.connect(real_db)
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1
        con.close()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rollback_without_flag_restores_db():
    """AC38: the exact documented rollback command (no --restore-db) restores
    the final V1 DB and leaves its session rows readable."""
    root = _tmp("cutover-rollback-default-")
    try:
        ctx = _setup(root)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        real_db = os.path.join(ctx["home"], ".local", "share", "opencode",
                               "opencode.db")
        os.makedirs(os.path.dirname(real_db))
        with open(real_db, "w") as fh:
            fh.write("failed-v2")
        rb = subprocess.run(
            [sys.executable, SCRIPT, "--rollback", "--manifest", manifest,
             "--home", ctx["home"]],
            capture_output=True, text=True)
        assert rb.returncode == 0, (rb.returncode, rb.stdout, rb.stderr)
        con = sqlite3.connect(real_db)
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 1
        con.close()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_residual_missing_refuses():
    """AC34: absent migration evidence fails closed before the switch."""
    root = _tmp("cutover-migration-missing-")
    try:
        ctx = _setup(root)
        os.unlink(ctx["migration"])
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest))
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "migration residual gate failed" in (r.stdout + r.stderr), r.stdout + r.stderr
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
        assert not os.path.exists(manifest)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_residual_unclassified_refuses():
    """AC34: a positive residual without classification/acceptance refuses."""
    root = _tmp("cutover-migration-unclassified-")
    try:
        ctx = _setup(root)
        with open(ctx["migration"], "w") as fh:
            fh.write("source_sessions_not_migrated=2\n")
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest) +
                 ["--migration-classification",
                  os.path.join(root, "absent-classification.json")])
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "unclassified" in (r.stdout + r.stderr), r.stdout + r.stderr
        assert os.readlink(ctx["link"]) == ctx["v1_bin"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_residual_classification_accepts():
    """AC34: the classified resumable-backfill evidence is accepted."""
    root = _tmp("cutover-migration-classified-")
    try:
        ctx = _setup(root)
        with open(ctx["migration"], "w") as fh:
            fh.write("source_sessions_not_migrated=2\n")
        cls = os.path.join(root, "classification.json")
        with open(cls, "w") as fh:
            json.dump({"residual_count": 2,
                       "classification": "resumable-backfill",
                       "cursor": "ses_cursor",
                       "all_missing_below_cursor": True,
                       "source_untouched": True,
                       "dated": "2026-10-29"}, fh)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest) + ["--migration-classification", cls])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert os.readlink(ctx["link"]).endswith("opencode-wrapper")
        data = json.load(open(manifest))
        assert data["switched"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_owner_acceptance_accepts():
    """AC34: a dated owner acceptance is the alternate positive-residual gate."""
    root = _tmp("cutover-migration-accept-")
    try:
        ctx = _setup(root)
        with open(ctx["migration"], "w") as fh:
            fh.write("source_sessions_not_migrated=2\n")
        acc = os.path.join(root, "acceptance.json")
        with open(acc, "w") as fh:
            json.dump({"owner_acceptance": True, "residual_count": 2,
                       "dated": "2026-10-29", "owner": "owner"}, fh)
        manifest = os.path.join(root, "manifest.json")
        r = _run(_args(ctx, manifest) +
                 ["--migration-acceptance", acc,
                  "--migration-classification",
                  os.path.join(root, "absent-classification.json")])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert os.readlink(ctx["link"]).endswith("opencode-wrapper")
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
