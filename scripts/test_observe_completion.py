#!/usr/bin/env python3
"""RED-first contract tests for scripts/observe_completion.py (RM-058).

Hermetic: a unified stub `opencode` on PATH serves both the dispatch stream
(contract-invalid failure case) and the wake delivery (`--session` case); the
orchestrator session lives in an `OPENCODE_DB_PATH` fixture; the poll loop is
driven with an injectable `sleep` / `now` so no real waiting happens.

Covers AC1 (wake-on-success within SLA), AC2 (failure + abort enumeration),
AC3 (rule-1 quiescence gate), AC4 (deadline escalation is durable), AC7
(heartbeat line ownership / poll-gated claims), AC9 (RM-059 seam intact).

Run: python3 scripts/test_observe_completion.py
"""
import contextlib
import datetime
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
OBSERVE = os.path.join(HERE, "observe_completion.py")
DISPATCH = os.path.join(HERE, "dispatch_agent.py")


def _ts(offset=0):
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")

# One stub serves both roles: a wake delivery is identified by `--attach`
# (the amended D2 vehicle); otherwise it emits a canned `--format json`
# dispatch stream.
STUB_OPENCODE = r'''#!/usr/bin/env python3
"""Stub opencode for test_observe_completion.py (no model calls)."""
import json
import os
import sys

argv = sys.argv[1:]

if argv[:1] == ["api"]:
    out = os.environ.get("WAKE_STUB_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(argv) + "\n")
    if os.environ.get("WAKE_STUB_FAIL"):
        print('{"_tag": "InternalError"}')
        print("HTTP 500 Internal Server Error")
        sys.exit(0)
    if os.environ.get("WAKE_STUB_404"):
        print('{"_tag": "SessionNotFoundError"}')
        print("HTTP 404 Not Found")
        sys.exit(0)
    method = argv[1] if len(argv) > 1 else ""
    path = argv[2] if len(argv) > 2 else ""
    if method == "GET" and path.startswith("/api/session/"):
        sid = path.rsplit("/", 1)[-1]
        print(json.dumps({"data": {"id": sid}}))
        sys.exit(0)
    print('{"ok": true}')
    sys.exit(0)

mode = os.environ.get("STUB_MODE", "valid")
sid = "ses_stub_valid"


def emit(obj):
    print(json.dumps(obj), flush=True)


emit({"type": "step_start", "sessionID": sid,
      "part": {"type": "step-start", "sessionID": sid}})
if mode == "missmarker":
    text = "Verification: all green"
else:
    text = "Verification: all green\nHandoff: ready"
emit({"type": "text", "sessionID": sid,
      "part": {"type": "text", "sessionID": sid, "text": text}})
emit({"type": "step_finish", "sessionID": sid,
      "part": {"type": "step-finish", "tokens": {"input": 1, "output": 1},
               "cost": 0.0}})
'''


# --- helpers -----------------------------------------------------------------

def _load_observe():
    assert os.path.isfile(OBSERVE), "scripts/observe_completion.py missing (red-first)"
    spec = importlib.util.spec_from_file_location("observe_completion", OBSERVE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_bin(td):
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    stub = os.path.join(bin_dir, "opencode")
    with open(stub, "w", encoding="utf-8") as fh:
        fh.write(STUB_OPENCODE)
    os.chmod(stub, 0o755)
    return bin_dir


def _blocks(parts):
    blocks = []
    closed = False
    for d in parts:
        t = d.get("type")
        if t == "text":
            blocks.append({"type": "text", "text": d.get("text") or ""})
        elif t == "tool":
            blocks.append({"type": "tool", "name": d.get("tool"),
                           "state": d.get("state") or {}})
        elif t in ("step-finish", "step_finish"):
            closed = True
    return blocks, closed


def _insert_messages(con, sid, parts, updated):
    blocks, closed = _blocks(parts)
    data = {"content": blocks}
    if closed:
        data["finish"] = "stop"
    con.execute(
        "INSERT INTO session_message (id, session_id, type, seq, "
        "time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
        (f"{sid}-m0", sid, "assistant", 1, 1000, updated, json.dumps(data)))


def _make_db(path, sessions):
    """sessions: list of (sid, parts, time_updated) -> V2 storage fixture."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session_v2 (id TEXT PRIMARY KEY, model TEXT, title TEXT, "
        "agent TEXT, cost REAL, tokens_input INTEGER, tokens_output INTEGER, "
        "time_updated INTEGER, time_created INTEGER, directory TEXT, "
        "parent_id TEXT, time_idle INTEGER, idle_outcome TEXT)")
    con.execute(
        "CREATE TABLE session_message (id TEXT, session_id TEXT, type TEXT, "
        "seq INTEGER, time_created INTEGER, time_updated INTEGER, data TEXT)")
    for sid, parts, updated in sessions:
        con.execute(
            "INSERT INTO session_v2 (id, model, title, agent, cost, "
            "tokens_input, tokens_output, time_updated, time_created) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, None, "orchestrator", "architect", 0, 0, 0, updated, 1000))
        _insert_messages(con, sid, parts, updated)
    con.commit()
    con.close()


def _set_parts(path, sid, parts, updated):
    con = sqlite3.connect(path)
    con.execute("DELETE FROM session_message WHERE session_id=?", (sid,))
    _insert_messages(con, sid, parts, updated)
    con.execute("UPDATE session_v2 SET time_updated=? WHERE id=?", (updated, sid))
    con.commit()
    con.close()


IDLE = [{"type": "text", "text": "done"}, {"type": "step-finish"}]
IN_FLIGHT = [{"type": "tool", "tool": "bash",
              "state": {"status": "running", "input": {"command": "sleep 999"}}}]
# mid-generation: the newest assistant step is open (trailing step-start), no
# tool in flight -- the 2026-10-15 generation-blindness instance (AC3b).
OPEN_STEP = [{"type": "text", "text": "partial"}, {"type": "step-start"}]


def _write_hb(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _hb_lines(path):
    return [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]


def _cfg(obs, hb, agent="architect", sid="ses_orch", child="ses_stub_valid",
         result=None, logs=None, wake_url="http://127.0.0.1:4096",
         wake_agent="curator", **extra):
    argv = ["--heartbeat", hb, "--agent", agent,
            "--orchestrator-session", sid,
            "--interval", "0", "--deadline", "300", "--liveness-seconds", "480"]
    if child:
        argv += ["--child-session", child]
    if result:
        argv += ["--result", result]
    if logs:
        argv += ["--logs-dir", logs]
    if wake_agent:
        argv += ["--wake-agent", wake_agent]
    if wake_url:
        argv += ["--wake-url", wake_url]
    for k, v in extra.items():
        argv += ["--" + k.replace("_", "-"), str(v)]
    return obs.build_parser().parse_args(argv)


@contextlib.contextmanager
def _env(overrides):
    old = {}
    for k, v in overrides.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _invs(path):
    if not os.path.isfile(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _run_dispatch(td, extra, mode="valid"):
    bin_dir = _stub_bin(td)
    prompt = os.path.join(td, "prompt.md")
    with open(prompt, "w", encoding="utf-8") as fh:
        fh.write("Do the thing.")
    out = os.path.join(td, "result.md")
    logs = os.path.join(td, "logs")
    cmd = [sys.executable, DISPATCH, "--agent", "architect",
           "--prompt-file", prompt, "--out", out, "--logs-dir", logs,
           "--timeout", "10"] + list(extra)
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["STUB_MODE"] = mode
    subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=REPO,
                   timeout=60)
    return out, logs


# --- AC1: wake-on-success, owner-ping-free -----------------------------------

def test_ac1_wake_on_success_exactly_once():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac1-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, result=os.path.join(td, "result.md"),
                   logs=os.path.join(td, "logs"),
                   wake_url="http://127.0.0.1:4096", wake_agent="curator")
        shutil.rmtree(os.path.join(td, "logs"), ignore_errors=True)
        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_WAKE_URL": None, "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=lambda s: None)
        assert rc == 0, rc
        invs = _invs(inv)
        assert len(invs) == 3, invs
        # AC1/AC19: preflight -> switch agent -> prompt, all on the same id.
        calls = [(i[1], i[2]) for i in invs]
        assert calls == [
            ("GET", "/api/session/ses_orch"),
            ("POST", "/api/session/ses_orch/agent"),
            ("POST", "/api/session/ses_orch/prompt"),
        ], calls
        assert '"agent": "curator"' in invs[1][-1], invs[1]
        text = invs[2][-1]
        assert "DISPATCH WAKE architect outcome=success" in text, text
        assert "DISPATCH WAKE architect outcome=success" in text, text
        assert "child=ses_stub_valid" in text, text
        assert hb in text, text
        # exactly one WAKE line, and it is the last heartbeat line
        lines = _hb_lines(hb)
        wakes = [l for l in lines if " WAKE " in l]
        assert len(wakes) == 1, lines
        assert lines[-1] == wakes[0], lines
        # the observer wrote its SURVEY proof (child evidence existed)
        assert sum(1 for l in lines if " SURVEY " in l) == 1, lines
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC2: failure + abort both enumerated ------------------------------------

def test_ac2_failure_names_missing_markers():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac2f-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        out, logs = _run_dispatch(
            td, ["--heartbeat", hb, "--contract", "implement-handoff"],
            mode="missmarker")
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, result=out, logs=logs, child="ses_stub_valid")
        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=lambda s: None)
        assert rc == 0, rc
        invs = _invs(inv)
        assert len(invs) == 3, invs
        text = invs[2][-1]
        assert "outcome=failure" in text, text
        assert "Handoff" in text, text
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_ac2_abort_names_liveness_basis():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac2a-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T09:00:00Z START p.md",
        ])
        inv = os.path.join(td, "inv.jsonl")
        missing_db = os.path.join(td, "missing.db")
        cfg = _cfg(obs, hb, child=None, logs=None, liveness_seconds=0)
        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": missing_db, "WAKE_STUB_OUT": inv,
                   "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=lambda s: None)
        assert rc == 0, rc
        invs = _invs(inv)
        assert len(invs) == 3, invs
        text = invs[2][-1]
        assert "outcome=aborted" in text, text
        assert "no heartbeat" in text.lower(), text
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC3: rule-1 quiescence gate ---------------------------------------------

def test_ac3_gate_blocks_wake_until_quiescent():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac3-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IN_FLIGHT, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, logs=None)

        state = {"calls": 0}

        def sleep_hook(_s):
            state["calls"] += 1
            if state["calls"] == 1:
                # the orchestrator had a tool in flight; the wake must not have
                # fired yet
                assert not os.path.exists(inv), "wake fired while in flight"
                # the tool lands -> the session becomes quiescent
                _set_parts(dbp, "ses_orch", IDLE, 2000)

        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=sleep_hook)
        assert rc == 0, rc
        invs = _invs(inv)
        assert len(invs) == 3, invs
        assert "outcome=success" in invs[2][-1], invs
        assert state["calls"] >= 1, state
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC3b: mid-generation open step blocks the wake (2026-10-15 latent) ------

def test_ac3b_gate_blocks_mid_generation_open_step():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac3b-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        # the newest assistant step is open, no tool in flight, time_updated
        # stable across two polls -- the generation-blind predicate read this
        # as quiescent; the revised gate must not.
        _make_db(dbp, [("ses_orch", OPEN_STEP, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, logs=None)

        state = {"calls": 0}

        def sleep_hook(_s):
            state["calls"] += 1
            if state["calls"] >= 2:
                # two stable polls with an open step and still no wake
                assert not os.path.exists(inv), "wake fired mid-generation"
                _set_parts(dbp, "ses_orch", IDLE, 2000)

        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_WAKE_URL": None, "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=sleep_hook)
        assert rc == 0, rc
        invs = _invs(inv)
        assert len(invs) == 3, invs
        assert "outcome=success" in invs[2][-1], invs
        assert state["calls"] >= 2, state
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC4: deadline / no-target escalation is durable, not silent --------------

def _deferred_lines(hb):
    return [l for l in _hb_lines(hb) if " WAKE_DEFERRED " in l]


def test_ac4a_deadline_busy_names_gate():
    """AC4(a): deadline forced short with the orchestrator continuously busy --
    zero accepted deliveries, exactly one WAKE_DEFERRED whose reason names the
    gate."""
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac4a-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IN_FLIGHT, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, deadline=1.0, interval=0.3)
        clock = {"t": 0.0}

        def fake_now():
            return clock["t"]

        def fake_sleep(s):
            clock["t"] += s or 0.05

        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_WAKE_URL": None, "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=fake_sleep, now=fake_now)
        assert rc == 0, rc
        assert _invs(inv) == [], "no wake may fire while continuously in flight"
        defers = _deferred_lines(hb)
        assert len(defers) == 1, _hb_lines(hb)
        assert defers[0].endswith("WAKE_DEFERRED success reason=quiescence-gate"), \
            defers
        assert _hb_lines(hb)[-1] == defers[0], _hb_lines(hb)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_ac4b_no_attach_target_defers_without_spawning():
    """AC4(b): no --wake-url resolvable and env unset -- the observer writes
    WAKE_DEFERRED ... reason=no-attach-target at the first terminal poll and
    never spawns opencode (the legacy ghost vehicle is structurally gone)."""
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac4b-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, wake_url=None, wake_agent="curator")
        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_WAKE_URL": None, "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=lambda s: None)
        assert rc == 0, rc
        assert _invs(inv) == [], "no opencode subprocess may spawn without a target"
        defers = _deferred_lines(hb)
        assert len(defers) == 1, _hb_lines(hb)
        assert defers[0].endswith("WAKE_DEFERRED success reason=no-attach-target"), \
            defers
        assert _hb_lines(hb)[-1] == defers[0], _hb_lines(hb)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_ac4c_refused_delivery_retries_then_defers():
    """AC4(c): the server refuses (stub exits 1) on every attempt until the
    deadline -- retries are bounded by the deadline and the one final
    WAKE_DEFERRED reason= names the refusal."""
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac4c-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb, deadline=1.0, interval=0.3)
        clock = {"t": 0.0}

        def fake_now():
            return clock["t"]

        def fake_sleep(s):
            clock["t"] += s or 0.05

        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "WAKE_STUB_FAIL": "1", "OPENCODE_WAKE_URL": None,
                   "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=fake_sleep, now=fake_now)
        assert rc == 0, rc
        # the refusal was retried (>=2) but bounded by the deadline (not a spin)
        attempts = len(_invs(inv))
        assert 2 <= attempts <= 8, f"retries not bounded by the deadline: {attempts}"
        defers = _deferred_lines(hb)
        assert len(defers) == 1, _hb_lines(hb)
        assert "reason=" in defers[0], defers
        assert "500" in defers[0], defers
        assert _hb_lines(hb)[-1] == defers[0], _hb_lines(hb)
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC7: no status claim without a poll (heartbeat line ownership) ----------

def test_ac7_survey_only_after_child_evidence_then_wake_last():
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-ac7-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            f"{_ts(0)} START p.md",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        cfg = _cfg(obs, hb)

        state = {"calls": 0}

        def sleep_hook(_s):
            state["calls"] += 1
            if state["calls"] == 1:
                # the launch record alone produced no SURVEY: assert that here
                assert sum(1 for l in _hb_lines(hb) if " SURVEY " in l) == 0
                with open(hb, "a", encoding="utf-8") as fh:
                    fh.write(f"{_ts(1)} STEP 1/1 recon\n")
            elif state["calls"] == 2:
                # exactly one SURVEY after the first child-owned line
                assert sum(1 for l in _hb_lines(hb) if " SURVEY " in l) == 1
                with open(hb, "a", encoding="utf-8") as fh:
                    fh.write(f"{_ts(2)} DONE ok\n")

        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=sleep_hook)
        assert rc == 0, rc
        lines = _hb_lines(hb)
        assert sum(1 for l in lines if " SURVEY " in l) == 1, lines
        step_i = next(i for i, l in enumerate(lines) if " STEP " in l)
        survey_i = next(i for i, l in enumerate(lines) if " SURVEY " in l)
        assert survey_i > step_i, lines
        assert lines[-1].endswith("WAKE success"), lines
        assert len(_invs(inv)) == 3, _invs(inv)
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --- AC9: RM-059 seam intact -------------------------------------------------

def test_ac9_no_liveness_vocabulary_and_awaiting():
    obs = _load_observe()
    src = open(OBSERVE, encoding="utf-8").read()
    assert "verdict(" not in src, "observer must not compute a liveness verdict"
    assert not re.search(r"\b(STALLED|DEAD|BLOCKING|OK|WARN)\b", src), \
        "observer must not emit the RM-059 liveness vocabulary"
    assert "AWAITING" in src
    assert "has_terminal_result" in src

    hb = {"entries": [("2026-10-15T12:00:00Z", "START", "x")],
          "last_age": 1.0, "repeats": 0}
    assert obs.classify(hb, None, 5.0, 480, False)[0] == "AWAITING"
    assert obs.classify(hb, None, 5000.0, 480, False)[0] == "aborted"


def test_status_hook_snapshot_keeps_one_terminal_wake():
    """RM-069 AC10/AC11: the opt-in status snapshot is a read-only fallback
    surface — it adds no prompt, and the terminal wake stays exactly once."""
    obs = _load_observe()
    td = tempfile.mkdtemp(prefix="observe-status-")
    try:
        bin_dir = _stub_bin(td)
        hb = os.path.join(td, "progress.log")
        _write_hb(hb, [
            "# progress: architect dispatch",
            "2026-10-15T12:00:00Z START p.md",
            "2026-10-15T12:00:05Z STEP 1/1 recon",
            "2026-10-15T12:01:00Z DONE ok",
        ])
        dbp = os.path.join(td, "opencode.db")
        _make_db(dbp, [("ses_orch", IDLE, 1000)])
        inv = os.path.join(td, "inv.jsonl")
        status = os.path.join(td, "status.json")
        cfg = _cfg(obs, hb, result=os.path.join(td, "result.md"),
                   logs=os.path.join(td, "logs"),
                   status_file=status)
        with _env({"PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                   "OPENCODE_DB_PATH": dbp, "WAKE_STUB_OUT": inv,
                   "OPENCODE_WAKE_URL": None, "OPENCODE_V2_API_VIA_CLI": "1",
                   "OPENCODE_V2_NO_SERVICE": "1"}):
            rc = obs.run(cfg, sleep=lambda s: None)
        assert rc == 0, rc
        snapshot = json.load(open(status, encoding="utf-8"))
        assert snapshot["outcome"] == "success", snapshot
        assert snapshot["terminal"] is True, snapshot
        assert snapshot["agent"] == "architect", snapshot
        assert snapshot["thresholds"]["stall_seconds"] == 240, snapshot
        assert snapshot["thresholds"]["liveness_seconds"] == 480, snapshot
        # one wake prompt, unchanged by the snapshot
        invs = _invs(inv)
        assert [i[1:3] for i in invs] == [
            ["GET", "/api/session/ses_orch"],
            ["POST", "/api/session/ses_orch/agent"],
            ["POST", "/api/session/ses_orch/prompt"],
        ], invs
        lines = _hb_lines(hb)
        assert len([l for l in lines if " WAKE " in l]) == 1, lines
    finally:
        shutil.rmtree(td, ignore_errors=True)


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
