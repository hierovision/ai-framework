#!/usr/bin/env python3
"""Run-vehicle dispatcher: one top-level `opencode run --agent` session.

Why (plan agent-teams-dispatch): the free tier rejects a model call made from
a nested Task subagent, and the core personas are free-bound. `opencode run
--agent <name>` is a top-level session (free allowed), carries the agent's
config, supports per-call lane choice and `--session` resume, and its JSON
event stream yields session/model attribution.

What it does:
  * reads the prompt from --prompt-file;
  * runs `opencode run --agent <name> --model <id> [--session <id>]
    [--standalone|--server URL] --format json <prompt>` in its own process
    group, with `cwd`/`PWD` set to the dispatch directory (V2 has no `--dir`);
  * prints `session_id=<id>` as soon as the stream names it (question relay);
  * with --stream-out/--stream-err FILE, tees the raw stdout/stderr lines
    live (fresh dispatch truncates, `--session` resume appends);
  * with --heartbeat FILE, writes the dispatcher envelope (header + START
    before launch, exactly one terminal DONE/BLOCKED line) and injects the
    canonical supervision block naming that file;
  * with --allow-dirs PATH (repeatable), grants least-privilege external
    directory permission for this run through an ordered V2 rule set written
    to a temporary XDG_CONFIG_HOME (V2 ignores OPENCODE_CONFIG_CONTENT);
  * with --profile NAME|auto|none (default auto), merges the per-agent-class
    least-privilege defaults from scripts/dispatch-profiles.json on top of
    --allow-dirs (D4);
  * with --worktree NAME, runs the child in its own git worktree at
    .scratch/worktrees/NAME on branch dispatch/NAME so the parent tree can
    never leave main (D3);
  * with --wake-to SESSION-ID (requires --heartbeat), spawns the detached
    completion-observer (scripts/observe_completion.py) once the child's
    session id is printed, forwards the attach target to it (--wake-url,
    resolved from env OPENCODE_WAKE_URL when omitted, and --wake-agent,
    required with --wake-to), so the orchestrator is woken on terminal state
    through its own server (D2);
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
  python3 scripts/dispatch_agent.py --agent implementer --prompt-file p.md \
      --heartbeat run.progress.log --worktree feat-x \
      --wake-to ses_orchestrator
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
import tempfile
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import opencode_v2 as v2  # noqa: E402 - shared V2 adapter
import heartbeat_io  # noqa: E402 - atomic newline-delimited heartbeat appends
import scratch_cleanup  # noqa: E402 - bounded per-run scratch cleanup


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
PROFILES_PATH = os.path.join(SCRIPT_DIR, "dispatch-profiles.json")
OBSERVER_DEADLINE = 300
PERMISSION_DENY_RE = re.compile(
    r"external_directory|auto-reject|permission denied", re.IGNORECASE)
# ANSI escapes kept out of the record detail: CSI (SGR and non-SGR), OSC
# terminated by BEL or ST, and two-character escapes.
ANSI_RE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


# --- stream parsing (pure; the adapter owns V2 shapes) ----------------------

def parse_stream(raw):
    return v2.parse_stream(raw)


def _parts(events):
    for ev in events:
        part = ev.get("part") if isinstance(ev.get("part"), dict) else ev
        if isinstance(part, dict):
            yield part


def session_id_of(events):
    return v2.session_id_of(events)


def final_text(events):
    return v2.final_text(events)


def token_totals(events):
    return v2.token_totals(events)


def resolve_agent_model(agent, explicit=None):
    """Explicit --model wins; else the target's V2 discovery binding.

    V2 discovery order: project `.opencode/agents/<name>.md`, repo
    `agents/<name>.md`, then the global layout. A missing binding is a
    usage error (exit 2) — a dispatch never runs on an unintended model.
    """
    if explicit:
        return explicit
    candidates = [
        os.path.join(os.getcwd(), ".opencode", "agents", agent + ".md"),
        os.path.join(REPO_ROOT, "agents", agent + ".md"),
        os.path.expanduser(f"~/.config/opencode/agents/{agent}.md"),
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            continue
        fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
        m = re.search(r"^model:\s*(\S+)\s*$", fm, re.MULTILINE)
        if m:
            return m.group(1)
    return None


def resolve_session_model(session_id):
    """The model the finished run actually used, from the V2 session row.

    Read-only through the adapter; any absence degrades to None so the caller
    falls back to the declared binding.
    """
    if not session_id:
        return None
    try:
        con = v2.connect()
    except Exception:
        return None
    if con is None:
        return None
    try:
        sess = v2.find_session(con, sid=session_id)
        return v2.session_model(sess) if sess is not None else None
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


def heartbeat_begin(path, task, detail, fresh):
    """Write the dispatcher envelope header + START before launch (AC4).

    One O_APPEND write, never a held writer: the observer appends `SURVEY
    running` while the run is live and its bytes must survive the terminal
    line (F11).
    """
    text = (f"# progress: {task}\n" if fresh else "")
    text += f"{now_iso()} START {detail}\n"
    heartbeat_io.append_records(path, text, fresh=fresh)


def heartbeat_terminal(path, outcome, detail):
    """Append exactly one terminal line: DONE ok on success, else BLOCKED."""
    if outcome == "success":
        text = f"{now_iso()} DONE ok\n"
    else:
        text = f"{now_iso()} BLOCKED {detail or outcome}\n"
    heartbeat_io.append_records(path, text)


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
    """Name a V2 permission auto-reject instead of reporting `empty result`."""
    return v2.classify_denial(events, stderr_text)


# --- external-path grants (AC12) --------------------------------------------

def permission_config(dirs, existing_raw=None):
    """Build the V2 config document carrying deny-first ordered rules.

    The adapter owns the rule order (catch-all deny first, explicit allow
    roots after, execute deny last). Caller `OPENCODE_CONFIG_CONTENT` is kept
    for observability but V2 does not honor it for grant injection.
    """
    return v2.config_with_permissions({}, dirs)


def validate_grants(dirs):
    for d in dirs or []:
        if not os.path.isdir(d):
            return f"--allow-dirs requires an existing directory: {d}"
    return None


# --- per-agent-class profiles (D4) ------------------------------------------

def load_profiles(path=PROFILES_PATH):
    """Return (profiles, aliases). Missing/malformed file degrades to empty."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    aliases = data.get("aliases") if isinstance(data.get("aliases"), dict) else {}
    profiles = {k: v for k, v in data.items()
                if k != "aliases" and isinstance(v, dict)}
    return profiles, aliases


def resolve_profile_name(agent, profiles, aliases):
    """Exact agent key wins, then an alias, then longest-prefix profile name."""
    if agent in profiles:
        return agent
    if agent in aliases and aliases[agent] in profiles:
        return aliases[agent]
    best = None
    for name in profiles:
        if name == "default":
            continue
        if agent == name or agent.startswith(name + "-"):
            if best is None or len(name) > len(best):
                best = name
    return best or "default"


def resolve_profile(agent, profile_flag, profiles, aliases):
    """Return (name, settings) or (None, None) for an unknown named profile.

    `auto` resolves by agent class; `none` disables defaults ({} settings);
    any other value must name a profile.
    """
    if profile_flag == "none":
        return "none", {"allow_dirs": [], "worktree": False, "timeout": None}
    if profile_flag == "auto":
        name = resolve_profile_name(agent, profiles, aliases)
    else:
        if profile_flag not in profiles:
            return None, None
        name = profile_flag
    merged = dict(profiles.get("default", {}))
    merged.update(profiles.get(name, {}))
    return name, merged


def expand_dirs(dirs):
    """Expand `$HOME` / `~` / env vars in profile grant paths."""
    return [os.path.expanduser(os.path.expandvars(d)) for d in (dirs or [])]


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:40] or "dispatch"


def default_worktree_name(prompt_file, heartbeat_path):
    """Derive a worktree name when a profile sets `worktree: true` and no
    explicit `--worktree <name>` was given: the heartbeat task, else the
    prompt-file basename."""
    task = None
    if heartbeat_path and os.path.isfile(heartbeat_path):
        try:
            with open(heartbeat_path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("# progress:"):
                        task = line.split(":", 1)[1].strip()
                        break
        except OSError:
            task = None
    if task:
        return _slug(task)
    return _slug(os.path.splitext(os.path.basename(prompt_file or ""))[0])


# --- worktree-safe dispatch (D3) --------------------------------------------

def worktree_setup(repo, name, resume):
    """Return (path, branch, error). A fresh dispatch requires the parent
    checkout on `main`; a resume requires the worktree to already exist."""
    branch = f"dispatch/{name}"
    path = os.path.join(repo, ".scratch", "worktrees", name)
    if resume:
        if not os.path.isdir(path):
            return None, branch, f"worktree not found for --session resume: {path}"
        return path, branch, None
    head = subprocess.run(["git", "-C", repo, "symbolic-ref", "--short", "HEAD"],
                          capture_output=True, text=True)
    current = head.stdout.strip()
    if head.returncode != 0 or current != "main":
        return None, branch, (f"parent repo is not on main (HEAD="
                              f"{current or 'detached'})")
    if not os.path.isdir(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError as exc:
            return None, branch, f"cannot create worktree parent dir: {exc}"
        add = subprocess.run(
            ["git", "-C", repo, "worktree", "add", "-b", branch, path],
            capture_output=True, text=True)
        if add.returncode != 0:
            tail = " ".join((add.stderr or "").split())[:200]
            return None, branch, f"git worktree add failed: {tail}"
    return path, branch, None


def spawn_observer(a, child_sid, dispatch_dir, out_path, logs_dir, worktree,
                   branch, wake_url=None, wake_agent=None):
    """Spawn the detached completion-observer (D2). Returns the Popen or None.

    `OBSERVE_COMPLETION_PATH` overrides the script path (hermetic test seam).
    The attach target (--wake-url/--wake-agent) is forwarded so the observer
    can deliver through the orchestrator's own server; when no URL resolves the
    observer still supervises and defers with `reason=no-attach-target`.
    """
    observer = (os.environ.get("OBSERVE_COMPLETION_PATH")
                or os.path.join(SCRIPT_DIR, "observe_completion.py"))
    argv = [sys.executable, observer,
            "--heartbeat", a.heartbeat, "--agent", a.agent,
            "--orchestrator-session", a.wake_to,
            "--dir", dispatch_dir or os.getcwd(),
            "--deadline", str(OBSERVER_DEADLINE),
            "--child-session", child_sid or "",
            "--result", out_path]
    if logs_dir:
        argv += ["--logs-dir", logs_dir]
    if worktree:
        argv += ["--worktree", worktree]
    if branch:
        argv += ["--branch", branch]
    if wake_url:
        argv += ["--wake-url", wake_url]
    if wake_agent:
        argv += ["--wake-agent", wake_agent]
    try:
        logf = open(a.heartbeat + ".observer.log", "a", encoding="utf-8")
    except OSError:
        logf = subprocess.DEVNULL
    try:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=logf,
                                stderr=subprocess.STDOUT, start_new_session=True,
                                close_fds=True)
    except OSError as exc:
        print(f"warning: cannot spawn completion-observer: {exc}", file=sys.stderr)
        return None


# --- process execution -------------------------------------------------------

def _maybe_print_session(line, printed, on_session=None):
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
        if on_session is not None:
            try:
                on_session(sid)
            except Exception as exc:  # noqa: BLE001 - never break the stream tee
                print(f"warning: on_session callback failed: {exc}",
                      file=sys.stderr)


def run_opencode(argv, timeout, tee_out=None, tee_err=None, env=None,
                 on_session=None, cwd=None):
    """Run in its own process group; kill the group at timeout.

    Returns (returncode, stdout, stderr, timed_out). The session id is
    printed as soon as the stream names it (question relay); `on_session`, when
    given, is called once with that id (the dispatcher spawns the
    completion-observer from it). `tee_out` / `tee_err` are optional writable
    file handles; each line is written and flushed as it is read (AC1/AC2),
    while the in-memory accumulation stays unchanged so contract validation is
    untouched.
    """
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True, env=env, cwd=cwd)
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
                    _maybe_print_session(line, printed, on_session)
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
                    help="Dispatch working directory (V2: passed as cwd/PWD, "
                         "never as a CLI flag).")
    ap.add_argument("--standalone", action="store_true",
                    help="Run V2 with a private server (no shared service).")
    ap.add_argument("--server", default=None, metavar="URL",
                    help="Connect to this V2 server URL instead of the service.")
    ap.add_argument("--contract", default=None,
                    help="Delegated-result contract to validate (RM-023).")
    ap.add_argument("--markers", default=None,
                    help="Comma-separated markers (overrides --contract).")
    ap.add_argument("--out", default=None,
                    help="Result file (default: <prompt-file>.result.md).")
    ap.add_argument("--timeout", type=int, default=None,
                    help=f"Seconds before the run group is killed (default "
                         f"{DEFAULT_TIMEOUT}, or the profile's timeout).")
    ap.add_argument("--logs-dir", default=None,
                    help="Run-log directory (default: observing-runs repo logs/).")
    ap.add_argument("--profile", default="auto", metavar="NAME|auto|none",
                    help="Permission/worktree profile from "
                         "scripts/dispatch-profiles.json (default: auto by "
                         "agent class; none disables defaults).")
    ap.add_argument("--worktree", default=None, metavar="NAME",
                    help="Run in git worktree .scratch/worktrees/NAME on "
                         "branch dispatch/NAME (parent must be on main).")
    ap.add_argument("--wake-to", dest="wake_to", default=None,
                    metavar="SESSION-ID",
                    help="Spawn the completion-observer for this orchestrator "
                         "session (requires --heartbeat and --wake-agent).")
    ap.add_argument("--wake-url", dest="wake_url", default=None, metavar="URL",
                    help="Attach URL of the orchestrator's server for the wake "
                         "(default: env OPENCODE_WAKE_URL). No URL resolves -> "
                         "the observer defers with reason=no-attach-target.")
    ap.add_argument("--wake-agent", dest="wake_agent", default=None, metavar="NAME",
                    help="Agent the orchestrator session runs as (required with "
                         "--wake-to: opencode does not inherit the session's agent).")
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
    if not binding:
        print(f"error: no model binding for {a.agent}", file=sys.stderr)
        return 2
    out_path = a.out or (a.prompt_file + ".result.md")
    append = bool(a.session)

    # Per-agent-class profile (D4): least-privilege grants + worktree default.
    profiles, aliases = load_profiles()
    profile_name, profile = resolve_profile(a.agent, a.profile, profiles, aliases)
    if profile_name is None:
        print(f"error: unknown --profile {a.profile!r} (known: auto, none, "
              f"{', '.join(sorted(profiles))})", file=sys.stderr)
        return 2
    profile_dirs = expand_dirs(profile.get("allow_dirs"))
    timeout = a.timeout if a.timeout is not None else (
        profile.get("timeout") or DEFAULT_TIMEOUT)

    # Worktree (D3): an explicit --worktree wins; else the profile default.
    worktree_name = a.worktree
    if worktree_name is None and profile.get("worktree"):
        worktree_name = default_worktree_name(a.prompt_file, a.heartbeat)

    if a.wake_to and not a.heartbeat:
        print("error: --wake-to requires --heartbeat", file=sys.stderr)
        return 2
    if a.wake_to and not a.wake_agent:
        print("error: --wake-to requires --wake-agent (opencode does not "
              "inherit the session's agent)", file=sys.stderr)
        return 2

    # The attach URL travels with the dispatch contract; the worker context
    # inherits OPENCODE_WAKE_URL from the TUI launch (no state file exists).
    wake_url = a.wake_url or os.environ.get("OPENCODE_WAKE_URL") or None

    # Preflight: a `--session` resume must name a real session; an unknown
    # id exits 2 with no opencode launch (never creates a ghost session).
    if a.session:
        exists, _payload = v2.session_get(a.session, server=a.server)
        if exists is None:
            con = v2.connect()
            try:
                exists = v2.find_session(con, sid=a.session) is not None
            finally:
                if con is not None:
                    con.close()
        if not exists:
            print(f"error: unknown session {a.session}", file=sys.stderr)
            return 2

    # Preflight: validate explicit grants and open every target before opencode
    # runs (AC6) — an unopenable target exits 2 with no session created.
    # Profile dirs are defaults, applied without an existence check.
    grant_error = validate_grants(a.allow_dirs or [])
    if grant_error:
        print(f"error: {grant_error}", file=sys.stderr)
        return 2
    tee_out = tee_err = None
    hb_path = a.heartbeat
    try:
        if a.stream_out:
            tee_out = _open_artifact(a.stream_out, append)
        if a.stream_err:
            tee_err = _open_artifact(a.stream_err, append)
        if hb_path:
            heartbeat_io.check_writable(hb_path)
    except OSError as exc:
        for handle in (tee_out, tee_err):
            if handle is not None:
                handle.close()
        print(f"error: cannot open dispatch artifact: {exc}", file=sys.stderr)
        return 2

    # Worktree setup between preflight and launch (D3): the parent checkout
    # must be on main for a fresh dispatch; a resume reuses the worktree.
    dispatch_dir = a.dir_
    worktree_path = branch = None
    if worktree_name:
        worktree_path, branch, wt_err = worktree_setup(
            os.getcwd(), worktree_name, resume=append)
        if wt_err:
            for handle in (tee_out, tee_err):
                if handle is not None:
                    handle.close()
            print(f"error: --worktree: {wt_err}", file=sys.stderr)
            return 2
        dispatch_dir = worktree_path

    # Profile grants + explicit --allow-dirs union (D4). V2 ignores
    # OPENCODE_CONFIG_CONTENT for grants; a generated XDG_CONFIG_HOME root
    # carries the deny-first rules and links the agent corpus.
    grant_dirs = profile_dirs + list(a.allow_dirs or [])
    child_env = dict(os.environ)
    dispatch_root = os.environ.get(
        "DISPATCH_CONFIG_ROOT",
        os.path.join(REPO_ROOT, ".scratch", "dispatch-config"))
    os.makedirs(dispatch_root, exist_ok=True)
    # F12: per-run config trees are diagnostic evidence on failure, but the
    # directory cannot grow without bound. Keep the newest few and drop stale
    # ones before adding this run.
    # Reserve one slot for the run about to start, so the post-create count
    # never exceeds DEFAULT_KEEP.
    scratch_cleanup.prune_run_configs(
        dispatch_root, keep=max(0, scratch_cleanup.DEFAULT_KEEP - 1),
        max_age_seconds=scratch_cleanup.DEFAULT_MAX_AGE)
    config_root = tempfile.mkdtemp(prefix="run-", dir=dispatch_root)
    agents_src = os.path.join(REPO_ROOT, ".opencode", "agents")
    if not os.path.isdir(agents_src):
        agents_src = os.path.join(REPO_ROOT, "agents")
    v2.write_temp_config(
        config_root,
        permission_config(grant_dirs, os.environ.get("OPENCODE_CONFIG_CONTENT")),
        agents_dir=agents_src,
        skills_dir=os.path.join(REPO_ROOT, "skills"))
    child_env["XDG_CONFIG_HOME"] = config_root
    child_env["PWD"] = dispatch_dir or os.getcwd()

    if hb_path:
        heartbeat_begin(hb_path, f"{a.agent} dispatch", a.prompt_file,
                        fresh=not append)
        if not append:
            # only a fresh run injects the supervision block; a `--session`
            # resume would otherwise accumulate `---` blocks each time (M4)
            prompt = prompt.rstrip() + "\n" + heartbeat_prompt_block(a.heartbeat)

    # V2 2.1.4 accepts --standalone/--server only on the `run` subcommand
    # (live 2026-10-28: `opencode --standalone run` exits 1 "Unrecognized
    # flag"; the consumer runner is the same shape).
    opencode_argv = ["opencode", "run"]
    if a.server:
        opencode_argv += ["--server", a.server]
    elif a.standalone or grant_dirs:
        opencode_argv += ["--standalone"]
    opencode_argv += ["--agent", a.agent, "--format", "json",
                      "--model", binding]
    if a.session:
        opencode_argv += ["--session", a.session]
    opencode_argv.append(prompt)

    print(f"dispatch: agent={a.agent} binding={binding or '?'} "
          f"timeout={timeout}s profile={profile_name} "
          f"allow_dirs={len(grant_dirs)}", flush=True)
    if worktree_path:
        print(f"worktree={worktree_path} branch={branch}", flush=True)

    def on_session(sid):
        # spawn the completion-observer once the child session id is known (D2)
        if a.wake_to:
            spawn_observer(a, sid, dispatch_dir, out_path,
                           a.logs_dir or log_run.DEFAULT_LOGS_DIR,
                           worktree_path, branch,
                           wake_url=wake_url, wake_agent=a.wake_agent)

    started = time.monotonic()
    rc_proc, raw, stderr_text, timed_out = run_opencode(
        opencode_argv, timeout, tee_out=tee_out, tee_err=tee_err,
        env=child_env, on_session=on_session,
        cwd=dispatch_dir or os.getcwd())
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
            # AC15: a private server (--standalone, or the implicit
            # standalone used for grants) is killed with its process group;
            # a shared/--server session must be interrupted AND verified
            # inactive. `--server` + `--allow-dirs` is still shared-service.
            private_server = a.standalone or (grant_dirs and not a.server)
            if private_server:
                interrupt = "not-needed"
            elif not session_id:
                interrupt = "no-session"
            else:
                status, _ = v2.session_interrupt(session_id, server=a.server)
                if status not in (200, 202, 204):
                    interrupt = "failed"
                else:
                    active = v2.session_active(server=a.server)
                    interrupt = ("ok" if active is not None
                                 and session_id not in active else "failed")
            detail = (f"timeout after {timeout}s "
                      f"(process group killed, interrupt={interrupt})")
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
            # A permission auto-reject means the task could not run, even
            # when the model narrates the denial and returns a non-empty
            # answer (D2 negative drill, 2026-10-28).
            denied = permission_denial(events, stderr_text)
            if denied:
                outcome, exit_code = "failure", 1
                detail = denied
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
        if hb_path:
            heartbeat_terminal(hb_path, outcome, detail)

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

    # F12: a successful run leaves no generated config behind. A failed run
    # keeps it as diagnostic evidence; the next dispatch's bounded prune caps
    # how many of those survive. Tests set DISPATCH_KEEP_CONFIG=1 to inspect
    # the generated rules after the process exits.
    if os.environ.get("DISPATCH_KEEP_CONFIG") != "1":
        scratch_cleanup.cleanup_run_config(config_root, outcome)
    print(f"result={out_path}", flush=True)
    if exit_code != 0:
        print(f"{outcome}: {detail}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
