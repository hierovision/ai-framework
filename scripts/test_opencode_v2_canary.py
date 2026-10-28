#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_v2_canary.py (fail closed).

Proves: C5 is the first mutation (a binary invoked before C5 aborts), a
non-scratch/real DB path is refused, credentials never reach evidence, C4 is
a fresh-DB 10/10 gate, and the migration gate reports its fidelity residual
instead of claiming lossless migration.

Run: python3 scripts/test_opencode_v2_canary.py
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
SCRIPT = os.path.join(HERE, "opencode_v2_canary.py")
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

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
    print("opencode v2.1.4")
    sys.exit(0)
if (not os.path.isfile(c5) and args[:1] != ["--version"]
        and os.environ.get("V2_TEST_ALLOW_NO_C5") != "1"):
    print("INVOKED-BEFORE-C5", file=sys.stderr)
    sys.exit(9)
if args[:1] == ["auth"]:
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
    """AC34/AC9: an incomplete backfill is reported, never called lossless."""
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
        assert r.returncode == 0, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_sessions_not_migrated=2" in text, text
        assert "requires classification or owner acceptance" in text, text
        assert "source_untouched=True" in text, text
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
