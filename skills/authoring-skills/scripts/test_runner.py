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

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_behavioral_eval.py")

spec = importlib.util.spec_from_file_location("run_behavioral_eval", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)  # also imports RM-001's log_run (AC2)


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


def test_cli_pass_branch():
    root = _make_skills_root()
    logs = tempfile.mkdtemp()
    try:
        r = subprocess.run([sys.executable, RUNNER, "--skills-root", root,
                            "--logs-dir", logs, "--stub-output", "ALL"],
                           capture_output=True, text=True)
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
                           capture_output=True, text=True)
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
                           capture_output=True, text=True)
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
                            "--limit", "1"], capture_output=True, text=True)
        assert "included evals: 1" in r.stdout, r.stdout
        r2 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs,
                             "--limit", "1", "--stub-output", "ALL"],
                            capture_output=True, text=True)
        assert r2.returncode == 0, r2.stderr
        recs = _read_logs(logs)
        assert len(recs) == 1, f"--limit 1 must run exactly one eval, got {len(recs)}"

        # --skill beta runs only beta
        logs2 = tempfile.mkdtemp()
        try:
            r3 = subprocess.run([sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs2,
                                 "--skill", "beta", "--stub-output", "ALL"],
                                capture_output=True, text=True)
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
    assert args == ["run", "--dir", "/tmp/x",
                    "--model", "opencode/nemotron-3-ultra-free",
                    "--format", "json", "prompt p"], args
    # no model -> no --model flag (opencode default; developer-local runs only)
    args2 = runner.opencode_run_args("/tmp/x", "prompt p", model=None)
    assert "--model" not in args2, args2
    # CI mode must refuse a paid-tier model and refuse to run model-less
    for bad in ("opencode-go/kimi-k3", "opencode/claude-sonnet-5"):
        try:
            runner.assert_ci_free_model(bad)
            raise SystemExit(f"assert_ci_free_model accepted {bad}")
        except ValueError:
            pass
    runner.assert_ci_free_model("opencode/nemotron-3-ultra-free")  # ok
    print("PASS  --model selects the eval model; CI mode enforces *-free only")


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
                            "--skills-root", root], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        default_lines = [l for l in r.stdout.splitlines() if "#" in l]
        assert len(default_lines) == 4, r.stdout  # one per skill (fallback included)
        r2 = subprocess.run([sys.executable, RUNNER, "--list", "--core",
                             "--skills-root", root], capture_output=True, text=True)
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
    ("authoring-skills", 1),
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
    fixture = os.path.join(FIXTURE_ROOT, "authoring-skills__1")
    logs = tempfile.mkdtemp(prefix="beval-fix-logs-")
    try:
        r = subprocess.run(
            [sys.executable, RUNNER, "--default", "--skill", "authoring-skills",
             "--event-fixture", fixture, "--no-quarantine", "--logs-dir", logs],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "authoring-skills#1" in r.stdout and "PASS" in r.stdout, r.stdout
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
            capture_output=True, text=True)
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
            capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        recs = _read_logs(logs)
        assert recs and all(x["eval_pass"] is True for x in recs), recs

        logs2 = tempfile.mkdtemp(prefix="beval-typed-logs2-")
        r2 = subprocess.run(
            [sys.executable, RUNNER, "--skills-root", root, "--logs-dir", logs2,
             "--stub-output", ":MISS:", "--no-quarantine"],
            capture_output=True, text=True)
        assert r2.returncode == 1, r2.stdout + r2.stderr
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(logs2, ignore_errors=True)
        print("PASS  typed evals pass under --stub-output ALL and fail under :MISS:")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    tests = [
        test_assert_behavior,
        test_run_eval_pass_and_fail,
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
