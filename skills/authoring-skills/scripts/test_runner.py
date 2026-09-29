#!/usr/bin/env python3
"""Offline (no-model) tests for run_behavioral_eval.py (RM-002 AC1, AC2, AC4, AC7).

Run: python3 skills/authoring-skills/scripts/test_runner.py
Exit 0 = the gate fails-when-wrong and passes-when-right, and uses RM-001's
log_run.py (single source of truth).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_behavioral_eval.py")

spec = importlib.util.spec_from_file_location("run_behavioral_eval", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)  # also imports RM-001's log_run (AC2)


def _hermetic_env():
    """Env without CI-mode triggers for runner subprocesses.

    GitHub Actions sets CI=true, and the runner infers ci_mode from it
    (`args.ci or AI_FRAMEWORK_FREE_TIER or CI` in run_behavioral_eval.py),
    which filters the synthetic go-tier fixtures out of the selection. These
    tests assert non-CI stub/list behaviour, so they must control the flag
    explicitly — the new CI gate (2026-09-29) exposed two that passed locally
    and failed under CI=true.
    """
    return {k: v for k, v in os.environ.items()
            if k not in ("CI", "AI_FRAMEWORK_FREE_TIER")}



def _make_skills_root():
    root = tempfile.mkdtemp(prefix="beval-skills-")
    # alpha: one normal eval + one deferred eval
    alpha = os.path.join(root, "alpha", "evals")
    os.makedirs(alpha)
    json.dump({
        "default_model_tier": "go",
        "evals": [
            {"id": 1, "prompt": "p", "expected_behavior": ["alpha does X", "alpha does Y"]},
            {"id": 2, "prompt": "p", "expected_behavior": ["alpha deferred Z"], "deferred": True},
        ],
    }, open(os.path.join(alpha, "evals.json"), "w"))
    # beta: one normal eval
    beta = os.path.join(root, "beta", "evals")
    os.makedirs(beta)
    json.dump({
        "evals": [{"id": 1, "prompt": "p", "expected_behavior": ["beta does W"]}],
    }, open(os.path.join(beta, "evals.json"), "w"))
    return root


def _make_marker_skills_root():
    """Skills root exercising the two-tier marker selection (RM-003 pass 4)."""
    root = tempfile.mkdtemp(prefix="beval-markers-")

    def skill(name, evals):
        d = os.path.join(root, name, "evals")
        os.makedirs(d)
        json.dump({"evals": evals}, open(os.path.join(d, "evals.json"), "w"))

    # marked default + core; a non-default sibling
    skill("auth-skill", [
        {"id": 1, "prompt": "p", "expected_behavior": ["auth one"],
         "default": True, "core": True},
        {"id": 2, "prompt": "p", "expected_behavior": ["auth two"]},
    ])
    # marked default only (not a core skill)
    skill("obs-skill", [
        {"id": 1, "prompt": "p", "expected_behavior": ["obs one"], "default": True},
        {"id": 2, "prompt": "p", "expected_behavior": ["obs two"]},
    ])
    # core only, first eval in file order
    skill("core-a", [
        {"id": 1, "prompt": "p", "expected_behavior": ["core a one"], "core": True},
        {"id": 2, "prompt": "p", "expected_behavior": ["core a two"]},
    ])
    # no markers at all -> first-eval fallback
    skill("unmarked", [
        {"id": 1, "prompt": "p", "expected_behavior": ["unmarked one"]},
        {"id": 2, "prompt": "p", "expected_behavior": ["unmarked two"]},
    ])
    return root


def _read_logs(logs_dir):
    recs = []
    if not os.path.isdir(logs_dir):
        return recs
    for fn in os.listdir(logs_dir):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(logs_dir, fn), encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def test_assert_behavior():
    exp = ["A", "B"]
    assert runner.assert_behavior(exp, "A\nB") == []
    assert runner.assert_behavior(exp, "a and b here") == []  # case-insensitive
    miss = runner.assert_behavior(exp, "only A present")
    assert miss == ["B"], miss


FATAL_STREAM = (
    '{"type":"error","timestamp":1,"sessionID":"ses_test",'
    '"error":{"name":"UnknownError","data":{"message":"boom","ref":"err_x"}}}\n'
)


def test_run_eval_pass_and_fail():
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A", "B"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    try:
        passed, missing, path = runner.run_eval(e, lambda _e: "A\nB", logs_dir=d)
        assert passed and not missing
        recs = _read_logs(d)
        assert len(recs) == 1 and recs[0]["eval_pass"] is True
        assert recs[0]["outcome"] == "success"

        passed, missing, path = runner.run_eval(e, lambda _e: "only A", logs_dir=d)
        assert not passed and missing == ["B"]
        recs = _read_logs(d)
        assert recs[-1]["eval_pass"] is False
        assert recs[-1]["outcome"] == "failure"
        assert "B" in (recs[-1]["detail"] or "")
    finally:
        shutil.rmtree(d)


def test_fresh_retry_on_dead_session():
    """2026-09-28: a session that dies with no work gets a fresh-session retry.

    A dead-session stream (only an error event, e.g. provider UnknownError on
    a resumed session) cannot be recovered by resuming; the runner must
    restart in a fresh session, log the retry, and never apply this path to
    content misses.
    """
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    calls = {"n": 0}

    def stub(_e, turn=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return runner.EvalResult(raw=FATAL_STREAM)  # initial session dies
        return runner.EvalResult(raw="A")  # fresh retry succeeds

    old_cont = os.environ.get("BEVAL_MAX_CONTINUATIONS")
    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_CONTINUATIONS"] = "1"
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "1"
    try:
        passed, missing, _ = runner.run_eval(e, stub, logs_dir=d, sleep=lambda _s: None)
        assert passed, missing
        recs = _read_logs(d)
        assert any("fresh retry" in (r.get("detail") or "") for r in recs), recs
        assert calls["n"] == 2, calls  # dead sessions are not nudged; retried fresh
    finally:
        for k, v in (("BEVAL_MAX_CONTINUATIONS", old_cont),
                     ("BEVAL_MAX_FRESH_RETRIES", old_fresh)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(d)


CONTENT_STALL_STREAM = (
    '{"type":"tool","sessionID":"ses_two","part":{"type":"tool","tool":"read",'
    '"state":{"status":"completed","input":{"filePath":"x"}}}}\n'
    '{"type":"text","sessionID":"ses_two","part":{"type":"text","text":"working"}}\n'
)


def test_nudge_applies_to_fresh_session():
    """2026-09-28: a fresh attempt that stalls (0 writes) gets the same nudge."""
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    calls = {"n": 0}

    def stub(_e, turn=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return runner.EvalResult(raw=FATAL_STREAM)          # initial: dead
        if calls["n"] == 2:
            return runner.EvalResult(raw=CONTENT_STALL_STREAM)  # fresh: stalled
        return runner.EvalResult(raw="A")                       # nudged: done

    old_cont = os.environ.get("BEVAL_MAX_CONTINUATIONS")
    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_CONTINUATIONS"] = "1"
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "1"
    try:
        passed, missing, _ = runner.run_eval(e, stub, logs_dir=d)
        assert passed, missing
        recs = _read_logs(d)
        assert any("continuation" in (r.get("detail") or "") for r in recs), recs
        assert calls["n"] == 3, calls
    finally:
        for k, v in (("BEVAL_MAX_CONTINUATIONS", old_cont),
                     ("BEVAL_MAX_FRESH_RETRIES", old_fresh)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(d)


def test_all_turns_persisted_on_failure():
    """2026-09-28: every turn's stream is persisted when an eval fails."""
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()

    def stub(_e, turn=None):
        return runner.EvalResult(raw=FATAL_STREAM)

    old_cont = os.environ.get("BEVAL_MAX_CONTINUATIONS")
    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_CONTINUATIONS"] = "1"
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "1"
    try:
        passed, missing, _ = runner.run_eval(e, stub, logs_dir=d)
        assert not passed
        streams = sorted(os.listdir(os.path.join(d, "eval-streams")))
        assert len(streams) == 2, streams  # initial + fresh (dead -> no nudge)
        assert any("turn0-initial" in s for s in streams), streams
        assert any("turn1-fresh1" in s for s in streams), streams
    finally:
        for k, v in (("BEVAL_MAX_CONTINUATIONS", old_cont),
                     ("BEVAL_MAX_FRESH_RETRIES", old_fresh)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(d)


def test_phrases_survive_whitespace_wrapping():
    """2026-09-28: phrase checks normalize whitespace (markdown line-wraps)."""
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "SKILL.md"), "w") as fh:
            fh.write("name: build\ndescription: x\n\npresent the plan's manual\n"
                     "   validation steps to the user\n")
        ctx = runner.build_context(runner.EvalResult(raw="", workdir=d))
        ok = {"artifact": [{"path": "**/SKILL.md",
                            "phrases": ["manual validation", "name:"]}]}
        assert runner.assert_expect(ok, ctx) == [], runner.assert_expect(ok, ctx)
        bad = {"artifact": [{"path": "**/SKILL.md", "phrases": ["manual sign-off"]}]}
        assert runner.assert_expect(bad, ctx), "different wording must still fail"
        assert runner.assert_text(["manual validation"],
                                  "the manual\nvalidation handoff") == []
    finally:
        shutil.rmtree(d)


def test_cli_pass_branch():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--skills-root", root,
                            "--logs-dir", logs, "--stub-output", "ALL"],
                           capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode == 0, r.stderr
        recs = _read_logs(logs)
        assert len(recs) == 2, f"expected 2 non-deferred records, got {len(recs)}"
        assert all(x["eval_pass"] is True for x in recs)
        print("PASS  stub ALL -> exit 0, eval_pass=true for every included eval")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_cli_fail_branch():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--skills-root", root,
                            "--logs-dir", logs, "--stub-output", ":MISS:"],
                           capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode != 0, "omitting an expected behavior must fail the gate"
        recs = _read_logs(logs)
        assert recs and all(x["eval_pass"] is False for x in recs)
        print("PASS  stub :MISS: -> exit non-zero, eval_pass=false")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_deferred_excluded():
    root = _make_skills_root()
    try:
        evals = runner.load_skill_evals(root)
        included = runner.filter_evals(evals, include_deferred=False)
        ids = [(e["skill"], e["eval_id"]) for e in included]
        assert ("alpha", 2) not in ids, "deferred eval must be excluded by default"
        assert ("alpha", 1) in ids and ("beta", 1) in ids

        # --list omits the deferred eval from the runnable set, but must
        # SURFACE that deferred evals were excluded (no silent coverage drop).
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root],
                           capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode == 0
        assert "included evals: 2" in r.stdout, r.stdout
        assert "alpha#2" not in r.stdout, "deferred eval must not be listed by default"
        assert "deferred: 1 excluded" in r.stdout, \
            "default --list must surface how many deferred evals are excluded"
        print("PASS  deferred eval excluded from default run; --list surfaces the count")
    finally:
        shutil.rmtree(root)


def test_subset_sharding():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        # --limit 1 runs only the first included eval
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root,
                            "--limit", "1"], capture_output=True, text=True, env=_hermetic_env())
        assert "included evals: 1" in r.stdout, r.stdout
        r2 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
                             "--limit", "1", "--stub-output", "ALL"],
                            capture_output=True, text=True, env=_hermetic_env())
        assert r2.returncode == 0, r2.stderr
        recs = _read_logs(logs)
        assert len(recs) == 1, f"--limit 1 must run exactly one eval, got {len(recs)}"

        # --skill beta runs only beta
        logs2 = tempfile.mkdtemp()
        try:
            r3 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs2,
                                 "--skill", "beta", "--stub-output", "ALL"],
                                capture_output=True, text=True, env=_hermetic_env())
            assert r3.returncode == 0, r3.stderr
            recs2 = _read_logs(logs2)
            assert len(recs2) == 1 and recs2[0]["skill"] == "beta"
        finally:
            shutil.rmtree(logs2)
        print("PASS  --limit / --skill shard the run (subset skips the rest)")
    finally:
        shutil.rmtree(root); shutil.rmtree(logs)


def test_ci_free_only():
    root = tempfile.mkdtemp(prefix="beval-ci-")
    try:
        s = os.path.join(root, "s", "evals"); os.makedirs(s)
        json.dump({"evals": [
            {"id": 1, "prompt": "p", "expected_behavior": ["free ok"], "default_model_tier": "free"},
            {"id": 2, "prompt": "p", "expected_behavior": ["go skip"], "default_model_tier": "go"},
            {"id": 3, "prompt": "p", "expected_behavior": ["zen skip"], "default_model_tier": "zen"},
        ]}, open(os.path.join(s, "evals.json"), "w"))
        env = {**os.environ, "AI_FRAMEWORK_FREE_TIER": "1"}
        r = subprocess.run([sys.executable, RUNNER, "--list", "--skills-root", root],
                           capture_output=True, text=True, env=env)
        assert "tier=free" in r.stdout and "tier=go" not in r.stdout and "tier=zen" not in r.stdout, r.stdout
        logs = tempfile.mkdtemp()
        r2 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
                             "--stub-output", "ALL"], capture_output=True, text=True, env=env)
        assert r2.returncode == 0, r2.stderr
        recs = _read_logs(logs)
        assert len(recs) == 1 and recs[0]["model"] == "free", recs
        print("PASS  CI mode (AI_FRAMEWORK_FREE_TIER=1) skips go/zen, runs free only")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_model_flag_and_ci_guard():
    """RM-002 AC5 live gate (2026-09-16): invoke_opencode must SELECT a model.
    opencode's environment default on a fresh CI runner is `big-pickle`
    (disabled at the gateway), so an eval without an explicit --model fails
    every assertion for an infra reason, not a regression. The command must
    carry --model <id>, and CI mode must refuse non-`*-free` models
    (Model-cost policy) and refuse to run model-less.
    """
    args = runner.opencode_run_args("/tmp/x", "prompt p",
                                    model="opencode/nemotron-3-ultra-free")
    assert args == ["run", "--print-logs", "--log-level", "ERROR",
                    "--dir", "/tmp/x",
                    "--model", "opencode/nemotron-3-ultra-free",
                    "--format", "json", "prompt p"], args
    # no model -> no --model flag (opencode default; developer-local runs only)
    args2 = runner.opencode_run_args("/tmp/x", "prompt p", model=None)
    assert "--model" not in args2, args2
    # CI mode must refuse a pay-as-you-go Zen model and refuse to run model-less;
    # the zero-marginal-cost lanes (*-free, opencode-go flat-rate, the legacy
    # deepseek direct-key lane) are accepted (eval lane = Go, 2026-09-29).
    for bad in ("opencode/claude-sonnet-5", "opencode/glm-5.3"):
        try:
            runner.assert_ci_free_model(bad)
            raise SystemExit(f"assert_ci_free_model accepted {bad}")
        except ValueError:
            pass
    runner.assert_ci_free_model("opencode/nemotron-3-ultra-free")  # ok
    runner.assert_ci_free_model("opencode-go/deepseek-v4.1-flash")  # ok (eval lane)
    runner.assert_ci_free_model("deepseek/deepseek-flash")  # ok (legacy direct key)
    print("PASS  --model selects the eval model; CI mode enforces the free/Go lanes")


def test_default_marker_selection_and_fallback():
    """RM-003 AC12: --default resolves exactly one canary per skill.

    A marked skill yields its `"default": true` eval; an unmarked skill falls
    back to the first eval in file order (never empty).
    """
    root = _make_marker_skills_root()
    try:
        evals = runner.load_skill_evals(root)
        sel = runner.filter_evals(evals, default_only=True, skill="auth-skill")
        assert [(e["skill"], e["eval_id"]) for e in sel] == [("auth-skill", 1)], sel
        fallback = runner.filter_evals(evals, default_only=True, skill="unmarked")
        assert [(e["skill"], e["eval_id"]) for e in fallback] == [("unmarked", 1)], fallback
        print("PASS  --default = one canary per skill (marker, else first-eval fallback)")
    finally:
        shutil.rmtree(root)


def test_core_marker_selection():
    """RM-003 AC12: --core resolves exactly the core-marked evals."""
    root = _make_marker_skills_root()
    try:
        evals = runner.load_skill_evals(root)
        sel = runner.filter_evals(evals, core_only=True)
        got = [(e["skill"], e["eval_id"]) for e in sel]
        assert got == [("auth-skill", 1), ("core-a", 1)], got
        print("PASS  --core = exactly the core-marked evals")
    finally:
        shutil.rmtree(root)


def test_selected_path_ignores_limit():
    """RM-003 AC8/AC12: the marker-selected path ignores --limit (sharding only)."""
    root = _make_marker_skills_root()
    try:
        evals = runner.load_skill_evals(root)
        assert len(runner.filter_evals(evals, core_only=True, limit=1)) == 2
        # one per skill, despite --limit 1
        assert len(runner.filter_evals(evals, default_only=True, limit=1)) == 4
        print("PASS  --limit ignored on the --default / --core selected paths")
    finally:
        shutil.rmtree(root)


def test_cli_list_default_and_core():
    """RM-003 AC12: `--list --default` / `--list --core` list the resolved sets."""
    root = _make_marker_skills_root()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--list", "--default",
                            "--skills-root", root], capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode == 0, r.stderr
        default_lines = [l for l in r.stdout.splitlines() if "#" in l]
        assert len(default_lines) == 4, r.stdout  # one per skill (fallback included)
        r2 = subprocess.run([sys.executable, RUNNER, "--list", "--core",
                             "--skills-root", root], capture_output=True, text=True, env=_hermetic_env())
        assert r2.returncode == 0, r2.stderr
        core_lines = [l for l in r2.stdout.splitlines() if "#" in l]
        assert len(core_lines) == 2, r2.stdout
        print("PASS  --list --default / --core list the resolved selections")
    finally:
        shutil.rmtree(root)


def test_repo_core_and_default_markers():
    """RM-003 AC12: the six core skills carry core; the two canaries default."""
    skills_root = os.path.normpath(os.path.join(HERE, "..", ".."))
    evals = runner.load_skill_evals(skills_root)
    core = {e["skill"] for e in evals if e["core"]}
    assert core == {"authoring-skills", "designing-architecture",
                    "implementing-features", "reviewing-code",
                    "triaging-requirements", "writing-unit-tests"}, core
    defaults = {e["skill"] for e in evals if e["default"]}
    assert {"authoring-skills", "observing-runs"} <= defaults, defaults
    print("PASS  repo markers: six core skills carry core; authoring+observing default")


# ---------------------------------------------------------------------------
# RM-003 pass 5: typed-assertion matcher + canary fixture replay (AC20/AC21)
# ---------------------------------------------------------------------------

FIXTURE_ROOT = os.path.normpath(
    os.path.join(HERE, "..", "evals", "fixtures", "event-streams"))

CANARY_KEYS = {
    ("authoring-skills", 2),
    ("observing-runs", 1),
    ("designing-architecture", 1),
    ("implementing-features", 1),
    ("reviewing-code", 1),
    ("triaging-requirements", 1),
    ("writing-unit-tests", 1),
}


def _load_fixture(skill, eval_id):
    d = os.path.join(FIXTURE_ROOT, f"{skill}__{eval_id}")
    assert os.path.isdir(d), f"missing event-stream fixture: {d}"
    raw = open(os.path.join(d, "events.jsonl"), encoding="utf-8").read()
    return runner.EvalResult(raw=raw, workdir=d)


def test_event_stream_parse_and_final_text():
    ctx = runner.build_context(_load_fixture("observing-runs", 1))
    assert ctx["parse_error"] is None, ctx["parse_error"]
    assert "ROI guardrail" in ctx["final_text"], ctx["final_text"]
    calls = runner.extract_tool_calls(ctx["events"])
    assert calls and calls[0]["tool"] == "bash", calls
    assert "log_run.py" in calls[0]["args"]["command"], calls
    print("PASS  parse event stream -> tool calls + final text")


def test_action_predicate():
    ctx = runner.build_context(_load_fixture("observing-runs", 1))
    ok = {"action": [{"tool": "bash", "args": {"command": "*log_run.py*"}}]}
    assert runner.assert_expect(ok, ctx) == [], runner.assert_expect(ok, ctx)
    bad = {"action": [{"tool": "bash", "args": {"command": "*never-runs*"}}]}
    assert runner.assert_expect(bad, ctx), "non-matching command glob must fail"
    bad_tool = {"action": [{"tool": "write"}]}
    assert runner.assert_expect(bad_tool, ctx), "non-matching tool must fail"
    print("PASS  action predicate: matches tool+arg globs, misses otherwise")


def test_artifact_predicate():
    d = tempfile.mkdtemp(prefix="beval-art-")
    try:
        os.makedirs(os.path.join(d, "src", "lib"))
        with open(os.path.join(d, "src", "lib", "offline-queue.ts"), "w") as fh:
            fh.write("export function queueSession() {}\n")
        ctx = runner.build_context(runner.EvalResult(raw="", workdir=d))
        ok = {"artifact": [{"path": "src/lib/offline-queue.ts",
                            "phrases": ["queueSession", "export"]}]}
        assert runner.assert_expect(ok, ctx) == [], runner.assert_expect(ok, ctx)
        bad = {"artifact": [{"path": "src/lib/offline-queue.ts",
                             "phrases": ["nonexistent-phrase"]}]}
        assert runner.assert_expect(bad, ctx), "missing phrase must fail"
        absent = {"artifact": [{"path": "src/lib/absent.ts", "phrases": ["x"]}]}
        assert runner.assert_expect(absent, ctx), "absent file must fail"
        globbed = {"artifact": [{"path": "**/offline-queue.ts",
                                 "phrases": ["queueSession"]}]}
        assert runner.assert_expect(globbed, ctx) == [], runner.assert_expect(globbed, ctx)
        print("PASS  artifact predicate: reads a written file + glob paths")
    finally:
        shutil.rmtree(d)


def test_text_predicate_and_expect_wins():
    # expect wins over legacy expected_behavior: the legacy phrase is absent but
    # the typed text phrase is present.
    stream = '{"type":"text","part":{"type":"text","text":"a typed phrase here"}}\n'
    ctx = runner.build_context(runner.EvalResult(raw=stream))
    e = {"expected_behavior": ["THIS LEGACY PHRASE IS ABSENT"],
         "expect": {"text": ["typed phrase"]}}
    assert runner.assert_eval(e, ctx) == [], runner.assert_eval(e, ctx)
    # Without expect, the legacy text-class path still gates.
    assert runner.assert_eval({"expected_behavior": ["typed phrase"]}, ctx) == []
    assert runner.assert_eval({"expected_behavior": ["absent"]}, ctx), \
        "legacy substring path must still fail on a miss"
    print("PASS  expect wins over legacy; legacy expected_behavior still works as text")


def test_parse_failure_fails_closed():
    e = {"expect": {"text": ["anything"]}}
    ctx = runner.build_context(runner.EvalResult(raw="not json at all\n{oops"))
    missing = runner.assert_eval(e, ctx)
    assert missing and "parse error" in missing[0], missing
    print("PASS  a malformed event stream fails closed for a typed eval")


def test_seven_canaries_replay_fixtures():
    skills_root = os.path.normpath(os.path.join(HERE, "..", ".."))
    evals = runner.load_skill_evals(skills_root)
    by_key = {runner.eval_key(e): e for e in evals}
    for skill, eval_id in sorted(CANARY_KEYS):
        key = f"{skill}#{eval_id}"
        assert key in by_key, f"missing canary {key}"
        e = by_key[key]
        assert isinstance(e.get("expect"), dict) and e["expect"], \
            f"{key} must carry a typed expect block (AC20)"
        ctx = runner.build_context(_load_fixture(skill, eval_id))
        missing = runner.assert_eval(e, ctx)
        assert missing == [], f"{key} fixture did not satisfy its expect: {missing}"
    print("PASS  all seven canaries replay their fixtures through the matcher")


def test_event_fixture_cli():
    # The --default selection resolves the manifest's `default` marker —
    # authoring-skills' canary migrated #1→#2 in RM-003 pass 6 (ADR-0004:
    # the marker is the source of truth), so the replayed fixture is the
    # canary's own harvested/synthetic stream at fixtures/event-streams/
    # authoring-skills__2.
    fixture = os.path.join(FIXTURE_ROOT, "authoring-skills__2")
    logs = tempfile.mkdtemp(prefix="beval-fix-logs-")
    try:
        r = subprocess.run(
            [sys.executable, RUNNER, "--default", "--skill", "authoring-skills",
             "--event-fixture", fixture, "--no-quarantine", "--logs-dir", logs],
            capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode == 0, r.stdout + r.stderr
        assert "authoring-skills#2" in r.stdout and "PASS" in r.stdout, r.stdout
        recs = _read_logs(logs)
        assert recs and recs[-1]["eval_pass"] is True, recs
    finally:
        shutil.rmtree(logs, ignore_errors=True)
    # A stream that does not satisfy the canary must fail the gate.
    empty = tempfile.mkdtemp(prefix="beval-fix-empty-")
    logs2 = tempfile.mkdtemp(prefix="beval-fix-logs2-")
    try:
        with open(os.path.join(empty, "events.jsonl"), "w") as fh:
            fh.write('{"type":"text","part":{"type":"text","text":"unrelated"}}\n')
        r2 = subprocess.run(
            [sys.executable, RUNNER, "--default", "--skill", "authoring-skills",
             "--event-fixture", empty, "--no-quarantine", "--logs-dir", logs2],
            capture_output=True, text=True, env=_hermetic_env())
        assert r2.returncode == 1, r2.stdout + r2.stderr
    finally:
        shutil.rmtree(empty, ignore_errors=True)
        shutil.rmtree(logs2, ignore_errors=True)
    print("PASS  --event-fixture CLI replays a stream with no model/network")


def test_typed_stub_synthesis():
    """AC21: a typed eval passes under --stub-output ALL (stream synthesized).

    Coverage-gate expand (pass 5): the typed matcher must not make the
    hermetic stub path unusable — the stub synthesizes a matching event stream
    + artifact for a typed eval, and :MISS: still fails it.
    """
    root = tempfile.mkdtemp(prefix="beval-typed-")
    try:
        d = os.path.join(root, "typed-skill", "evals")
        os.makedirs(d)
        json.dump({"evals": [{
            "id": 1, "prompt": "p",
            "expect": {
                "action": [{"tool": "bash", "args": {"command": "*log_run.py*"}}],
                "artifact": [{"path": "**/out.md", "phrases": ["hi"]}],
                "text": ["typed text"],
            },
        }]}, open(os.path.join(d, "evals.json"), "w"))
        logs = tempfile.mkdtemp(prefix="beval-typed-logs-")
        r = subprocess.run(
            [sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
             "--stub-output", "ALL", "--no-quarantine"],
            capture_output=True, text=True, env=_hermetic_env())
        assert r.returncode == 0, r.stdout + r.stderr
        recs = _read_logs(logs)
        assert recs and all(x["eval_pass"] is True for x in recs), recs

        logs2 = tempfile.mkdtemp(prefix="beval-typed-logs2-")
        r2 = subprocess.run(
            [sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs2,
             "--stub-output", ":MISS:", "--no-quarantine"],
            capture_output=True, text=True, env=_hermetic_env())
        assert r2.returncode == 1, r2.stdout + r2.stderr
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(logs2, ignore_errors=True)
        print("PASS  typed evals pass under --stub-output ALL and fail under :MISS:")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dead_session_error_signature_in_log():
    """RM-021 (2026-09-28): a dead session's final record is outcome=error
    (infra) with the actual provider signature in `detail`, not the opaque
    "fatal stream", so infra is separable from content misses."""
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "0"
    try:
        passed, missing, _ = runner.run_eval(
            e, lambda _e, turn=None: runner.EvalResult(raw=FATAL_STREAM), logs_dir=d)
        assert not passed
        rec = _read_logs(d)[-1]
        assert rec["outcome"] == "error", rec
        assert "UnknownError" in (rec["detail"] or ""), rec["detail"]
        assert "ref=err_x" in (rec["detail"] or ""), rec["detail"]
    finally:
        if old_fresh is None:
            os.environ.pop("BEVAL_MAX_FRESH_RETRIES", None)
        else:
            os.environ["BEVAL_MAX_FRESH_RETRIES"] = old_fresh
        shutil.rmtree(d)


def test_opencode_run_args_capture_server_logs():
    """RM-021: `opencode run --print-logs --log-level ERROR` so a dead session's
    server-side err_* cause lands on stderr and is persisted."""
    args = runner.opencode_run_args("/tmp/x", "p", model="deepseek/deepseek-flash")
    assert "--print-logs" in args, args
    assert args[args.index("--log-level") + 1] == "ERROR", args


def test_persist_streams_redacts_stderr_and_writes_it():
    """RM-021: the captured server-log stderr is persisted redacted — the
    diagnostic channel never writes the provider key."""
    d = tempfile.mkdtemp()
    os.environ["DEEPSEEK_API_KEY"] = "sk-secret-123"
    try:
        e = {"skill": "alpha", "eval_id": 1}
        res = runner.EvalResult(raw=FATAL_STREAM, stderr="ERROR boom key=sk-secret-123")
        runner._persist_event_streams(d, e, [("initial", res)])
        sd = os.path.join(d, "eval-streams")
        logs = [f for f in os.listdir(sd) if f.endswith("-stderr.log")]
        assert logs, os.listdir(sd)
        body = open(os.path.join(sd, logs[0]), encoding="utf-8").read()
        assert "sk-secret-123" not in body, body
        assert "***" in body, body
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)
        shutil.rmtree(d)


def test_last_record_drives_cli_summary_class():
    """RM-021: the CLI summary reads the final run-log record so an infra death
    prints as `infra error: ...` instead of a phantom `missing:` content miss."""
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "run-x.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"outcome": "error", "detail": "fresh retry 1"}) + "\n")
            fh.write("not json\n")
            fh.write(json.dumps({"outcome": "error",
                                 "detail": "dead session: UnknownError ref=err_z"}) + "\n")
        rec = runner._last_record(p)
        assert rec.get("outcome") == "error", rec
        assert "dead session" in (rec.get("detail") or ""), rec
        assert runner._last_record(os.path.join(d, "absent.jsonl")) == {}
    finally:
        shutil.rmtree(d)


def test_resolved_cause_and_model_resolution_detector():
    """RM-021: the wrapped `UnknownError` stream must resolve to the concrete
    cause from the captured server stderr, and the class must be detectable."""
    cause = runner._resolved_cause(
        'ts level=ERROR run=x message=failed ref=err_1 '
        'error="ProviderModelNotFoundError: Model not found: deepseek/deepseek-flash. Did you mean"')
    assert cause.startswith("ProviderModelNotFoundError: Model not found"), cause
    assert runner._resolved_cause("") == ""
    assert runner.is_model_resolution_error("dead session: UnknownError ref=err_1 (ProviderModelNotFoundError)")
    assert not runner.is_model_resolution_error("missing: text: phrase not found: 'Verdict'")
    # 2026-09-28 weekly run: dead sessions caused by an external_directory
    # auto-reject (the agent reached for a /tmp scratch dir) must also resolve.
    ansi = "\x1b[93m\x1b[1m! \x1b[0mpermission requested: external_directory (/tmp/audit-report-iIL08P/*); auto-rejecting\n"
    cause = runner._resolved_cause(ansi)
    assert cause.startswith("external_directory auto-reject (/tmp/audit-report"), cause
    assert runner.is_model_resolution_error(cause) is False


def test_model_listed_and_preflight_model():
    """RM-021: fail fast (and distinctly) when the model is not in the catalog;
    fail OPEN when the preflight itself cannot run."""
    out = "opencode/x\ndeepseek/deepseek-flash\nopencode/y\n"
    assert runner.model_listed(out, "deepseek/deepseek-flash")
    assert not runner.model_listed(out, "deepseek/deepseek-flash-x")
    original = runner.subprocess.run

    class _P:
        def __init__(self, s):
            self.stdout, self.stderr = s, ""

    try:
        runner.subprocess.run = lambda *a, **k: _P(out)
        assert runner.preflight_model("deepseek/deepseek-flash") == (True, "")
        ok, why = runner.preflight_model("nope/nope")
        assert ok is False and "nope/nope" in why, (ok, why)

        def boom(*a, **k):
            raise OSError("no binary")

        runner.subprocess.run = boom
        ok, why = runner.preflight_model("deepseek/deepseek-flash")
        assert ok is None and "skipped" in why, (ok, why)
    finally:
        runner.subprocess.run = original


def test_fresh_retry_backoff_uses_injected_sleep():
    """RM-021: a fresh retry waits (the dead class is catalog resolution; the
    immediate retries all re-hit it). The injected sleep keeps tests hermetic."""
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    delays = []
    calls = {"n": 0}

    def stub(_e, turn=None):
        calls["n"] += 1
        return runner.EvalResult(raw=FATAL_STREAM if calls["n"] == 1 else "A")

    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "1"
    try:
        passed, missing, _ = runner.run_eval(e, stub, logs_dir=d, sleep=delays.append)
        assert passed, missing
        assert delays == [float(runner.FRESH_RETRY_BACKOFF_SECONDS[0])], delays
    finally:
        if old_fresh is None:
            os.environ.pop("BEVAL_MAX_FRESH_RETRIES", None)
        else:
            os.environ["BEVAL_MAX_FRESH_RETRIES"] = old_fresh
        shutil.rmtree(d)


def test_infra_death_does_not_quarantine_but_content_miss_does():
    """RM-021: a dead session (infra) must not mark an eval flaky; a content
    miss still must."""
    d = tempfile.mkdtemp()
    qp = os.path.join(d, "quarantine.json")
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    old_fresh = os.environ.get("BEVAL_MAX_FRESH_RETRIES")
    os.environ["BEVAL_MAX_FRESH_RETRIES"] = "0"
    try:
        runner.run_eval(e, lambda _e, turn=None: runner.EvalResult(raw=FATAL_STREAM),
                        logs_dir=d, quarantine_path=qp, sleep=lambda _s: None)
        assert "alpha#1" not in runner.quarantine.load(qp), runner.quarantine.load(qp)
        runner.run_eval(e, lambda _e: "xyz", logs_dir=d, quarantine_path=qp,
                        sleep=lambda _s: None)
        assert "alpha#1" in runner.quarantine.load(qp), runner.quarantine.load(qp)
    finally:
        if old_fresh is None:
            os.environ.pop("BEVAL_MAX_FRESH_RETRIES", None)
        else:
            os.environ["BEVAL_MAX_FRESH_RETRIES"] = old_fresh
        shutil.rmtree(d)


def test_eval_record_carries_measured_tokens_and_duration():
    """RM-021 (2026-09-29): a run's record carries MEASURED tokens + wall time,
    so suite cost/time projections come from evidence — never from running the
    full suite to size it. Both step-finish shapes must be counted."""
    stream = (
        '{"type":"step_finish","part":{"type":"step-finish","tokens":{"input":1200,"output":340}}}\n'
        '{"type":"step-finish","part":{"type":"step-finish","tokens":{"input":800,"output":160}}}\n'
        '{"type":"text","part":{"type":"text","text":"A"}}\n'
    )
    e = {"skill": "alpha", "eval_id": 1, "expected_behavior": ["A"], "model_tier": "go"}
    d = tempfile.mkdtemp()
    try:
        def slow_stub(_e, turn=None):
            time.sleep(0.02)  # the timer must cover the model call, not just the tail
            return runner.EvalResult(raw=stream)

        passed, missing, _ = runner.run_eval(
            e, slow_stub, logs_dir=d, sleep=lambda _s: None)
        assert passed, missing
        rec = _read_logs(d)[-1]
        assert rec["tokens_in"] == 2000, rec
        assert rec["tokens_out"] == 500, rec
        assert rec["cost"] == 0.002, rec  # measured, provider-reported
        # Regression: the timer used to start AFTER get_output, so a real call's
        # wall time was ~1 ms. It must cover the invocation.
        assert rec["duration_ms"] >= 20, rec
    finally:
        shutil.rmtree(d)


def main():
    tests = [
        test_assert_behavior,
        test_run_eval_pass_and_fail,
        test_fresh_retry_on_dead_session,
        test_nudge_applies_to_fresh_session,
        test_all_turns_persisted_on_failure,
        test_phrases_survive_whitespace_wrapping,
        test_cli_pass_branch,
        test_cli_fail_branch,
        test_deferred_excluded,
        test_subset_sharding,
        test_ci_free_only,
        test_model_flag_and_ci_guard,
        test_default_marker_selection_and_fallback,
        test_core_marker_selection,
        test_selected_path_ignores_limit,
        test_cli_list_default_and_core,
        test_repo_core_and_default_markers,
        test_event_stream_parse_and_final_text,
        test_action_predicate,
        test_artifact_predicate,
        test_text_predicate_and_expect_wins,
        test_parse_failure_fails_closed,
        test_seven_canaries_replay_fixtures,
        test_event_fixture_cli,
        test_typed_stub_synthesis,
        test_dead_session_error_signature_in_log,
        test_opencode_run_args_capture_server_logs,
        test_persist_streams_redacts_stderr_and_writes_it,
        test_last_record_drives_cli_summary_class,
        test_resolved_cause_and_model_resolution_detector,
        test_model_listed_and_preflight_model,
        test_fresh_retry_backoff_uses_injected_sleep,
        test_infra_death_does_not_quarantine_but_content_miss_does,
        test_eval_record_carries_measured_tokens_and_duration,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
