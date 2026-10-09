#!/usr/bin/env python3
"""Tests for scripts/session_guard.py (plan session-guard-fail-fast) —
offline, no real DB, no network.

One test per acceptance criterion AC1–AC10 (AC11–AC13 are docs/CI/smoke
checks outside this suite). Run: python3 scripts/test_session_guard.py
"""
import importlib.util
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
GUARD = os.path.join(HERE, "session_guard.py")
LOG_RUN = os.path.join(REPO, "skills", "observing-runs", "scripts", "log_run.py")

T0 = 1791388100000  # fixed ms epoch anchor (2026-10-07T11:48:20Z-ish)


def _load_guard():
    """Load scripts/session_guard.py; every AC fails naming its absence
    until the module exists (red-first, pre-implementation)."""
    if not os.path.isfile(GUARD):
        raise AssertionError(
            "scripts/session_guard.py missing — session-tree guard not implemented")
    spec = importlib.util.spec_from_file_location("session_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- fixture DB --------------------------------------------------------------

def _make_db(path, sessions, messages=(), parts=()):
    """Minimal opencode.db-shaped fixture. Sessions/messages/parts rows carry
    only the columns the guard reads (names match the live schema)."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session (id TEXT PRIMARY KEY, parent_id TEXT, title TEXT,"
        " agent TEXT, directory TEXT, model TEXT, cost REAL, tokens_input INTEGER,"
        " tokens_output INTEGER, time_created INTEGER, time_updated INTEGER)")
    con.execute(
        "CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT,"
        " time_created INTEGER, time_updated INTEGER, data TEXT)")
    con.execute(
        "CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,"
        " time_created INTEGER, time_updated INTEGER, data TEXT)")
    for s in sessions:
        con.execute(
            "INSERT INTO session (id, parent_id, title, agent, directory,"
            " time_created, time_updated) VALUES (?,?,?,?,?,?,?)",
            (s["id"], s.get("parent_id"), s.get("title", ""), s.get("agent"),
             s.get("directory", "/tmp/repo"), s.get("time_created", T0),
             s.get("time_updated", T0)))
    for m in messages:
        con.execute(
            "INSERT INTO message (id, session_id, time_created, time_updated,"
            " data) VALUES (?,?,?,?,?)",
            (m["id"], m["session_id"], m.get("time_created", T0),
             m.get("time_updated", T0),
             json.dumps({"role": m.get("role", "assistant")})))
    for p in parts:
        con.execute(
            "INSERT INTO part (id, message_id, session_id, time_created,"
            " time_updated, data) VALUES (?,?,?,?,?,?)",
            (p["id"], p.get("message_id"), p["session_id"],
             p.get("time_created", T0), p.get("time_updated", T0),
             json.dumps(p["data"])))
    con.commit()
    con.close()


def _result_session(sid, parent_id, text, created=T0, title="Review PR 9",
                   agent="reviewer", make_result=True):
    """A child session with one assistant message + its result text part.
    `text=None` -> empty result (no text part)."""
    sessions = [{"id": sid, "parent_id": parent_id, "title": title,
                 "agent": agent, "time_created": created,
                 "time_updated": created + 1000}]
    messages = [{"id": sid + "-m1", "session_id": sid, "role": "assistant",
                 "time_created": created + 500, "time_updated": created + 500}]
    parts = []
    if make_result and text is not None:
        parts.append({"id": sid + "-p1", "message_id": sid + "-m1",
                      "session_id": sid, "time_created": created + 600,
                      "time_updated": created + 600,
                      "data": {"type": "text", "text": text}})
    return sessions, messages, parts


def _scan(g, dbp, root_id, **opts):
    con = g.connect(dbp)
    try:
        nodes = g.enumerate_tree(con, root_id, max_depth=opts.pop("max_depth", 2))
        return g.detect_patterns(con, nodes, **opts)
    finally:
        con.close()


def _patterns(hits):
    return sorted({h["pattern"] for h in hits})


def _pid_dead(pid):
    """True when pid is gone or a terminated zombie (post-kill before reap)."""
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split()[2] == "Z"
    except (OSError, IndexError):
        return True


def _hits(hits, pattern):
    return [h for h in hits if h["pattern"] == pattern]


# --- AC1: tree enumeration ---------------------------------------------------

def test_tree_enumeration_depth_cap():
    """AC1: reports exactly the root's descendants (depth <= 2), excludes
    unrelated roots and depth-3 nodes."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-tree-")
    try:
        dbp = os.path.join(work, "opencode.db")
        rows = [
            {"id": "root", "parent_id": None, "title": "orchestrator"},
            {"id": "c1", "parent_id": "root", "title": "child one"},
            {"id": "c2", "parent_id": "root", "title": "child two"},
            {"id": "gc", "parent_id": "c1", "title": "grandchild"},
            {"id": "ggc", "parent_id": "gc", "title": "great-grandchild"},
            {"id": "u", "parent_id": None, "title": "unrelated root"},
            {"id": "uc", "parent_id": "u", "title": "unrelated child"},
        ]
        _make_db(dbp, rows)
        con = g.connect(dbp)
        try:
            nodes = g.enumerate_tree(con, "root", max_depth=2)
        finally:
            con.close()
        ids = {n["id"] for n in nodes}
        depth = {n["id"]: n["depth"] for n in nodes}
        assert ids == {"root", "c1", "c2", "gc"}, ids
        assert "ggc" not in ids, "depth-3 node leaked past the cap"
        assert "u" not in ids and "uc" not in ids, "unrelated tree included"
        assert depth["root"] == 0 and depth["gc"] == 2, depth
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC2: empty-result detection ---------------------------------------------

def test_empty_result_detection():
    """AC2: empty final text AND contract-marker misses both match
    `empty-result`; a marker-complete result does not."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-empty-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s1, m1, p1 = _result_session("empty1", "root", text=None)
        s2, m2, p2 = _result_session("malformed1", "root", text="LGTM, all good.")
        s3, m3, p3 = _result_session(
            "clean1", "root",
            text="## Findings\nnone material\n## Recommendation\nmerge")
        _make_db(dbp, [root] + s1 + s2 + s3, m1 + m2 + m3, p1 + p2 + p3)
        hits = _scan(g, dbp, "root", contract="council-lens")
        empty = _hits(hits, "empty-result")
        named = {sid for h in empty for sid in h["sessions"]}
        assert named == {"empty1", "malformed1"}, (named, _patterns(hits))
        assert any("empty1" in str(h.get("evidence", "")) for h in empty), empty
        assert not any("clean1" in str(h.get("evidence", "")) for h in empty)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC3: permission-auto-reject detection -----------------------------------

def test_permission_auto_reject_detection():
    """AC3: an external_directory auto-reject matches `permission-auto-reject`
    (more specific than generic `empty-result`) and names the denied path."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-perm-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s1, m1, p1 = _result_session("denied1", "root", text=None)
        p1.append({
            "id": "denied1-p2", "message_id": "denied1-m1",
            "session_id": "denied1", "time_created": T0 + 700,
            "time_updated": T0 + 700,
            "data": {"type": "tool", "tool": "bash",
                     "state": {"status": "error",
                               "output": "permission requested: external_directory"
                                         " (/tmp/audit-report-*); auto-rejecting"}}})
        _make_db(dbp, [root] + s1, m1, p1)
        hits = _scan(g, dbp, "root")
        assert "permission-auto-reject" in _patterns(hits), _patterns(hits)
        hit = _hits(hits, "permission-auto-reject")[0]
        assert "denied1" in hit["sessions"], hit
        assert "/tmp/audit-report-*" in str(hit.get("evidence", "")), hit
        assert "--allow-dirs" in str(hit.get("evidence", "")), \
            "evidence must carry the --allow-dirs recovery hint (plan registry)"
        assert not _hits(hits, "empty-result"), \
            "the denial explains the empty result; generic empty must not shadow it"
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC4: identical-retry-loop ----------------------------------------------

def test_identical_retry_loop():
    """AC4: >=2 identical relaunches of the same agent+prompt after failures
    match `identical-retry-loop` with abort as the default action."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-retry-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        title = "Review PR 16 CI verify"
        s1, m1, p1 = _result_session("try1", "root", text=None,
                                     created=T0, title=title, agent="reviewer")
        s2, m2, p2 = _result_session("try2", "root", text=None,
                                     created=T0 + 5 * 60 * 1000,
                                     title=title, agent="reviewer")
        s3, m3, p3 = _result_session("try3", "root", text=None,
                                     created=T0 + 10 * 60 * 1000,
                                     title=title, agent="reviewer")
        s4, m4, p4 = _result_session("other", "root", text=None,
                                     created=T0, title="Review PR 17 docs records",
                                     agent="reviewer")
        _make_db(dbp, [root] + s1 + s2 + s3 + s4, m1 + m2 + m3 + m4,
                 p1 + p2 + p3 + p4)
        hits = _scan(g, dbp, "root", contract="council-lens",
                     retry_cap=2, retry_window_min=30)
        loops = _hits(hits, "identical-retry-loop")
        assert loops, _patterns(hits)
        assert set(loops[0]["sessions"]) >= {"try1", "try2", "try3"}, loops
        assert loops[0].get("action") == "abort", loops
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC5: liveness reuse -----------------------------------------------------

def test_liveness_reuse():
    """AC5: a quiet gap > --call-seconds yields `blocking-wait` and an old
    last event yields `stalled`, produced through the imported
    watch_agent.analyze_session/verdict — no second liveness implementation."""
    g = _load_guard()
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import watch_agent as watch  # noqa: F401 - shared sys.modules for identity
    assert getattr(g, "watch", None) is not None and \
        g.watch.analyze_session is watch.analyze_session, \
        "guard must reuse watch_agent.analyze_session, not reimplement it"
    work = tempfile.mkdtemp(prefix="guard-live-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        # no result text: a genuinely hung child. A child WITH a completed
        # result is `done` under the lifecycle fix (AC2/AC5), not stalled, so
        # it can no longer exercise the stalled path here.
        s1, m1, p1 = _result_session("stuck1", "root", text=None, created=T0)
        # two tool calls 400s apart -> invisible blocking black box
        p1.append({"id": "stuck1-p2", "message_id": "stuck1-m1",
                   "session_id": "stuck1", "time_created": T0 + 2000,
                   "time_updated": T0 + 2000,
                   "data": {"type": "tool", "tool": "bash",
                            "state": {"status": "completed",
                                      "input": {"command": "pytest -q"}}}})
        p1.append({"id": "stuck1-p3", "message_id": "stuck1-m1",
                   "session_id": "stuck1", "time_created": T0 + 402000,
                   "time_updated": T0 + 402000,
                   "data": {"type": "tool", "tool": "bash",
                            "state": {"status": "completed",
                                      "input": {"command": "pytest -q"}}}})
        _make_db(dbp, [root] + s1, m1, p1)
        # now = 10 min after the last event: last-event age 600s > stall 240s
        now = (T0 + 402000) / 1000 + 600
        hits = _scan(g, dbp, "root", call_seconds=300, stall_seconds=240,
                     now=now, contract="council-lens")
        patterns = _patterns(hits)
        assert "blocking-wait" in patterns, patterns
        assert "stalled" in patterns, patterns
        assert "stuck1" in _hits(hits, "blocking-wait")[0]["sessions"]
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC6: wave-failure -------------------------------------------------------

def test_wave_failure():
    """AC6: >= wave-ratio (0.6) of a dispatch wave failing with a shared
    pattern matches `wave-failure`; 2/5 does not."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-wave-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        sessions, messages, parts = [], [], []
        for i in range(5):
            text = None if i < 3 else "## Findings\nok\n## Recommendation\nmerge"
            s, m, p = _result_session(f"rev{i}", "root", text=text,
                                      created=T0 + i * 2000,
                                      title=f"Review PR {16 + i}",
                                      agent="reviewer")
            sessions += s
            messages += m
            parts += p
        _make_db(dbp, [root] + sessions, messages, parts)
        hits = _scan(g, dbp, "root", contract="council-lens", wave_ratio=0.6)
        waves = _hits(hits, "wave-failure")
        assert waves, _patterns(hits)
        assert waves[0].get("action") == "abort", waves
        assert set(waves[0]["sessions"]) >= {"rev0", "rev1", "rev2"}, waves

        # control: 2 of 5 empty -> below the ratio
        dbp2 = os.path.join(work, "opencode2.db")
        sessions, messages, parts = [], [], []
        for i in range(5):
            text = None if i < 2 else "## Findings\nok\n## Recommendation\nmerge"
            s, m, p = _result_session(f"rv{i}", "root", text=text,
                                      created=T0 + i * 2000,
                                      title=f"Review PR {26 + i}",
                                      agent="reviewer")
            sessions += s
            messages += m
            parts += p
        _make_db(dbp2, [root] + sessions, messages, parts)
        hits2 = _scan(g, dbp2, "root", contract="council-lens", wave_ratio=0.6)
        assert not _hits(hits2, "wave-failure"), _patterns(hits2)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC7: budget-exceeded ----------------------------------------------------

def test_budget_exceeded():
    """AC7: tree wall clock beyond --budget-minutes matches `budget-exceeded`;
    0 disables the check."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-budget-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator",
                "time_created": T0, "time_updated": T0}
        _make_db(dbp, [root])
        now = T0 / 1000 + 50 * 60  # 50 minutes in
        hits = _scan(g, dbp, "root", budget_minutes=45, now=now)
        budget = _hits(hits, "budget-exceeded")
        assert budget, _patterns(hits)
        assert budget[0].get("action") == "abort", budget
        hits0 = _scan(g, dbp, "root", budget_minutes=0, now=now)
        assert not _hits(hits0, "budget-exceeded"), _patterns(hits0)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC8: abort mechanics (wrap) --------------------------------------------

def test_abort_mechanics_wrap():
    """AC8: an abort-class pattern in --wrap mode kills the owned root process
    group, writes the ABORT sentinel (pattern, evidence, UTC ts, root id),
    emits exactly one kind=agent outcome=stopped run-log record naming the
    pattern, and exits 5."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-abort-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        title = "Review PR 16 CI verify"
        s1, m1, p1 = _result_session("try1", "root", text=None, created=T0,
                                     title=title)
        s2, m2, p2 = _result_session("try2", "root", text=None,
                                     created=T0 + 5 * 60 * 1000, title=title)
        s3, m3, p3 = _result_session("try3", "root", text=None,
                                     created=T0 + 10 * 60 * 1000, title=title)
        _make_db(dbp, [root] + s1 + s2 + s3, m1 + m2 + m3, p1 + p2 + p3)
        sentinel = os.path.join(work, "ABORT.root")
        logs_dir = os.path.join(work, "logs")
        os.makedirs(logs_dir)
        pidfile = os.path.join(work, "wrapped.pid")
        gpidfile = os.path.join(work, "wrapped-gchild.pid")
        # now = 20 min after the wave: retry-loop fires, budget (45) does not
        fixed_now = T0 / 1000 + 20 * 60
        proc = subprocess.Popen(
            [sys.executable, GUARD, "--root", "root", "--watch", "1",
             "--retry-cap", "2", "--retry-window-min", "30",
             "--sentinel", sentinel, "--logs-dir", logs_dir, "--json",
             "--fixed-now", str(fixed_now), "--db", dbp,
             # leader + a grandchild in the same process group: a plain
             # os.kill(leader) would strand the grandchild (review finding 2)
             "--wrap", "--", "bash", "-c",
             'echo $$ > "$1"; sleep 60 & echo $! > "$2"; wait',
             "bash", pidfile, gpidfile],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "OPENCODE_DB_PATH": dbp}, start_new_session=True)
        rc = proc.wait(timeout=30)
        out, err = proc.communicate(timeout=5)
        assert rc == 5, (rc, out, err)
        assert os.path.isfile(sentinel), "ABORT sentinel not written"
        rec = json.load(open(sentinel))
        assert rec["pattern"] == "identical-retry-loop", rec
        assert rec["root_session_id"] == "root", rec
        assert rec.get("evidence"), rec
        assert rec["sessions"], rec
        assert rec["ts"].endswith("Z"), rec
        # wrapped leader AND its grandchild are dead (process-group kill)
        for label, pf in (("leader", pidfile), ("grandchild", gpidfile)):
            for _ in range(20):
                if os.path.isfile(pf):
                    break
                time.sleep(0.1)
            assert os.path.isfile(pf), \
                f"wrapped {label} pid handshake missing ({pf}) — kill raced startup"
        wrapped_pid = int(open(pidfile).read().strip())
        gchild_pid = int(open(gpidfile).read().strip())
        time.sleep(0.2)
        assert _pid_dead(wrapped_pid), \
            f"wrapped root pid {wrapped_pid} survived the abort"
        assert _pid_dead(gchild_pid), \
            f"grandchild pid {gchild_pid} survived the group abort"
        records = []
        for name in sorted(os.listdir(logs_dir)):
            if name.endswith(".jsonl"):
                with open(os.path.join(logs_dir, name)) as fh:
                    records += [json.loads(l) for l in fh if l.strip()]
        assert len(records) == 1, records
        assert records[0]["kind"] == "agent", records
        assert records[0]["outcome"] == "stopped", records
        assert "identical-retry-loop" in (records[0].get("detail") or ""), records
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- AC9: observe-mode safety ------------------------------------------------

def test_observe_mode_safety():
    """AC9: observe mode never kills (sentinel + non-zero exit only);
    --kill-root --root-pid kills exactly that pid's group and exits 5."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-obs-")
    victim = None
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator",
                "time_created": T0, "time_updated": T0}
        _make_db(dbp, [root])
        now = T0 / 1000 + 50 * 60
        sentinel = os.path.join(work, "ABORT.root")
        logs_dir = os.path.join(work, "logs")
        os.makedirs(logs_dir)
        victim = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True)
        # budget abort-class, observe mode: no kill authority
        r = subprocess.run(
            [sys.executable, GUARD, "--root", "root", "--once",
             "--budget-minutes", "45", "--sentinel", sentinel,
             "--logs-dir", logs_dir, "--json",
             "--fixed-now", str(now), "--db", dbp],
            capture_output=True, text=True, timeout=30)
        assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
        assert r.returncode != 5, "observe mode without kill authority must not report abort-performed"
        assert os.path.isfile(sentinel), r
        assert victim.poll() is None, "observe mode killed a foreign process"
        # explicit root kill: exactly that pid dies, exit 5
        sentinel2 = os.path.join(work, "ABORT2.root")
        r2 = subprocess.run(
            [sys.executable, GUARD, "--root", "root", "--once",
             "--budget-minutes", "45", "--sentinel", sentinel2,
             "--logs-dir", logs_dir, "--fixed-now", str(now), "--db", dbp,
             "--kill-root", "--root-pid", str(victim.pid)],
            capture_output=True, text=True, timeout=30)
        assert r2.returncode == 5, (r2.returncode, r2.stdout, r2.stderr)
        try:
            victim.wait(timeout=10)
        except subprocess.TimeoutExpired:
            victim.kill()
            raise AssertionError("--kill-root did not terminate the root pid")
    finally:
        if victim is not None and victim.poll() is None:
            try:
                os.killpg(os.getpgid(victim.pid), signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(work, ignore_errors=True)


# --- AC10: read-only DB + write surfaces ------------------------------------

def test_read_only_db_uri():
    """AC10: the guard's DB connection is a file:…?mode=ro URI opened with
    uri=True; write surfaces are the sentinel and the one run-log record."""
    g = _load_guard()
    assert g.db_uri("/tmp/x/opencode.db") == "file:/tmp/x/opencode.db?mode=ro", \
        g.db_uri("/tmp/x/opencode.db")
    captured = {}

    class _FakeCon:
        def row_factory(self, *_):
            pass

    real = g.sqlite3.connect

    def _spy(url, **kw):
        captured["url"] = url
        captured["kw"] = kw
        return real(url, **kw)

    g.sqlite3.connect = _spy
    try:
        work = tempfile.mkdtemp(prefix="guard-ro-")
        dbp = os.path.join(work, "opencode.db")
        _make_db(dbp, [{"id": "root", "parent_id": None}])
        con = g.connect(dbp)
        con.close()
    finally:
        g.sqlite3.connect = real
        shutil.rmtree(work, ignore_errors=True)
    assert captured.get("kw", {}).get("uri") is True, captured
    assert str(captured.get("url", "")).endswith("?mode=ro"), captured


# --- coverage-gate expansion: dead-stream (registry row, no AC) -------------

def test_dead_stream_detection():
    """A dispatched child with zero messages and zero parts matches
    `dead-stream` (RM-026 class) — the registry row's detector."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-dead-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        ghost = {"id": "ghost1", "parent_id": "root", "title": "Review PR 99",
                 "agent": "reviewer", "time_created": T0, "time_updated": T0}
        s, m, p = _result_session("alive1", "root",
                                  text="## Findings\nok\n## Recommendation\nmerge")
        _make_db(dbp, [root, ghost] + s, m, p)
        hits = _scan(g, dbp, "root", contract="council-lens")
        dead = _hits(hits, "dead-stream")
        assert dead and dead[0]["sessions"] == ["ghost1"], (dead, _patterns(hits))
        assert "ghost1" not in {sid for h in _hits(hits, "empty-result")
                                for sid in h["sessions"]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- review-fix cases (review findings 1, 3, 4) ------------------------------

def test_kill_group_spares_no_lingering_member():
    """Finding 2 (discriminating): a leader that exited AND was reaped must
    not let a SIGTERM-ignoring group member survive the abort — group
    liveness is killpg(pgid, 0), never os.kill(leader, 0)."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-kg-")
    try:
        leaderf = os.path.join(work, "leader.pid")
        memberf = os.path.join(work, "member.pid")
        # setsid: the bash leader's pid is the process-group id. It spawns a
        # SIGTERM-ignoring python member, then exits (reaped below).
        subprocess.run(
            ["setsid", "bash", "-c",
             'echo $$ > "$1"; python3 -c '
             '"import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN);'
             ' time.sleep(30)" & echo $! > "$2"; exit 0',
             "bash", leaderf, memberf],
            timeout=10)
        for _ in range(50):
            if os.path.isfile(leaderf) and os.path.isfile(memberf):
                break
            time.sleep(0.05)
        assert os.path.isfile(leaderf) and os.path.isfile(memberf), \
            "leader/member pid handshake missing"
        leader = int(open(leaderf).read().strip())
        member = int(open(memberf).read().strip())
        # precondition: the leader is fully gone (the exact defect condition —
        # os.kill(leader, 0) raises while the group still has a live member)
        try:
            os.kill(leader, 0)
            leader_gone = False
        except OSError:
            leader_gone = True
        time.sleep(0.2)
        if not leader_gone:
            try:
                os.kill(leader, 0)
                raise AssertionError("leader never exited — fixture broken")
            except OSError:
                pass
        g.kill_group(leader, grace=1)
        time.sleep(0.2)
        assert _pid_dead(member), \
            f"TERM-ignoring group member {member} survived the group abort"
    finally:
        try:
            os.kill(int(open(memberf).read().strip()), signal.SIGKILL)
        except (OSError, FileNotFoundError, ValueError):
            pass
        shutil.rmtree(work, ignore_errors=True)


def test_unknown_contract_exits_4():
    """Finding 3: a typo'd --contract must not silently downgrade detection
    to emptiness-only — unknown contract is unclassifiable (exit 4)."""
    work = tempfile.mkdtemp(prefix="guard-uc-")
    try:
        dbp = os.path.join(work, "opencode.db")
        _make_db(dbp, [{"id": "root", "parent_id": None, "title": "orch"}])
        r = subprocess.run(
            [sys.executable, GUARD, "--root", "root", "--once",
             "--db", dbp, "--contract", "council-lense-typo"],
            capture_output=True, text=True, timeout=30)
        assert r.returncode == 4, (r.returncode, r.stdout, r.stderr)
        assert "unknown contract" in r.stderr, r.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_missing_root_exits_4():
    """Finding 4: an absent root session is unclassifiable (exit 4), never a
    clean pass over an empty node set."""
    work = tempfile.mkdtemp(prefix="guard-mr-")
    try:
        dbp = os.path.join(work, "opencode.db")
        _make_db(dbp, [{"id": "root", "parent_id": None, "title": "orch"}])
        r = subprocess.run(
            [sys.executable, GUARD, "--root", "ses_not_in_db", "--once",
             "--db", dbp],
            capture_output=True, text=True, timeout=30)
        assert r.returncode == 4, (r.returncode, r.stdout, r.stderr)
        assert "not found" in r.stderr, r.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_observe_watch_rescans():
    """Finding 1: observe mode honors --watch N (continuous supervision) and
    keeps scanning while the tree is warn-level — one scan per second."""
    work = tempfile.mkdtemp(prefix="guard-w-")
    proc = None
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s1, m1, p1 = _result_session("denied1", "root", text=None)
        p1.append({
            "id": "denied1-p2", "message_id": "denied1-m1",
            "session_id": "denied1", "time_created": T0 + 700,
            "time_updated": T0 + 700,
            "data": {"type": "tool", "tool": "bash",
                     "state": {"status": "error",
                               "output": "permission requested: external_directory"
                                         " (/tmp/x); auto-rejecting"}}})
        _make_db(dbp, [root] + s1, m1, p1)
        proc = subprocess.Popen(
            [sys.executable, GUARD, "--root", "root", "--watch", "1",
             "--budget-minutes", "0",  # warn-only tree: no abort-class pattern
             "--db", dbp, "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(2.5)  # >= 2 scans at 1s cadence
        proc.terminate()
        out, _ = proc.communicate(timeout=5)
        scans = [l for l in out.splitlines() if l.strip().startswith("{")]
        assert len(scans) >= 2, \
            f"observe --watch ran {len(scans)} scan(s); expected continuous re-scan"
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)


# --- child lifecycle (plan session-guard-task-child-lifecycle) ---------------

def _reasoning(sid, ms):
    """A reasoning part (no text, no tool) on the child's single assistant
    message — the still-streaming shape observed 2026-10-09."""
    return {"id": f"{sid}-r", "message_id": f"{sid}-m1", "session_id": sid,
            "time_created": ms, "time_updated": ms,
            "data": {"type": "reasoning", "text": "thinking about the task"}}


def test_in_flight_child_not_empty_result():
    """AC1: a still-streaming child (no text part yet, last event within the
    stall window, no in-flight tool) produces NO empty-result hit."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-inflight-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s, m, p = _result_session("stream1", "root", text=None)
        p.append(_reasoning("stream1", T0 + 600))
        _make_db(dbp, [root] + s, m, p)
        now = (T0 + 600) / 1000 + 10  # 10s after the last event: recent
        hits = _scan(g, dbp, "root", stall_seconds=240, call_seconds=300,
                     now=now)
        assert not _hits(hits, "empty-result"), _patterns(hits)
        assert not _hits(hits, "stalled"), _patterns(hits)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_completed_child_not_stalled_or_empty():
    """AC2: a completed child (non-empty result text, no in-flight tool)
    quiet past the stall window produces NO stalled and NO empty-result hit."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-done-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s, m, p = _result_session("done1", "root", text="final answer")
        _make_db(dbp, [root] + s, m, p)
        now = (T0 + 600) / 1000 + 600  # 600s quiet > stall window (240)
        hits = _scan(g, dbp, "root", stall_seconds=240, now=now)
        assert not _hits(hits, "stalled"), _patterns(hits)
        assert not _hits(hits, "empty-result"), _patterns(hits)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_dead_empty_child_still_empty_result():
    """AC3 (regression guard): an empty result, no in-flight call, quiet past
    the stall window still produces the empty-result hit (RM-023's shape)."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-deadempty-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s, m, p = _result_session("emptyq", "root", text=None)
        _make_db(dbp, [root] + s, m, p)
        now = (T0 + 600) / 1000 + 600
        hits = _scan(g, dbp, "root", stall_seconds=240, now=now)
        empty = _hits(hits, "empty-result")
        assert empty and "emptyq" in empty[0]["sessions"], _patterns(hits)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_wave_failure_counts_only_real_failures():
    """AC4: a wave of 1 genuinely failed + 2 in-flight children produces NO
    wave-failure hit (1/3 < 0.6); in-flight children are not failures."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-wave2-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s1, m1, p1 = _result_session("fail0", "root", text=None, created=T0,
                                     title="Review A", agent="reviewer")
        s2, m2, p2 = _result_session("live1", "root", text=None,
                                     created=T0 + 1000, title="Review B",
                                     agent="reviewer")
        p2.append(_reasoning("live1", T0 + 1600))
        s3, m3, p3 = _result_session("live2", "root", text=None,
                                     created=T0 + 2000, title="Review C",
                                     agent="reviewer")
        p3.append(_reasoning("live2", T0 + 2600))
        _make_db(dbp, [root] + s1 + s2 + s3, m1 + m2 + m3, p1 + p2 + p3)
        now = (T0 + 2600) / 1000 + 10  # in-flight children are recent
        hits = _scan(g, dbp, "root", wave_ratio=0.6, stall_seconds=240,
                     now=now)
        assert not _hits(hits, "wave-failure"), _patterns(hits)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_contract_mode_completed_and_in_flight():
    """AC6: with --contract, a completed child missing markers still fails
    validation (empty-result naming the missing markers); an in-flight child
    is skipped, never marked."""
    g = _load_guard()
    work = tempfile.mkdtemp(prefix="guard-contract-")
    try:
        dbp = os.path.join(work, "opencode.db")
        root = {"id": "root", "parent_id": None, "title": "orchestrator"}
        s1, m1, p1 = _result_session("malformed1", "root", text="LGTM, all good.")
        s2, m2, p2 = _result_session("stream1", "root", text=None)
        p2.append(_reasoning("stream1", T0 + 600))
        _make_db(dbp, [root] + s1 + s2, m1 + m2, p1 + p2)
        now = (T0 + 600) / 1000 + 10
        hits = _scan(g, dbp, "root", contract="council-lens",
                     stall_seconds=240, now=now)
        empty = _hits(hits, "empty-result")
        named = {sid for h in empty for sid in h["sessions"]}
        assert named == {"malformed1"}, (named, _patterns(hits))
        ev = " ".join(str(h.get("evidence", "")) for h in empty)
        assert "Findings" in ev and "Recommendation" in ev, ev
        assert not _hits(hits, "stalled"), _patterns(hits)
    finally:
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
    print(f"{len(tests) - failed}/{len(tests)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
