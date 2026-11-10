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
if args[:2] == ["service", "set"]:
    sys.exit(0)
if args[:2] == ["service", "start"]:
    mode = os.environ.get("V2_TEST_MIGRATION", "complete")
    if mode == "crash":
        print("fake service start failed", file=sys.stderr)
        sys.exit(7)
    db = os.environ.get("OPENCODE_DB")
    if db and os.path.isfile(db):
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, "
                    "value TEXT NOT NULL, time_created INTEGER NOT NULL, "
                    "time_updated INTEGER NOT NULL)")
        if mode != "timeout":
            con.execute("CREATE TABLE IF NOT EXISTS session_v2 "
                        "(id TEXT PRIMARY KEY)")
            skip = set(json.loads(os.environ.get("V2_TEST_SKIP_IDS", "[]")))
            rows = [r[0] for r in con.execute("SELECT id FROM session")]
            if mode != "noop":
                for sid in rows:
                    if sid not in skip:
                        con.execute("INSERT OR IGNORE INTO session_v2(id) "
                                    "VALUES (?)", (sid,))
            value = '{"phase":"completed"}'
        else:
            value = '{"phase":"sessions"}'
        now = 1
        con.execute("INSERT INTO kv(key,value,time_created,time_updated) "
                    "VALUES ('migration.v1-v2',?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                    "time_updated=excluded.time_updated",
                    (value, now, now))
        con.commit()
        con.close()
    sys.exit(0)
if args[:2] == ["service", "stop"]:
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


def _source_db(root, baseline_ids=(), completed=False):
    path = os.path.join(root, "source.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE message (id TEXT, session_id TEXT)")
    for i in range(12):
        con.execute("INSERT INTO session(id) VALUES (?)", (f"ses_{i:03d}",))
        con.execute("INSERT INTO message VALUES (?, ?)", (f"msg_{i}", f"ses_{i:03d}"))
    if baseline_ids:
        con.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY)")
        for sid in baseline_ids:
            con.execute("INSERT INTO session_v2(id) VALUES (?)", (sid,))
    con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                "time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL)")
    phase = '{"phase":"completed"}' if completed else '{"phase":"sessions"}'
    con.execute("INSERT INTO kv(key,value,time_created,time_updated) "
                "VALUES ('migration.v1-v2',?,1,1)", (phase,))
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


def _migration_args(root, source):
    return argparse.Namespace(
        scratch_root=root, source_db=source, opencode_bin="x",
        version=v2.VERSION_PIN)


def test_migration_resume_imports_all_and_excludes_baseline():
    """The gate re-arms a completed cursor and proves V1 + V2 baseline rows."""
    root = _tmp("canary-migration-resume-")
    try:
        binary = _fake_bin(root)
        src = _source_db(root, baseline_ids=("ses_pre001", "ses_pre002"),
                         completed=True)
        out = os.path.join(root, "ev")
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"V2_TEST_ALLOW_NO_C5": "1", "V2_TEST_MIGRATION": "complete"})
        assert r.returncode == 0, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_session_rows=12" in text, text
        assert "source_v2_baseline_rows=2" in text, text
        assert "source_v2_baseline_only_rows=2" in text, text
        assert "target_session_rows=14" in text, text
        assert "migrated_source_rows=12" in text, text
        assert "source_sessions_not_migrated=0" in text, text
        assert "target_only_ids=0" in text, text
        assert "zero_migration=False" in text, text
        assert "migration_armed=True" in text, text
        assert "migration_phase=completed" in text, text
        assert "migration_timed_out=False" in text, text
        assert "migration=PASS" in text, text
        rehearsal = os.path.join(out, "migration-rehearsal.db")
        assert stat.S_IMODE(os.stat(rehearsal).st_mode) == 0o600
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_missing_row_fails_without_acceptance():
    """A completed phase with a missing V1 row is a hard failure, no residual."""
    root = _tmp("canary-migration-missing-")
    try:
        binary = _fake_bin(root)
        src = _source_db(root, completed=True)
        out = os.path.join(root, "ev")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "migration-residual-acceptance.json"),
                  "w", encoding="utf-8") as fh:
            json.dump({"version": v2.VERSION_PIN, "residual": 1,
                       "owner": "owner", "date": "2026-11-10"}, fh)
        skip = json.dumps(["ses_011"])
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"V2_TEST_ALLOW_NO_C5": "1", "V2_TEST_MIGRATION": "complete",
                  "V2_TEST_SKIP_IDS": skip})
        assert r.returncode == 1, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_sessions_not_migrated=1" in text, text
        assert "target_only_ids=0" in text, text
        assert "residual_accepted" not in text, text
        assert "migration=FAIL" in text, text
        assert "source_untouched=True" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_zero_rows_fails():
    root = _tmp("canary-migration-zero-")
    try:
        binary = _fake_bin(root)
        src = _source_db(root, completed=True)
        out = os.path.join(root, "ev")
        r = _run(root, ["--gate", "migration", "--scratch-root", out,
                        "--source-db", src, "--opencode-bin", binary],
                 {"V2_TEST_ALLOW_NO_C5": "1", "V2_TEST_MIGRATION": "noop"})
        assert r.returncode == 1, (r.stdout, r.stderr)
        text = open(os.path.join(out, "migration-rehearsal.txt")).read()
        assert "source_session_rows=12" in text, text
        assert "migrated_source_rows=0" in text, text
        assert "zero_migration=True" in text, text
        assert "source_sessions_not_migrated=12" in text, text
        assert "migration=FAIL" in text, text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_migration_timeout_fails_and_stops_service():
    """A non-completing phase times out, fails, and always cleans the service."""
    root = _tmp("canary-migration-timeout-")
    real_run = canary.v2_run
    real_stop = canary.stop_scratch_services
    real_timeout = canary.MIGRATION_TIMEOUT
    stopped = []
    try:
        source = _source_db(root, completed=True)

        def fake_run(_args, _env, argv, timeout=180):
            return subprocess.CompletedProcess(argv, 0, "", "")

        canary.v2_run = fake_run
        canary.free_port = lambda: 12345
        canary.stop_scratch_services = lambda path: stopped.append(path) or []
        canary.MIGRATION_TIMEOUT = 0.2
        ok, text = canary.gate_migration(_migration_args(root, source))
        assert ok is False, text
        assert "migration_timed_out=True" in text, text
        assert "migration_phase=sessions" in text, text
        assert "migration=FAIL" in text, text
        assert stopped, "gate must stop the scratch service in finally"
    finally:
        canary.v2_run = real_run
        canary.stop_scratch_services = real_stop
        canary.MIGRATION_TIMEOUT = real_timeout
        shutil.rmtree(root, ignore_errors=True)


def test_migration_service_start_failure_stops_service():
    """A failed service start is named and still cleans up the process tree."""
    root = _tmp("canary-migration-start-fail-")
    real_run = canary.v2_run
    real_stop = canary.stop_scratch_services
    stopped = []
    try:
        source = _source_db(root, completed=True)

        def fake_run(_args, _env, argv, timeout=180):
            if argv[:2] == ["service", "start"]:
                raise subprocess.TimeoutExpired(argv, timeout)
            return subprocess.CompletedProcess(argv, 0, "", "")

        canary.v2_run = fake_run
        canary.free_port = lambda: 12345
        canary.stop_scratch_services = lambda path: stopped.append(path) or []
        ok, text = canary.gate_migration(_migration_args(root, source))
        assert ok is False, text
        assert "service_error=TimeoutExpired" in text, text
        assert "migration=FAIL" in text, text
        assert stopped, "failed start must still stop the scratch service"
    finally:
        canary.v2_run = real_run
        canary.stop_scratch_services = real_stop
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
    assert partial["ok"] is False
    assert partial["missing"] == {"ses_2"}
    phantom = canary.migration_membership(
        {"ses_1"}, {"ses_1", "ses_phantom"})
    assert phantom["ok"] is False
    assert phantom["phantom"] == {"ses_phantom"}


def test_migration_membership_excludes_source_v2_baseline():
    """Pre-existing project V2 rows are baseline, never target-only phantoms."""
    member = canary.migration_membership(
        {"ses_1"}, {"ses_1", "ses_pre_a", "ses_pre_b"},
        baseline_ids={"ses_pre_a", "ses_pre_b"})
    assert member["ok"] is True, member
    assert member["baseline"] == 2
    assert member["baseline_only"] == 2
    assert member["target"] == 3
    assert member["migrated"] == 1
    assert member["phantom"] == set()
    # A genuinely new unknown ID is still a phantom after baseline exclusion.
    member = canary.migration_membership(
        {"ses_1"}, {"ses_1", "ses_pre_a", "ses_unknown"},
        baseline_ids={"ses_pre_a"})
    assert member["ok"] is False
    assert member["phantom"] == {"ses_unknown"}


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


def _c7_namespace(root):
    return argparse.Namespace(scratch_root=root, opencode_bin="/fake/opencode")


def _c7_patch(loader, plugin_rows="", plugin_list_raises=False):
    """Patch C7's service/loader seams for a hermetic gate call."""
    saved = {
        "v2_run": canary.v2_run,
        "assert_scratch_db": canary.v2.assert_scratch_db,
        "free_port": canary.free_port,
        "stop_scratch_services": canary.stop_scratch_services,
        "c7_loader_probe": canary.c7_loader_probe,
    }

    def fake_v2_run(_args, _env, argv, timeout=180):
        if argv[:2] == ["debug", "config"]:
            return subprocess.CompletedProcess(
                argv, 0, "canary-marker ./plugins/canary-plugin", "")
        if argv[:2] == ["plugin", "list"]:
            if plugin_list_raises:
                raise subprocess.TimeoutExpired(argv, timeout)
            return subprocess.CompletedProcess(argv, 0, plugin_rows, "")
        if argv[:3] == ["api", "GET", "/api/agent"]:
            return subprocess.CompletedProcess(argv, 0, "canary-marker", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    canary.v2_run = fake_v2_run
    canary.v2.assert_scratch_db = lambda *args, **kwargs: None
    canary.free_port = lambda: 12345
    canary.stop_scratch_services = lambda *args, **kwargs: []
    canary.c7_loader_probe = loader
    return saved


def _c7_restore(saved, root):
    canary.v2_run = saved["v2_run"]
    canary.v2.assert_scratch_db = saved["assert_scratch_db"]
    canary.free_port = saved["free_port"]
    canary.stop_scratch_services = saved["stop_scratch_services"]
    canary.c7_loader_probe = saved["c7_loader_probe"]
    shutil.rmtree(root, ignore_errors=True)


def test_c7_passes_with_empty_plugin_list_and_loader_proof():
    """AC-C7: `plugin list` empty is diagnostic only; real loader proof passes."""
    root = _tmp("canary-c7-loader-pass-")
    stale = os.path.join(root, "c7", "config", "opencode", "plugins",
                         "canary-plugin", "index.js")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        fh.write("stale canary-plugin initialized\n")
    saved = _c7_patch(lambda _args, _config, plugin_dir, token: (
        f'msg="loading plugin" id={os.path.realpath(plugin_dir)} '
        f'entrypoint=file://{os.path.realpath(plugin_dir)}/index.js\n'
        f"canary-plugin initialized probe={token}\n", None))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is True, text
        assert "plugin_list_rows=" in text, text
        assert "plugin_list_loader_proof=False" in text, text
        assert "loader_loaded_plugin=True" in text, text
        assert "loader_marker_attributed=True" in text, text
        assert "C7=PASS" in text, text
        config = os.path.join(root, "c7", "config", "opencode",
                              "opencode.jsonc")
        with open(config, encoding="utf-8") as fh:
            assert "./plugins/canary-plugin" in fh.read()
        with open(stale, encoding="utf-8") as fh:
            index = fh.read()
        assert "stale canary-plugin initialized" not in index, index
        assert "OPENCODE_LOADER_PROBE_TOKEN" in index, index
    finally:
        _c7_restore(saved, root)


def test_c7_wipes_out_of_band_sentinel_under_c7():
    """AC-C7: a stale out-of-band sentinel under c7/ is removed before setup.

    The sentinel lives outside the generated config/plugin tree, so only the
    pre-setup `c7/` wipe removes it; deleting that wipe leaves the file and
    turns this test red.
    """
    root = _tmp("canary-c7-stale-sentinel-")
    sentinel = os.path.join(root, "c7", "out-of-band-sentinel.txt")
    os.makedirs(os.path.dirname(sentinel), exist_ok=True)
    with open(sentinel, "w", encoding="utf-8") as fh:
        fh.write("stale-c7-residue\n")
    saved = _c7_patch(lambda _args, _config, plugin_dir, token: (
        f'msg="loading plugin" id={os.path.realpath(plugin_dir)} '
        f'entrypoint=file://{os.path.realpath(plugin_dir)}/index.js\n'
        f"canary-plugin initialized probe={token}\n", None))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is True, text
        assert not os.path.exists(sentinel), \
            "stale out-of-band c7/ residue survived the pre-setup wipe"
        assert "stale_c7_state_cleared=True" in text, text
        assert "C7=PASS" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_plugin_list_failure_is_diagnostic_only():
    """AC-C7: a plugin-list timeout stays diagnostic when loader proof is real."""
    root = _tmp("canary-c7-plugin-list-error-")
    saved = _c7_patch(lambda _args, _config, plugin_dir, token: (
        f'msg="loading plugin" id={os.path.realpath(plugin_dir)}\n'
        f"canary-plugin initialized probe={token}\n", None),
        plugin_list_raises=True)
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is True, text
        assert "plugin_list_error=TimeoutExpired" in text, text
        assert "C7=PASS" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_fails_when_loader_line_missing():
    """AC-C7: a marker without a loader line naming the directory is a FAIL."""
    root = _tmp("canary-c7-loader-missing-")
    saved = _c7_patch(lambda _args, _config, _plugin_dir, token: (
        f"canary-plugin initialized probe={token}\n", None))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is False, text
        assert "loader_loaded_plugin=False" in text, text
        assert "loader did not load" in text, text
        assert "C7=FAIL" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_fails_when_marker_unattributed():
    """AC-C7: a loader line without this probe's marker token is a FAIL."""
    root = _tmp("canary-c7-marker-missing-")
    saved = _c7_patch(lambda _args, _config, plugin_dir, _token: (
        f'msg="loading plugin" id={os.path.realpath(plugin_dir)} '
        f'entrypoint=file://{os.path.realpath(plugin_dir)}/index.js\n'
        "canary-plugin initialized probe=someone-else\n", None))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is False, text
        assert "loader_loaded_plugin=True" in text, text
        assert "loader_marker_attributed=False" in text, text
        assert "startup marker missing or not attributed" in text, text
        assert "C7=FAIL" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_loader_timeout_is_named_failure():
    root = _tmp("canary-c7-loader-timeout-")
    saved = _c7_patch(lambda *_args, **_kwargs: ("", "timeout"))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is False, text
        assert "loader_probe_error=timeout" in text, text
        assert "loader probe timed out" in text, text
        assert "C7=FAIL" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_loader_spawn_failure_is_named_failure():
    root = _tmp("canary-c7-loader-spawn-")
    saved = _c7_patch(lambda *_args, **_kwargs: (
        "", "cannot launch /fake/opencode: ENOENT"))
    try:
        ok, text = canary.gate_c7(_c7_namespace(root))
        assert ok is False, text
        assert "loader_probe_error=cannot launch" in text, text
        assert "C7=FAIL" in text, text
    finally:
        _c7_restore(saved, root)


def test_c7_loader_verdict_matches_directory_and_token():
    root = _tmp("canary-c7-verdict-")
    try:
        plugin = os.path.join(root, "plugins", "canary-plugin")
        other = os.path.join(root, "plugins", "other")
        token = "probe-token"
        good = (f'msg="loading plugin" id={os.path.realpath(plugin)}\n'
                f"canary-plugin initialized probe={token}\n")
        loaded, markers, failures = canary.c7_loader_log_verdict(
            good, plugin, token)
        assert len(loaded) == 1, loaded
        assert len(markers) == 1, markers
        assert not failures
        wrong_dir = (f'msg="loading plugin" id={os.path.realpath(other)}\n'
                     f"canary-plugin initialized probe={token}\n")
        loaded, markers, _ = canary.c7_loader_log_verdict(
            wrong_dir, plugin, token)
        assert not loaded
        assert len(markers) == 1
        wrong_token = (f'msg="loading plugin" id={os.path.realpath(plugin)}\n'
                       "canary-plugin initialized probe=other-token\n")
        loaded, markers, _ = canary.c7_loader_log_verdict(
            wrong_token, plugin, token)
        assert len(loaded) == 1
        assert not markers
        failed = (f'msg="loading plugin" id={os.path.realpath(plugin)}\n'
                  "failed to load plugin canary-plugin\n")
        _loaded, _markers, failures = canary.c7_loader_log_verdict(
            failed, plugin, token)
        assert failures
    finally:
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


def test_import_current_auth_timeout_is_named():
    root = _tmp("canary-auth-timeout-")
    real_run = canary.subprocess.run
    real_home = os.environ.get("HOME")
    try:
        fake_home = os.path.join(root, "home")
        auth = os.path.join(fake_home, ".local", "share", "opencode",
                            "auth.json")
        os.makedirs(os.path.dirname(auth))
        with open(auth, "w", encoding="utf-8") as fh:
            json.dump({"opencode-go": {"type": "api", "key": "k"}}, fh)
        os.environ["HOME"] = fake_home

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 120)

        canary.subprocess.run = timeout
        args = argparse.Namespace(opencode_bin="x", scratch_root=root)
        ok, detail = canary.import_current_auth(
            args, os.path.join(root, "c3.db"))
        assert ok is False
        assert "auth import probe failed" in detail
        assert "TimeoutExpired" in detail
    finally:
        canary.subprocess.run = real_run
        if real_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = real_home
        shutil.rmtree(root, ignore_errors=True)


def test_gate_c3_probe_timeout_is_named():
    root = _tmp("canary-c3-timeout-")
    real_assert = canary.v2.assert_scratch_db
    real_auth = canary.import_current_auth
    real_run = canary.v2_run
    try:
        canary.v2.assert_scratch_db = lambda *args, **kwargs: None
        canary.import_current_auth = lambda *args, **kwargs: (True, "ok")

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 120)

        canary.v2_run = timeout
        ok, text = canary.gate_c3(argparse.Namespace(
            scratch_root=root, opencode_bin="x", version=v2.VERSION_PIN))
        assert ok is False
        assert "models_probe_error=TimeoutExpired" in text
        assert "C3=FAIL" in text
    finally:
        canary.v2.assert_scratch_db = real_assert
        canary.import_current_auth = real_auth
        canary.v2_run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_gate_c4_probe_timeout_is_named():
    root = _tmp("canary-c4-timeout-")
    real_assert = canary.v2.assert_scratch_db
    real_auth = canary.import_current_auth
    real_run = canary.v2_run
    try:
        canary.v2.assert_scratch_db = lambda *args, **kwargs: None
        canary.import_current_auth = lambda *args, **kwargs: (True, "ok")

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 180)

        canary.v2_run = timeout
        ok, text = canary.gate_c4(argparse.Namespace(
            scratch_root=root, opencode_bin="x", version=v2.VERSION_PIN))
        assert ok is False
        assert "error:TimeoutExpired" in text
        assert "C4=FAIL" in text
    finally:
        canary.v2.assert_scratch_db = real_assert
        canary.import_current_auth = real_auth
        canary.v2_run = real_run
        shutil.rmtree(root, ignore_errors=True)


def test_gate_migration_probe_timeout_is_named():
    root = _tmp("canary-migration-probe-timeout-")
    real_run = canary.v2_run
    real_stop = canary.stop_scratch_services
    try:
        source = _source_db(root)

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 900)

        canary.v2_run = timeout
        canary.stop_scratch_services = lambda *args, **kwargs: []
        ok, detail = canary.gate_migration(argparse.Namespace(
            scratch_root=root, source_db=source, opencode_bin="x",
            version=v2.VERSION_PIN))
        assert ok is False
        assert "service_error=TimeoutExpired" in detail
        text = open(os.path.join(root, "migration-rehearsal.txt")).read()
        assert "service_error=TimeoutExpired" in text
        assert "migration=FAIL" in text
    finally:
        canary.v2_run = real_run
        canary.stop_scratch_services = real_stop
        shutil.rmtree(root, ignore_errors=True)


def test_gate_c8_probe_timeout_is_named():
    root = _tmp("canary-c8-timeout-")
    real_run = canary.subprocess.run
    try:
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 120)

        canary.subprocess.run = timeout
        ok, text = canary.gate_c8(argparse.Namespace(scratch_root=root))
        assert ok is False
        assert "probe error" in text
        assert "C8=FAIL" in text
    finally:
        canary.subprocess.run = real_run
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
