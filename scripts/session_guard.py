#!/usr/bin/env python3
"""Session-tree failure-pattern guard with abort authority (fail fast, not
fail slow). Plan: .opencode/plans/session-guard-fail-fast.md (RM-045).

Observes an orchestrating session's full subagent tree (workers and workers'
workers, depth <= 2 per reference/agent-teams.md) out-of-band, matches a
versioned registry of known failure patterns, and escalates:

  flag  ->  kill-child (surface)  ->  abort the root session

Abort is a process-group kill (SIGTERM, then SIGKILL after a grace period):
`opencode session` exposes only list/delete — there is no abort subcommand
(verified 2026-10-07). Every abort is recorded exactly once: an ABORT
sentinel (pattern + evidence + UTC timestamp) and one run-log record
kind=agent / outcome=stopped via the observing-runs schema owner.

Design constraints (inherited from scripts/watch_agent.py):
  * transient supervision only — read-only on the opencode DB (file:...?mode=ro)
    and session streams; never writes the observed session's context;
  * liveness comes from watch_agent's pure analysis — never reimplemented here;
  * the only write surfaces are the ABORT sentinel and the single run-log
    record.

Exit codes: 0 clean, 2 warned (flag/kill-child, or abort warranted without
kill authority), 5 abort performed, 4 unknown (no root / no DB).

Usage:
  python3 scripts/session_guard.py --root <session-id> [--once | --watch 15]
  python3 scripts/session_guard.py --parent <session-id> --once --json
  python3 scripts/session_guard.py --cwd ~/repos/project --watch 15
  python3 scripts/session_guard.py --root <id> --wrap -- opencode run ...
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import watch_agent as watch  # noqa: E402 - shared module object (identity-tested)

# --- pattern registry v1 -----------------------------------------------------
# (pattern, default action). Actions: flag | kill-child | abort.
# Each detector below is grounded in an observed incident; the registry is
# versioned by this table — extend it by adding a detector + a row here.

ACTIONS = {
    "empty-result": "flag",
    "permission-auto-reject": "flag",
    "dead-stream": "flag",
    "blocking-wait": "kill-child",
    "stalled": "kill-child",
    "identical-retry-loop": "abort",
    "wave-failure": "abort",
    "budget-exceeded": "abort",
}

PATTERN_DOC = {
    "empty-result": "final result empty or missing its declared contract markers (RM-023)",
    "permission-auto-reject": "a tool call died on an auto-rejected permission (external_directory class)",
    "dead-stream": "dispatched child with zero messages and zero parts (RM-026 class)",
    "blocking-wait": "quiet gap > --call-seconds between session events (watch_agent)",
    "stalled": "no heartbeat and no event within the stall budget (watch_agent verdict)",
    "identical-retry-loop": ">= retry_cap identical relaunches after failed results (RM-024)",
    "wave-failure": ">= wave-ratio of one dispatch wave failing with a shared pattern",
    "budget-exceeded": "tree wall clock beyond --budget-minutes",
}

PERMISSION_RE = re.compile(
    r"permission requested: external_directory \(([^)]*)\)[^.\n]*auto-rejecting"
    r"|permission denied: \S+ (\S+)")

_validate_mod = None


def _validator():
    """Load scripts/validate_delegated_result.py once (RM-023 contract)."""
    global _validate_mod
    if _validate_mod is None:
        path = os.path.join(HERE, "validate_delegated_result.py")
        spec = importlib.util.spec_from_file_location(
            "validate_delegated_result", path)
        _validate_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_validate_mod)
    return _validate_mod


def _log_run():
    path = os.path.join(REPO_ROOT, "skills", "observing-runs", "scripts",
                        "log_run.py")
    spec = importlib.util.spec_from_file_location("log_run", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- DB access (read-only; AC10) ---------------------------------------------

def db_uri(path):
    """The ONLY connection form the guard uses: read-only URI (AC10)."""
    return f"file:{path}?mode=ro"


def connect(path=None):
    path = path or watch.db_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        con = sqlite3.connect(db_uri(path), uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


# --- tree enumeration (AC1) --------------------------------------------------

def enumerate_tree(con, root_id, max_depth=2):
    """Root + descendants, depth-capped. Nodes: id, parent_id, depth, agent,
    title, time_created. A depth-3 node and any unrelated root never appear.
    """
    cur = con.cursor()
    cur.execute("SELECT * FROM session WHERE id=?", (root_id,))
    row = cur.fetchone()
    if row is None:
        return []
    nodes = []
    frontier = [(dict(row), 0)]
    seen = {root_id}
    while frontier:
        node, depth = frontier.pop(0)
        nodes.append({
            "id": node["id"], "parent_id": node["parent_id"], "depth": depth,
            "agent": node["agent"], "title": node["title"],
            "time_created": node["time_created"],
        })
        if depth >= max_depth:
            continue
        cur.execute("SELECT * FROM session WHERE parent_id=?", (node["id"],))
        for child in cur.fetchall():
            if child["id"] in seen:
                continue
            seen.add(child["id"])
            frontier.append((dict(child), depth + 1))
    nodes.sort(key=lambda n: (n["depth"], n["time_created"] or 0))
    return nodes


# --- per-node result + evidence readers --------------------------------------

def result_text(con, session_id):
    """Final result text: the text parts of the last assistant message.
    Empty string when the session produced no assistant text (RM-023's
    empty-result shape)."""
    cur = con.cursor()
    cur.execute(
        "SELECT id, data FROM message WHERE session_id=? ORDER BY time_created",
        (session_id,))
    last_id = None
    for r in cur.fetchall():
        try:
            d = json.loads(r["data"])
        except (TypeError, ValueError):
            continue
        if d.get("role") == "assistant":
            last_id = r["id"]
    if last_id is None:
        return ""
    cur.execute(
        "SELECT data FROM part WHERE message_id=? ORDER BY time_created",
        (last_id,))
    texts = []
    for r in cur.fetchall():
        try:
            d = json.loads(r["data"])
        except (TypeError, ValueError):
            continue
        if d.get("type") == "text" and (d.get("text") or "").strip():
            texts.append(d["text"])
    return "\n".join(texts)


def _permission_denial(parts):
    """The latest denial CARRIER among a session's parts, or None (AC9).

    A denial carrier is an ERROR-state tool part whose output matches
    PERMISSION_RE — the shape the AC3 fixture models. Successful/completed
    tool output is never scanned: a child that merely quotes denial-shaped
    text (e.g. reads the guard's own source or the supervision reference)
    must not false-trigger. Returns {"path", "ms"} or None; `ms` is the
    carrier's time_created so the caller can test recency on the event clock
    (AC12), never the part index.
    """
    latest = None
    for ms, d in parts:
        if d.get("type") != "tool":
            continue
        st = d.get("state") or {}
        if st.get("status") != "error":
            continue
        m = None
        for field in ("output", "error"):
            out = st.get(field)
            if isinstance(out, str):
                m = PERMISSION_RE.search(out)
                if m:
                    break
        if not m:
            continue
        latest = {"path": m.group(1) or m.group(2) or "?", "ms": ms}
    return latest


def _count_rows(con, table, session_id):
    cur = con.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE session_id=?",
                (session_id,))
    return cur.fetchone()[0]


def _load_parts(con, session_id):
    """watch_agent's part loader: [(time_created_ms, data_dict), ...]."""
    return watch.load_parts(con, session_id)


# --- liveness (reuse only; AC5) ----------------------------------------------

def _verdict_at(an, stall_seconds, call_seconds, now):
    """watch_agent.verdict with the clock pinned to `now` when given (test
    seam). No liveness logic lives in this module."""
    if now is None:
        return watch.verdict(None, an, stall_seconds, call_seconds)
    real = time.time
    time.time = lambda: now  # watch_agent reads time.time() via age_of()
    try:
        return watch.verdict(None, an, stall_seconds, call_seconds)
    finally:
        time.time = real


def _recent_event(an, now, stall_seconds):
    """True when the session's last event is within the stall window (the
    child is still streaming). No parts -> no recency signal."""
    if an["last_ms"] is None:
        return False
    return (now - an["last_ms"] / 1000.0) <= stall_seconds


# --- pattern detection -------------------------------------------------------

def _hit(pattern, sessions, evidence):
    return {"pattern": pattern, "action": ACTIONS[pattern],
            "sessions": sorted(sessions), "evidence": evidence}


def detect_patterns(con, nodes, *, contract=None, wave_ratio=0.6,
                    retry_cap=2, retry_window_min=30, budget_minutes=45,
                    call_seconds=300, stall_seconds=240, loop_repeats=3,
                    wave_window_s=60, wave_min_children=2, now=None):
    now = time.time() if now is None else now
    hits = []
    if not nodes:
        return hits
    root = nodes[0]
    children = [n for n in nodes if n["depth"] >= 1]

    # -- per-node result classification (lifecycle-aware) ------------------
    # opencode.db records no completion column, so completion is inferred:
    # a non-empty result text with no in-flight tool call is a done child.
    # Order: permission-auto-reject -> dead-stream -> has_result ->
    # in-flight -> empty-result (RM-023's real shape, detected only once the
    # child is genuinely quiet with no result).
    failed = {}      # sid -> failing pattern (result-level failures)
    denied = {}      # sid -> denied path
    analyses = {}    # sid -> watch_agent analysis (computed once)
    done = {}        # sid -> True for a completed (has-result) child
    for n in children:
        sid = n["id"]
        n_msg, n_part = (_count_rows(con, "message", sid),
                         _count_rows(con, "part", sid))
        if n_msg == 0 and n_part == 0:
            failed[sid] = "dead-stream"
            hits.append(_hit("dead-stream", [sid],
                             f"{sid}: zero messages and zero parts"))
            continue
        parts = _load_parts(con, sid)
        an = watch.analyze_session(n, parts, call_seconds, loop_repeats)
        analyses[sid] = an
        text = result_text(con, sid)
        # The done predicate is the ONE shared with watch_agent (AC11/AC12):
        # a non-empty last text followed by a terminal step-finish, no tool in
        # flight. A message without step-finish is an unfinished turn — its
        # text does NOT make the child done.
        has_result = watch.has_terminal_result(parts, an["running"])
        # The permission scan reads ONLY denial carriers (error-state tool
        # parts) and a denial explains the death only when it is the child's
        # LATEST event (max time_created, AC12 — never the part index, so a
        # timestamp tie cannot downgrade a denial-death to empty-result) AND
        # the child is not done. A child that was denied, recovered, and kept
        # working is not a denial-death; a child whose SUCCESSFUL tool output
        # merely quotes denial-shaped text is not a denial at all (AC9).
        denial = _permission_denial(parts)
        latest_ms = max((ms for ms, _ in parts if ms is not None), default=None)
        if denial and denial["ms"] == latest_ms and not has_result:
            path = denial["path"]
            denied[sid] = path
            failed[sid] = "permission-auto-reject"
            hits.append(_hit("permission-auto-reject", [sid],
                             f"{sid}: permission denied on {path} "
                             f"(hint: grant with --allow-dirs {path})"))
            continue  # the denial explains the death; no shadowing generic hit
        if has_result:
            done[sid] = True  # completed: no liveness hit, contract still checked
            if contract:
                val = _validator()
                markers = val.CONTRACTS.get(contract)
                ok, missing = val.validate(text, markers or [])
                if not ok:
                    if missing is None:
                        ev = f"{sid}: empty result (contract {contract})"
                    else:
                        ev = (f"{sid}: malformed result (contract {contract}, "
                              f"missing {missing})")
                    failed[sid] = "empty-result"
                    hits.append(_hit("empty-result", [sid], ev))
            continue
        if an["running"] or _recent_event(an, now, stall_seconds):
            continue  # still streaming: no result-level classification yet
        # quiet past the stall window, no in-flight call, no terminal marker
        if text.strip():
            # an unfinished turn that already emitted interim text is a hung
            # child, not an empty result: leave it to the liveness rules below
            # (STALLED/DEAD), never a false empty-result.
            continue
        # quiet, no in-flight call, and genuinely no result text
        failed[sid] = "empty-result"
        ev = (f"{sid}: empty result (contract {contract})" if contract
              else f"{sid}: empty result")
        hits.append(_hit("empty-result", [sid], ev))

    # -- liveness (watch_agent analysis; AC5) -------------------------------
    for n in children:
        sid = n["id"]
        an = analyses.get(sid)
        if an is None:
            parts = _load_parts(con, sid)
            an = watch.analyze_session(n, parts, call_seconds, loop_repeats)
        if an["blocking_waits"]:
            gaps = ", ".join(f"{g[1]:.0f}s/{g[0]}" for g in an["blocking_waits"][:3])
            hits.append(_hit("blocking-wait", [sid],
                             f"{sid}: quiet gap(s) > {call_seconds}s ({gaps})"))
        if done.get(sid):
            continue  # a completed child is done, not stalled
        verdict, why = _verdict_at(an, stall_seconds, call_seconds, now)
        if verdict in ("STALLED", "DEAD"):
            hits.append(_hit("stalled", [sid],
                             f"{sid}: {verdict} — " + "; ".join(why[:2])))

    # -- identical-retry-loop (RM-024's bound; AC4) --------------------------
    groups = {}
    for n in children:
        sid = n["id"]
        if sid not in failed:
            continue
        key = (n["agent"] or "", " ".join((n["title"] or "").split()).lower())
        groups.setdefault(key, []).append(n)
    for (agent, title), group in groups.items():
        group.sort(key=lambda n: n["time_created"] or 0)
        if len(group) < retry_cap + 1:
            continue
        span = ((group[-1]["time_created"] or 0)
                - (group[0]["time_created"] or 0)) / 1000.0
        if span > retry_window_min * 60:
            continue
        digest = hashlib.sha256(
            f"{agent}\n{title}".encode("utf-8")).hexdigest()[:12]
        hits.append(_hit(
            "identical-retry-loop", [n["id"] for n in group],
            f"{len(group)} identical relaunches of {agent or '?'} "
            f"\"{title[:60]}\" (title digest {digest}) within "
            f"{span/60:.0f}min after failed results"))

    # -- wave-failure (the 3-of-5 shape; AC6) -------------------------------
    kids = sorted(children, key=lambda n: n["time_created"] or 0)
    waves, current = [], []
    for n in kids:
        if current and (n["time_created"] or 0) - \
                (current[0]["time_created"] or 0) > wave_window_s * 1000:
            waves.append(current)
            current = []
        current.append(n)
    if current:
        waves.append(current)
    for wave in waves:
        if len(wave) < wave_min_children:
            continue
        by_pattern = {}
        for n in wave:
            if n["id"] in failed:
                by_pattern.setdefault(failed[n["id"]], []).append(n["id"])
        for pattern, sids in by_pattern.items():
            if len(sids) < wave_min_children:
                continue
            ratio = len(sids) / len(wave)
            if ratio >= wave_ratio:
                hits.append(_hit(
                    "wave-failure", sids,
                    f"wave@{(wave[0]['time_created'] or 0)}: {len(sids)}/"
                    f"{len(wave)} children failed with {pattern}"))

    # -- budget (AC7) --------------------------------------------------------
    if budget_minutes and budget_minutes > 0:
        age = now - (root["time_created"] or now) / 1000.0
        if age > budget_minutes * 60:
            hits.append(_hit(
                "budget-exceeded", [root["id"]],
                f"tree age {age/60:.0f}min > budget {budget_minutes}min"))
    return hits


# --- abort mechanics (AC8/AC9) ----------------------------------------------

def write_sentinel(path, root_id, pattern, evidence, sessions):
    payload = {
        "pattern": pattern,
        "evidence": evidence,
        "sessions": sessions,
        "ts": now_iso(),
        "root_session_id": root_id,
    }
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return payload


def emit_record(pattern, evidence, logs_dir=None):
    """Exactly one kind=agent / outcome=stopped record via the schema owner."""
    log_run = _log_run()
    record = {
        "kind": "agent",
        "agent": "session-guard",
        "model": None,
        "tokens_in": None,
        "tokens_out": None,
        "cost": None,
        "duration_ms": None,
        "outcome": "stopped",
        "detail": f"session-guard abort: {pattern} — {evidence}"[:log_run.DETAIL_MAX],
    }
    return log_run.log_record(record, logs_dir=logs_dir)


def kill_group(pid, grace=5):
    """SIGTERM the process group, then ALWAYS SIGKILL the group after `grace`
    seconds unless the whole group is gone. Group liveness is probed with
    killpg(pgid, 0) — never the leader alone: a leader that exits on SIGTERM
    must not strand grandchildren in the group (review finding 2, 2026-10-07).
    """
    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = pid

    def group_alive():
        try:
            os.killpg(pgid, 0)
            return True
        except OSError:
            return False

    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + grace
    while time.time() < deadline:
        if not group_alive():
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


# --- orchestration -----------------------------------------------------------

def select_root(con, args):
    if args.root or args.parent:
        return args.root or args.parent
    if args.cwd:
        cur = con.cursor()
        cur.execute(
            "SELECT id FROM session WHERE parent_id IS NULL AND directory=?"
            " ORDER BY time_updated DESC LIMIT 1",
            (os.path.abspath(args.cwd),))
        row = cur.fetchone()
        return row["id"] if row else None
    return None


def scan_once(args, root_id):
    con = connect(args.db)
    if con is None:
        return None, None, None
    try:
        nodes = enumerate_tree(con, root_id, max_depth=2)
        hits = detect_patterns(
            con, nodes, contract=args.contract, wave_ratio=args.wave_ratio,
            retry_cap=args.retry_cap, retry_window_min=args.retry_window_min,
            budget_minutes=args.budget_minutes, call_seconds=args.call_seconds,
            stall_seconds=args.stall_seconds, now=args.fixed_now)
        return nodes, hits, con
    finally:
        if con is not None:
            con.close()


def decide(hits):
    """(verdict, exit_code): abort-class dominates, then kill-child, then flag."""
    if any(h["action"] == "abort" for h in hits):
        return "abort", None
    if any(h["action"] == "kill-child" for h in hits):
        return "warn", 2
    if hits:
        return "warn", 2
    return "clean", 0


def run_abort(args, hits, root_id, root_pid):
    """Sentinel + exactly one run-log record; kill only when authority exists.
    Returns the exit code (5 killed, 2 abort warranted without authority)."""
    primary = next(h for h in hits if h["action"] == "abort")
    sentinel = args.sentinel or os.path.join(
        ".scratch", "session-guard", f"ABORT.{root_id}")
    payload = write_sentinel(sentinel, root_id, primary["pattern"],
                             primary["evidence"], primary["sessions"])
    try:
        emit_record(primary["pattern"], primary["evidence"],
                    logs_dir=args.logs_dir)
    except Exception as exc:  # noqa: BLE001 - never mask the abort itself
        print(f"error: run-log record failed: {exc}", file=sys.stderr)
    if root_pid is not None:
        kill_group(root_pid)
        print(f"ABORT pattern={primary['pattern']} root={root_id} "
              f"pid={root_pid} sentinel={sentinel}", flush=True)
        return 5
    print(f"ABORT-PENDING pattern={primary['pattern']} root={root_id} "
          f"sentinel={sentinel} (no kill authority)", flush=True)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Session-tree failure-pattern guard (fail fast).")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--root", help="root session id of the supervised tree")
    sel.add_argument("--parent", help="alias of --root")
    sel.add_argument("--cwd", help="pick the newest root session in this dir")
    ap.add_argument("--db", help="opencode.db path (default: OPENCODE_DB_PATH"
                                " or the live DB)")
    ap.add_argument("--once", action="store_true", help="single scan and exit")
    ap.add_argument("--watch", type=int, metavar="SECONDS", default=0,
                    help="re-scan every N seconds until the wrapped cmd ends")
    ap.add_argument("--budget-minutes", type=float, default=45,
                    help="tree wall-clock budget; 0 disables (default 45)")
    ap.add_argument("--wave-ratio", type=float, default=0.6)
    ap.add_argument("--call-seconds", type=int, default=300)
    ap.add_argument("--stall-seconds", type=int, default=240)
    ap.add_argument("--retry-cap", type=int, default=2,
                    help="identical relaunches tolerated before abort (RM-024)")
    ap.add_argument("--retry-window-min", type=int, default=30)
    ap.add_argument("--contract", help="delegated-result contract name for"
                                      " result validation (RM-023)")
    ap.add_argument("--kill-root", action="store_true",
                    help="allow root kill in observe mode (with --root-pid)")
    ap.add_argument("--root-pid", type=int,
                    help="pid whose process group dies on abort")
    ap.add_argument("--sentinel", help="ABORT sentinel path")
    ap.add_argument("--logs-dir", help="run-log directory (schema owner default"
                                      " when omitted)")
    ap.add_argument("--fixed-now", type=float, help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true")
    # `--wrap -- CMD...` is split by hand: argparse's REMAINDER mishandles the
    # `--` separator (it ends option parsing before the remainder is taken).
    argv = list(sys.argv[1:] if argv is None else argv)
    wrap_cmd = None
    if "--wrap" in argv:
        i = argv.index("--wrap")
        wrap_cmd = argv[i + 1:]
        argv = argv[:i]
        if wrap_cmd[:1] == ["--"]:
            wrap_cmd = wrap_cmd[1:]
    a = ap.parse_args(argv)
    if a.contract and a.contract not in _validator().CONTRACTS:
        print(f"error: unknown contract: {a.contract} (known: "
              f"{', '.join(sorted(_validator().CONTRACTS))})", file=sys.stderr)
        return 4

    con = connect(a.db)
    if con is None:
        print("error: cannot open a read-only opencode.db", file=sys.stderr)
        return 4
    root_id = select_root(con, a)
    con.close()
    if not root_id:
        print("error: no root session resolved (pass --root/--parent/--cwd)",
              file=sys.stderr)
        return 4

    wrapped = None
    if wrap_cmd is not None:
        if not wrap_cmd:
            print("error: --wrap needs a command after --", file=sys.stderr)
            return 4
        wrapped = subprocess.Popen(wrap_cmd, start_new_session=True)
        # Let the wrapped command reach exec / its startup handshake before
        # the first scan can abort it (review finding 7: a pid handshake
        # racing the abort is a test flake, not a feature).
        time.sleep(0.3)

    def one_pass():
        nodes, hits, _ = scan_once(a, root_id)
        if nodes is None:
            print("error: DB disappeared mid-run", file=sys.stderr)
            return 4, "unknown"
        if not nodes:
            print(f"error: root session not found: {root_id}", file=sys.stderr)
            return 4, "unknown"
        verdict, code = decide(hits)
        if a.json:
            print(json.dumps({"root": root_id, "verdict": verdict,
                              "nodes": nodes, "hits": hits}, default=str),
                  flush=True)
        else:
            for h in hits:
                print(f"  ! {h['pattern']:<22} [{h['action']}] {h['evidence']}",
                      flush=True)
            print(f"=== session-guard {now_iso()} root={root_id} "
                  f"nodes={len(nodes)} hits={len(hits)} verdict={verdict}",
                  flush=True)
        if verdict == "abort":
            pid = wrapped.pid if wrapped is not None else (
                a.root_pid if a.kill_root else None)
            return run_abort(a, hits, root_id, pid), "abort"
        return code, verdict

    try:
        if wrapped is not None:
            period = a.watch or 5
            while True:
                code, _verdict = one_pass()
                if code == 5:
                    return code
                if wrapped.poll() is not None:
                    return one_pass()[0]
                time.sleep(period)
        # Observe mode: --watch N keeps scanning (continuous supervision,
        # §5's documented launch form) until an abort-class pattern fires —
        # one sentinel + one record, then exit (review finding 1).
        while True:
            code, verdict = one_pass()
            if not a.watch or verdict == "abort":
                return code
            time.sleep(a.watch)
    finally:
        if wrapped is not None and wrapped.poll() is None:
            try:
                os.killpg(os.getpgid(wrapped.pid), signal.SIGKILL)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
