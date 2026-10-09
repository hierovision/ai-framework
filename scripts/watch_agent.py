#!/usr/bin/env python3
"""Watchdog for opencode subagent runs (orchestrator-side, out-of-band).

Two independent liveness sources are cross-checked:

  1. the mandatory HEARTBEAT file a dispatched subagent appends to
     (`.scratch/<program>/progress/<task>.log`), and
  2. opencode's own session event stream (session/part rows in the
     opencode SQLite DB, available read-only), which cannot be faked by
     a subagent that stopped reporting.

It answers the three questions an orchestrator actually has while a
long subagent runs:

  * is it alive, or stalled/dead?
  * is it making progress, or looping (repeated identical calls /
    repeated identical heartbeats)?
  * is it behaving (bounded calls, no out-of-scope mutation), or
    thrashing / drifting outside its brief?

Design constraints (from skills/observing-runs + AGENTS.md rule 3):
  * transient supervision only: reads .scratch/ and the opencode DB;
    never writes the durable run log, never captures raw transcripts
    beyond short targets;
  * never injects anything back into the observed agent's context.

Exit codes: 0 OK/WARN, 2 STALLED or BLOCKING, 3 DEAD, 4 UNKNOWN.

Usage:
  python3 scripts/watch_agent.py --progress FILE [--session ID | --title SUBSTR]
  python3 scripts/watch_agent.py --title "Author D2" --tail 15
  python3 scripts/watch_agent.py --progress FILE --watch 15
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time

DB = os.path.expanduser("~/.local/share/opencode/opencode.db")

# --- bad-behavior heuristics -------------------------------------------------

MUTATE = r"(\brm\b|\bmv\b|\bcp\b|\bln\b|\btee\b|\bsed\s+-i\b|\bchmod\b|\bchown\b|\binstall\b|\btouch\b|\bmkdir\b|\btruncate\b)"
# bash commands that mutate state outside the brief's sandbox
DENY_BASH = [
    (re.compile(r"\bgit\s+(commit|push|reset|checkout|switch|clean|tag)\b"), "git-mutation"),
    (re.compile(rf"{MUTATE}[^\n]*(~?/?\.config/opencode)"), "global-opencode-config"),
    (re.compile(r"\b(sudo|doas)\b"), "privilege-escalation"),
    (re.compile(r"\bcurl\b[^|]*\|\s*(sh|bash)\b"), "pipe-to-shell"),
    (re.compile(r"\brm\s+(-\w+\s+)*(~|/home|/etc|/usr|/var|/opt)(?!/tmp)"), "out-of-sandbox-rm"),
]
# long single blocking calls are invisible to the orchestrator -> flag them
DEFAULT_CALL_SECONDS = 300
DEFAULT_STALL_SECONDS = 240
DEFAULT_LOOP_REPEATS = 3


def now_iso():
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmmss(ms):
    if not ms:
        return "-"
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%H:%M:%S")


def age_of(ms):
    if not ms:
        return None
    return time.time() - ms / 1000


def fmt_age(sec):
    if sec is None:
        return "-"
    if sec < 90:
        return f"{sec:.0f}s"
    return f"{sec/60:.1f}m"


def session_model(sess):
    """Resolve the session row's `model` JSON blob to `<providerID>/<id>`.

    The blob is volatile (probed 2026-10-02:
    `{"id":"nemotron-3-ultra-free","providerID":"opencode","variant":"default"}`).
    Every missing/odd shape degrades to None — never a crash
    (reference/opencode-integration.md).
    """
    try:
        raw = sess["model"]
    except (KeyError, IndexError, TypeError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    provider, model_id = data.get("providerID"), data.get("id")
    if not provider or not model_id:
        return None
    return f"{provider}/{model_id}"


# --- heartbeat source --------------------------------------------------------

HB_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+(\S+)\s*(.*)$")


def read_heartbeat(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        lines = [l.rstrip("\n") for l in open(path, errors="replace")]
    except OSError:
        return None
    entries = []
    for l in lines:
        m = HB_RE.match(l)
        if m:
            ts, tag, rest = m.groups()
            entries.append((ts, tag.upper(), rest))
        elif l.strip():
            entries.append((None, "RAW", l.strip()[:160]))
    last_age = None
    if entries:
        try:
            last_ts = dt.datetime.strptime(entries[-1][0], "%Y-%m-%dT%H:%M:%SZ")
            last_age = time.time() - last_ts.replace(tzinfo=dt.timezone.utc).timestamp()
        except (TypeError, ValueError):
            last_age = time.time() - os.path.getmtime(path)
    # loop detection: identical consecutive non-EXTERNAL fingerprint
    fp = [(t, r[:80]) for _, t, r in entries if t not in ("CALL", "POLL", "EVAL")]
    repeats = 0
    for i in range(1, len(fp)):
        if fp[i] == fp[i - 1]:
            repeats += 1
    return {"entries": entries, "last_age": last_age, "repeats": repeats}


# --- session event-stream source --------------------------------------------

def db_path():
    """The session DB path: `OPENCODE_DB_PATH` override (read at call time,
    so hermetic tests and the dispatcher can share one reader), else the
    default location."""
    return os.path.expanduser(os.environ.get("OPENCODE_DB_PATH") or DB)


def db():
    path = db_path()
    if not os.path.isfile(path):
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


def find_session(con, sid=None, title=None, parent=None, cwd=None):
    cur = con.cursor()
    if sid:
        cur.execute("SELECT * FROM session WHERE id=?", (sid,))
        return cur.fetchone()
    where, args = [], []
    if title:
        where.append("title LIKE ?")
        args.append(f"%{title}%")
    if parent:
        where.append("parent_id=?")
        args.append(parent)
    if cwd:
        where.append("directory=?")
        args.append(os.path.abspath(cwd))
    sql = "SELECT * FROM session"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY time_updated DESC LIMIT 1"
    cur.execute(sql, args)
    return cur.fetchone()


def load_parts(con, sid):
    cur = con.cursor()
    cur.execute(
        "SELECT id,data,time_created FROM part WHERE session_id=? ORDER BY time_created", (sid,)
    )
    out = []
    for r in cur.fetchall():
        try:
            d = json.loads(r["data"])
        except (TypeError, ValueError):
            continue
        out.append((r["time_created"], d))
    return out


def has_terminal_result(parts, running):
    """The ONE completion predicate shared by both supervision surfaces
    (AC11/AC12). `parts` is the flat [(time_created_ms, data), ...] view; it
    carries no message roles, so completion is derived from the terminal
    marker: a non-empty text part immediately followed by a `step-finish`
    part, with no tool part between them, and no tool call in flight.
    opencode.db records no completion column — a turn without `step-finish`
    is unfinished regardless of the text it already emitted, so a
    still-streaming text-only child and a hung child carrying interim text
    are both NOT done."""
    last_text = None
    for i, (_ms, d) in enumerate(parts):
        if d.get("type") == "text" and (d.get("text") or "").strip():
            last_text = i
    if last_text is None:
        return False
    if last_text + 1 >= len(parts):
        return False
    if (parts[last_text + 1][1].get("type") or "") != "step-finish":
        return False
    return not running


def analyze_session(sess, parts, call_seconds, loop_repeats):
    """opencode does not record real tool durations (start~=end), so the
    honest signal for a blocking black box is the QUIET GAP between two
    consecutive parts; attribute it to the tool that preceded it."""
    tools, targets = {}, {}
    created, edited, running = 0, 0, []
    blocking_waits, bad = [], []
    last_ms, writes_last, last_tool = None, None, None
    timeline = []
    for i, (ms, d) in enumerate(parts):
        last_ms = ms or last_ms
        nxt = parts[i + 1][0] if i + 1 < len(parts) else None
        if d.get("type") != "tool":
            continue
        st = d.get("state", {}) or {}
        inp = st.get("input", {}) or {}
        name = d.get("tool") or "?"
        status = st.get("status") or "?"
        target = (
            inp.get("filePath")
            or inp.get("command")
            or inp.get("pattern")
            or inp.get("description")
            or inp.get("skill")
            or ""
        )
        tools[name] = tools.get(name, 0) + 1
        key = f"{name}:{target[:200]}" if target else name
        targets[key] = targets.get(key, 0) + 1
        timeline.append((ms, name, status, target))
        last_tool = (name, status, target, ms)
        if name == "write":
            created += 1
            writes_last = ms
        if name == "edit":
            edited += 1
        if name in ("write", "edit") and inp.get("filePath"):
            p = os.path.abspath(inp["filePath"])
            if not p.startswith(("/tmp/opencode", os.path.expanduser("~/repos"))):
                bad.append(("OUT-OF-SCOPE-WRITE", inp["filePath"][:90]))
        if name == "bash":
            cmd = inp.get("command", "") or ""
            for rx, tag in DENY_BASH:
                if rx.search(cmd):
                    bad.append((tag, cmd[:90]))
        if nxt and (nxt - ms) / 1000 > call_seconds:
            blocking_waits.append((name, (nxt - ms) / 1000, target[:70]))
    if last_tool and last_tool[1] in ("running", "pending"):
        running.append((last_tool[0], fmt_age(time.time() - last_tool[3] / 1000), last_tool[2][:70]))
    # re-editing one file is normal iteration; repeated identical *calls*
    # (bash/read) are the real thrash signal
    loops = [
        (k, v)
        for k, v in targets.items()
        if v >= (8 if k.startswith(("write:", "edit:")) else loop_repeats)
    ]
    # Completion is inferred honestly (AC11/AC12): the terminal step-finish
    # marker after the final non-empty text, with no tool in flight. The
    # plain "non-empty text" reading over-approximated done — post-completion
    # silence must not read as a stall, but an unfinished turn must not read
    # as completed either.
    has_result = has_terminal_result(parts, running)
    return dict(
        tools=tools,
        targets=targets,
        created=created,
        edited=edited,
        running=running,
        blocking_waits=blocking_waits,
        bad=bad,
        loops=loops,
        last_ms=last_ms,
        writes_last=writes_last,
        timeline=timeline,
        part_count=len(parts),
        has_result=has_result,
    )


# --- verdict (pure, testable) -----------------------------------------------

def verdict(hb, an, stall_seconds=DEFAULT_STALL_SECONDS,
            call_seconds=DEFAULT_CALL_SECONDS):
    """Return (verdict, why) from a heartbeat and a session analysis."""
    hb_age = hb["last_age"] if hb else None
    s_age = age_of(an["last_ms"]) if an else None
    result, why = "UNKNOWN", []
    if an is None and hb is None:
        why.append("no heartbeat file and no session found")
        return result, why
    if an and an["running"]:
        result = "BLOCKING"
        why.append(f"{len(an['running'])} call(s) in flight > {call_seconds}s")
    live_age = min([x for x in (hb_age, s_age) if x is not None], default=None)
    if live_age is not None:
        # A completed session (non-empty result, no in-flight tool) is done:
        # post-completion quiet is not a stall. Defensive: an in-flight call
        # still wins (BLOCKING), so only skip when nothing is running.
        completed = bool(an and an.get("has_result") and not an["running"])
        if completed:
            if result == "UNKNOWN":
                result = "OK"
        elif live_age > 2 * stall_seconds:
            result = "DEAD"
            why.append(f"no heartbeat and no event for {fmt_age(live_age)}")
        elif live_age > stall_seconds:
            if result != "DEAD":
                result = "STALLED"
            why.append(f"quiet for {fmt_age(live_age)}")
        elif result == "UNKNOWN":
            result = "OK"
    if an and an["blocking_waits"]:
        why.append(f"{len(an['blocking_waits'])} quiet gap(s) > {call_seconds}s = invisible blocking black box")
    if s_age is not None and s_age > call_seconds and result == "OK":
        why.append(f"possibly inside a long call ({fmt_age(s_age)} quiet)")
    if hb and hb["repeats"] >= 2:
        why.append(f"heartbeat loop signal: {hb['repeats']} repeated steps")
    if an and an["loops"]:
        why.append("loop signal: " + ", ".join(f"{k} x{v}" for k, v in an["loops"][:3]))
    return result, why


_EXIT = {"OK": 0, "WARN": 0, "STALLED": 2, "BLOCKING": 2, "DEAD": 3, "UNKNOWN": 4}


def verdict_exit_code(result):
    return _EXIT.get(result, 4)


# --- report -----------------------------------------------------------------

def status_line(label, text):
    print(f"{label:<14} {text}")


def _report(a, hb, sess, an, result, why):
    hb_age = hb["last_age"] if hb else None
    s_age = age_of(an["last_ms"]) if an else None
    print(f"=== watchdog {now_iso()} ===")
    status_line("verdict:", result + ("  " + "; ".join(why) if why else ""))
    if hb:
        status_line("heartbeat:", f"{a.progress}  last={fmt_age(hb_age)} ago  {len(hb['entries'])} entries")
    else:
        status_line("heartbeat:", "(none)")
    if an:
        title = (sess["title"] or "")[:58]
        status_line("session:", f"{sess['id']}  {sess['agent']}  "
                               f"{session_model(sess) or '-'}  \"{title}\"")
        status_line("", f"last-event {fmt_age(s_age)} ago | parts={an['part_count']} | "
                        f"writes={an['created']} edits={an['edited']} | cost=${sess['cost'] or 0:.3f} "
                        f"| in/out={sess['tokens_input'] or 0}/{sess['tokens_output'] or 0}")
        status_line("tools:", "  ".join(f"{k}={v}" for k, v in sorted(an["tools"].items())))
        if an["running"]:
            for n, age, tgt in an["running"]:
                print(f"  ! IN FLIGHT  {n} running {age}: {tgt}")
        for n, dur, tgt in an["blocking_waits"][:6]:
            print(f"  ! BLOCKING WAIT {n} quiet {dur:.0f}s: {tgt}")
        for tag, tgt in an["bad"][:8]:
            print(f"  ! {tag:<20} {tgt}")
        for k, v in an["loops"][:6]:
            print(f"  ! LOOP       {k} x{v}")
        print(f"--- last {a.tail} events ---")
        for ms, n, st, tgt in an["timeline"][-a.tail:]:
            print(f"  {hhmmss(ms)} {n:<6} [{st}] {tgt[:100]}")
    elif hb:
        print(f"--- last {a.tail} heartbeats ---")
        for ts, tag, rest in hb["entries"][-a.tail:]:
            print(f"  {ts or '?':<20} {tag:<6} {rest}")


def _json(hb, sess, an, result, why):
    hb_age = hb["last_age"] if hb else None
    s_age = age_of(an["last_ms"]) if an else None
    print(json.dumps({
        "verdict": result, "why": why, "heartbeat_age_s": hb_age,
        "session": None if not sess else {"id": sess["id"], "title": sess["title"],
                                          "agent": sess["agent"], "cost": sess["cost"],
                                          "tokens_in": sess["tokens_input"],
                                          "tokens_out": sess["tokens_output"],
                                          "model": session_model(sess)},
        "session_age_s": s_age, "analysis": None if not an else {
            "tools": an["tools"], "created": an["created"], "edited": an["edited"],
            "blocking_waits": an["blocking_waits"], "running": an["running"],
            "bad": an["bad"], "loops": an["loops"]},
    }, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--progress", help="heartbeat log path")
    ap.add_argument("--session", help="explicit session id")
    ap.add_argument("--title", help="substring of session title")
    ap.add_argument("--parent", help="parent session id")
    ap.add_argument("--cwd", help="restrict title search to this repo dir")
    ap.add_argument("--tail", type=int, default=8, help="timeline entries to show")
    ap.add_argument("--stall-seconds", type=int, default=DEFAULT_STALL_SECONDS)
    ap.add_argument("--call-seconds", type=int, default=DEFAULT_CALL_SECONDS)
    ap.add_argument("--loop-repeats", type=int, default=DEFAULT_LOOP_REPEATS)
    ap.add_argument("--watch", type=int, metavar="SECONDS", default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    while True:
        hb = read_heartbeat(a.progress)
        con = db()
        sess = find_session(con, a.session, a.title, a.parent, a.cwd) if con and (a.session or a.title or a.parent) else None
        an = analyze_session(sess, load_parts(con, sess["id"]), a.call_seconds, a.loop_repeats) if sess else None
        result, why = verdict(hb, an, a.stall_seconds, a.call_seconds)
        if a.json:
            _json(hb, sess, an, result, why)
        else:
            _report(a, hb, sess, an, result, why)
        if not a.watch:
            return verdict_exit_code(result)
        time.sleep(a.watch)


if __name__ == "__main__":
    sys.exit(main())
