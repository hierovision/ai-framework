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


def assert_behavior(expected, output):
    """Return the list of expected strings NOT found (case-insensitive substring)."""
    out_l = (output or "").lower()
    return [exp for exp in expected if exp.lower() not in out_l]


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


def assert_artifact(entries, workdir):
    """Return missing `artifact` predicates (file path glob + content phrases)."""
    missing = []
    for entry in entries:
        path = entry.get("path")
        phrases = entry.get("phrases") or []
        found = False
        for fp in _artifact_files(workdir, path):
            try:
                content = open(fp, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if all(p.lower() in content.lower() for p in phrases):
                found = True
                break
        if not found:
            missing.append(
                f"artifact: no file matching {path!r} containing all phrases {phrases}")
    return missing


def assert_text(phrases, final_text):
    """Return missing `text` key-phrases (case-insensitive substring)."""
    low = (final_text or "").lower()
    return [f"text: phrase not found: {p!r}" for p in phrases if p.lower() not in low]


def assert_expect(expect, ctx):
    """Return missing descriptions for one typed `expect` block (fails closed)."""
    if ctx.get("parse_error"):
        return [f"event stream parse error: {ctx['parse_error']}"]
    missing = []
    if expect.get("action"):
        missing += assert_action(expect["action"], ctx["events"])
    if expect.get("artifact"):
        missing += assert_artifact(expect["artifact"], ctx["workdir"])
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
    """
    result = get_output(e)
    try:
        ctx = build_context(result)
        missing = assert_eval(e, ctx)
        attempts = 0
        while (missing and attempts < max_retries
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
        passed = not missing
        detail = None
        if missing:
            detail = ("missing: " + " | ".join(missing))[:DETAIL_MAX]
        rec = {
            "kind": "eval",
            "skill": e["skill"],
            "agent": None,
            "model": model or e["model_tier"],
            "outcome": "success" if passed else "failure",
            "eval_pass": passed,
            "detail": detail,
        }
        path = log_run.log_record(rec, logs_dir=logs_dir)
        if quarantine_path:
            if passed:
                quarantine.record_success(quarantine_path, eval_key(e))
            else:
                quarantine.record_failure(quarantine_path, eval_key(e))
        return passed, missing, path
    finally:
        if isinstance(result, EvalResult):
            result.close()


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
    args = ["run", "--dir", tmp]
    if model:
        args += ["--model", model]
    # RM-003 pass 5: capture the newline-delimited JSON event stream so typed
    # `action`/`artifact` predicates can observe tool events (AC21).
    args += ["--format", "json", prompt]
    return args


DIRECT_LANE_PREFIX = "deepseek/"  # user's own API key lane (model-routing.md)


def assert_ci_free_model(model):
    """Model-cost policy (RM-002, amended 2026-09-21 by user directive).

    CI selects only: `*-free` ($0 opencode tier) or the direct-key lane
    (`deepseek/*` — the user's own DeepSeek account, billed directly).
    Rationale: the free-tier gateway's 2026-09-20/21 outage (24h+; free
    models unable to serve even trivial prompts while the direct lane
    stayed healthy) plus the free generalist's inability to pass the
    core canaries made the free tier unfit as the eval substrate. The
    direct-key lane is ~$1-2/month at suite scale — see the 2026-09-21
    budget measurement in the RM-003 plan History.
    """
    if model.endswith("-free") or model.startswith(DIRECT_LANE_PREFIX):
        return
    raise ValueError(
        f"CI model must be `*-free` or the direct-key lane `{DIRECT_LANE_PREFIX}*` "
        f"(Model-cost policy, amended 2026-09-21), got {model!r}"
    )


def invoke_opencode(e, model=None):
    """Real fresh-agent invocation (CI only; needs the model credential).

    The model credential must already be in the environment (repo secret);
    it is consumed here, never echoed.
    """
    tmp = tempfile.mkdtemp(prefix="beval-")
    stall_timeout = int(os.environ.get("BEVAL_TIMEOUT_SECONDS", "240"))
    keep = False
    try:
        for rel in e["files"]:
            src = os.path.join(SKILLS_ROOT, e["skill"], "evals", rel)
            if os.path.exists(src):
                dst = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)
        # The model credential must already be in the environment (repo secret);
        # it is consumed here, never echoed.
        # start_new_session=True: a stalled opencode may leak child processes
        # (zombie `opencode` servers); the whole group must be re-apable, so
        # the TimeoutExpired handler below kills the group, not just the child.
        try:
            proc = subprocess.Popen(
                ["opencode"] + opencode_run_args(tmp, e["prompt"], model=model),
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
            proc.communicate()  # reap the killed group's pipes
            return EvalResult(
                raw=(f"eval stall: subprocess timed out after {stall_timeout}s "
                     f"with no completion (transient; subprocess group killed)"))
        # Keep the workdir: the artifact class reads files the agent wrote
        # there; run_eval closes (removes) it after matching.
        keep = True
        return EvalResult(raw=out, stderr=err, workdir=tmp, cleanup=True)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


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
    p.add_argument("--ci", action="store_true",
                   help="Enforce free-tier-only (skip go/zen evals); also auto-enabled "
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

    def get_output(e):
        if args.event_fixture:
            return load_event_fixture(args.event_fixture)
        if args.stub_output is not None:
            return stub_result(e, args.stub_output, _stub_calls)
        return invoke_opencode(e, model=args.model)

    failed = 0
    for e in selected:
        passed, missing, path = run_eval(e, get_output, logs_dir=args.logs_dir,
                                         model=args.model,
                                         max_retries=args.max_retries,
                                         quarantine_path=quarantine_path)
        status = "PASS" if passed else "FAIL"
        print(f"{status}  {e['skill']}#{e['eval_id']}  -> {path}")
        if not passed:
            failed += 1
            for m in missing:
                print(f"      missing: {m[:120]}")

    if failed:
        print(f"\n{failed} eval(s) failed regression gate", file=sys.stderr)
        return 1
    print("\nall included evals passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
