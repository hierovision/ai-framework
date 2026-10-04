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
  * with --stream-out/--stream-err FILE, tees the raw stdout/stderr lines
    live (fresh dispatch truncates, `--session` resume appends);
  * with --heartbeat FILE, writes the dispatcher envelope (header + START
    before launch, exactly one terminal DONE/BLOCKED line) and injects the
    canonical supervision block naming that file;
  * with --allow-dirs PATH (repeatable), grants least-privilege external
    directory permission for this run;
  * writes the final text to --out (default: <prompt-file>.result.md);
  * with --contract / --markers, validates the result via
    scripts/validate_delegated_result.py (RM-023): an empty or malformed
    result exits non-zero, and a permission denial is named instead of
    reported as an uninformative empty result;
  * resolves the attribution model from the finished session row (read-only
    via the watcher's reader), falling back to the declared binding;
  * emits exactly one kind=agent run-log record via the observing-runs schema
    owner (`log_run.py`) with agent, resolved model, tokens/cost from the
    stream, and outcome.

Lane policy, topology bounds, supervision, and the attribution contract:
reference/agent-teams.md, reference/subagent-supervision.md.

Exit codes: 0 success; 1 contract-invalid result; 2 usage/environment error;
3 provider/process/stream error; 4 timeout.

Usage:
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md \
      --contract implement-handoff --model opencode-go/kimi-k3
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md \
      --session ses_...        # resume (question relay)
  python3 scripts/dispatch_agent.py --agent architect --prompt-file p.md \
      --stream-out run.events.jsonl --stream-err run.stderr.log \
      --heartbeat run.progress.log --allow-dirs ../sibling-repo
"""
import argparse
import datetime
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
# The watcher owns the read-only session-store access (OPENCODE_DB_PATH-aware)
# and the `session.model` blob reader — imported, never redefined.
watch_agent = _load_module(
    os.path.join(SCRIPT_DIR, "watch_agent.py"), "watch_agent")

DEFAULT_TIMEOUT = 600
HEARTBEAT_PROTOCOL_REF = "reference/subagent-supervision.md"
PERMISSION_DENY_RE = re.compile(
    r"external_directory|auto-reject|permission denied", re.IGNORECASE)
# ANSI escapes kept out of the record detail: CSI (SGR and non-SGR), OSC
# terminated by BEL or ST, and two-character escapes.
ANSI_RE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


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


def resolve_session_model(session_id):
    """The model the finished run actually used, from the session row.

    Read-only through the watcher's reader (AC10). Any absence — no DB,
    missing row, unreadable blob — degrades to None so the caller falls back
    to the declared binding (AC11). Does not replicate opencode's
    agent-resolution precedence; the session row is ground truth.
    """
    if not session_id:
        return None
    try:
        con = watch_agent.db()
    except Exception:
        return None
    if con is None:
        return None
    try:
        sess = watch_agent.find_session(con, sid=session_id)
        return watch_agent.session_model(sess) if sess is not None else None
    except Exception:
        return None
    finally:
        try:
            con.close()
        except Exception:
            pass


# --- live visibility (stream tees + heartbeat) ------------------------------

def _open_artifact(path, append):
    """Open a stream/heartbeat target, creating parent dirs (AC6).

    Raises OSError with the path named — the caller exits 2 before opencode
    launches, so no session is created.
    """
    parent = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as exc:
        raise OSError(f"{path}: cannot create parent directory: {exc}") from exc
    try:
        return open(path, "a" if append else "w", encoding="utf-8")
    except OSError as exc:
        raise OSError(f"{path}: cannot open: {exc}") from exc


def heartbeat_begin(handle, task, detail, fresh):
    """Write the dispatcher envelope header + START before launch (AC4)."""
    if fresh:
        handle.write(f"# progress: {task}\n")
    handle.write(f"{now_iso()} START {detail}\n")
    handle.flush()


def heartbeat_terminal(handle, outcome, detail):
    """Append exactly one terminal line: DONE ok on success, else BLOCKED."""
    if outcome == "success":
        handle.write(f"{now_iso()} DONE ok\n")
    else:
        handle.write(f"{now_iso()} BLOCKED {detail or outcome}\n")
    handle.flush()


def heartbeat_prompt_block(path):
    """The canonical injected block: names the file, cites the protocol (AC5).

    The dispatcher never restates the STEP/CALL/POLL protocol; it points at
    reference/subagent-supervision.md §2 and the two mechanical rules.
    """
    return (
        "\n---\n"
        f"Supervision protocol ({HEARTBEAT_PROTOCOL_REF} §2): append "
        "one timestamped progress line per event to the absolute path\n"
        f"{os.path.abspath(path)}\n"
        "as you work — `STEP` when a step changes, `CALL begin`/`CALL end` "
        "around any command expected to run >30 s, `POLL` when polling "
        "detached work. No single blocking call over 180 s: detach long work "
        "with a log file and poll it. Never end silent.\n"
    )


def permission_denial(events, stderr_text):
    """Name a permission rejection instead of reporting `empty result` (AC13).

    Looks for a tool part with `state.status=error` carrying the
    external-directory rejection text, else the same text in captured stderr.
    """
    for part in _parts(events):
        if part.get("type") != "tool":
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        if state.get("status") != "error":
            continue
        if not PERMISSION_DENY_RE.search(json.dumps(state)):
            continue
        name = part.get("tool") or "?"
        inp = state.get("input") if isinstance(state.get("input"), dict) else {}
        target = (inp.get("command") or inp.get("filePath") or inp.get("path")
                  or inp.get("pattern") or "")
        target = str(target).splitlines()[0].strip()[:120] if target else ""
        return f"permission denied: {name}" + (f" {target}" if target else "")
    cleaned = ANSI_RE.sub("", stderr_text or "")
    if PERMISSION_DENY_RE.search(cleaned):
        m = re.search(r"external_directory\s*\(([^)]+)\)", cleaned, re.IGNORECASE)
        if m:
            return f"permission denied: external_directory {m.group(1).strip()}"
        line = next((l.strip() for l in cleaned.splitlines()
                     if PERMISSION_DENY_RE.search(l)), "")
        return "permission denied: " + (line[:200] or "external_directory")
    return None


# --- external-path grants (AC12) --------------------------------------------

def permission_config(dirs, existing_raw):
    """Merge `<abs-dir>/**` -> allow into OPENCODE_CONFIG_CONTENT.

    Caller-supplied settings win on conflict (existing keys are left intact).
    An unparsable `existing_raw` is discarded with a named stderr warning and
    the merge proceeds — a recoverable env issue must not hard-fail the
    dispatch, but the caller-settings loss is never silent.
    """
    config = {}
    if existing_raw:
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, dict):
                config = parsed
        except ValueError as exc:
            print(f"warning: ignoring unparsable OPENCODE_CONFIG_CONTENT: {exc}",
                  file=sys.stderr)
    perm = config.get("permission")
    if not isinstance(perm, dict):
        perm = {}
        config["permission"] = perm
    ext = perm.get("external_directory")
    if not isinstance(ext, dict):
        ext = {}
        perm["external_directory"] = ext
    for d in dirs:
        ext.setdefault(os.path.join(os.path.abspath(d), "**"), "allow")
    return config


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


def run_opencode(argv, timeout, tee_out=None, tee_err=None, env=None):
    """Run in its own process group; kill the group at timeout.

    Returns (returncode, stdout, stderr, timed_out). The session id is
    printed as soon as the stream names it (question relay). `tee_out` /
    `tee_err` are optional writable file handles; each line is written and
    flushed as it is read (AC1/AC2), while the in-memory accumulation stays
    unchanged so contract validation is untouched.
    """
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True, env=env)
    except OSError as exc:
        return 127, "", f"cannot launch opencode: {exc}", False

    out_lines, err_lines = [], []
    printed = {"sid": None}

    def reader(pipe, sink, is_stdout, tee):
        try:
            for line in iter(pipe.readline, ""):
                sink.append(line)
                if tee is not None:
                    tee.write(line)
                    tee.flush()
                if is_stdout:
                    _maybe_print_session(line, printed)
        finally:
            pipe.close()

    threads = [
        threading.Thread(target=reader, args=(proc.stdout, out_lines, True, tee_out),
                         daemon=True),
        threading.Thread(target=reader, args=(proc.stderr, err_lines, False, tee_err),
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
    ap.add_argument("--stream-out", dest="stream_out", default=None, metavar="FILE",
                    help="Tee the stdout JSON event stream live (fresh truncates, "
                         "--session resume appends).")
    ap.add_argument("--stream-err", dest="stream_err", default=None, metavar="FILE",
                    help="Tee stderr live (fresh truncates, --session resume appends).")
    ap.add_argument("--heartbeat", default=None, metavar="FILE",
                    help="Dispatcher envelope + injected supervision block for FILE.")
    ap.add_argument("--allow-dirs", dest="allow_dirs", action="append", default=None,
                    metavar="PATH",
                    help="Grant opencode external-directory access to PATH for this "
                         "run (repeatable, least privilege).")
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

    binding = resolve_agent_model(a.agent, a.model)
    out_path = a.out or (a.prompt_file + ".result.md")
    append = bool(a.session)

    # Preflight: validate grants and open every target before opencode runs
    # (AC6) — an unopenable target exits 2 with no session created.
    for d in (a.allow_dirs or []):
        if not os.path.isdir(d):
            print(f"error: --allow-dirs requires an existing directory: {d}",
                  file=sys.stderr)
            return 2
    tee_out = tee_err = hb = None
    try:
        if a.stream_out:
            tee_out = _open_artifact(a.stream_out, append)
        if a.stream_err:
            tee_err = _open_artifact(a.stream_err, append)
        if a.heartbeat:
            hb = _open_artifact(a.heartbeat, append)
    except OSError as exc:
        for handle in (tee_out, tee_err, hb):
            if handle is not None:
                handle.close()
        print(f"error: cannot open dispatch artifact: {exc}", file=sys.stderr)
        return 2

    child_env = None
    if a.allow_dirs:
        child_env = dict(os.environ)
        child_env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            permission_config(a.allow_dirs,
                              os.environ.get("OPENCODE_CONFIG_CONTENT")))

    if hb is not None:
        heartbeat_begin(hb, f"{a.agent} dispatch", a.prompt_file,
                        fresh=not append)
        if not append:
            # only a fresh run injects the supervision block; a `--session`
            # resume would otherwise accumulate `---` blocks each time (M4)
            prompt = prompt.rstrip() + "\n" + heartbeat_prompt_block(a.heartbeat)

    opencode_argv = ["opencode", "run", "--agent", a.agent, "--format", "json"]
    if a.dir_:
        opencode_argv += ["--dir", a.dir_]
    if a.model:
        opencode_argv += ["--model", a.model]
    if a.session:
        opencode_argv += ["--session", a.session]
    opencode_argv.append(prompt)

    print(f"dispatch: agent={a.agent} binding={binding or '?'} "
          f"timeout={a.timeout}s", flush=True)
    started = time.monotonic()
    rc_proc, raw, stderr_text, timed_out = run_opencode(
        opencode_argv, a.timeout, tee_out=tee_out, tee_err=tee_err, env=child_env)
    duration_ms = int((time.monotonic() - started) * 1000)
    for handle in (tee_out, tee_err):
        if handle is not None:
            handle.close()

    events, parse_errors = parse_stream(raw)
    text = final_text(events)
    tokens_in, tokens_out, cost = token_totals(events)
    session_id = session_id_of(events)
    model = resolve_session_model(session_id) or binding
    print(f"model={model or '?'}", flush=True)

    # Guard the outcome computation and result write so an unexpected
    # exception still writes exactly one heartbeat terminal line and closes
    # the handle (M1, "never end silent"), without masking the outcome.
    outcome, exit_code, detail = "error", 3, "dispatch did not complete"
    try:
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
                denied = permission_denial(events, stderr_text)
                outcome, exit_code = "failure", 1
                if denied:
                    detail = denied
                elif missing is None:
                    detail = "empty result"
                else:
                    detail = "missing marker(s): " + ", ".join(missing)
        else:
            outcome, exit_code = "success", 0
            detail = None

        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text + ("\n" if text else ""))
        except OSError as exc:
            outcome, exit_code = "error", 2
            detail = f"cannot write result: {exc}"
    except Exception as exc:  # noqa: BLE001 - never end silent
        outcome, exit_code = "error", 3
        # bound the detail at the outcome-branch convention (200) so a
        # pathological exception message cannot flood the tail-read heartbeat
        detail = f"unexpected dispatch error: {exc}"[:200]
    finally:
        if hb is not None:
            try:
                heartbeat_terminal(hb, outcome, detail)
            finally:
                hb.close()

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
    except Exception as exc:  # noqa: BLE001 - must not mask the dispatch outcome
        print(f"error: run-log record failed: {exc}", file=sys.stderr)

    print(f"result={out_path}", flush=True)
    if exit_code != 0:
        print(f"{outcome}: {detail}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
