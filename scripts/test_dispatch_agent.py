#!/usr/bin/env python3
"""RED-first tests for scripts/dispatch_agent.py.

Covers the original dispatch contract (plan agent-teams-dispatch
AC5/AC6/AC7) and the run-vehicle visibility pass (plan run-vehicle-visibility
AC1–AC14): live stream tees, heartbeat envelope + injection, preflight
failures, session-resolved attribution, external-path grants, and
denial-aware classification.

Hermetic: a stub `opencode` on PATH emits canned `--format json` streams; no
model calls, no network.

Run: python3 scripts/test_dispatch_agent.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
DISPATCH = os.path.join(HERE, "dispatch_agent.py")

# The stub mimics `opencode run --agent <n> --format json <prompt>`: a
# newline-delimited JSON stream with `sessionID` on every event, `text`
# parts carrying the final output, and `step_finish` parts carrying
# tokens/cost (the shapes probed live 2026-10-02). When STUB_DUMP_PROMPT /
# STUB_DUMP_ENV are set it dumps its final argv / environment (AC5/AC12).
STUB_OPENCODE = '''#!/usr/bin/env python3
"""Stub opencode for scripts/test_dispatch_agent.py (no model calls)."""
import json
import os
import sys
import time

mode = os.environ.get("STUB_MODE", "valid")
argv = sys.argv[1:]
assert "run" in argv, argv
assert "--format" in argv, argv

dump_prompt = os.environ.get("STUB_DUMP_PROMPT")
if dump_prompt:
    with open(dump_prompt, "w", encoding="utf-8") as fh:
        fh.write(argv[-1] if argv else "")

dump_env = os.environ.get("STUB_DUMP_ENV")
if dump_env:
    with open(dump_env, "w", encoding="utf-8") as fh:
        json.dump(dict(os.environ), fh)


def emit(obj):
    print(json.dumps(obj), flush=True)


def start(sid):
    emit({"type": "step_start", "sessionID": sid,
          "part": {"type": "step-start", "sessionID": sid}})


def valid_body(sid):
    start(sid)
    emit({"type": "text", "sessionID": sid,
          "part": {"type": "text", "sessionID": sid,
                   "text": "Verification: all green\\nHandoff: ready"}})
    emit({"type": "step_finish", "sessionID": sid,
          "part": {"type": "step-finish", "tokens": {"input": 100, "output": 50},
                   "cost": 0.0012}})


if mode == "timeout":
    start("ses_stub_timeout")
    time.sleep(30)  # dispatch_agent's --timeout must kill the group
    sys.exit(0)

if mode == "nonzero":
    start("ses_stub_err")
    print("provider exploded", file=sys.stderr)
    sys.exit(1)

if mode == "empty":
    sys.exit(0)

if mode == "malformed":
    start("ses_stub_malformed")
    print("this line is not json")
    sys.exit(0)

if mode == "noresult":
    start("ses_stub_noresult")
    sys.exit(0)

if mode == "paced":
    sid = "ses_stub_paced"
    start(sid)
    time.sleep(0.6)
    emit({"type": "text", "sessionID": sid,
          "part": {"type": "text", "sessionID": sid, "text": "one"}})
    time.sleep(0.6)
    emit({"type": "step_finish", "sessionID": sid,
          "part": {"type": "step-finish", "tokens": {"input": 1, "output": 1},
                   "cost": 0.0}})
    sys.exit(0)

if mode == "stderr":
    sid = "ses_stub_stderr"
    start(sid)
    print("diag one", file=sys.stderr, flush=True)
    time.sleep(0.4)
    print("diag two", file=sys.stderr, flush=True)
    emit({"type": "text", "sessionID": sid,
          "part": {"type": "text", "sessionID": sid,
                   "text": "Verification: ok\\nHandoff: ok"}})
    sys.exit(0)

if mode == "denied":
    sid = "ses_stub_denied"
    start(sid)
    emit({"type": "tool", "sessionID": sid,
          "part": {"type": "tool", "sessionID": sid, "tool": "read",
                   "state": {"status": "error",
                             "input": {"filePath": "/sibling/repo/secret.md"},
                             "error": "external_directory permission auto-reject"}}})
    sys.exit(0)

if mode == "denied_stderr":
    start("ses_stub_denied_stderr")
    # non-SGR CSI (erase-line) + OSC title, must be stripped from the detail
    print("\\x1b[2K\\x1b]0;title\\x07error: external_directory /sibling auto-reject",
          file=sys.stderr)
    sys.exit(0)

if mode == "surrogate":
    # a lone surrogate in the text makes the utf-8 result write raise
    # UnicodeEncodeError (a non-OSError) before the heartbeat terminal line
    sid = "ses_stub_surrogate"
    start(sid)
    emit({"type": "text", "sessionID": sid,
          "part": {"type": "text", "sessionID": sid,
                   "text": "Verification: ok\\nHandoff: \\ud800"}})
    sys.exit(0)

# valid
valid_body("ses_stub_valid")
'''


def _read(path):
    if not path or not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _flag_path(extra, flag):
    extra = extra or []
    if flag in extra:
        return extra[extra.index(flag) + 1]
    return None


def _lines(text):
    return [l for l in (text or "").splitlines() if l.strip()]


def _make_stub(td):
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    stub = os.path.join(bin_dir, "opencode")
    with open(stub, "w", encoding="utf-8") as fh:
        fh.write(STUB_OPENCODE)
    os.chmod(stub, 0o755)
    return bin_dir


def _run(mode, extra=None, timeout="10", env_extra=None):
    """Invoke dispatch_agent.py against the stub -> result namespace."""
    assert os.path.isfile(DISPATCH), "scripts/dispatch_agent.py missing (red-first)"
    td = tempfile.mkdtemp(prefix="dispatch-test-")
    try:
        bin_dir = _make_stub(td)

        prompt = os.path.join(td, "prompt.md")
        with open(prompt, "w", encoding="utf-8") as fh:
            fh.write("Do the thing.")

        out = os.path.join(td, "result.md")
        logs = os.path.join(td, "logs")
        cmd = [
            sys.executable, DISPATCH, "--agent", "architect",
            "--prompt-file", prompt, "--out", out, "--logs-dir", logs,
            "--timeout", timeout,
        ] + list(extra or [])
        env = dict(os.environ)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env["STUB_MODE"] = mode
        if env_extra:
            env.update(env_extra)

        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              cwd=REPO, timeout=60)
        elapsed = time.monotonic() - started

        records = []
        if os.path.isdir(logs):
            for name in sorted(os.listdir(logs)):
                if not name.endswith(".jsonl"):
                    continue
                with open(os.path.join(logs, name), encoding="utf-8") as fh:
                    records += [json.loads(l) for l in fh if l.strip()]
        return SimpleNamespace(
            rc=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            records=records, result_text=_read(out),
            stream_out=_read(_flag_path(extra, "--stream-out")),
            stream_err=_read(_flag_path(extra, "--stream-err")),
            heartbeat=_read(_flag_path(extra, "--heartbeat")),
            prompt_dump=_read(env.get("STUB_DUMP_PROMPT")),
            env_dump=_read(env.get("STUB_DUMP_ENV")),
            elapsed=elapsed)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _spawn(mode, extra=None):
    """Launch dispatch_agent.py without waiting, for live-observation tests."""
    td = tempfile.mkdtemp(prefix="dispatch-live-")
    bin_dir = _make_stub(td)
    prompt = os.path.join(td, "prompt.md")
    with open(prompt, "w", encoding="utf-8") as fh:
        fh.write("Do the thing.")
    cmd = [
        sys.executable, DISPATCH, "--agent", "architect",
        "--prompt-file", prompt,
        "--out", os.path.join(td, "result.md"),
        "--logs-dir", os.path.join(td, "logs"), "--timeout", "20",
    ] + list(extra or [])
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["STUB_MODE"] = mode
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, cwd=REPO)
    return td, proc


# --- original dispatch contract (unchanged) ---------------------------------

def test_valid_dispatch_records_attribution():
    """AC5+AC6+AC7: exit 0, session id printed, result written, one
    kind=agent record carrying agent + resolved model + tokens/cost."""
    r = _run("valid", extra=["--contract", "implement-handoff"])
    assert r.rc == 0, (r.rc, r.stdout, r.stderr)
    assert "session_id=ses_stub_valid" in r.stdout, r.stdout
    assert "Verification" in r.result_text, r.result_text
    assert len(r.records) == 1, r.records
    rec = r.records[0]
    assert rec["kind"] == "agent", rec
    assert rec["agent"] == "architect", rec
    assert rec["model"] == "opencode/nemotron-3-ultra-free", rec
    assert rec["outcome"] == "success", rec
    assert rec["tokens_in"] == 100 and rec["tokens_out"] == 50, rec
    assert abs(rec["cost"] - 0.0012) < 1e-9, rec
    assert rec["detail"] is None, rec
    # a --model override wins over the frontmatter binding
    r2 = _run("valid", extra=["--model", "opencode-go/kimi-k3"])
    assert r2.rc == 0, (r2.rc, r2.stderr)
    assert r2.records[0]["model"] == "opencode-go/kimi-k3", r2.records[0]


def test_empty_result_fails_contract():
    """AC5: an empty stream exits non-zero and the record is not success."""
    r = _run("empty", extra=["--contract", "implement-handoff"])
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] in ("error", "failure"), r.records
    assert r.records[0]["detail"], r.records


def test_malformed_result_fails_contract():
    """AC5: a non-JSON stream exits non-zero and the record is not success."""
    r = _run("malformed", extra=["--contract", "implement-handoff"])
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] in ("error", "failure"), r.records
    assert r.records[0]["detail"], r.records


def test_timeout_kills_and_records_error():
    """AC5: a stalled run is killed at --timeout, exits non-zero, records
    outcome=error with a timeout detail."""
    r = _run("timeout", timeout="1")
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.elapsed < 15, r.elapsed
    assert r.records and r.records[0]["outcome"] == "error", r.records
    assert "timeout" in (r.records[0]["detail"] or "").lower(), r.records


def test_nonzero_exit_records_error():
    """Coverage gate (Step 9b): a non-zero opencode exit is outcome=error
    with the exit code in the detail — the provider/process error branch."""
    r = _run("nonzero")
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] == "error", r.records
    assert "exited 1" in (r.records[0]["detail"] or ""), r.records


# --- AC1/AC2/AC3: live stream tees ------------------------------------------

def _observe_live(mode, flag, filename, expected):
    """Spawn a run, observe >=1 line in `flag` while alive, assert completeness."""
    obs = tempfile.mkdtemp(prefix="dispatch-obs-")
    td = None
    try:
        stream = os.path.join(obs, filename)
        td, proc = _spawn(mode, extra=[flag, stream])
        observed_mid = False
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if proc.poll() is None and _lines(_read(stream)):
                observed_mid = True
                break
            time.sleep(0.05)
        proc.wait(timeout=30)
        assert observed_mid, f"{stream} was empty while the child was alive"
        assert len(_lines(_read(stream))) == expected, _read(stream)
    finally:
        if td is not None:
            shutil.rmtree(td, ignore_errors=True)
        shutil.rmtree(obs, ignore_errors=True)


def test_stream_out_live_and_complete():
    """AC1: the stdout tee is live (>=1 line while the child runs) and
    complete (exactly 3 lines at exit)."""
    _observe_live("paced", "--stream-out", "events.jsonl", 3)


def test_stream_err_live_and_complete():
    """AC2: --stream-err captures stderr live and complete (2 lines)."""
    _observe_live("stderr", "--stream-err", "err.log", 2)


def test_stream_files_fresh_vs_resume():
    """AC3: a fresh dispatch truncates; --session resume appends."""
    work = tempfile.mkdtemp(prefix="dispatch-resume-")
    try:
        stream = os.path.join(work, "events.jsonl")
        r1 = _run("valid", extra=["--stream-out", stream])
        assert r1.rc == 0, (r1.rc, r1.stderr)
        assert len(_lines(r1.stream_out)) == 3, r1.stream_out
        r2 = _run("valid", extra=["--stream-out", stream,
                                  "--session", "ses_stub_valid"])
        assert r2.rc == 0, (r2.rc, r2.stderr)
        assert len(_lines(r2.stream_out)) == 6, r2.stream_out
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC4/AC5: heartbeat envelope + injection --------------------------------

def test_heartbeat_envelope_success():
    """AC4: header + START before the run; exactly one DONE ok after."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-")
    try:
        hb = os.path.join(work, "progress.log")
        r = _run("valid", extra=["--heartbeat", hb,
                                 "--contract", "implement-handoff"])
        assert r.rc == 0, (r.rc, r.stderr)
        lines = _lines(r.heartbeat)
        assert lines and lines[0].startswith("# progress:"), lines
        start_i = next(i for i, l in enumerate(lines) if " START " in l)
        terminals = [l for l in lines if " DONE " in l or " BLOCKED " in l]
        assert len(terminals) == 1 and "DONE ok" in terminals[0], lines
        assert start_i < lines.index(terminals[0]), lines
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_heartbeat_terminal_blocked():
    """AC4: contract failure and timeout both end in one BLOCKED line."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-")
    try:
        hb1 = os.path.join(work, "contract.log")
        r1 = _run("noresult", extra=["--heartbeat", hb1,
                                     "--contract", "implement-handoff"])
        assert r1.rc != 0, (r1.rc, r1.stdout)
        t1 = [l for l in _lines(r1.heartbeat) if " BLOCKED " in l]
        assert len(t1) == 1 and "empty result" in t1[0], r1.heartbeat

        hb2 = os.path.join(work, "timeout.log")
        r2 = _run("timeout", timeout="1",
                  extra=["--heartbeat", hb2, "--contract", "implement-handoff"])
        assert r2.rc != 0, (r2.rc, r2.stdout)
        t2 = [l for l in _lines(r2.heartbeat) if " BLOCKED " in l]
        assert len(t2) == 1 and "timeout" in t2[0].lower(), r2.heartbeat

        hb3 = os.path.join(work, "nonzero.log")
        r3 = _run("nonzero", extra=["--heartbeat", hb3])
        assert r3.rc != 0, (r3.rc, r3.stdout)
        t3 = [l for l in _lines(r3.heartbeat) if " BLOCKED " in l]
        assert len(t3) == 1 and "exited 1" in t3[0], r3.heartbeat

        # result-write failure also ends BLOCKED (and stays a terminal line)
        blocker = os.path.join(work, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        hb4 = os.path.join(work, "writefail.log")
        r4 = _run("valid", extra=["--heartbeat", hb4,
                                  "--out", os.path.join(blocker, "result.md")])
        assert r4.rc == 2, (r4.rc, r4.stdout, r4.stderr)
        t4 = [l for l in _lines(r4.heartbeat) if " BLOCKED " in l]
        assert len(t4) == 1 and "cannot write result" in t4[0], r4.heartbeat
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_heartbeat_terminal_on_unexpected_write_failure():
    """M1: an unexpected non-OSError result write, and an unexpected
    non-ValueError run-log record write, must still end in exactly one
    terminal line with the handle closed and the outcome/exit unmasked."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-")
    try:
        # (a) the result write raises UnicodeEncodeError (not OSError) before
        # the terminal write: the heartbeat must still terminate, no traceback.
        hb = os.path.join(work, "surrogate.log")
        r = _run("surrogate", extra=["--heartbeat", hb,
                                     "--contract", "implement-handoff"])
        assert "Traceback" not in r.stderr, r.stderr
        terminals = [l for l in _lines(r.heartbeat) if " BLOCKED " in l]
        assert len(terminals) == 1 and "unexpected" in terminals[0].lower(), \
            r.heartbeat
        assert r.rc == 3, (r.rc, r.stdout, r.stderr)

        # (b) the run-log record write raises OSError (not ValueError) after
        # the success outcome: warn, keep the outcome/exit, still terminate.
        blocker = os.path.join(work, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        hb2 = os.path.join(work, "recordfail.log")
        r2 = _run("valid", extra=["--heartbeat", hb2,
                                  "--contract", "implement-handoff",
                                  "--logs-dir", os.path.join(blocker, "logs")])
        assert "Traceback" not in r2.stderr, r2.stderr
        assert r2.rc == 0, (r2.rc, r2.stdout, r2.stderr)
        t2 = [l for l in _lines(r2.heartbeat) if " DONE " in l]
        assert len(t2) == 1 and "DONE ok" in t2[0], r2.heartbeat
        assert "run-log record" in r2.stderr, r2.stderr
        assert "result=" in r2.stdout, r2.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_heartbeat_prompt_injection():
    """AC5: the prompt carries the canonical block naming the heartbeat
    file and citing the protocol section."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-")
    try:
        hb = os.path.join(work, "progress.log")
        dump = os.path.join(work, "prompt.dump")
        r = _run("valid", extra=["--heartbeat", hb,
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_PROMPT": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        block = r.prompt_dump
        assert os.path.abspath(hb) in block, block
        assert "reference/subagent-supervision.md" in block, block
        assert "§2" in block, block
        for token in ("STEP", "CALL", "POLL", "180"):
            assert token in block, (token, block)

        # M4: a --session resume must NOT re-inject the block (no accumulation)
        hb2 = os.path.join(work, "resume.log")
        dump2 = os.path.join(work, "resume.dump")
        r2 = _run("valid", extra=["--heartbeat", hb2,
                                  "--session", "ses_stub_valid"],
                  env_extra={"STUB_DUMP_PROMPT": dump2})
        assert r2.rc == 0, (r2.rc, r2.stderr)
        assert "Supervision protocol" not in r2.prompt_dump, r2.prompt_dump
        assert os.path.abspath(hb2) not in r2.prompt_dump, r2.prompt_dump
        # the envelope still marks the resume
        assert any(" START " in l for l in _lines(r2.heartbeat)), r2.heartbeat
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC6: preflight failures ------------------------------------------------

def test_stream_open_failure_exits_2_before_launch():
    """AC6: an unopenable target exits 2 with no session created."""
    work = tempfile.mkdtemp(prefix="dispatch-pre-")
    try:
        blocker = os.path.join(work, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        target = os.path.join(blocker, "events.jsonl")
        r = _run("valid", extra=["--stream-out", target,
                                 "--contract", "implement-handoff"])
        assert r.rc == 2, (r.rc, r.stdout, r.stderr)
        assert "cannot open dispatch artifact" in r.stderr, r.stderr
        assert target in r.stderr, r.stderr
        assert "session_id=" not in r.stdout, r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC10/AC11: session-resolved attribution --------------------------------

def _make_session_db(path, sid, model_blob):
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session (id TEXT PRIMARY KEY, model TEXT, title TEXT, "
        "agent TEXT, cost REAL, tokens_input INTEGER, tokens_output INTEGER, "
        "time_updated INTEGER, directory TEXT, parent_id TEXT)")
    con.execute(
        "INSERT INTO session (id, model, title, agent) VALUES (?, ?, ?, ?)",
        (sid, json.dumps(model_blob), "probe", "architect"))
    con.commit()
    con.close()


def test_record_model_from_session_db():
    """AC10: the completion output and record use the session-resolved model
    while the pre-run line labels the frontmatter value as binding=."""
    work = tempfile.mkdtemp(prefix="dispatch-db-")
    try:
        dbp = os.path.join(work, "opencode.db")
        _make_session_db(dbp, "ses_stub_valid",
                         {"id": "glm-5.3-flash", "providerID": "opencode-go",
                          "variant": "default"})
        r = _run("valid", extra=["--contract", "implement-handoff"],
                 env_extra={"OPENCODE_DB_PATH": dbp})
        assert r.rc == 0, (r.rc, r.stderr)
        assert r.records[0]["model"] == "opencode-go/glm-5.3-flash", r.records
        assert "model=opencode-go/glm-5.3-flash" in r.stdout, r.stdout
        assert "binding=opencode/nemotron-3-ultra-free" in r.stdout, r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_model_fallback_without_db():
    """AC11: no DB / missing row degrade to the declared binding, and the
    explicit --model is the fallback when no DB is available."""
    work = tempfile.mkdtemp(prefix="dispatch-db-")
    try:
        missing = os.path.join(work, "missing.db")
        r = _run("valid", extra=["--contract", "implement-handoff"],
                 env_extra={"OPENCODE_DB_PATH": missing})
        assert r.rc == 0, (r.rc, r.stderr)
        assert r.records[0]["model"] == "opencode/nemotron-3-ultra-free", r.records
        assert "model=opencode/nemotron-3-ultra-free" in r.stdout, r.stdout

        r2 = _run("valid", extra=["--contract", "implement-handoff",
                                  "--model", "opencode-go/glm-5.3-flash"],
                  env_extra={"OPENCODE_DB_PATH": missing})
        assert r2.records[0]["model"] == "opencode-go/glm-5.3-flash", r2.records

        # a DB that lacks the session row also falls back
        dbp = os.path.join(work, "other.db")
        _make_session_db(dbp, "ses_other",
                         {"id": "x", "providerID": "opencode-go"})
        r3 = _run("valid", extra=["--contract", "implement-handoff"],
                  env_extra={"OPENCODE_DB_PATH": dbp})
        assert r3.records[0]["model"] == "opencode/nemotron-3-ultra-free", r3.records
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC12/AC13/AC14: grants + denial classification -------------------------

def test_allow_dir_grants_external_permission():
    """AC12: --allow-dirs emits the external_directory allow-map, merges
    caller settings (caller wins), and rejects a non-existent path."""
    work = tempfile.mkdtemp(prefix="dispatch-grant-")
    try:
        granted = os.path.join(work, "sibling")
        os.makedirs(granted)
        key = os.path.join(os.path.abspath(granted), "**")
        dump = os.path.join(work, "env.json")
        r = _run("valid", extra=["--allow-dirs", granted,
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ENV": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        env = json.loads(r.env_dump)
        cfg = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert cfg["permission"]["external_directory"][key] == "allow", cfg

        # caller-supplied settings win on conflict
        caller = json.dumps({"permission": {"external_directory": {key: "deny"}}})
        dump2 = os.path.join(work, "env2.json")
        r2 = _run("valid", extra=["--allow-dirs", granted,
                                  "--contract", "implement-handoff"],
                  env_extra={"STUB_DUMP_ENV": dump2,
                             "OPENCODE_CONFIG_CONTENT": caller})
        cfg2 = json.loads(json.loads(r2.env_dump)["OPENCODE_CONFIG_CONTENT"])
        assert cfg2["permission"]["external_directory"][key] == "deny", cfg2

        # a non-existent path exits 2 before a session is created
        r3 = _run("valid", extra=["--allow-dirs", os.path.join(work, "nope"),
                                  "--contract", "implement-handoff"])
        assert r3.rc == 2, (r3.rc, r3.stderr)
        assert "session_id=" not in r3.stdout, r3.stdout

        # M3: a regular file is not a directory — exit 2 before launch
        somefile = os.path.join(work, "somefile.txt")
        with open(somefile, "w", encoding="utf-8") as fh:
            fh.write("x")
        r4 = _run("valid", extra=["--allow-dirs", somefile,
                                  "--contract", "implement-handoff"])
        assert r4.rc == 2, (r4.rc, r4.stderr)
        assert "session_id=" not in r4.stdout, r4.stdout
        assert "directory" in r4.stderr, r4.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_permission_config_warns_on_malformed_caller_env():
    """M2: an unparsable caller OPENCODE_CONFIG_CONTENT warns to stderr and is
    discarded, but --allow-dirs is still merged and the dispatch proceeds."""
    work = tempfile.mkdtemp(prefix="dispatch-grant-")
    try:
        granted = os.path.join(work, "sibling")
        os.makedirs(granted)
        key = os.path.join(os.path.abspath(granted), "**")
        dump = os.path.join(work, "env.json")
        r = _run("valid", extra=["--allow-dirs", granted,
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ENV": dump,
                            "OPENCODE_CONFIG_CONTENT": "{not valid json"})
        assert r.rc == 0, (r.rc, r.stderr)
        assert "OPENCODE_CONFIG_CONTENT" in r.stderr, r.stderr
        cfg = json.loads(json.loads(r.env_dump)["OPENCODE_CONFIG_CONTENT"])
        assert cfg["permission"]["external_directory"][key] == "allow", cfg
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_permission_denial_classification():
    """AC13/AC14: a denied tool part (or external_directory stderr) yields
    `permission denied: <tool> <target>` instead of `empty result`."""
    r = _run("denied", extra=["--contract", "implement-handoff"])
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] == "failure", r.records
    detail = r.records[0]["detail"] or ""
    assert detail.startswith("permission denied:"), detail
    assert "read" in detail and "/sibling/repo/secret.md" in detail, detail

    r2 = _run("denied_stderr", extra=["--contract", "implement-handoff"])
    assert r2.rc != 0, (r2.rc, r2.stdout)
    detail2 = r2.records[0]["detail"] or ""
    assert detail2.startswith("permission denied:"), detail2
    assert "external_directory" in detail2, detail2
    # N3: non-SGR CSI and OSC escapes are stripped from the record detail
    assert "\x1b" not in detail2, repr(detail2)
    assert "[2K" not in detail2, repr(detail2)


def test_reference_docs_carry_the_recipe():
    """AC8/AC14: the reference docs name the flag trio, --allow-dirs, and
    the session-resolved attribution contract."""
    sup = open(os.path.join(REPO, "reference", "subagent-supervision.md"),
               encoding="utf-8").read()
    for phrase in ("--stream-out", "--stream-err", "--heartbeat",
                   "--allow-dirs"):
        assert phrase in sup, f"subagent-supervision.md missing {phrase!r}"
    teams = open(os.path.join(REPO, "reference", "agent-teams.md"),
                 encoding="utf-8").read()
    for phrase in ("--stream-out", "--heartbeat", "--allow-dirs",
                   "session-resolved"):
        assert phrase in teams, f"agent-teams.md missing {phrase!r}"


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
