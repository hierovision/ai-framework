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
import contextlib
import importlib.util
import io
import json
import os
import re
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import opencode_v2 as v2  # noqa: E402 - the marker contract owner

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
if argv[:2] == ["service", "status"]:
    print(os.environ.get("STUB_SERVICE_URL", "stopped"))
    sys.exit(0)
if argv[:1] == ["api"]:
    path = argv[-1] if argv else ""
    dump_api_path = os.environ.get("STUB_DUMP_API")
    if dump_api_path:
        with open(dump_api_path, "a", encoding="utf-8") as fh:
            fh.write((argv[1] if len(argv) > 1 else "?") + " " + path + chr(10))
    if path.endswith("/active"):
        print('{"data": {}}')
        sys.exit(0)
    if path.endswith("/interrupt"):
        print('{"interrupted": true}')
        sys.exit(0)
    if "ses_stub_valid" in path or "ses_stub_timeout" in path:
        print('{"data": {"id": "ses_stub_valid"}}')
        sys.exit(0)
    print('{"_tag": "SessionNotFoundError"}')
    print("HTTP 404 Not Found")
    sys.exit(0)
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

dump_cwd = os.environ.get("STUB_DUMP_CWD")
if dump_cwd:
    with open(dump_cwd, "w", encoding="utf-8") as fh:
        fh.write(os.getcwd())

dump_argv = os.environ.get("STUB_DUMP_ARGV")
if dump_argv:
    with open(dump_argv, "w", encoding="utf-8") as fh:
        json.dump(argv, fh)


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

if mode == "commitdir":
    # emulate a child that touches branches: commit a file in its --dir (the
    # 2026-10-13 wrong-branch class; the worktree must confine this)
    import subprocess
    d = os.getcwd()
    with open(os.path.join(d, "child.txt"), "w", encoding="utf-8") as fh:
        fh.write("child\\n")
    subprocess.run(["git", "-C", d, "add", "child.txt"], check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "-C", d, "commit", "-m", "child commit"], check=True,
                   capture_output=True, text=True)
    valid_body("ses_stub_valid")
    sys.exit(0)

# valid
valid_body("ses_stub_valid")
'''

# Stub completion-observer: records its argv, so the dispatcher's spawn of the
# observer (via OBSERVE_COMPLETION_PATH) can be asserted hermetically.
OBSERVER_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

out = os.environ.get("OBSERVER_STUB_OUT")
if out:
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(sys.argv[1:], fh)
sys.exit(0)
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


def _run(mode, extra=None, timeout="10", env_extra=None, cwd=REPO,
         agent="architect"):
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
            sys.executable, DISPATCH, "--agent", agent,
            "--prompt-file", prompt, "--out", out, "--logs-dir", logs,
            "--timeout", timeout,
        ] + list(extra or [])
        env = dict(os.environ)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env["STUB_MODE"] = mode
        env["OPENCODE_V2_NO_SERVICE"] = "1"
        # Tests inspect the generated XDG config after the run; the production
        # default cleans a successful run's tree (F12).
        env["DISPATCH_KEEP_CONFIG"] = "1"
        # the ambient opencode session exports its own OPENCODE_CONFIG_CONTENT;
        # drop it so the dispatch's own merge is what the stub observes
        env.pop("OPENCODE_CONFIG_CONTENT", None)
        if env_extra:
            env.update(env_extra)

        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              cwd=cwd, timeout=60)
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
            argv_dump=_read(env.get("STUB_DUMP_ARGV")),
            api_dump=_read(env.get("STUB_DUMP_API")),
            cwd_dump=_read(env.get("STUB_DUMP_CWD")),
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
    env["OPENCODE_V2_NO_SERVICE"] = "1"
    env["DISPATCH_KEEP_CONFIG"] = "1"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, cwd=REPO)
    return td, proc


def _run_unexpected_error_in_process(long_message, hb_path):
    """Exercise the guarded outcome block with a long-message non-OSError.

    A natural result-write fault (UnicodeEncodeError) has a short message, so
    an over-cap detail cannot be produced through the stub. Load
    dispatch_agent.py fresh and make the contract validator raise inside the
    guarded block, then drive main() in-process. Returns the exit code.
    """
    spec = importlib.util.spec_from_file_location(
        "dispatch_agent_inproc", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stream = ('{"type": "text", "sessionID": "ses_inproc", '
              '"part": {"type": "text", "sessionID": "ses_inproc", '
              '"text": "Verification: ok\\nHandoff: ok"}}\n')
    mod.run_opencode = lambda *a, **k: (0, stream, "", False)
    mod.resolve_session_model = lambda sid: None

    class LongError(Exception):
        pass

    def boom(text, markers):
        raise LongError(long_message)

    mod.validate_delegated_result.validate = boom
    work = tempfile.mkdtemp(prefix="dispatch-inproc-")
    try:
        prompt = os.path.join(work, "prompt.md")
        with open(prompt, "w", encoding="utf-8") as fh:
            fh.write("Do the thing.")
        argv = ["--agent", "architect", "--prompt-file", prompt,
                "--out", os.path.join(work, "result.md"),
                "--logs-dir", os.path.join(work, "logs"),
                "--heartbeat", hb_path, "--contract", "implement-handoff"]
        silence = io.StringIO()
        with contextlib.redirect_stdout(silence), \
                contextlib.redirect_stderr(silence):
            return mod.main(argv)
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
    assert rec["model"] == "opencode-go/kimi-k3.1-pro", rec
    assert rec["outcome"] == "success", rec
    assert rec["tokens_in"] == 100 and rec["tokens_out"] == 50, rec
    assert abs(rec["cost"] - 0.0012) < 1e-9, rec
    assert rec["detail"] is None, rec
    # a --model override wins over the frontmatter binding
    r2 = _run("valid", extra=["--model", "opencode-go/qwen3.8-flash"])
    assert r2.rc == 0, (r2.rc, r2.stderr)
    assert r2.records[0]["model"] == "opencode-go/qwen3.8-flash", r2.records[0]


def test_v2_service_flags_follow_run_subcommand():
    """AC13: V2 2.1.4 accepts `--standalone`/`--server` only on `run`
    (2026-10-28 live: the global placement exited 1 "Unrecognized flag")."""
    work = tempfile.mkdtemp(prefix="dispatch-argv-")
    try:
        for flag, extra in (("--standalone", []),
                            ("--server", ["--server", "http://127.0.0.1:4096"])):
            dump = os.path.join(work, flag.lstrip("-") + ".json")
            r = _run("valid", extra=extra + ["--contract", "implement-handoff"],
                     env_extra={"STUB_DUMP_ARGV": dump})
            assert r.rc == 0, (r.rc, r.stderr)
            argv = json.loads(r.argv_dump)
            assert "run" in argv, argv
            if flag == "--standalone" and flag not in argv:
                # grant-free agent profile still requests a private server
                assert False, argv
            assert argv.index("run") < argv.index(flag), argv
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_dispatch_sets_cwd_and_pwd():
    """AC13: --dir is passed as cwd + PWD, never as a V1 CLI flag."""
    work = tempfile.mkdtemp(prefix="dispatch-cwd-")
    try:
        dispatch_dir = os.path.join(work, "target")
        os.makedirs(dispatch_dir)
        env_dump = os.path.join(work, "env.json")
        cwd_dump = os.path.join(work, "cwd.txt")
        r = _run("valid", extra=["--dir", dispatch_dir,
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ENV": env_dump,
                            "STUB_DUMP_CWD": cwd_dump})
        assert r.rc == 0, (r.rc, r.stdout, r.stderr)
        assert os.path.realpath(r.cwd_dump) == os.path.realpath(dispatch_dir), r.cwd_dump
        env = json.loads(r.env_dump)
        assert os.path.realpath(env.get("PWD", "")) == os.path.realpath(dispatch_dir), env.get("PWD")
        argv = json.loads(r.argv_dump) if r.argv_dump else []
        assert "--dir" not in argv, argv
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_missing_model_binding_exits_2_before_launch():
    """AC18: an agent with no model: binding exits 2, no session, no launch."""
    r = _run("valid", agent="no-such-agent")
    assert r.rc == 2, (r.rc, r.stdout, r.stderr)
    assert "no model binding" in r.stderr, r.stderr
    assert "session_id=" not in r.stdout, r.stdout
    assert not r.records, r.records


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


def test_shared_server_timeout_interrupts_and_verifies():
    """AC15: --server + --allow-dirs remains shared-service; timeout calls
    interrupt, verifies /api/session/active, and records interrupt=ok."""
    work = tempfile.mkdtemp(prefix="dispatch-interrupt-")
    try:
        granted = os.path.join(work, "granted")
        os.makedirs(granted)
        dump = os.path.join(work, "api.log")
        r = _run("timeout", timeout="1",
                 extra=["--server", "http://127.0.0.1:4096",
                        "--allow-dirs", granted],
                 env_extra={"STUB_DUMP_API": dump,
                            "OPENCODE_V2_API_VIA_CLI": "1"})
        assert r.rc == 4, (r.rc, r.stdout, r.stderr)
        detail = r.records[0]["detail"] or ""
        assert "interrupt=ok" in detail, detail
        calls = r.api_dump
        assert "interrupt" in calls, calls
        assert "/active" in calls, calls
    finally:
        shutil.rmtree(work, ignore_errors=True)


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


def test_concurrent_append_keeps_complete_heartbeat_records():
    """F11: the observer's append cannot be clobbered by a held dispatcher
    writer. Every record stays complete and newline-delimited (no `unning`)."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-race-")
    hb = os.path.join(work, "progress.log")
    td, proc = _spawn("paced", extra=["--heartbeat", hb])
    try:
        deadline = time.time() + 10
        while time.time() < deadline and " START " not in _read(hb):
            time.sleep(0.02)
        assert " START " in _read(hb), _read(hb)
        # The completion observer appends while the dispatcher still holds the
        # run open (paced emits, then sleeps ~1.2s before the terminal line).
        for i in range(3):
            with open(hb, "a", encoding="utf-8") as fh:
                fh.write(f"2026-10-29T00:00:0{i}Z SURVEY running\n")
            time.sleep(0.05)
        proc.communicate(timeout=30)
        text = _read(hb)
        lines = [l for l in text.splitlines() if l.strip()]
        assert not any(l.strip() == "unning" for l in lines), text
        assert text.count("SURVEY running") == 3, text
        record = re.compile(
            r"^(# progress:|\d{4}-\d{2}-\d{2}T\S+ "
            r"(START|DONE|BLOCKED|SURVEY|WAKE|STEP|CALL|POLL)\b)")
        for line in lines:
            assert record.match(line), f"partial record: {line!r} in {text!r}"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(td, ignore_errors=True)


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
    terminal line with the handle closed and the outcome/exit unmasked.
    The unexpected-error detail must also be bounded (~200) so a
    pathological exception cannot flood the tail-read heartbeat file."""
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

        # (c) a long-message non-OSError raised inside the guarded outcome
        # block: the heartbeat detail must be bounded at the outcome-branch
        # convention (~200), not written in full.
        hb3 = os.path.join(work, "longerr.log")
        rc3 = _run_unexpected_error_in_process("E" * 500, hb3)
        assert rc3 == 3, rc3
        t3 = [l for l in _lines(_read(hb3)) if " BLOCKED " in l]
        assert len(t3) == 1, t3
        assert "unexpected dispatch error: " in t3[0], t3
        after = t3[0].split("unexpected dispatch error: ", 1)[1]
        assert len(after) <= 200, len(after)
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
        "CREATE TABLE session_v2 (id TEXT PRIMARY KEY, model TEXT, title TEXT, "
        "agent TEXT, cost REAL, tokens_input INTEGER, tokens_output INTEGER, "
        "time_updated INTEGER, directory TEXT, parent_id TEXT)")
    con.execute(
        "INSERT INTO session_v2 (id, model, title, agent) VALUES (?, ?, ?, ?)",
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
                         {"id": "qwen3.8-flash", "providerID": "opencode-go",
                          "variant": "default"})
        r = _run("valid", extra=["--contract", "implement-handoff"],
                 env_extra={"OPENCODE_DB_PATH": dbp})
        assert r.rc == 0, (r.rc, r.stderr)
        assert r.records[0]["model"] == "opencode-go/qwen3.8-flash", r.records
        assert "model=opencode-go/qwen3.8-flash" in r.stdout, r.stdout
        assert "binding=opencode-go/kimi-k3.1-pro" in r.stdout, r.stdout
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
        assert r.records[0]["model"] == "opencode-go/kimi-k3.1-pro", r.records
        assert "model=opencode-go/kimi-k3.1-pro" in r.stdout, r.stdout

        r2 = _run("valid", extra=["--contract", "implement-handoff",
                                  "--model", "opencode-go/qwen3.8-flash"],
                  env_extra={"OPENCODE_DB_PATH": missing})
        assert r2.records[0]["model"] == "opencode-go/qwen3.8-flash", r2.records

        # a DB that lacks the session row also falls back
        dbp = os.path.join(work, "other.db")
        _make_session_db(dbp, "ses_other",
                         {"id": "x", "providerID": "opencode-go"})
        r3 = _run("valid", extra=["--contract", "implement-handoff"],
                  env_extra={"OPENCODE_DB_PATH": dbp})
        assert r3.records[0]["model"] == "opencode-go/kimi-k3.1-pro", r3.records
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC12/AC13/AC14: grants + denial classification -------------------------

def test_allow_dir_grants_external_permission():
    """AC16: --allow-dirs emits deny-first ordered V2 rules with an explicit
    allow root, and rejects a non-existent path before launch."""
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
        rules = _ext_map(dump)
        # deny-first catch-all, allow after it, execute deny last
        assert rules[0] == {"action": "external_directory", "resource": "*",
                            "effect": "deny"}, rules
        assert key in _allow_set(rules), rules
        assert rules[-1]["action"] == "execute" and \
            rules[-1]["effect"] == "deny", rules

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
    """M2/V2: an unparsable caller OPENCODE_CONFIG_CONTENT is irrelevant to V2
    grants (the accepted mechanism is the generated XDG_CONFIG_HOME); the
    dispatch proceeds and the allow root is still present."""
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
        assert key in _allow_set(_ext_map(dump))
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

    # A denial is a failed dispatch even without a delegated-result contract:
    # the D2 negative drill has no markers, yet must exit non-zero.
    r3 = _run("denied")
    assert r3.rc != 0, (r3.rc, r3.stdout)
    detail3 = r3.records[0]["detail"] or ""
    assert detail3.startswith("permission denied:"), detail3


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


# --- AC6: per-agent-class permission profile (RM-058 D4) --------------------

def _ext_map(dump_path):
    env = json.loads(_read(dump_path))
    root = env["XDG_CONFIG_HOME"]
    with open(os.path.join(root, "opencode", "opencode.jsonc")) as fh:
        return json.load(fh)["permissions"]


def _allow_set(rules):
    return {r["resource"] for r in rules
            if r["action"] == "external_directory" and r["effect"] == "allow"}


def test_profile_env_merge():
    """AC16/D4: profile grants become ordered V2 allow roots; the test class
    is narrower; --profile none leaves only the deny-first baseline."""
    work = tempfile.mkdtemp(prefix="dispatch-profile-")
    try:
        extra = os.path.join(work, "extra")
        os.makedirs(extra)
        dump = os.path.join(work, "env.json")
        r = _run("valid", extra=["--profile", "auto", "--allow-dirs", extra,
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ENV": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        allowed = _allow_set(_ext_map(dump))
        roots = [os.path.expanduser("~/repos"),
                 os.path.expanduser("~/.config/opencode"),
                 os.path.expanduser("~/.local/share/opencode"), extra]
        for d in roots:
            assert os.path.join(os.path.abspath(d), "**") in allowed, \
                (d, allowed)

        dump2 = os.path.join(work, "env2.json")
        r2 = _run("valid", agent="test-writer", extra=["--profile", "auto",
                                                       "--contract", "implement-handoff"],
                  env_extra={"STUB_DUMP_ENV": dump2})
        assert r2.rc == 0, (r2.rc, r2.stderr)
        allowed2 = _allow_set(_ext_map(dump2))
        assert os.path.join(os.path.expanduser("~/repos"), "**") in allowed2
        assert os.path.join(os.path.expanduser("~/.config/opencode"), "**") \
            not in allowed2, allowed2

        dump3 = os.path.join(work, "env3.json")
        r3 = _run("valid", extra=["--profile", "none",
                                  "--contract", "implement-handoff"],
                  env_extra={"STUB_DUMP_ENV": dump3})
        assert r3.rc == 0, (r3.rc, r3.stderr)
        assert _allow_set(_ext_map(dump3)) == set(), _ext_map(dump3)

        # an unknown named profile exits 2 before launch
        r5 = _run("valid", extra=["--profile", "nope",
                                  "--contract", "implement-handoff"])
        assert r5.rc == 2, (r5.rc, r5.stderr)
        assert "session_id=" not in r5.stdout, r5.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC5: worktree-safe dispatch (RM-058 D3) --------------------------------

def _git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True)


def _init_repo(path):
    subprocess.run(["git", "init", "-b", "main", path], check=True,
                   capture_output=True)
    _git(path, "config", "user.email", "test@test")
    _git(path, "config", "user.name", "test")
    with open(os.path.join(path, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("init\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


def _count(repo):
    return int(_git(repo, "rev-list", "--count", "HEAD").stdout.strip())


def _head(repo):
    return _git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()


def test_worktree_safety():
    """AC5: with --worktree the child's commit lands on dispatch/<name> inside
    .scratch/worktrees/<name> while the parent stays on main with zero new
    commits; a parent off main exits 2 before launch. The absent-flag case is
    the red-first 2026-10-13 reproduction (parent branch mutated)."""
    # (0) red-first rehearsal: WITHOUT --worktree the child mutates the parent
    repo0 = tempfile.mkdtemp(prefix="dispatch-wt-red-")
    try:
        _init_repo(repo0)
        base0 = _count(repo0)
        _run("commitdir", extra=[], cwd=repo0)
        assert _count(repo0) == base0 + 1, \
            "red-first: pre-fix dispatch did not mutate the parent branch"
        assert "child commit" in _git(repo0, "log", "--oneline").stdout
    finally:
        shutil.rmtree(repo0, ignore_errors=True)

    repo = tempfile.mkdtemp(prefix="dispatch-wt-")
    try:
        _init_repo(repo)
        base = _count(repo)
        r = _run("commitdir", extra=["--worktree", "t1"], cwd=repo)
        assert r.rc == 0, (r.rc, r.stdout, r.stderr)
        assert "dispatch/t1" in r.stdout, r.stdout

        # parent is untouched, still on main
        assert _head(repo) == "main", _head(repo)
        assert _count(repo) == base, _count(repo)
        assert "child commit" not in _git(repo, "log", "--oneline").stdout

        # the commit landed on dispatch/t1 inside the worktree only
        wt = os.path.join(repo, ".scratch", "worktrees", "t1")
        assert os.path.isdir(wt), wt
        assert _head(wt) == "dispatch/t1", _head(wt)
        assert "child commit" in _git(wt, "log", "--oneline").stdout

        # a --session resume reuses the existing worktree, parent untouched
        r_resume = _run("valid", extra=["--worktree", "t1",
                                        "--session", "ses_stub_valid"], cwd=repo)
        assert r_resume.rc == 0, (r_resume.rc, r_resume.stdout, r_resume.stderr)
        assert _head(repo) == "main", _head(repo)
        assert _count(repo) == base, _count(repo)

        # a resume against a missing worktree refuses before opencode launches
        r_missing = _run("valid", extra=["--worktree", "nope",
                                         "--session", "ses_stub_valid"], cwd=repo)
        assert r_missing.rc == 2, (r_missing.rc, r_missing.stderr)
        assert "not found" in r_missing.stderr, r_missing.stderr
        assert "session_id=" not in r_missing.stdout, r_missing.stdout

        # a parent off main refuses before opencode launches (no session)
        _git(repo, "checkout", "-b", "off-main")
        r2 = _run("commitdir", extra=["--worktree", "t2"], cwd=repo)
        assert r2.rc == 2, (r2.rc, r2.stdout, r2.stderr)
        assert "not on main" in r2.stderr, r2.stderr
        assert "session_id=" not in r2.stdout, r2.stdout
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def _dispatch_module():
    spec = importlib.util.spec_from_file_location("dispatch_mod", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_profile_class_resolution():
    """D4 coverage: exact key > alias > longest-prefix; dir expansion; the
    profile-driven worktree name derivation."""
    mod = _dispatch_module()
    profiles, aliases = mod.load_profiles()
    assert mod.resolve_profile_name("architect", profiles, aliases) == "architect"
    assert mod.resolve_profile_name("council-architecture", profiles,
                                    aliases) == "council"
    assert mod.resolve_profile_name("test-writer", profiles, aliases) == "test"
    assert mod.resolve_profile_name("vision-critic-fast", profiles,
                                    aliases) == "reviewer"
    assert mod.resolve_profile_name("debugger", profiles, aliases) == "implementer"
    assert mod.resolve_profile_name("totally-unknown", profiles,
                                    aliases) == "default"
    assert mod.expand_dirs(["$HOME/repos"]) == [os.path.expanduser("~/repos")]
    assert mod.resolve_profile("x", "none", profiles, aliases)[1]["allow_dirs"] == []
    assert mod.resolve_profile("x", "nope", profiles, aliases) == (None, None)

    work = tempfile.mkdtemp(prefix="dispatch-wtname-")
    try:
        hb = os.path.join(work, "progress.log")
        with open(hb, "w", encoding="utf-8") as fh:
            fh.write("# progress: implement RM-058\n")
        assert mod.default_worktree_name(os.path.join(work, "p.md"), hb) == \
            "implement-rm-058"
        assert mod.default_worktree_name(os.path.join(work, "my-task.md"),
                                         None) == "my-task"
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC1 integration: --wake-to spawns the observer (RM-058 D2) -------------

def _write_observer_stub(path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(OBSERVER_STUB)
    os.chmod(path, 0o755)


def test_wake_to_spawns_observer():
    """AC1 integration point: with --wake-to the dispatcher spawns the detached
    observer once the child session id prints and forwards the attach target
    (--wake-url/--wake-agent); without --wake-to no observer is spawned."""
    work = tempfile.mkdtemp(prefix="dispatch-wake-")
    try:
        hb = os.path.join(work, "progress.log")
        marker = os.path.join(work, "observer.json")
        stub = os.path.join(work, "observer_stub.py")
        _write_observer_stub(stub)
        r = _run("valid", extra=["--heartbeat", hb, "--wake-to", "ses_orch",
                                 "--wake-agent", "curator",
                                 "--wake-url", "http://127.0.0.1:4096",
                                 "--contract", "implement-handoff"],
                 env_extra={"OBSERVE_COMPLETION_PATH": stub,
                            "OBSERVER_STUB_OUT": marker})
        assert r.rc == 0, (r.rc, r.stderr)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not os.path.isfile(marker):
            time.sleep(0.05)
        assert os.path.isfile(marker), "observer was not spawned"
        argv = json.loads(_read(marker))
        assert "--orchestrator-session" in argv and "ses_orch" in argv, argv
        assert "--child-session" in argv and "ses_stub_valid" in argv, argv
        assert "--heartbeat" in argv and hb in argv, argv
        assert "--wake-agent" in argv and "curator" in argv, argv
        assert "--wake-url" in argv, argv
        assert argv[argv.index("--wake-url") + 1] == "http://127.0.0.1:4096", argv

        # --wake-url omitted resolves from OPENCODE_WAKE_URL and is forwarded
        marker_env = os.path.join(work, "observer_env.json")
        r_env = _run("valid", extra=["--heartbeat", hb, "--wake-to", "ses_orch",
                                     "--wake-agent", "curator",
                                     "--contract", "implement-handoff"],
                     env_extra={"OBSERVE_COMPLETION_PATH": stub,
                                "OBSERVER_STUB_OUT": marker_env,
                                "OPENCODE_WAKE_URL": "http://127.0.0.1:4199"})
        assert r_env.rc == 0, (r_env.rc, r_env.stderr)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not os.path.isfile(marker_env):
            time.sleep(0.05)
        argv_env = json.loads(_read(marker_env))
        assert "--wake-url" in argv_env, argv_env
        assert argv_env[argv_env.index("--wake-url") + 1] == \
            "http://127.0.0.1:4199", argv_env

        # without --wake-to no observer is spawned
        marker2 = os.path.join(work, "observer2.json")
        r2 = _run("valid", extra=["--heartbeat", hb,
                                  "--contract", "implement-handoff"],
                  env_extra={"OBSERVE_COMPLETION_PATH": stub,
                             "OBSERVER_STUB_OUT": marker2})
        assert r2.rc == 0, (r2.rc, r2.stderr)
        time.sleep(0.3)
        assert not os.path.isfile(marker2), "observer spawned without --wake-to"

        # --wake-to without --heartbeat is a usage error (exit 2)
        r3 = _run("valid", extra=["--wake-to", "ses_orch",
                                  "--wake-agent", "curator"])
        assert r3.rc == 2, (r3.rc, r3.stderr)

        # --wake-to without --wake-agent is a usage error, before launch
        hb4 = os.path.join(work, "noagent.log")
        r4 = _run("valid", extra=["--heartbeat", hb4, "--wake-to", "ses_orch"])
        assert r4.rc == 2, (r4.rc, r4.stdout, r4.stderr)
        assert "session_id=" not in r4.stdout, r4.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC7: the launch echo proves intent, never status -----------------------

def test_dispatcher_heartbeat_has_no_survey_claim():
    """AC7: the dispatcher writes only the envelope (header + START + one
    terminal line); a `SURVEY running` claim comes only from the observer."""
    work = tempfile.mkdtemp(prefix="dispatch-hb-")
    try:
        hb = os.path.join(work, "progress.log")
        r = _run("valid", extra=["--heartbeat", hb,
                                 "--contract", "implement-handoff"])
        assert r.rc == 0, (r.rc, r.stderr)
        lines = _lines(r.heartbeat)
        assert not any(" SURVEY " in l for l in lines), lines
        assert not any(" WAKE " in l for l in lines), lines
        terminals = [l for l in lines if " DONE " in l or " BLOCKED " in l]
        assert len(terminals) == 1 and "DONE ok" in terminals[0], lines
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_delegation_title_marker_associates_run_vehicle():
    """RM-069 AC1: a run-vehicle child carries the machine-readable marker in
    its `--title`, so the observer maps it without a side registry. The
    literal is the cross-language contract asserted by the TS parser test."""
    work = tempfile.mkdtemp(prefix="dispatch-delegation-")
    try:
        dump = os.path.join(work, "argv.json")
        r = _run("valid", extra=["--delegation-to", "ses_parent",
                                 "--task-label", "RM-069 drill",
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ARGV": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        argv = json.loads(r.argv_dump)
        title = argv[argv.index("--title") + 1]
        assert title == "[delegate:ses_parent] architect: RM-069 drill", title
        assert "delegation=[delegate:ses_parent] architect: RM-069 drill" in r.stdout
        parsed = v2.parse_delegation_title(title)
        assert parsed == {"orchestratorID": "ses_parent", "agent": "architect",
                          "task": "RM-069 drill"}, parsed
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_delegation_title_defaults_to_wake_to_and_flattens():
    """RM-069: --wake-to already names the orchestrator; the task label
    defaults to the heartbeat header and the marker never carries newlines."""
    work = tempfile.mkdtemp(prefix="dispatch-delegation-wake-")
    try:
        hb = os.path.join(work, "progress.log")
        dump = os.path.join(work, "argv.json")
        prompt = os.path.join(work, "prompt.md")
        with open(prompt, "w", encoding="utf-8") as fh:
            fh.write("Do it.")
        r = _run("valid", extra=["--heartbeat", hb, "--wake-to", "ses_orch",
                                 "--wake-agent", "curator",
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ARGV": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        argv = json.loads(r.argv_dump)
        title = argv[argv.index("--title") + 1]
        assert title.startswith("[delegate:ses_orch] architect: "), title
        assert "\n" not in title, title
        long_title = v2.delegation_title("ses_orch", "architect", "x " * 400)
        assert len(long_title) <= v2.DELEGATION_TITLE_MAX, len(long_title)
        assert long_title.endswith("..."), long_title
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_headless_dispatch_has_no_delegation_marker():
    """RM-069: a headless/standalone dispatch has no interactive parent and
    keeps the existing contract — no title marker, no observer assumption."""
    work = tempfile.mkdtemp(prefix="dispatch-no-delegation-")
    try:
        dump = os.path.join(work, "argv.json")
        r = _run("valid", extra=["--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ARGV": dump})
        assert r.rc == 0, (r.rc, r.stderr)
        argv = json.loads(r.argv_dump)
        assert "--title" not in argv, argv
        assert "delegation=" not in r.stdout, r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_interactive_dispatch_joins_the_shared_service():
    """RM-069 AC1: with a running service and no private-server reason, the
    child is dispatched onto that service so the TUI event stream owns it."""
    work = tempfile.mkdtemp(prefix="dispatch-shared-service-")
    try:
        dump = os.path.join(work, "argv.json")
        r = _run("valid", extra=["--delegation-to", "ses_parent",
                                 "--profile", "none",
                                 "--contract", "implement-handoff"],
                 env_extra={"STUB_DUMP_ARGV": dump,
                            "OPENCODE_V2_NO_SERVICE": "",
                            "STUB_SERVICE_URL": "http://127.0.0.1:4096"})
        assert r.rc == 0, (r.rc, r.stderr)
        v2.reset_service_cache()
        argv = json.loads(r.argv_dump)
        assert argv[argv.index("--server") + 1] == "http://127.0.0.1:4096", argv
        assert "--standalone" not in argv, argv
    finally:
        v2.reset_service_cache()
        shutil.rmtree(work, ignore_errors=True)


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
