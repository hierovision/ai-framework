#!/usr/bin/env python3
"""Run-vehicle dispatcher: one top-level `opencode run --agent` session.

Why (plan agent-teams-dispatch): the free tier rejects a model call made from
a nested Task subagent, and the core personas are free-bound. `opencode run
--agent <name>` is a top-level session (free allowed), carries the agent's
config, supports per-call lane choice and `--session` resume, and its JSON
event stream yields session/model attribution.

What it does:
  * reads the prompt from --prompt-file;
  * runs `opencode run --agent <name> [--model <id>] [--session <id>]
    [--dir <dir>] --format json <prompt>` in its own process group;
  * prints `session_id=<id>` as soon as the stream names it (question relay);
  * writes the final text to --out (default: <prompt-file>.result.md);
  * with --contract / --markers, validates the result via
    scripts/validate_delegated_result.py (RM-023): an empty or malformed
    result exits non-zero;
  * emits exactly one kind=agent run-log record via the observing-runs schema
    owner (`log_run.py`) with agent, resolved model, tokens/cost from the
    stream, and outcome.

Lane policy, topology bounds, and the attribution contract:
reference/agent-teams.md.

Exit codes: 0 success; 1 contract-invalid result; 2 usage/environment error;
3 provider/process/stream error; 4 timeout.

Usage:
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md \
      --contract implement-handoff --model opencode-go/kimi-k3
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md \
      --session ses_...        # resume (question relay)
"""
import argparse
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Single source of truth for the run-log schema (RM-001) and the
# delegated-result contracts (RM-023) — imported, never redefined.
log_run = _load_module(
    os.path.join(REPO_ROOT, "skills", "observing-runs", "scripts", "log_run.py"),
    "log_run")
validate_delegated_result = _load_module(
    os.path.join(SCRIPT_DIR, "validate_delegated_result.py"),
    "validate_delegated_result")

DEFAULT_TIMEOUT = 600


# --- stream parsing (pure) ---------------------------------------------------

def parse_stream(raw):
    """Return (events, parse_errors) for a newline-delimited JSON stream."""
    events, errors = [], []
    for i, line in enumerate((raw or "").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {i}: {exc.msg}")
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            errors.append(f"line {i}: event is not a JSON object")
    return events, errors


def _parts(events):
    for ev in events:
        part = ev.get("part") if isinstance(ev.get("part"), dict) else ev
        if isinstance(part, dict):
            yield part


def session_id_of(events):
    """First session id the stream names (top-level or part-level)."""
    for ev in events:
        if ev.get("sessionID"):
            return ev["sessionID"]
        part = ev.get("part")
        if isinstance(part, dict) and part.get("sessionID"):
            return part["sessionID"]
    return None


def final_text(events):
    """Join the stream's text parts (the delegated result)."""
    chunks = [p["text"] for p in _parts(events)
              if p.get("type") == "text" and isinstance(p.get("text"), str)]
    return "\n".join(chunks).strip()


def token_totals(events):
    """Sum tokens/cost across step-finish events. Missing stays None."""
    tokens_in = tokens_out = cost = None
    for part in _parts(events):
        if part.get("type") not in ("step-finish", "step_finish"):
            continue
        tk = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        for key, value in (("input", tk.get("input")), ("output", tk.get("output"))):
            if isinstance(value, (int, float)):
                if key == "input":
                    tokens_in = (tokens_in or 0) + int(value)
                else:
                    tokens_out = (tokens_out or 0) + int(value)
        c = part.get("cost")
        if isinstance(c, (int, float)):
            cost = (cost or 0.0) + float(c)
    return tokens_in, tokens_out, (round(cost, 6) if cost else None)


def resolve_agent_model(agent, explicit=None):
    """Explicit --model wins; else the target's frontmatter binding, else None.

    Named dispatch honors the target's declared model
    (reference/opencode-integration.md).
    """
    if explicit:
        return explicit
    path = os.path.join(REPO_ROOT, "agents", agent + ".md")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None
    fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
    m = re.search(r"^model:\s*(\S+)\s*$", fm, re.MULTILINE)
    return m.group(1) if m else None


# --- process execution -------------------------------------------------------

def _maybe_print_session(line, printed):
    if printed["sid"]:
        return
    try:
        ev = json.loads(line)
    except (TypeError, ValueError):
        return
    if not isinstance(ev, dict):
        return
    sid = ev.get("sessionID")
    if not sid and isinstance(ev.get("part"), dict):
        sid = ev["part"].get("sessionID")
    if sid:
        printed["sid"] = sid
        print(f"session_id={sid}", flush=True)


def run_opencode(argv, timeout):
    """Run in its own process group; kill the group at timeout.

    Returns (returncode, stdout, stderr, timed_out). The session id is
    printed as soon as the stream names it (question relay).
    """
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True)
    except OSError as exc:
        return 127, "", f"cannot launch opencode: {exc}", False

    out_lines, err_lines = [], []
    printed = {"sid": None}

    def reader(pipe, sink, is_stdout):
        try:
            for line in iter(pipe.readline, ""):
                sink.append(line)
                if is_stdout:
                    _maybe_print_session(line, printed)
        finally:
            pipe.close()

    threads = [
        threading.Thread(target=reader, args=(proc.stdout, out_lines, True),
                         daemon=True),
        threading.Thread(target=reader, args=(proc.stderr, err_lines, False),
                         daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    for thread in threads:
        thread.join(timeout=5)
    rc = proc.returncode if proc.returncode is not None else -1
    return rc, "".join(out_lines), "".join(err_lines), timed_out


# --- main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run-vehicle dispatcher (one top-level `opencode run` session).")
    ap.add_argument("--agent", required=True, help="Agent name to dispatch.")
    ap.add_argument("--prompt-file", required=True, help="File with the prompt.")
    ap.add_argument("--model", default=None,
                    help="Lane override (provider/model); default: the agent's binding.")
    ap.add_argument("--session", default=None,
                    help="Resume this opencode session id (question relay).")
    ap.add_argument("--dir", dest="dir_", default=None,
                    help="opencode working directory (default: cwd).")
    ap.add_argument("--contract", default=None,
                    help="Delegated-result contract to validate (RM-023).")
    ap.add_argument("--markers", default=None,
                    help="Comma-separated markers (overrides --contract).")
    ap.add_argument("--out", default=None,
                    help="Result file (default: <prompt-file>.result.md).")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"Seconds before the run group is killed (default {DEFAULT_TIMEOUT}).")
    ap.add_argument("--logs-dir", default=None,
                    help="Run-log directory (default: observing-runs repo logs/).")
    a = ap.parse_args(argv)

    try:
        with open(a.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read()
    except OSError as exc:
        print(f"error: cannot read --prompt-file: {exc}", file=sys.stderr)
        return 2
    if not prompt.strip():
        print("error: --prompt-file is empty", file=sys.stderr)
        return 2

    markers = None
    if a.markers:
        markers = [m.strip() for m in a.markers.split(",") if m.strip()]
    elif a.contract:
        if a.contract not in validate_delegated_result.CONTRACTS:
            print(f"error: unknown contract {a.contract!r} (known: "
                  f"{', '.join(sorted(validate_delegated_result.CONTRACTS))})",
                  file=sys.stderr)
            return 2
        markers = validate_delegated_result.CONTRACTS[a.contract]

    model = resolve_agent_model(a.agent, a.model)
    out_path = a.out or (a.prompt_file + ".result.md")

    opencode_argv = ["opencode", "run", "--agent", a.agent, "--format", "json"]
    if a.dir_:
        opencode_argv += ["--dir", a.dir_]
    if a.model:
        opencode_argv += ["--model", a.model]
    if a.session:
        opencode_argv += ["--session", a.session]
    opencode_argv.append(prompt)

    print(f"dispatch: agent={a.agent} model={model or '?'} timeout={a.timeout}s",
          flush=True)
    started = time.monotonic()
    rc_proc, raw, stderr_text, timed_out = run_opencode(opencode_argv, a.timeout)
    duration_ms = int((time.monotonic() - started) * 1000)

    events, parse_errors = parse_stream(raw)
    text = final_text(events)
    tokens_in, tokens_out, cost = token_totals(events)
    session_id = session_id_of(events)

    if timed_out:
        outcome, exit_code = "error", 4
        detail = f"timeout after {a.timeout}s (process group killed)"
    elif rc_proc != 0:
        outcome, exit_code = "error", 3
        tail = " ".join((stderr_text or "").split())[:200]
        detail = f"opencode exited {rc_proc}" + (f": {tail}" if tail else "")
    elif session_id is None:
        outcome, exit_code = "error", 3
        detail = "no session id in event stream (empty/dead stream)"
    elif markers is not None and parse_errors:
        outcome, exit_code = "failure", 1
        detail = f"malformed event stream: {parse_errors[0]}"
    elif markers is not None:
        ok, missing = validate_delegated_result.validate(text, markers)
        if ok:
            outcome, exit_code = "success", 0
            detail = None
        else:
            outcome, exit_code = "failure", 1
            detail = ("empty result" if missing is None
                      else "missing marker(s): " + ", ".join(missing))
    else:
        outcome, exit_code = "success", 0
        detail = None

    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + ("\n" if text else ""))
    except OSError as exc:
        outcome, exit_code = "error", 2
        detail = f"cannot write result: {exc}"

    record = {
        "kind": "agent",
        "agent": a.agent,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "duration_ms": duration_ms,
        "outcome": outcome,
        "detail": detail[:log_run.DETAIL_MAX] if detail else None,
    }
    try:
        log_path = log_run.log_record(record, logs_dir=a.logs_dir)
        print(f"run_log={log_path}", flush=True)
    except ValueError as exc:
        print(f"error: run-log record rejected: {exc}", file=sys.stderr)
        if exit_code == 0:
            exit_code = 2

    print(f"result={out_path}", flush=True)
    if exit_code != 0:
        print(f"{outcome}: {detail}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
