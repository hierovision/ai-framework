#!/usr/bin/env python3
"""Completion-observer: wake the orchestrator when a detached dispatch ends.

RM-058 (plan `.opencode/plans/rm-058-orchestrator-wake.md`). Spawned detached by
`scripts/dispatch_agent.py` immediately after the child's `session_id=` is
printed (D2). It polls the ONE durable supervision surface — the dispatcher's
heartbeat envelope plus the run-log record `/scripts/log_run.py` already emits
(D1) — and delivers a fixed-shape wake into the orchestrator conversation with
an explicit `opencode run --session <id>` (never `--continue`; AGENTS.md
rule 1), gated on the orchestrator session being quiescent (D2 step 4).

Boundaries:
  * The wake vehicle and rule-1 quiescence gate: D2.
  * Terminal classification (success / failure / error / aborted) plus the
    liveness-window abort: D1's table.
  * Heartbeat line ownership: it appends exactly one `SURVEY running` after the
    first poll that finds real child evidence, then one terminal `WAKE <outcome>`
    / `WAKE_DEFERRED <outcome>` line (D5).
  * The wake text shape: D7.
  * RM-059 seam (D6): this module consumes ONLY the completion predicate
    (`watch_agent.has_terminal_result`) and the read-only session readers. It
    never computes the intervention/liveness state and never emits that
    vocabulary — quiet-but-non-terminal is its own `AWAITING` classification.

Exit codes: 0 after a terminal observation (wake delivered or deferred);
2 usage/environment error.
"""
import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import time


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# The completion predicate and the read-only session-store readers live in the
# watcher; imported, never redefined (D6).
watch_agent = _load_module(os.path.join(SCRIPT_DIR, "watch_agent.py"), "watch_agent")

# Tags written by the dispatcher envelope and by the child, and the observer's
# own tags (D5 line ownership). Only child-owned tags prove the child runs.
_ENVELOPE_TAGS = {"START", "DONE", "BLOCKED"}
_OWNER_TAGS = {"SURVEY", "WAKE", "WAKE_DEFERRED"}
_CHILD_TAGS = {"STEP", "CALL", "POLL", "EVAL"}

DEFAULT_INTERVAL = 30
DEFAULT_DEADLINE = 300
# 2x the watcher's stall window (D1 abort semantics).
DEFAULT_LIVENESS_SECONDS = 2 * watch_agent.DEFAULT_STALL_SECONDS
WAKE_SUBPROCESS_TIMEOUT = 180


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts):
    """Epoch seconds for a heartbeat/run-log UTC ISO timestamp, else None."""
    if not ts:
        return None
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp()


# --- durable-surface readers (read-only) ------------------------------------

def heartbeat_task(path):
    """The `# progress: <task>` header value, or None."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("# progress:"):
                    return line.split(":", 1)[1].strip() or None
                if line.strip() and not line.startswith("#"):
                    break
    except OSError:
        return None
    return None


def start_epoch(hb):
    """Epoch of the dispatcher's START line (the child window floor), or None."""
    for ts, tag, _rest in (hb.get("entries", []) if hb else []):
        if tag == "START":
            return _parse_ts(ts)
    return None


def terminal_line(hb):
    """The dispatcher's terminal heartbeat entry: (tag, rest) or None."""
    if not hb:
        return None
    for ts, tag, rest in hb.get("entries", []):
        if tag in ("DONE", "BLOCKED"):
            return tag, rest
    return None


def child_evidence(hb, child_has_parts):
    """True once the child has proven it runs: a child-owned line or DB parts."""
    if child_has_parts:
        return True
    for _ts, tag, _rest in (hb.get("entries", []) if hb else []):
        if tag in _CHILD_TAGS:
            return True
    return False


def liveness_age(hb, child_last_epoch, wall_now):
    """Age of the freshest non-observer activity, or None.

    The observer's own SURVEY/WAKE lines are excluded so they cannot keep a
    dead child looking fresh.
    """
    epochs = []
    for ts, tag, _rest in reversed((hb or {}).get("entries", [])):
        if ts and tag not in _OWNER_TAGS:
            ep = _parse_ts(ts)
            if ep is not None:
                epochs.append(ep)
            break
    if child_last_epoch is not None:
        epochs.append(child_last_epoch)
    if not epochs:
        return None
    return wall_now - max(epochs)


def read_run_log(logs_dir, agent, since_epoch):
    """The latest matching `kind=agent` run-log record and its file path.

    Corroboration only (D1): the dispatcher-written terminal heartbeat line is
    authoritative. Never writes a record (AC10).
    """
    if not logs_dir or not os.path.isdir(logs_dir):
        return None, None
    best, best_path, best_ts = None, None, None
    try:
        names = sorted(os.listdir(logs_dir))
    except OSError:
        return None, None
    for name in names:
        if not (name.startswith("run-") and name.endswith(".jsonl")):
            continue
        path = os.path.join(logs_dir, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            if rec.get("kind") != "agent" or rec.get("agent") != agent:
                continue
            ep = _parse_ts(rec.get("ts"))
            if since_epoch is not None and ep is not None and ep < since_epoch:
                continue
            if ep is None and best is not None:
                continue
            if best_ts is None or (ep is not None and ep >= best_ts):
                best, best_path, best_ts = rec, path, ep
    return best, best_path


# --- classification (pure) ---------------------------------------------------

def classify(hb, run_rec, live_age, liveness_seconds, child_running):
    """Return (outcome, detail) for the durable surface.

    outcome in {success, failure, error, aborted, AWAITING}. The dispatcher's
    terminal heartbeat line is authoritative; the run-log record only
    disambiguates a BLOCKED line into failure vs error; the liveness window
    names an abort when the dispatcher died before writing a terminal line.
    """
    term = terminal_line(hb)
    if term:
        tag, rest = term
        if tag == "DONE":
            return "success", None
        detail = rest or "blocked"
        outcome = "failure"
        if run_rec:
            recorded = run_rec.get("outcome")
            if recorded == "error":
                outcome = "error"
            elif recorded == "stopped":
                outcome = "aborted"
            if run_rec.get("detail"):
                detail = run_rec["detail"]
        return outcome, detail
    if (not child_running) and live_age is not None \
            and live_age > liveness_seconds:
        return "aborted", (f"no heartbeat or session event for "
                           f"{int(live_age)}s; dispatcher wrote no terminal line")
    return "AWAITING", None


# --- wake delivery (D2 / D7) -------------------------------------------------

def wake_text(cfg, outcome, detail, run_path, hb_path):
    task = heartbeat_task(hb_path) or cfg.agent
    lines = [
        f"DISPATCH WAKE {cfg.agent} outcome={outcome}",
        f"task={task}  child={cfg.child_session or '?'}",
        f"result={cfg.result or '?'}  log={run_path or 'none'}  "
        f"heartbeat={os.path.abspath(hb_path)}",
    ]
    if detail:
        lines.append(f"detail={detail}")
    if cfg.worktree:
        lines.append(f"worktree={cfg.worktree} branch={cfg.branch or '?'}")
        lines.append(f"landing=not-yet; cleanup needed: "
                     f"{cfg.worktree} + {cfg.branch or '?'}")
    else:
        lines.append("landing=not-yet; cleanup needed: none")
    return "\n".join(lines)


def deliver(cfg, text):
    """Append the wake to the orchestrator conversation via an explicit
    `--session` (never `--continue`). Returns True on a clean exit."""
    argv = ["opencode", "run", "--session", cfg.orchestrator_session,
            "--format", "json"]
    if cfg.model:
        argv += ["--model", cfg.model]
    argv.append(text)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=WAKE_SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# --- quiescence gate (D2 step 4) ---------------------------------------------

def orchestrator_quiescent(cfg, state):
    """True when the orchestrator session has no tool in flight and its
    `time_updated` is stable across two polls. No DB -> cannot gate, deliver
    (heartbeat-only mode, D1)."""
    try:
        con = watch_agent.db()
    except Exception:  # noqa: BLE001 - best-effort gate
        con = None
    if con is None:
        return True
    try:
        sess = watch_agent.find_session(con, sid=cfg.orchestrator_session)
        if sess is None:
            return True
        parts = watch_agent.load_parts(con, sess["id"])
        an = watch_agent.analyze_session(sess, parts, cfg.call_seconds,
                                         cfg.loop_repeats)
        updated = sess["time_updated"]
        prev = state.get("orchestrator_updated")
        state["orchestrator_updated"] = updated
        if an["running"]:
            return False
        return prev is not None and prev == updated
    except Exception:  # noqa: BLE001 - a broken DB must not stall the wake
        return True
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass


# --- child proof (DB corroboration) -----------------------------------------

def _child_db_state(cfg):
    """(has_parts, has_terminal, running) for the child session, or
    (False, False, False) when unknown."""
    if not cfg.child_session:
        return False, False, False
    try:
        con = watch_agent.db()
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        return False, False, False
    try:
        sess = watch_agent.find_session(con, sid=cfg.child_session)
        if sess is None:
            return False, False, False
        parts = watch_agent.load_parts(con, sess["id"])
        if not parts:
            return False, False, False
        an = watch_agent.analyze_session(sess, parts, cfg.call_seconds,
                                         cfg.loop_repeats)
        terminal = watch_agent.has_terminal_result(parts, an["running"])
        return True, terminal, bool(an["running"])
    except Exception:  # noqa: BLE001
        return False, False, False
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass


# --- loop --------------------------------------------------------------------

def _append_line(path, text):
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{now_iso()} {text}\n")
            fh.flush()
    except OSError:
        pass


def run(cfg, sleep=time.sleep, now=time.monotonic):
    """Poll the durable surface until terminal; wake on terminal or defer.

    `sleep` and `now` are injectable for hermetic tests. `now` is a monotonic
    clock used only for the delivery deadline; liveness uses wall-clock parsed
    timestamps.
    """
    hb_path = cfg.heartbeat
    state = {}
    survey_written = False
    terminal_at = None
    while True:
        hb = watch_agent.read_heartbeat(hb_path)
        child_has_parts, _child_terminal, child_running = _child_db_state(cfg)

        if not survey_written and child_evidence(hb, child_has_parts):
            _append_line(hb_path, "SURVEY running")
            survey_written = True

        since = start_epoch(hb)
        run_rec, run_path = read_run_log(cfg.logs_dir, cfg.agent, since)

        live_age = liveness_age(hb, _child_last_epoch(cfg), time.time())
        outcome, detail = classify(hb, run_rec, live_age,
                                   cfg.liveness_seconds, child_running)

        if outcome == "AWAITING":
            sleep(cfg.interval)
            continue

        if terminal_at is None:
            terminal_at = now()
        if orchestrator_quiescent(cfg, state):
            text = wake_text(cfg, outcome, detail, run_path, hb_path)
            if deliver(cfg, text):
                _append_line(hb_path, f"WAKE {outcome}")
                return 0
        if now() - terminal_at > cfg.deadline:
            _append_line(hb_path, f"WAKE_DEFERRED {outcome} heartbeat={hb_path}")
            return 0
        sleep(cfg.interval)


def _child_last_epoch(cfg):
    if not cfg.child_session:
        return None
    try:
        con = watch_agent.db()
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        return None
    try:
        sess = watch_agent.find_session(con, sid=cfg.child_session)
        if sess is None:
            return None
        parts = watch_agent.load_parts(con, sess["id"])
        if not parts:
            return None
        ms = parts[-1][0]
        return (ms / 1000.0) if ms else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass


# --- CLI ---------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        description="Completion-observer: wake the orchestrator on dispatch end.")
    ap.add_argument("--heartbeat", required=True,
                    help="Dispatcher heartbeat file (the durable surface).")
    ap.add_argument("--agent", required=True, help="Dispatched agent name.")
    ap.add_argument("--dir", dest="dir_", default=None,
                    help="Dispatch working directory.")
    ap.add_argument("--orchestrator-session", dest="orchestrator_session",
                    required=True, help="Session id to append the wake to.")
    ap.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE,
                    help="Delivery retry budget in seconds after terminal "
                         f"(default {DEFAULT_DEADLINE}).")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                    help=f"Poll interval seconds (default {DEFAULT_INTERVAL}).")
    ap.add_argument("--liveness-seconds", type=float,
                    default=DEFAULT_LIVENESS_SECONDS,
                    help="Abort window when no terminal line appears "
                         f"(default {DEFAULT_LIVENESS_SECONDS}).")
    ap.add_argument("--child-session", dest="child_session", default=None,
                    help="Child session id (for the wake + DB corroboration).")
    ap.add_argument("--result", default=None, help="Child result file path.")
    ap.add_argument("--logs-dir", dest="logs_dir", default=None,
                    help="Run-log directory (default: repo logs/).")
    ap.add_argument("--worktree", default=None,
                    help="Worktree path when --worktree dispatch was used.")
    ap.add_argument("--branch", default=None, help="Worktree branch name.")
    ap.add_argument("--model", default=None,
                    help="Orchestrator model for the wake run (optional).")
    ap.add_argument("--call-seconds", dest="call_seconds", type=int,
                    default=watch_agent.DEFAULT_CALL_SECONDS)
    ap.add_argument("--loop-repeats", dest="loop_repeats", type=int,
                    default=watch_agent.DEFAULT_LOOP_REPEATS)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    if not a.heartbeat:
        print("error: --heartbeat is required", file=sys.stderr)
        return 2
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
