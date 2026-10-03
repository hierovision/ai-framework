#!/usr/bin/env python3
"""Run the behavioral (fresh-agent) eval suite and gate on regressions.

For every skill's `evals/evals.json`, launch a fresh agent session with the
skill installed, capture its `opencode run --format json` event stream, and
assert its typed `expect` block (RM-003 pass 5). Any miss fails the build and
writes an `eval_pass=false` run-log record via RM-001's `log_run.py` (single
source of truth — the schema is NOT redefined here).

Typed assertion protocol (RM-003 pass 5 / AC16–AC21): an eval may carry an
`expect` block with up to three closed classes —
`action` (tool-event predicates over the event stream), `artifact` (a written
file + key phrases in its content), `text` (a key phrase in the final
response). `expect` wins when present; an eval without it falls back to the
legacy `expected_behavior` substring path (text-class, flagged legacy). The
stream is newline-delimited JSON: a text event carries
`part.type='text'`/`.text`; a tool event carries `part.type='tool'`/`.tool`
with `state.input` args. A stream parse failure fails closed (never a silent
pass). See `../references/eval-assertions.md` for the full schema.

Offline gate: the assertion logic + listing/subset logic are pure and
testable without a model (see test_runner.py, which injects a stub agent).
The real agent invocation (`invoke_opencode`) is only used in CI, where the
model-access credential (a repository secret) is present.

Free-tier adherence (GitHub Free, private repo): the companion workflow runs
WEEKLY (not nightly) and supports `--limit` / `--skill` subset sharding so a
full run stays within the 2,000 min/month cap.

Deferral: evals flagged `deferred: true` (real-browser / harness-unavailable)
are excluded from the default run. `default_model_tier` (top-level) selects the
tier; both are additive, backward-compatible extensions to the eval protocol.

Two-tier marker selection (RM-003 pass 4): `--default` runs each selected
skill's `"default": true` canary (fallback: first eval in file order);
`--core` runs the `"core": true` evals (the six core skills). The selected
paths ignore `--limit` (sharding only). See AC6 / AC12.
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import signal
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))  # skills/authoring-skills/scripts
SKILLS_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OBSERVE_SCRIPTS = os.path.join(SKILLS_ROOT, "observing-runs", "scripts")
if OBSERVE_SCRIPTS not in sys.path:
    sys.path.insert(0, OBSERVE_SCRIPTS)
import log_run  # RM-001 single source of truth (AC2)

# Repo-root scripts/ (quarantine.py lives there per the plan's Files to Create).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import quarantine  # RM-003 AC9 single source of truth for quarantine state

DETAIL_MAX = log_run.DETAIL_MAX

# RM-003 AC9: one retry per eval on a *transient* failure, with backoff.
RETRY_BACKOFF_SECONDS = (2, 5)
# Fresh-session retry backoff (2026-09-28, RM-021): the dominant dead-session
# class is model-catalog resolution failing right after a fresh runner starts;
# immediate retries all re-hit the unloaded catalog (three attempts spanned 4s
# in CI, each dying in ~2s). A short then longer wait lets resolution settle.
FRESH_RETRY_BACKOFF_SECONDS = (5, 15)
# The resolved cause the opencode server logs for that class. The event stream
# carries only the wrapper (`UnknownError: Unexpected server error`); the real
# error is `ProviderModelNotFoundError: Model not found: <id>`.
MODEL_RESOLUTION_RE = re.compile(r"Model not found|ProviderModelNotFound", re.I)
TRANSIENT_RE = re.compile(
    r"timeout|timed out|rate.?limit|too many requests|\b429\b|\b50[23]\b|"
    r"unavailable|connection (refused|reset|error)|econnreset|fetch failed",
    re.IGNORECASE,
)


def load_skill_evals(skills_root):
    """Yield normalized eval entries from every skill's evals/evals.json."""
    out = []
    if not os.path.isdir(skills_root):
        return out
    for name in sorted(os.listdir(skills_root)):
        ev_path = os.path.join(skills_root, name, "evals", "evals.json")
        if not os.path.isfile(ev_path):
            continue
        try:
            data = json.load(open(ev_path, encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        tier = data.get("default_model_tier", "free")
        for e in data.get("evals", []):
            out.append({
                "skill": name,
                "eval_id": e.get("id"),
                "prompt": e.get("prompt", ""),
                "expected_behavior": e.get("expected_behavior", []),
                # RM-003 pass 5 typed assertions (AC16/AC21): a closed
                # action/artifact/text block; wins over expected_behavior.
                "expect": e.get("expect"),
                "deferred": bool(e.get("deferred", False)),
                "model_tier": e.get("default_model_tier", tier),
                "files": e.get("files", []),
                # RM-003 pass 4 two-tier markers (AC12): `default` = the
                # skill's per-change canary; `core` = a harness-change canary.
                "default": bool(e.get("default", False)),
                "core": bool(e.get("core", False)),
            })
    return out


def eval_key(e):
    """Stable quarantine key for one eval."""
    return f"{e['skill']}#{e['eval_id']}"


def filter_evals(evals, include_deferred=False, limit=None, skill=None,
                 ci_mode=False, quarantined=None, include_quarantine=False,
                 default_only=False, core_only=False):
    """Select the eval set.

    `skill` accepts a single name or a list (repeatable `--skill`), so the
    Layer 3 workflow can run several changed skills in one invocation.
    `quarantined` is a set of `skill#eval_id` keys excluded by default
    (RM-003 AC9); pass `include_quarantine=True` to run them anyway.

    Two-tier marker selection (RM-003 pass 4, AC6/AC12):
    - `default_only` (`--default`): per selected skill, keep exactly that
      skill's `"default": true` eval; when a skill has no marker, fall back to
      its first eval in file order (deterministic; never empty).
    - `core_only` (`--core`): keep only evals carrying `"core": true`.
    The marker-selected paths ignore `limit`; `limit` is retained for sharding
    only (AC8).
    """
    if isinstance(skill, str):
        skill = [skill]
    out = []
    for e in evals:
        if e["deferred"]:
            if not include_deferred:
                continue
        elif ci_mode and e["model_tier"] in ("go", "zen"):
            continue  # paid tiers excluded from CI by rm-002 Model-cost policy
        if quarantined and not include_quarantine and eval_key(e) in quarantined:
            continue  # RM-003 AC9 quarantine
        out.append(e)
    if skill:
        out = [e for e in out if e["skill"] in skill]
    if core_only:
        out = [e for e in out if e.get("core")]
    elif default_only:
        by_skill = {}
        for e in out:
            by_skill.setdefault(e["skill"], []).append(e)
        kept = []
        for items in by_skill.values():
            marked = [x for x in items if x.get("default")]
            kept.append(marked[0] if marked else items[0])  # marker, else first
        keep_ids = {id(x) for x in kept}
        out = [e for e in out if id(e) in keep_ids]
    if limit is not None and not (default_only or core_only):
        out = out[:limit]
    return out


def is_transient(text):
    """True when an eval output/detail carries a transient-failure indicator."""
    return bool(TRANSIENT_RE.search(text or ""))


def _dead_session(ctx):
    """True when the last invocation died without doing any work.

    Two shapes observed in CI (2026-09-28):
    - a stream whose only event is a provider error (e.g. `UnknownError` on a
      resumed session whose previous turn ended on rejected tool calls);
    - a stall with no events (timeout / connection error).

    Content misses — an agent that acted and missed assertions — are NOT dead
    sessions: those route to continuations/quarantine, never to a fresh retry.
    """
    events = ctx.get("events") or []
    if events:
        return all(ev.get("type") == "error" for ev in events)
    return is_transient((ctx.get("raw") or "") + " " + (ctx.get("stderr") or ""))


def _error_signature(ctx):
    """Compact, failure-only signature of a dead session's cause.

    2026-09-28 (RM-021): the run log used to say only "fatal stream", which
    hid the actual provider/opencode error. 44/117 persisted failure streams
    in weekly run 36455843309 carried exactly one event —
    `UnknownError: Unexpected server error ... ref=err_*` — and that cause is
    what the report must aggregate. Returns e.g. `UnknownError ref=err_abc`.
    """
    for ev in (ctx.get("events") or []):
        if ev.get("type") == "error":
            err = ev.get("error") or {}
            name = err.get("name") or "error"
            data = err.get("data") if isinstance(err.get("data"), dict) else {}
            ref = (data or {}).get("ref")
            base = name + (f" ref={ref}" if ref else "")
            cause = _resolved_cause(ctx.get("stderr") or "")
            return base + (f" ({cause})" if cause else "")
    return "no events"


def _redact(text):
    """Strip provider credentials from diagnostic text before persistence.

    2026-09-28: extracted from `_persist_event_streams` so server-log capture
    (stderr) passes through the same redaction as event streams — error text
    can echo env values.
    """
    out = text or ""
    for env_key in ("DEEPSEEK_API_KEY", "OPENCODE_API_KEY", "OPENCODE_GO_API_KEY"):
        secret = os.environ.get(env_key)
        if secret and secret in out:
            out = out.replace(secret, "***")
    return out


def assert_behavior(expected, output):
    """Return the list of expected strings NOT found.

    Case-insensitive substring after whitespace normalization (2026-09-28:
    markdown line-wraps broke multi-word phrases like "manual validation").
    """
    out_l = _norm_ws(output).lower()
    return [exp for exp in expected if _norm_ws(exp).lower() not in out_l]


# ---------------------------------------------------------------------------
# Typed assertion protocol (RM-003 pass 5, AC16/AC17/AC21)
#
# `expect` (when present) is a closed block with up to three classes:
#   action   tool-event predicates over the `opencode run --format json` stream
#   artifact a written file (glob path under the run workdir) + key phrases
#   text     a key phrase in the final response text
# The matcher is a pure function of (expect, context) so it is testable from a
# committed event-stream fixture with no model and no network.
# ---------------------------------------------------------------------------

class EvalResult:
    """One invocation's raw event stream (+ stderr + workdir for artifacts)."""

    __slots__ = ("raw", "stderr", "workdir", "cleanup")

    def __init__(self, raw, stderr="", workdir=None, cleanup=False):
        self.raw = raw or ""
        self.stderr = stderr or ""
        self.workdir = workdir
        self.cleanup = cleanup

    def close(self):
        if self.cleanup and self.workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)


def parse_event_stream(raw):
    """Parse a newline-delimited JSON event stream -> (events, errors).

    A malformed line is recorded as an error rather than dropped; callers fail
    closed on a non-empty error list for a typed eval. ANSI escape sequences
    are stripped first (opencode may banner stdout with TTY codes); a line
    that is empty after stripping is skipped. Non-JSON residue carries a
    sanitized snippet of itself in the error — fail closed, but with evidence.
    """
    events, errors = [], []
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    for i, line in enumerate((raw or "").splitlines(), start=1):
        line = ansi.sub("", line).strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            snippet = line[:160].replace("\n", "\\n")
            errors.append(f"line {i}: {exc.msg} | content: {snippet!r}")
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            errors.append(f"line {i}: event is not a JSON object")
    return events, errors


def _event_part(ev):
    part = ev.get("part")
    return part if isinstance(part, dict) else {}


def _event_type(ev):
    return _event_part(ev).get("type") or ev.get("type")


def extract_final_text(events):
    """Concatenate the text-event parts of the stream (the final response)."""
    chunks = []
    for ev in events:
        if _event_type(ev) != "text":
            continue
        part = _event_part(ev)
        txt = part.get("text")
        if txt is None:
            txt = ev.get("text")
        if isinstance(txt, str):
            chunks.append(txt)
    return "\n".join(chunks)


def extract_tool_calls(events):
    """Return the parsed tool events as `{"tool": ..., "args": {...}}`."""
    calls = []
    for ev in events:
        if _event_type(ev) != "tool":
            continue
        part = _event_part(ev)
        tool = part.get("tool") or ev.get("tool")
        args = None
        state = part.get("state")
        if isinstance(state, dict) and isinstance(state.get("input"), dict):
            args = state["input"]
        elif isinstance(part.get("input"), dict):
            args = part["input"]
        elif isinstance(ev.get("input"), dict):
            args = ev["input"]
        calls.append({"tool": tool, "args": args or {}})
    return calls


def build_context(result):
    """Normalize a `get_output` result (EvalResult or raw str) for matching.

    A plain string is treated as a legacy raw output: when it does not parse as
    an event stream the whole string is the text channel (backward compatible
    with `--stub-output` and injected stub callables).
    """
    if isinstance(result, EvalResult):
        raw, stderr, workdir = result.raw, result.stderr, result.workdir
    else:
        raw, stderr, workdir = result, "", None
    events, errors = parse_event_stream(raw)
    final_text = extract_final_text(events) if events else (raw or "")
    return {
        "raw": raw or "",
        "stderr": stderr or "",
        "workdir": workdir,
        "events": events,
        "final_text": final_text,
        "parse_error": ("; ".join(errors) if errors else None),
    }


def _glob_match(value, pattern):
    if value is None:
        return False
    return fnmatch.fnmatchcase(str(value), pattern)


def _norm_ws(s):
    """Collapse whitespace runs to single spaces for phrase matching.

    2026-09-28: phrase assertions are case-insensitive substrings, so a
    markdown line-wrap inside a phrase ("manual\\n   validation steps")
    failed a semantic match. Normalizing whitespace makes phrase checks
    robust to wrapping; it does not bridge any other wording difference.
    """
    return re.sub(r"\s+", " ", s or "")


def assert_action(entries, events):
    """Return missing `action` predicates (tool name + argument globs)."""
    calls = extract_tool_calls(events)
    missing = []
    for entry in entries:
        tool = entry.get("tool")
        args_spec = entry.get("args") or {}
        ok = any(
            _glob_match(call["tool"], tool)
            and all(_glob_match(call["args"].get(k), v) for k, v in args_spec.items())
            for call in calls
        )
        if not ok:
            detail = ", ".join(f"{k}={v!r}" for k, v in args_spec.items()) or "no args"
            missing.append(f"action: no tool event matching tool={tool!r} ({detail})")
    return missing


def _artifact_files(workdir, path):
    if not workdir:
        return []
    target = path if os.path.isabs(path) else os.path.join(workdir, path)
    files = [p for p in glob.glob(target, recursive=True) if os.path.isfile(p)]
    if os.path.isfile(target) and target not in files:
        files.append(target)
    return files


def assert_artifact(entries, workdir, events=None):
    """Return missing `artifact` predicates (file path glob + content phrases).

    Two match surfaces, either satisfies the predicate:
    1. the workdir filesystem (a file the agent wrote directly), and
    2. `write` tool events from the session stream — filePath glob + content
       phrases. (2026-09-21: a correctly-behaving authoring agent installs
       the drafted skill into the global opencode layout, OUTSIDE the eval
       workdir; the write event is the observable per the protocol's nature
       rule. Diagnosed from run 35610869434.)
    """
    missing = []
    for entry in entries:
        path = entry.get("path")
        phrases = entry.get("phrases") or []
        norms = [_norm_ws(p).lower() for p in phrases]
        found = False
        # Surface 1: workdir filesystem.
        for fp in _artifact_files(workdir, path):
            try:
                content = _norm_ws(open(fp, encoding="utf-8", errors="replace").read()).lower()
            except OSError:
                continue
            if all(p in content for p in norms):
                found = True
                break
        # Surface 2: write events (path glob + event content).
        if not found and events:
            for call in extract_tool_calls(events):
                if call["tool"] not in ("write", "edit"):
                    continue
                if not _glob_match(call["args"].get("filePath"), path):
                    continue
                content = _norm_ws(str(call["args"].get("content") or "")).lower()
                if all(p in content for p in norms):
                    found = True
                    break
        if not found:
            missing.append(
                f"artifact: no file matching {path!r} containing all phrases {phrases}")
    return missing


def assert_text(phrases, final_text):
    """Return missing `text` key-phrases (case-insensitive, whitespace-normalized)."""
    low = _norm_ws(final_text).lower()
    return [f"text: phrase not found: {p!r}" for p in phrases
            if _norm_ws(p).lower() not in low]


def assert_expect(expect, ctx):
    """Return missing descriptions for one typed `expect` block (fails closed)."""
    if ctx.get("parse_error"):
        return [f"event stream parse error: {ctx['parse_error']}"]
    missing = []
    if expect.get("action"):
        missing += assert_action(expect["action"], ctx["events"])
    if expect.get("artifact"):
        missing += assert_artifact(expect["artifact"], ctx["workdir"], ctx["events"])
    if expect.get("text"):
        missing += assert_text(expect["text"], ctx["final_text"])
    if not any(expect.get(k) for k in ("action", "artifact", "text")):
        missing.append("expect: empty typed block (no action/artifact/text entries)")
    return missing


def assert_eval(e, ctx):
    """Assert one eval: typed `expect` when present, else legacy text-class."""
    expect = e.get("expect")
    if isinstance(expect, dict) and expect:
        return assert_expect(expect, ctx)
    return assert_behavior(e.get("expected_behavior", []), ctx["final_text"])


def _token_totals(turns):
    """Sum (input, output, cost) across every turn's step-finish events.

    2026-09-29 (RM-021): the run log's tokens_in/tokens_out were always null,
    so neither the per-eval cost of a run nor a suite projection could be
    computed from evidence. Sampling one eval now yields a real per-eval token
    figure to extrapolate from — small probe, measured answer.
    """
    ti = to = 0
    cost = 0.0
    for _label, res in turns or []:
        events, _errors = parse_event_stream(getattr(res, "raw", "") or "")
        for ev in events:
            part = ev.get("part") if isinstance(ev.get("part"), dict) else ev
            if not isinstance(part, dict):
                continue
            if part.get("type") not in ("step-finish", "step_finish"):
                continue
            tk = part.get("tokens") or {}
            ti += int(tk.get("input") or 0)
            to += int(tk.get("output") or 0)
            # Providers report measured cost per step; prefer it over any
            # price table (2026-09-29). Cache-write input can dominate, so
            # token sums alone under-report some models (gpt-6-luna).
            try:
                cost += float(part.get("cost") or 0.0)
            except (TypeError, ValueError):
                pass
    return (ti or None), (to or None), (round(cost, 6) if cost else None)


_WRITE_ISH_RE = re.compile(
    r"(?:^|[\s;&|])(?:>>|<<|>|tee\b|mkdir\b|cp\b|mv\b|rm\b|sed\s+-i|dd\b|truncate\b)")


def _has_work_activity(ctx):
    """True when a turn produced work.

    2026-09-29: counting ONLY write/edit tool calls misfired — agents routinely
    write artifacts via bash (`cat > f`, heredocs, node scripts), so a turn with
    21-26 tool_use events and real output was judged "0 write events" and nudged
    repeatedly, ending in dead sessions recorded as INFRA failures. Count any
    write/edit call, or a bash command that writes.
    """
    for call in extract_tool_calls(ctx.get("events") or []):
        if call["tool"] in ("write", "edit"):
            return True
        if call["tool"] == "bash":
            cmd = (call.get("args") or {}).get("command") or ""
            if _WRITE_ISH_RE.search(cmd):
                return True
    return False


def run_eval(e, get_output, logs_dir=None, model=None, max_retries=1,
             sleep=time.sleep, quarantine_path=None):
    """Run one eval via `get_output(e)`, assert, and write a run-log record.

    Returns (passed, missing, record_path). `model` (concrete ID, e.g.
    `opencode/nemotron-3-ultra-free`) overrides the tier label in the record
    when the caller selected the model explicitly — the log should record
    what actually ran.

    RM-003 AC9: a *transient* failure (timeout / rate limit / model
    unavailable / connection error) is retried at most `max_retries` times
    with `RETRY_BACKOFF_SECONDS` backoff. `quarantine_path`, when set,
    records the final failure (or clears on success) — CI-owned only.

    2026-09-28 resilience: a session that DIES with no work (a stream whose
    only event is an error, or a stall with no events) is retried in a FRESH
    session — bounded by `BEVAL_MAX_FRESH_RETRIES` (default 2, clamp 2) and
    logged. Content misses never take this path. On failure, every turn's raw
    stream is persisted for diagnosis.
    """
    started = time.monotonic()
    result = get_output(e)
    try:
        ctx = build_context(result)
        best_missing = assert_eval(e, ctx)
        missing = best_missing
        turns = [("initial", result)]
        # A turn with NO events at all is a stall (provider/gateway), not an
        # agent error: repeated attempts burn ~4 min each for nothing
        # (2026-09-30: modeling-threats#1 stalled 4x = 16 of a 20-min shard).
        no_event_turns = 0 if ctx["events"] else 1
        attempts = 0
        # Transient retry applies to NON-STREAM output only (stall strings,
        # legacy raw): a parseable event stream has no transient signature in
        # its raw text — agent chatter mentioning 'timeout' poisoned the
        # classifier (2026-09-21). Streams with missing assertions route to
        # the continuation policy below instead.
        while (missing and attempts < max_retries
               and not ctx["events"]
               and is_transient(ctx["raw"] + " " + ctx["stderr"])):
            # Per-attempt annotation (2026-09-19 directive): a retry means the
            # model hit an unexpected event (stall / rate limit / transient
            # error) — that event is reliability evidence, not noise, and gets
            # its OWN run-log record so a later attempt's success cannot bury it.
            delay = RETRY_BACKOFF_SECONDS[min(attempts, len(RETRY_BACKOFF_SECONDS) - 1)]
            attempts += 1
            # Reliability annotation record: eval_pass=None so aggregators count
            # only FINAL verdicts toward pass rates (RM-001 null semantics).
            log_run.log_record({
                "kind": "eval",
                "skill": e["skill"],
                "agent": None,
                "model": model or e["model_tier"],
                "outcome": "error",
                "eval_pass": None,
                "detail": ("transient attempt %d: %s" % (attempts, ctx["raw"]))[:DETAIL_MAX],
            }, logs_dir=logs_dir)
            if isinstance(result, EvalResult):
                result.close()
            sleep(delay)
            result = get_output(e)
            ctx = build_context(result)
            missing = assert_eval(e, ctx)
            best_missing = missing if len(missing) < len(best_missing) else best_missing
            if not ctx["events"]:
                no_event_turns += 1
            turns.append((f"transient{attempts}", result))
        # Deterministic continuation policy (2026-09-21, the mechanical form
        # of an eval-run orchestrator): a turn that ends with MISSING
        # assertions and ZERO write/edit events is a premature stop — the
        # agent ended mid-task. Continue the SAME opencode session with an
        # explicit finish-now nudge; bounded and logged per turn. The session
        # id comes from the event stream itself. 2026-09-28: the policy runs
        # per session — the initial session, and again after each fresh retry
        # (a fresh session that then stalls deserves the same nudge).
        continuations = 0
        max_continuations = min(int(os.environ.get("BEVAL_MAX_CONTINUATIONS", "1")), 3)  # clamp: no runaway loops
        # Legacy evals carry prose `expected_behavior` only (no typed `expect`):
        # those substrings can never match, so every turn is "missing" and the
        # retry budget just burns turns into dead sessions (2026-09-29). Cap
        # them at one nudge; the migration backlog removes the class entirely.
        if not (isinstance(e.get("expect"), dict) and e["expect"]):
            max_continuations = min(max_continuations, 1)

        def nudge_session():
            """Same-session nudges for the CURRENT result (per-session budget)."""
            nonlocal result, ctx, missing, continuations, best_missing, no_event_turns
            used = 0
            while (best_missing and used < max_continuations
                   and not _dead_session(ctx)
                   and not _has_work_activity(ctx)):
                session_id = next((ev.get("sessionID") for ev in ctx["events"]
                                   if ev.get("sessionID")), None)
                if not session_id:
                    return
                used += 1
                continuations += 1
                nudge = ("Continue the task to completion in this session. Do the "
                         "work now — write the required files (any tool is fine); "
                         "do not end with a plan to write them later.")
                log_run.log_record({
                    "kind": "eval",
                    "skill": e["skill"],
                    "agent": None,
                    "model": model or e["model_tier"],
                    "outcome": "error",
                    "eval_pass": None,
                    "detail": (f"continuation turn {continuations}: premature stop "
                               f"(0 write events, session {session_id})")[:DETAIL_MAX],
                }, logs_dir=logs_dir)
                if isinstance(result, EvalResult):
                    result.close()
                result = get_output(e, {"session_id": session_id, "nudge": nudge})
                ctx = build_context(result)
                missing = assert_eval(e, ctx)
                best_missing = missing if len(missing) < len(best_missing) else best_missing
                if not ctx["events"]:
                    no_event_turns += 1
                turns.append((f"continuation{continuations}", result))

        nudge_session()

        # Fresh-session retry on a dead session (2026-09-28): when a session
        # dies with no work, resuming it cannot help — observed: a resumed
        # session hard-fails with a provider UnknownError after a turn ends on
        # rejected tool calls. Restart in a FRESH session instead; bounded
        # (default 2, clamp 2) and logged per attempt. Never applied to
        # content misses.
        max_fresh = min(int(os.environ.get("BEVAL_MAX_FRESH_RETRIES", "2")), 2)
        fresh = 0
        while (best_missing and fresh < max_fresh and _dead_session(ctx)):
            fresh += 1
            delay = FRESH_RETRY_BACKOFF_SECONDS[min(fresh - 1, len(FRESH_RETRY_BACKOFF_SECONDS) - 1)]
            sleep(delay)
            log_run.log_record({
                "kind": "eval",
                "skill": e["skill"],
                "agent": None,
                "model": model or e["model_tier"],
                "outcome": "error",
                "eval_pass": None,
                "detail": (f"fresh retry {fresh}: session died with no work "
                           f"({_error_signature(ctx)}); restarting fresh")[:DETAIL_MAX],
            }, logs_dir=logs_dir)
            if isinstance(result, EvalResult):
                result.close()
            result = get_output(e)  # fresh session
            ctx = build_context(result)
            missing = assert_eval(e, ctx)
            best_missing = missing if len(missing) < len(best_missing) else best_missing
            if not ctx["events"]:
                no_event_turns += 1
            turns.append((f"fresh{fresh}", result))
            nudge_session()  # a fresh session that stalls gets the same nudge
            if no_event_turns >= 2:
                break  # two no-event turns: stop burning the budget on a stall

        # Grade the BEST turn, not the last: a productive turn followed by a
        # dead continuation was recorded as an infra failure even though the
        # work was done (2026-09-29).
        passed = not best_missing
        dead = bool(best_missing) and _dead_session(ctx)
        detail = None
        if best_missing:
            if dead:
                # Infra failure, not a content miss: keep the cause visible and
                # separable from `failure` so the report/green-run signals are
                # not polluted by provider errors (RM-021, 2026-09-28).
                detail = (f"dead session: {_error_signature(ctx)} — "
                          f"no work produced")[:DETAIL_MAX]
            else:
                detail = ("missing: " + " | ".join(best_missing))[:DETAIL_MAX]
            _persist_event_streams(logs_dir, e, turns)
        tok_in, tok_out, tok_cost = _token_totals(turns)
        rec = {
            "kind": "eval",
            "skill": e["skill"],
            "eval": eval_key(e),
            "agent": None,
            "model": model or e["model_tier"],
            "outcome": "success" if passed else ("error" if dead else "failure"),
            "eval_pass": passed,
            "detail": detail,
            # Measured, not guessed (2026-09-29): every run teaches the
            # extrapolation a real per-eval token + wall-time figure.
            "tokens_in": tok_in,
            "tokens_out": tok_out,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "cost": tok_cost,
        }
        path = log_run.log_record(rec, logs_dir=logs_dir)
        if quarantine_path:
            if passed:
                quarantine.record_success(quarantine_path, eval_key(e))
            elif not dead:
                # An infra death is not eval flakiness (RM-021, 2026-09-28):
                # quarantine must not mark an eval "watching" because the
                # provider/model catalog failed to resolve.
                quarantine.record_failure(quarantine_path, eval_key(e))
        return passed, missing, path
    finally:
        if isinstance(result, EvalResult):
            result.close()


def augment_prompt(prompt, workdir, files):
    """Append the ABSOLUTE target root to an eval prompt.

    2026-09-29 (RM-021): the prompt fix that replaced "repo is the working
    directory" used a RELATIVE fixture path, but agents still resolved artifact
    paths against the installed skill's checkout (or a /tmp habit) and were
    auto-rejected as `external_directory` — 108 such rejects in one full run
    (66 into the CI checkout, 33 into agent-chosen /tmp), each ending a turn
    with 0 writes (premature stop -> dead session -> infra failure). Handing
    the agent the materialized ABSOLUTE path, plus an explicit "write only
    here", removes the ambiguity at its source.
    """
    rels = [os.path.dirname(f) for f in (files or []) if f]
    root = None
    if rels:
        try:
            root = os.path.commonpath(rels)
        except ValueError:
            root = None
    if not root:
        return prompt
    abs_root = os.path.join(workdir, root)
    return (f"{prompt}\n\nTarget repo root (absolute): {abs_root}. Treat that "
            f"directory as the repo root, write every artifact inside it, and "
            f"never write outside it.")


def opencode_run_args(tmp, prompt, model=None):
    """argv for one fresh-agent invocation (after `opencode`) — pure, hermetic.

    Validated 2026-09-06 against https://opencode.ai/docs/cli/#run-1:
    `opencode run [message..]` with `--dir`, `--agent`, `--model/-m`, `--file/-f`,
    `--format` flags. There is NO `--skill` flag — the skill resolves from the
    installed layout via `--dir`.

    `model` MUST be passed in CI (workflow selects the free generalist; see
    reference/model-routing.md): opencode's environment default on a fresh CI
    runner is `big-pickle`, which is disabled at the gateway — found by the
    RM-002 AC5 live gate, 2026-09-16. Omitted only for developer-local runs
    that intentionally use the environment default.
    """
    args = ["run", "--print-logs", "--log-level", "ERROR", "--dir", tmp]
    if model:
        args += ["--model", model]
    # RM-003 pass 5: capture the newline-delimited JSON event stream so typed
    # `action`/`artifact` predicates can observe tool events (AC21).
    # 2026-09-28 (RM-021 observability): ALSO capture opencode's own server log
    # on stderr at ERROR level, so a dead-session `UnknownError ... ref=err_*`
    # (an opencode-server error with no client-visible cause) is resolvable
    # from the uploaded artifact instead of "check server logs" with no logs.
    args += ["--format", "json", prompt]
    return args


DIRECT_LANE_PREFIX = "deepseek/"  # user's own API key lane (model-routing.md)
GO_LANE_PREFIX = "opencode-go/"   # Go flat-rate lane — the CI eval lane (2026-09-29)


def assert_ci_free_model(model):
    """Model-cost policy (RM-002; amended 2026-09-21 and 2026-09-29).

    CI may select only lanes with no per-run marginal cost:
      - `*-free` — the $0 opencode tier;
      - `opencode-go/*` — the Go flat-rate tier ($10/mo allowance) — the CI
        eval lane since 2026-09-29, when the user directive moved evals off
        their personal DeepSeek API key;
      - `deepseek/*` — the legacy direct-key lane, retained for
        developer-local runs.
    Zen pay-as-you-go (`opencode/*`, non-free) is never allowed in CI.
    """
    if (model.endswith("-free") or model.startswith(GO_LANE_PREFIX)
            or model.startswith(DIRECT_LANE_PREFIX)):
        return
    raise ValueError(
        f"CI model must be `*-free`, `{GO_LANE_PREFIX}*` (flat-rate) or the "
        f"legacy direct-key lane `{DIRECT_LANE_PREFIX}*` (Model-cost policy, "
        f"amended 2026-09-29), got {model!r}"
    )


def _resolved_cause(stderr):
    """Concrete error the opencode server logged, extracted from stderr.

    `opencode run --print-logs` writes e.g.
    `level=ERROR ... error="ProviderModelNotFoundError: Model not found: deepseek/deepseek-flash"`.
    Returns the first quoted error (bounded), else the model-resolution class
    name when the text matches it, else "".
    """
    m = re.search(r'error="([^"]{0,200})"', stderr or "")
    if m:
        return m.group(1)[:140]
    # opencode auto-rejects writes outside the run workdir (`external_directory`);
    # the rejected turn then ends with no work and the stream carries only the
    # UnknownError wrapper. Seen in the 2026-09-28 weekly run (RM-021).
    m = re.search(r"permission requested: external_directory \(([^)]{0,120})\)"
                  r"[^\n]*auto-reject", stderr or "")
    if m:
        return f"external_directory auto-reject ({m.group(1)})"
    if MODEL_RESOLUTION_RE.search(stderr or ""):
        return "ProviderModelNotFoundError"
    return ""


def is_model_resolution_error(text):
    """True when `text` names the model-resolution failure class."""
    return bool(MODEL_RESOLUTION_RE.search(text or ""))


def model_listed(output, model):
    """True when `opencode models` output lists `model` as an exact line."""
    return any(line.strip() == model for line in (output or "").splitlines())


def preflight_model(model):
    """Best-effort catalog check before a suite; ADVISORY ONLY.

    Returns `(True, "")` when listed and `(False, reason)` / `(None, reason)`
    otherwise — the caller must NOT block on this. 2026-09-28 CI finding:
    `opencode models` is not a reliable oracle across environments — a CI
    runner listed 12 gateway models and omitted `deepseek/deepseek-flash`
    (the direct-key lane the suite actually uses, which resolves and runs
    fine there). A listing gap therefore means "cannot tell", never "broken".
    The behaviour-based guard is the consecutive-death early abort instead.
    """
    try:
        proc = subprocess.run(["opencode", "models"], capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"preflight skipped: `opencode models` failed ({exc})"
    text = (proc.stdout or "") + (proc.stderr or "")
    if model_listed(text, model):
        return True, ""
    return False, (f"model {model!r} is not in `opencode models` "
                   f"({len(text.splitlines())} lines listed; CI omits the "
                   f"direct-key lane — advisory only)")


def _copy_fixture_files(tmp, skill, files, skills_root=None):
    """Copy eval fixtures into tmp at the repo-relative layout.

    RM-021 AC1: every destination resolves under `tmp`. Paths that escape the
    repo root are skipped rather than crashing. Returns the number of files
    copied.
    """
    skills_root = skills_root or SKILLS_ROOT
    repo_root = os.path.dirname(skills_root)
    norm_repo = os.path.normpath(os.path.abspath(repo_root))
    copied = 0
    for rel in files or []:
        src = os.path.join(skills_root, skill, "evals", rel)
        norm_src = os.path.normpath(os.path.abspath(src))
        # An absolute path outside the repo, or enough `..` segments, can
        # escape. Reject anything not under the repo root.
        if not (norm_src == norm_repo or norm_src.startswith(norm_repo + os.sep)):
            continue
        if not os.path.isfile(norm_src):
            continue
        rel_to_repo = os.path.relpath(norm_src, norm_repo)
        dst = os.path.join(tmp, rel_to_repo)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(norm_src, dst)
        copied += 1
    return copied


def invoke_opencode(e, model=None, turn=None):
    """Real fresh-agent invocation (CI only; needs the model credential).

    The model credential must already be in the environment (repo secret);
    it is consumed here, never echoed.

    `turn` (optional dict): when present with `session_id`, the invocation
    CONTINUES that opencode session (deterministic continuation policy,
    2026-09-21 — the mechanical form of an eval-run orchestrator: the runner,
    not a model, ushers stalled agents forward; every nudge is logged).
    """
    tmp = tempfile.mkdtemp(prefix="beval-")
    stall_timeout = int(os.environ.get("BEVAL_TIMEOUT_SECONDS", "240"))
    keep = False
    try:
        if not (turn and turn.get("session_id")):
            _copy_fixture_files(tmp, e["skill"], e.get("files"))
        # The model credential must already be in the environment (repo secret);
        # it is consumed here, never echoed.
        # start_new_session=True: a stalled opencode may leak child processes
        # (zombie `opencode` servers); the whole group must be re-apable, so
        # the TimeoutExpired handler below kills the group, not just the child.
        if turn and turn.get("session_id"):
            argv = ["opencode", "run", "--dir", tmp, "--format", "json",
                    "-s", turn["session_id"], turn["nudge"]]
            if model:
                argv += ["--model", model]
        else:
            argv = ["opencode"] + opencode_run_args(
                    tmp, augment_prompt(e["prompt"], tmp, e.get("files")), model=model)
        try:
            proc = subprocess.Popen(
                argv,
                cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=os.environ,
                start_new_session=True,
            )
        except OSError as exc:
            return EvalResult(raw=f"opencode invocation failed: {exc}")
        try:
            out, err = proc.communicate(timeout=stall_timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass  # group already gone
            # RM-021 AC4: reap the killed group's pipes so the captured server
            # stderr (where opencode logs the resolving cause) is persisted.
            _out, _err = proc.communicate()
            return EvalResult(
                raw=(f"eval stall: subprocess timed out after {stall_timeout}s "
                     f"with no completion (transient; subprocess group killed)"),
                stderr=_redact(_err or "")[:4096])
        # Keep the workdir: the artifact class reads files the agent wrote
        # there; run_eval closes (removes) it after matching.
        keep = True
        return EvalResult(raw=out, stderr=err, workdir=tmp, cleanup=True)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def _persist_event_streams(logs_dir, e, turns):
    """Save EVERY turn's raw stream of a failed eval next to the run log.

    2026-09-28: only the final turn used to be persisted, which made the
    resume-death class (initial turn ends, resumed session errors) impossible
    to diagnose without a local repro. One file per turn, best-effort: never
    fails the eval because diagnostics could not be written.
    """
    if not logs_dir:
        logs_dir = "logs/"  # CI invokes the runner without --logs-dir
    try:
        d = os.path.join(logs_dir, "eval-streams")
        os.makedirs(d, exist_ok=True)
        slug = eval_key(e).replace("#", "__")
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        for idx, (label, res) in enumerate(turns):
            raw = _redact(getattr(res, "raw", "") or "")
            err = _redact(getattr(res, "stderr", "") or "")
            if raw:
                fn = os.path.join(d, f"{slug}-{stamp}-turn{idx}-{label}.jsonl")
                with open(fn, "w", encoding="utf-8") as fh:
                    fh.write(raw)
            # Server-log capture (2026-09-28, RM-021): `opencode run
            # --print-logs` writes the resolving cause of an err_* ref to
            # stderr; persist it (redacted, bounded) so a dead session is
            # diagnosable from the uploaded artifact alone.
            if err:
                efn = os.path.join(d, f"{slug}-{stamp}-turn{idx}-{label}-stderr.log")
                with open(efn, "w", encoding="utf-8") as fh:
                    fh.write(err[:8192])
    except OSError:
        pass


def load_event_fixture(path):
    """Replay a recorded event stream instead of invoking opencode (AC21).

    `path` is either an `events.jsonl` file or a directory containing one; the
    directory is the workdir for `artifact` predicates, so committed artifact
    files sit next to the stream.
    """
    events_path = path if os.path.isfile(path) else os.path.join(path, "events.jsonl")
    with open(events_path, encoding="utf-8") as fh:
        raw = fh.read()
    return EvalResult(raw=raw, workdir=os.path.dirname(os.path.abspath(events_path)))


def _stub_typed_result(e):
    """Synthesize a passing output for one eval (legacy text or typed stream)."""
    expect = e.get("expect")
    if not (isinstance(expect, dict) and expect):
        # Legacy eval (or typed-less): the text channel is the whole output.
        return EvalResult(raw="\n".join(e.get("expected_behavior", [])))
    workdir = tempfile.mkdtemp(prefix="beval-stub-")
    events = []
    for entry in expect.get("action", []):
        args = {k: (str(v).replace("*", "") or "x")
                for k, v in (entry.get("args") or {}).items()}
        tool = str(entry.get("tool", "")).replace("*", "") or "bash"
        events.append({"type": "tool", "part": {
            "type": "tool", "tool": tool,
            "state": {"status": "completed", "input": args}}})
    for entry in expect.get("artifact", []):
        rel = str(entry.get("path", "")).replace("*", "").strip("/")
        dest = os.path.join(workdir, rel) if rel else os.path.join(workdir, "artifact.txt")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entry.get("phrases", [])))
    text = "\n".join(expect.get("text", []))
    if text:
        events.append({"type": "text", "part": {"type": "text", "text": text}})
    raw = "\n".join(json.dumps(ev) for ev in events)
    return EvalResult(raw=raw, workdir=workdir, cleanup=True)


def stub_result(e, mode, calls):
    """Hermetic test output for one eval (ALL / :MISS: / :FLAKY:)."""
    if mode.startswith(":MISS:"):
        if e.get("expected_behavior"):
            return EvalResult(raw="\n".join(e["expected_behavior"][1:]))
        return EvalResult(raw="")
    if mode.startswith(":FLAKY:"):
        key = eval_key(e)
        n = calls.get(key, 0)
        calls[key] = n + 1
        if n == 0:
            return EvalResult(raw="error: connection timeout contacting model (transient)")
    return _stub_typed_result(e)


def _last_record(path):
    """Last run-log record written to `path` (for the CLI summary class)."""
    last = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        last = json.loads(line)
                    except ValueError:
                        continue
    except OSError:
        return {}
    return last or {}


def _record_infra_error(e, exc, logs_dir=None, model=None):
    """RM-021 AC2: record an unexpected eval-level crash as an infra error.

    Used when the runner's own loop catches an exception from `get_output` or
    `run_eval` so one crash cannot silently drop the eval.
    """
    detail = (f"runner crash: {type(exc).__name__}: {exc}")[:DETAIL_MAX]
    rec = {
        "kind": "eval",
        "skill": e["skill"],
        "eval": eval_key(e),
        "agent": None,
        "model": model or e.get("model_tier"),
        "outcome": "error",
        "eval_pass": False,
        "detail": detail,
    }
    return log_run.log_record(rec, logs_dir=logs_dir)


def _final_eval_keys(logs_dir):
    """Return the set of eval keys that have a final content verdict.

    Per-attempt annotation records have `eval_pass=None`; only True/False
    counts as a final verdict.
    """
    keys = set()
    if not logs_dir or not os.path.isdir(logs_dir):
        return keys
    for fn in os.listdir(logs_dir):
        if not fn.endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(logs_dir, fn), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if (rec.get("kind") == "eval"
                            and rec.get("eval") is not None
                            and rec.get("eval_pass") is not None):
                        keys.add(rec["eval"])
        except OSError:
            continue
    return keys


def _missing_eval_keys(selected, logs_dir):
    """RM-021 AC2: list selected eval keys with no final record."""
    final = _final_eval_keys(logs_dir)
    return [eval_key(e) for e in selected if eval_key(e) not in final]


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Run behavioral eval suite.")
    p.add_argument("--list", action="store_true",
                   help="Print the included eval set and exit (no agent calls).")
    p.add_argument("--include-deferred", action="store_true",
                   help="Also include evals flagged deferred:true.")
    p.add_argument("--limit", type=int, default=None,
                   help="Run only the first N included evals (subset sharding).")
    p.add_argument("--skill", action="append", default=None,
                   help="Run only evals for this skill (repeatable; subset sharding). "
                        "The Layer 3 workflow passes one --skill per changed skill.")
    p.add_argument("--default", dest="default_only", action="store_true",
                   help="Run each selected skill's single default-marked eval "
                        "(fallback: first eval in file order). Layer 3 skill path.")
    p.add_argument("--core", dest="core_only", action="store_true",
                   help="Run the core-marked evals (the six core skills' default "
                        "evals). Layer 3 harness path.")
    p.add_argument("--logs-dir", default=None,
                   help="Log directory (default repo logs/).")
    p.add_argument("--skills-root", default=SKILLS_ROOT,
                   help="Override the skills root (testing).")
    p.add_argument("--quarantine-file", default=None,
                   help="Quarantine state file (default <logs-dir>/quarantine.json).")
    p.add_argument("--no-quarantine", action="store_true",
                   help="Never read/write quarantine state (Layer 2 advisory local "
                        "runs MUST pass this; quarantine is CI-owned).")
    p.add_argument("--include-quarantine", action="store_true",
                   help="Run quarantined evals anyway (explicit opt-in).")
    p.add_argument("--max-retries", type=int, default=1,
                   help="Max transient-failure retries per eval (default 1).")
    p.add_argument("--no-preflight", action="store_true",
                   help="Skip the `opencode models` preflight (offline/dev runs).")
    p.add_argument("--ci", action="store_true",                   help="Enforce free-tier-only (skip go/zen evals); also auto-enabled "
                        "by AI_FRAMEWORK_FREE_TIER or CI env.")
    p.add_argument("--model", default=None,
                   help="Concrete model ID for `opencode run --model` "
                        "(e.g. opencode/nemotron-3-ultra-free). CI MUST set this: "
                        "opencode's environment default on a fresh runner is not "
                        "guaranteed to be a live free model (RM-002 AC5, 2026-09-16). "
                        "The ID is a binding — keep it in step with "
                        "reference/model-routing.md's free generalist.")
    p.add_argument("--stub-output", default=None,
                   help="Hermetic test mode: use this fixed output for every eval "
                        "instead of invoking opencode. 'ALL' passes every eval; "
                        "':MISS:' forces a permanent (non-transient) failure; "
                        "':FLAKY:' emits a transient error first, then passes "
                        "(exercises the retry path). Typed evals are synthesized "
                        "to match their expect block.")
    p.add_argument("--event-fixture", default=None,
                   help="Hermetic replay (RM-003 pass 5): path to a recorded "
                        "event-stream file (events.jsonl) or its directory; "
                        "replays it through the typed matcher instead of invoking "
                        "opencode (no model, no network). The directory is the "
                        "workdir for artifact predicates.")
    args = p.parse_args(argv)

    all_evals = load_skill_evals(args.skills_root)
    ci_mode = args.ci or bool(os.environ.get("AI_FRAMEWORK_FREE_TIER")) or bool(os.environ.get("CI"))
    if args.model and ci_mode:
        try:
            assert_ci_free_model(args.model)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    if ci_mode and not args.model:
        print("warning: --model not set in CI mode; opencode will use its "
              "environment default, which is NOT guaranteed to be a live free "
              "model (RM-002 AC5)", file=sys.stderr)

    # Quarantine is CI-owned: enabled by default (the CI jobs rely on it) but
    # Layer 2 advisory local runs MUST opt out with --no-quarantine.
    quarantine_path = None
    if not args.no_quarantine:
        quarantine_path = args.quarantine_file or os.path.join(
            args.logs_dir or log_run.DEFAULT_LOGS_DIR, "quarantine.json")
    quarantined = quarantine.quarantined_keys(quarantine_path) if quarantine_path else set()

    selected = filter_evals(all_evals, include_deferred=args.include_deferred,
                            limit=args.limit, skill=args.skill, ci_mode=ci_mode,
                            quarantined=quarantined,
                            include_quarantine=args.include_quarantine,
                            default_only=args.default_only,
                            core_only=args.core_only)

    if args.list:
        print(f"included evals: {len(selected)}")
        deferred_excluded = (
            0 if args.include_deferred
            else sum(1 for e in all_evals if e["deferred"])
        )
        if deferred_excluded:
            print(f"deferred: {deferred_excluded} excluded by default "
                  f"(pass --include-deferred to include)")
        paid_excluded = sum(
            1 for e in all_evals
            if ci_mode and not e["deferred"] and e["model_tier"] in ("go", "zen")
        )
        if paid_excluded:
            print(f"paid-tier: {paid_excluded} excluded by CI mode "
                  f"(free-only; see reference/model-routing.md)")
        if quarantined and not args.include_quarantine:
            excluded = sum(1 for e in all_evals
                           if not e["deferred"] and eval_key(e) in quarantined)
            if excluded:
                print(f"quarantined: {excluded} excluded by quarantine "
                      f"(pass --include-quarantine to include)")
        for e in selected:
            tag = "deferred" if e["deferred"] else "eval"
            print(f"  [{tag}] {e['skill']}#{e['eval_id']} (tier={e['model_tier']})")
        return 0

    if not selected:
        print("no evals selected", file=sys.stderr)
        return 0

    _stub_calls = {}

    def get_output(e, turn=None):
        if args.event_fixture:
            return load_event_fixture(args.event_fixture)
        if args.stub_output is not None:
            return stub_result(e, args.stub_output, _stub_calls)
        return invoke_opencode(e, model=args.model, turn=turn)

    # Catalog preflight (2026-09-28, RM-021): ADVISORY only. `opencode models`
    # is not a reliable oracle across environments (CI lists 12 gateway models
    # and omits the direct-key lane the suite uses), so a listing gap must
    # never block a suite. The real guard is the consecutive-death early abort
    # in the loop below. Skipped in stub/fixture mode (no model call).
    if (args.model and not args.stub_output and not args.event_fixture
            and not args.no_preflight):
        ok, why = preflight_model(args.model)
        if ok is not True:
            print(f"warning: preflight: {why}", file=sys.stderr)

    failed = 0
    infra_deaths = 0
    for e in selected:
        # RM-021 AC2: isolate per-eval exceptions so one crash cannot drop the
        # rest of the shard. Record an infra error and continue.
        try:
            passed, missing, path = run_eval(e, get_output, logs_dir=args.logs_dir,
                                             model=args.model,
                                             max_retries=args.max_retries,
                                             quarantine_path=quarantine_path)
        except Exception as exc:
            path = _record_infra_error(e, exc, logs_dir=args.logs_dir, model=args.model)
            passed, missing = False, [str(exc)]
        status = "PASS" if passed else "FAIL"
        print(f"{status}  {e['skill']}#{e['eval_id']}  -> {path}")
        if not passed:
            failed += 1
            rec = _last_record(path)
            if rec.get("outcome") == "error":
                # Infra death, not a content miss: printing "missing: ..." here
                # made a model/provider failure look like a failed assertion in
                # CI logs (RM-021, 2026-09-28).
                print(f"      infra error: {rec.get('detail') or 'dead session'}")
                infra_deaths = (infra_deaths + 1
                                if is_model_resolution_error(rec.get("detail")) else 0)
            else:
                infra_deaths = 0
                for m in missing:
                    print(f"      missing: {m[:120]}")
        else:
            infra_deaths = 0
        if infra_deaths >= 3:
            # Every eval dies the same infra way in ~2s: stop instead of burning
            # the suite and turning one broken catalog into hundreds of reds.
            print("aborting: model resolution failed for 3 consecutive evals "
                  "(infra, not a regression)", file=sys.stderr)
            return 3

    # RM-021 AC2: assert every selected eval has a final content record.
    missing_keys = _missing_eval_keys(selected, args.logs_dir)
    if missing_keys:
        print(f"\ncompleteness check failed: {len(missing_keys)} selected eval(s) "
              f"have no final record: {', '.join(missing_keys)}", file=sys.stderr)
        return 1

    if failed:
        print(f"\n{failed} eval(s) failed regression gate", file=sys.stderr)
        return 1
    print("\nall included evals passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
