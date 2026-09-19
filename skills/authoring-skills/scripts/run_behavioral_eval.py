#!/usr/bin/env python3
"""Run the behavioral (fresh-agent) eval suite and gate on regressions.

For every skill's `evals/evals.json`, launch a fresh agent session with the
skill installed, capture its final output, and assert each
`expected_behavior` entry is present (case-insensitive substring). Any miss
fails the build and writes an `eval_pass=false` run-log record via RM-001's
`log_run.py` (single source of truth — the schema is NOT redefined here).

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
"""
import argparse
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
                "deferred": bool(e.get("deferred", False)),
                "model_tier": e.get("default_model_tier", tier),
                "files": e.get("files", []),
            })
    return out


def eval_key(e):
    """Stable quarantine key for one eval."""
    return f"{e['skill']}#{e['eval_id']}"


def filter_evals(evals, include_deferred=False, limit=None, skill=None,
                 ci_mode=False, quarantined=None, include_quarantine=False):
    """Select the eval set.

    `skill` accepts a single name or a list (repeatable `--skill`), so the
    Layer 3 workflow can run several changed skills in one invocation.
    `quarantined` is a set of `skill#eval_id` keys excluded by default
    (RM-003 AC9); pass `include_quarantine=True` to run them anyway.
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
    if limit is not None:
        out = out[:limit]
    return out


def is_transient(text):
    """True when an eval output/detail carries a transient-failure indicator."""
    return bool(TRANSIENT_RE.search(text or ""))


def assert_behavior(expected, output):
    """Return the list of expected strings NOT found (case-insensitive substring)."""
    out_l = (output or "").lower()
    return [exp for exp in expected if exp.lower() not in out_l]


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
    output = get_output(e)
    missing = assert_behavior(e["expected_behavior"], output)
    attempts = 0
    while missing and attempts < max_retries and is_transient(output):
        delay = RETRY_BACKOFF_SECONDS[min(attempts, len(RETRY_BACKOFF_SECONDS) - 1)]
        attempts += 1
        sleep(delay)
        output = get_output(e)
        missing = assert_behavior(e["expected_behavior"], output)
    passed = not missing
    detail = None
    if missing:
        detail = ("missing expected_behavior: " + " | ".join(missing))[:DETAIL_MAX]
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
    args += [prompt]
    return args


def assert_ci_free_model(model):
    """Model-cost policy (rm-002): CI selects only `*-free` (the $0 tier)."""
    if not model.endswith("-free"):
        raise ValueError(
            f"CI model must be a `*-free` ID (Model-cost policy), got {model!r}"
        )


def invoke_opencode(e, model=None):
    """Real fresh-agent invocation (CI only; needs the model credential).

    The model credential must already be in the environment (repo secret);
    it is consumed here, never echoed.
    """
    tmp = tempfile.mkdtemp(prefix="beval-")
    stall_timeout = int(os.environ.get("BEVAL_TIMEOUT_SECONDS", "240"))
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
            return f"opencode invocation failed: {exc}"
        try:
            out, err = proc.communicate(timeout=stall_timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass  # group already gone
            proc.communicate()  # reap the killed group's pipes
            return (f"eval stall: subprocess timed out after {stall_timeout}s "
                    f"with no completion (transient; subprocess group killed)")
        return out + err
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
                        "(exercises the retry path).")
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
                            include_quarantine=args.include_quarantine)

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
        if args.stub_output is not None:
            if args.stub_output.startswith(":MISS:"):
                # omit the first expected behavior to force a stable failure
                return "\n".join(e["expected_behavior"][1:])
            if args.stub_output.startswith(":FLAKY:"):
                key = eval_key(e)
                n = _stub_calls.get(key, 0)
                _stub_calls[key] = n + 1
                if n == 0:
                    return "error: connection timeout contacting model (transient)"
                return "\n".join(e["expected_behavior"])
            return "\n".join(e["expected_behavior"])  # ALL
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
