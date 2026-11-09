#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_v2_canary.py (fail closed).

Proves: C5 is the first mutation (a binary invoked before C5 aborts), a
non-scratch/real DB path is refused, credentials never reach evidence, C4 is
a fresh-DB 10/10 gate, and the migration gate reports its fidelity residual
instead of claiming lossless migration.

Run: python3 scripts/test_opencode_v2_canary.py
"""
import argparse
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
SCRIPT = os.path.join(HERE, "opencode_v2_canary.py")
sys.path.insert(0, HERE)

import scratch_cleanup  # noqa: E402

import opencode_v2 as v2  # noqa: E402
import opencode_v2_canary as canary  # noqa: E402

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json
import os
import sqlite3
import sys

args = sys.argv[1:]
scratch = os.environ["V2_TEST_SCRATCH"]
c5 = os.path.join(scratch, "C5.txt")
log = os.path.join(scratch, "invocations.log")
with open(log, "a", encoding="utf-8") as fh:
    fh.write(" ".join(args) + "\n")
if "--version" in args:
    print("opencode v2.2.5")
    sys.exit(0)
if (not os.path.isfile(c5) and args[:1] != ["--version"]
        and os.environ.get("V2_TEST_ALLOW_NO_C5") != "1"):
    print("INVOKED-BEFORE-C5", file=sys.stderr)
    sys.exit(9)
if args[:1] == ["auth"]:
    dump = os.environ.get("V2_TEST_AUTH_DUMP")
    if dump:
        with open(dump, "w", encoding="utf-8") as fh:
            fh.write(sys.stdin.read())
    print("Imported 2 credentials")
    sys.exit(0)
if args[:1] == ["models"]:
    for binding in os.environ.get("V2_TEST_BINDINGS", "").split(","):
        if binding:
            print(binding)
    sys.exit(0)
if args[:1] == ["run"]:
    db = os.environ.get("OPENCODE_DB")
    if db and os.environ.get("V2_TEST_MIGRATE") == "1" and os.path.isfile(db):
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE IF NOT EXISTS session_v2 (id TEXT PRIMARY KEY)")
        skip = set(json.loads(os.environ.get("V2_TEST_SKIP_IDS", "[]")))
        rows = [r[0] for r in con.execute("SELECT id FROM session")]
        for sid in rows:
            if sid not in skip:
                con.execute("INSERT OR IGNORE INTO session_v2(id) VALUES (?)", (sid,))
        con.commit()
        con.close()
    sid = "ses_fake"
    print(json.dumps({"type": "step_start", "sessionID": sid,
                      "part": {"type": "step-start", "sessionID": sid}}))
    print(json.dumps({"type": "text", "sessionID": sid,
                      "part": {"type": "text", "sessionID": sid,
                               "text": "OK"}}))
    print(json.dumps({"type": "step_finish", "sessionID": sid,
                      "part": {"type": "step-finish",
                               "tokens": {"input": 1, "output": 1},
                               "cost": 0.0}}))
    sys.exit(0)
print("{}")
'''


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    scratch_cleanup.prune_test_scratch(base)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _fake_bin(root, name="opencode2"):
    d = os.path.join(root, "bin")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(FAKE_OPENCODE)
    os.chmod(path, 0o755)
    return path


def _source_db(root):
    path = os.path.join(root, "source.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE message (id TEXT, session_id TEXT)")
    for i in range(12):
        con.execute("INSERT INTO session(id) VALUES (?)", (f"ses_{i:03d}",))
        con.execute("INSERT INTO message VALUES (?, ?)", (f"msg_{i}", f"ses_{i:03d}"))
    con.commit()
    con.close()
    return path


def _run(root, args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    env["V2_TEST_SCRATCH"] = os.path.join(root, "ev")
    os.makedirs(env["V2_TEST_SCRATCH"], exist_ok=True)
    return subprocess.run([sys.executable, SCRIPT] + args, capture_output=True,
                          text=True, env=env)


def test_c5_is_first_mutation():
    """AC32: a V2 invocation before C5 aborts; C5 itself never invokes V2."""
    root = _tmp("canary-order-")
    try:
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        r = _run(root, ["--gate", "C5", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert os.path.isfile(os.path.join(out, "C5.txt"))
        assert not os.path.isfile(os.path.join(out, "invocations.log")), \
            "C5 must not invoke V2"
        assert "database_integrity_check=ok" in open(
            os.path.join(out, "C5.txt")).read()
        # A run that skips C5 evidence makes the fake binary abort.
        out2 = os.path.join(root, "ev2")
        r2 = _run(root, ["--gate", "C2", "--scratch-root", out2,
                         "--source-db", src, "--opencode-bin", binary])
        assert r2.returncode != 0, r2.stdout
        assert "C2=FAIL" in open(os.path.join(out2, "C2.txt")).read(), r2.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_forbidden_real_db_path():
    """AC32: the real DB is never an implicit or accepted scratch target."""
    try:
        v2.assert_scratch_db(v2.DEFAULT_DB, os.path.join(REPO, ".scratch"))
        raise AssertionError("real DB should be refused")
    except ValueError:
        pass
    try:
        v2.assert_scratch_db("/tmp/outside.db", os.path.join(REPO, ".scratch"))
        raise AssertionError("non-scratch DB should be refused")
    except ValueError:
        pass


def test_c3_secret_never_persisted():
    """AC33: credential import is isolated and never appears in evidence."""
    root = _tmp("canary-c3-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(os.path.join(home, ".local", "share", "opencode"))
        secret = "super-secret-key-value"
        with open(os.path.join(home, ".local", "share", "opencode",
                               "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": secret}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        bindings = ",".join(sorted(set(
            _agent_bindings().values())))
        env = {"HOME": home, "V2_TEST_BINDINGS": bindings,
               "V2_TEST_ALLOW_NO_C5": "1"}
        r = _run(root, ["--gate", "C3", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary], env)
        assert r.returncode == 0, (r.stdout, r.stderr)
        text = open(os.path.join(out, "C3-real.txt")).read()
        assert secret not in text, "secret leaked into evidence"
        assert "missing_bindings=0" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_c3_current_auth_beats_stale_account():
    """AC33: C3 imports the current auth.json key, not a stale account.json."""
    root = _tmp("canary-c3-stale-account-")
    try:
        home = os.path.join(root, "home")
        state = os.path.join(home, ".local", "share", "opencode")
        os.makedirs(state)
        with open(os.path.join(state, "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "current-key"}}, fh)
        with open(os.path.join(state, "account.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "stale-key"}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        dump = os.path.join(root, "auth-dump.json")
        env = {"HOME": home, "V2_TEST_BINDINGS": ",".join(sorted(set(
                   _agent_bindings().values()))),
               "V2_TEST_ALLOW_NO_C5": "1", "V2_TEST_AUTH_DUMP": dump}
        r = _run(root, ["--gate", "C3", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary], env)
        assert r.returncode == 0, (r.stdout, r.stderr)
        payload = json.load(open(dump))
        keys = [row["value"]["key"] for row in payload]
        assert "current-key" in keys, keys
        assert "stale-key" not in keys, keys
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_c4_fresh_db_ten_runs():
    """AC34: stability starts from zero rows and passes 10/10."""
    root = _tmp("canary-c4-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(os.path.join(home, ".local", "share", "opencode"))
        with open(os.path.join(home, ".local", "share", "opencode",
                               "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "k"}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        r = _run(root, ["--gate", "C4", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"HOME": home, "V2_TEST_ALLOW_NO_C5": "1"})
        assert r.returncode == 0, (r.stdout, r.stderr)
        text = open(os.path.join(out, "C4.txt")).read()
        assert "session_v2_before=0" in text, text
        assert "runs=10" in text, text
        assert "C4=PASS" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_reports_residual():
    """AC34/AC9: an incomplete backfill fails unless a dated acceptance exists."""
    root = _tmp("canary-migration-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(os.path.join(home, ".local", "share", "opencode"))
        with open(os.path.join(home, ".local", "share", "opencode",
                               "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "k"}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        skip = json.dumps(["ses_010", "ses_011"])
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"HOME": home, "V2_TEST_MIGRATE": "1",
                  "V2_TEST_SKIP_IDS": skip, "V2_TEST_ALLOW_NO_C5": "1"})
        assert r.returncode == 1, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_session_rows=12" in text, text
        assert "migrated_source_rows=10" in text, text
        assert "source_sessions_not_migrated=2" in text, text
        assert "target_only_ids=0" in text, text
        assert "migrated_ids_subset_of_source=True" in text, text
        assert "residual_accepted=False" in text, text
        assert "migration=FAIL" in text, text
        assert "requires classification or owner acceptance" in text, text
        assert "source_untouched=True" in text, text
        rehearsal = os.path.join(out, "migration-rehearsal.db")
        assert stat.S_IMODE(os.stat(rehearsal).st_mode) == 0o600
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_residual_acceptance_passes():
    root = _tmp("canary-migration-accept-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(os.path.join(home, ".local", "share", "opencode"))
        with open(os.path.join(home, ".local", "share", "opencode",
                               "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "k"}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "migration-residual-acceptance.json"),
                  "w", encoding="utf-8") as fh:
            json.dump({"version": v2.VERSION_PIN, "residual": 2,
                       "owner": "owner", "date": "2026-11-09"}, fh)
        skip = json.dumps(["ses_010", "ses_011"])
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"HOME": home, "V2_TEST_MIGRATE": "1",
                  "V2_TEST_SKIP_IDS": skip, "V2_TEST_ALLOW_NO_C5": "1"})
        assert r.returncode == 0, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_sessions_not_migrated=2" in text, text
        assert "residual_accepted=True" in text, text
        assert "migration=PASS" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_zero_rows_fails():
    root = _tmp("canary-migration-zero-")
    try:
        home = os.path.join(root, "home")
        os.makedirs(os.path.join(home, ".local", "share", "opencode"))
        with open(os.path.join(home, ".local", "share", "opencode",
                               "auth.json"), "w") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "k"}}, fh)
        binary = _fake_bin(root)
        src = _source_db(root)
        out = os.path.join(root, "ev")
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"HOME": home, "V2_TEST_ALLOW_NO_C5": "1"})
        assert r.returncode == 1, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_session_rows=12" in text, text
        assert "migrated_source_rows=0" in text, text
        assert "zero_migration=True" in text, text
        assert "source_sessions_not_migrated=12" in text, text
        assert "migration=FAIL" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _agent_bindings():
    import re
    bindings = {}
    d = os.path.join(REPO, "agents")
    for name in os.listdir(d):
        if not name.endswith(".md"):
            continue
        raw = open(os.path.join(d, name), encoding="utf-8").read()
        fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
        m = re.search(r"^model:\s*(\S+)\s*$", fm, re.MULTILINE)
        if m:
            bindings[name] = m.group(1)
    return bindings


def test_migration_membership_non_vacuous():
    empty = canary.migration_membership(set(), set())
    assert empty["ok"] is False
    assert empty["zero_migration"] is False
    zero = canary.migration_membership({"ses_1", "ses_2"}, set())
    assert zero["ok"] is False
    assert zero["zero_migration"] is True
    full = canary.migration_membership(
        {"ses_1", "ses_2"}, {"ses_1", "ses_2", "ses_run"},
        run_ids={"ses_run"})
    assert full["ok"] is True
    assert full["migrated"] == 2
    assert full["missing"] == set()
    assert full["phantom"] == set()
    assert full["run"] == 1
    partial = canary.migration_membership({"ses_1", "ses_2"}, {"ses_1"})
    assert partial["ok"] is True
    assert partial["missing"] == {"ses_2"}
    phantom = canary.migration_membership(
        {"ses_1"}, {"ses_1", "ses_phantom"})
    assert phantom["ok"] is False
    assert phantom["phantom"] == {"ses_phantom"}


def test_exact_version_helpers():
    assert canary.exact_version("opencode v2.2.6") == "2.2.6"
    assert canary.exact_version("v2.2.6") == "2.2.6"
    assert canary.exact_version("2.2.6") == "2.2.6"
    assert canary.exact_version("opencode v2.2.60") == "2.2.60"
    assert canary.exact_version("opencode v2.2.6-rc") is None
    assert canary.exact_version("1.19.4") == "1.19.4"
    assert canary.exact_version("v1.19.4") == "1.19.4"
    assert canary.exact_version("1.19.40") == "1.19.40"
    assert canary.exact_version("1.19.40") != "1.19.4"
    assert canary.exact_version("build 1.19.4") is None
    assert canary.api_version('{"version":"2.2.60"}') == "2.2.60"
    assert canary.api_version('{"version":"2.2.6"}') == "2.2.6"


def test_c7_asserts_markers():
    root = _tmp("canary-c7-")
    real_run = canary.v2_run
    real_assert = canary.v2.assert_scratch_db
    real_port = canary.free_port
    canary.v2.assert_scratch_db = lambda *args, **kwargs: None
    canary.free_port = lambda: 12345
    try:
        def respond(plugin_marker=True):
            def fake(_args, _env, argv, timeout=180):
                if argv[:2] == ["debug", "config"]:
                    return subprocess.CompletedProcess(
                        argv, 0, "canary-marker", "")
                if argv[:2] == ["plugin", "list"]:
                    stdout = "canary-plugin" if plugin_marker else ""
                    return subprocess.CompletedProcess(argv, 0, stdout, "")
                if argv[:3] == ["api", "GET", "/api/agent"]:
                    return subprocess.CompletedProcess(
                        argv, 0, "canary-marker", "")
                return subprocess.CompletedProcess(argv, 0, "", "")
            return fake
        canary.v2_run = respond(True)
        ok, text = canary.gate_c7(argparse.Namespace(scratch_root=root))
        assert ok is True, text
        assert "marker_plugin_present=True" in text
        assert "C7=PASS" in text
        canary.v2_run = respond(False)
        ok, text = canary.gate_c7(argparse.Namespace(scratch_root=root))
        assert ok is False, text
        assert "marker_plugin_present=False" in text
        assert "C7=FAIL" in text
    finally:
        canary.v2_run = real_run
        canary.v2.assert_scratch_db = real_assert
        canary.free_port = real_port
        shutil.rmtree(root, ignore_errors=True)


def test_c1_probe_timeout_is_named_failure():
    root = _tmp("canary-c1-timeout-")
    real_run = canary.subprocess.run
    try:
        prefix = os.path.join(root, "prefix")
        os.makedirs(os.path.join(prefix, "bin"))
        with open(os.path.join(prefix, "bin", "opencode2"), "w") as fh:
            fh.write("#!/bin/sh\n")
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 30)
        canary.subprocess.run = timeout
        args = argparse.Namespace(
            scratch_root=root, prefix=prefix, skip_install=True,
            version=v2.VERSION_PIN,
            default_bin=os.path.join(root, "default"),
            default_version=v2.VERSION_PIN)
        ok, detail = canary.gate_c1(args)
        assert ok is False
        assert "version probe failed" in detail
        text = open(os.path.join(root, "C1.txt")).read()
        assert "version_probe_error=TimeoutExpired" in text
        assert "C1=FAIL" in text
    finally:
        canary.subprocess.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_c1_install_timeout_is_named_failure():
    root = _tmp("canary-c1-install-timeout-")
    real_run = canary.subprocess.run
    try:
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 600)
        canary.subprocess.run = timeout
        args = argparse.Namespace(
            scratch_root=root, prefix=os.path.join(root, "prefix"),
            skip_install=False, version=v2.VERSION_PIN,
            default_bin=os.path.join(root, "default"),
            default_version=v2.VERSION_PIN)
        ok, detail = canary.gate_c1(args)
        assert ok is False
        assert "install probe failed" in detail
        text = open(os.path.join(root, "C1.txt")).read()
        assert "install_error=TimeoutExpired" in text
        assert "C1=FAIL" in text
    finally:
        canary.subprocess.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def _write_exec(path, output):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\necho '" + output + "'\n")
    os.chmod(path, 0o755)


def test_c1_rejects_default_version_change():
    root = _tmp("canary-c1-default-change-")
    try:
        prefix = os.path.join(root, "prefix")
        candidate = os.path.join(prefix, "bin", "opencode2")
        _write_exec(candidate, f"opencode v{v2.VERSION_PIN}")
        default = os.path.join(root, "default")
        _write_exec(default, "opencode v2.2.5")
        args = argparse.Namespace(
            scratch_root=root, prefix=prefix, skip_install=True,
            version=v2.VERSION_PIN, default_bin=default,
            default_version=v2.VERSION_PIN)
        ok, detail = canary.gate_c1(args)
        assert ok is False
        assert "C1=FAIL" in detail
        _write_exec(default, f"opencode v{v2.VERSION_PIN}")
        ok, detail = canary.gate_c1(args)
        assert ok is True, detail
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_c6_version_probe_timeout_is_named_failure():
    root = _tmp("canary-c6-timeout-")
    real_run = canary.subprocess.run
    try:
        prefix = os.path.join(root, "v1")
        _write_exec(os.path.join(prefix, "bin", "opencode"), "1.19.4")

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 30)

        canary.subprocess.run = timeout
        ok, detail = canary.gate_c6(
            argparse.Namespace(scratch_root=root, v1_prefix=prefix))
        assert ok is False
        assert "V1 version probe failed" in detail
        text = open(os.path.join(root, "C6.txt")).read()
        assert "v1_version_probe_error=TimeoutExpired" in text
        assert "C6=FAIL" in text
    finally:
        canary.subprocess.run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_default_bin_path_is_explicit_link():
    root = _tmp("canary-default-link-")
    fake_home = os.path.join(root, "home")
    link = os.path.join(fake_home, ".yarn", "bin", "opencode")
    _write_exec(link, f"opencode v{v2.VERSION_PIN}")
    path_dir = os.path.join(root, "pathbin")
    _write_exec(os.path.join(path_dir, "opencode"), "1.19.4")
    real_home = os.environ.get("HOME")
    real_path = os.environ.get("PATH", "")
    os.environ["HOME"] = fake_home
    os.environ["PATH"] = path_dir + os.pathsep + real_path
    try:
        assert canary.default_bin_path() == link
        proc = subprocess.run([canary.default_bin_path(), "--version"],
                              capture_output=True, text=True)
        assert canary.exact_version(proc.stdout) == v2.VERSION_PIN
    finally:
        if real_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = real_home
        os.environ["PATH"] = real_path
        shutil.rmtree(root, ignore_errors=True)


def test_usage_example_documents_v1_default():
    doc = canary.__doc__ or ""
    assert "--default-version 1.19.4" in doc
    assert "--default-bin" in doc
    assert "--v1-prefix" in doc


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
