#!/usr/bin/env python3
"""Deterministic tests for eval-report.py + query_runs.py coverage-gaps
(RM-003 AC1, AC3, AC4, AC11).

Run: python3 scripts/test_eval_report.py
Exit 0 = aggregate per-run scores, the four coverage-gap arrays, the green-run
status shape, and the quota projection are correct.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
QUERY = os.path.join(REPO_ROOT, "skills", "observing-runs", "scripts", "query_runs.py")
_SPEC = importlib.util.spec_from_file_location(
    "eval_report", os.path.join(HERE, "eval-report.py"))
report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(report)

_QS = importlib.util.spec_from_file_location("query_runs", QUERY)
query_runs = importlib.util.module_from_spec(_QS)
_QS.loader.exec_module(query_runs)

FIXTURE_LINES = [
    {"ts": "2026-09-17T06:00:00Z", "run_id": "r1", "kind": "eval",
     "skill": "writing-unit-tests", "model": "free", "tokens_in": 800,
     "tokens_out": 300, "duration_ms": 142000, "outcome": "success",
     "eval_pass": True, "detail": None},
    {"ts": "2026-09-17T06:01:00Z", "run_id": "r2", "kind": "eval",
     "skill": "observing-runs", "model": "free", "tokens_in": 700,
     "tokens_out": 250, "duration_ms": 120000, "outcome": "failure",
     "eval_pass": False, "detail": "missing x"},
    {"ts": "2026-09-17T06:02:00Z", "run_id": "r3", "kind": "skill",
     "skill": "writing-unit-tests", "model": None, "tokens_in": None,
     "tokens_out": None, "duration_ms": None, "outcome": "success",
     "eval_pass": None, "detail": None},
]


def _seed_logs(d):
    with open(os.path.join(d, "run-2026-09-17.jsonl"), "w", encoding="utf-8") as fh:
        for line in FIXTURE_LINES:
            fh.write(json.dumps(line) + "\n")


def test_aggregate_report_per_run_scores():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        out = report.aggregate_report(d)
        assert out["aggregate"]["eval_rows"] == 2, out["aggregate"]
        assert out["aggregate"]["eval_passed"] == 1, out["aggregate"]
        assert "writing-unit-tests" in out["per_skill"]
        runs = out["per_skill"]["writing-unit-tests"]
        assert len(runs) == 1 and runs[0]["run_id"] == "r1"
        assert runs[0]["duration_ms"] == 142000 and runs[0]["eval_pass"] is True
        assert len(out["per_skill"]["observing-runs"]) == 1
    finally:
        shutil.rmtree(d)


def test_coverage_gaps_shape_and_quarantine():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        with open(os.path.join(d, "quarantine.json"), "w", encoding="utf-8") as fh:
            json.dump({"writing-unit-tests#3": {
                "fail_count": 3, "first_fail": "2026-09-15",
                "last_fail": "2026-09-17", "status": "quarantined"}}, fh)
        gaps = report.coverage_gaps(d)
        assert set(gaps) == {"zero_eval_skills", "deferred_evals",
                             "free_tier_excluded_evals", "quarantined_evals",
                             "no_default_marker", "deferred_skills",
                             "core_covered", "core_uncovered",
                             "smoke_uncovered", "legacy_assertion_evals",
                             "legacy_assertion_count"}, gaps
        # writing-unit-tests + observing-runs have eval records -> not zero.
        assert "writing-unit-tests" not in gaps["zero_eval_skills"]
        assert "observing-runs" not in gaps["zero_eval_skills"]
        assert "authoring-skills" in gaps["zero_eval_skills"]
        # deferred evals (optimizing-model-routing + validating-against-official-docs).
        deferred_skills = {x["skill"] for x in gaps["deferred_evals"]}
        assert {"optimizing-model-routing", "validating-against-official-docs"} <= deferred_skills
        assert gaps["free_tier_excluded_evals"] == []
        assert gaps["quarantined_evals"][0]["key"] == "writing-unit-tests#3"
        # RM-005 AC4: deferred_skills names registry-declared deferrals —
        # empty today (no skill is deferred), distinct from deferred_evals
        # (eval-level) and from no_default_marker (undeclared gaps).
        assert gaps["deferred_skills"] == [], gaps["deferred_skills"]
    finally:
        shutil.rmtree(d)


def test_query_runs_coverage_gaps_cli():
    d = tempfile.mkdtemp()
    try:
        _seed_logs(d)
        r = subprocess.run([sys.executable, QUERY, "coverage-gaps",
                            "--logs-dir", d], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        gaps = json.loads(r.stdout)
        assert "zero_eval_skills" in gaps and "deferred_evals" in gaps
    finally:
        shutil.rmtree(d)


def test_green_run_status_not_achieved_and_recorded():
    not_achieved = report.green_run_status()
    assert not_achieved["achieved"] is False
    assert "2026-09-21" in not_achieved["reason"]
    assert "35108912831" in not_achieved["reason"]

    achieved = report.green_run_status(
        achieved=True, run_id="123", date="2026-09-21", branch="main",
        duration_min=18.5, all_pass=True, quarantine_flips=0,
        artifact_url="https://example/actions/runs/123")
    assert achieved["achieved"] is True and achieved["run_id"] == "123"
    assert achieved["duration_min"] == 18.5


def test_quota_projection_under_guardrail():
    q = report.quota_projection()
    assert q["guardrail_limit"] == 1800
    assert q["projected_monthly"] == round(
        q["weekly_min_used"] + q["per_change_min_used"], 1)
    assert q["projected_monthly"] < q["guardrail_limit"], q


def test_coverage_gaps_default_and_core_arrays():
    """RM-003 pass 4 / AC3: no_default_marker + core coverage arrays.

    Additive to the three required arrays. The six core skills must resolve a
    core-marked canary; only the two pass-4 canaries carry `default`.
    """
    d = tempfile.mkdtemp()
    try:
        gaps = report.coverage_gaps(d)
        for key in ("no_default_marker", "core_covered",
                    "core_uncovered", "smoke_uncovered"):
            assert key in gaps, (key, gaps)
        covered = {x["skill"] for x in gaps["core_covered"]}
        assert covered == set(query_runs.CORE_SKILLS), covered
        assert gaps["core_uncovered"] == [], gaps["core_uncovered"]
        # default marker rollout: only authoring-skills + observing-runs this pass
        assert "authoring-skills" not in gaps["no_default_marker"]
        assert "observing-runs" not in gaps["no_default_marker"]
        assert "designing-architecture" in gaps["no_default_marker"]
        # core_covered entries name the canary eval id — read back from each
        # manifest's own `core: true` marker (authoring-skills migrated its
        # canary #1→#2 in pass 6; the manifest is the source of truth, not a
        # hardcoded id).
        for item in gaps["core_covered"]:
            manifest = json.load(open(os.path.join(
                HERE, "..", "skills", item["skill"], "evals", "evals.json")))
            marked = [e["id"] for e in manifest.get("evals", [])
                      if isinstance(e, dict) and e.get("core")]
            assert item["eval_id"] in marked, (item, marked)
    finally:
        shutil.rmtree(d)


def test_coverage_gaps_deferred_status():
    """RM-005 AC4: a registry-declared deferral is a state, not a gap.

    A skill with registry status=deferred is excluded from
    `no_default_marker` and named in an explicit `deferred_skills` array;
    an active skill without a `default` marker still shows up there.
    """
    d = tempfile.mkdtemp()
    try:
        sroot = os.path.join(d, "skills")
        for s in ("alpha-active", "beta-deferred"):
            os.makedirs(os.path.join(sroot, s, "evals"))
            with open(os.path.join(sroot, s, "evals", "evals.json"), "w") as fh:
                json.dump({"skill_name": s, "evals": [
                    {"id": 1, "prompt": "p", "expected_behavior": ["x"]}]}, fh)
        registry = {"version": 1, "skills": [
            {"name": "alpha-active", "type": "skill", "owner": "@hierovision",
             "maturity": "L2", "status": "active",
             "boundary_ref": "skills/alpha-active/SKILL.md"},
            {"name": "beta-deferred", "type": "skill", "owner": "@hierovision",
             "maturity": "L1", "status": "deferred",
             "boundary_ref": "skills/beta-deferred/SKILL.md"},
        ], "personas": []}
        gaps = report.coverage_gaps(d, skills_root=sroot, registry=registry)
        assert gaps["no_default_marker"] == ["alpha-active"], gaps
        assert gaps["deferred_skills"] == ["beta-deferred"], gaps
        # without a registry (or absent file) the behavior degrades to the
        # pre-registry shape: no deferred_skills array invention, plain gaps
        gaps2 = report.coverage_gaps(d, skills_root=sroot, registry=None)
        assert sorted(gaps2["no_default_marker"]) == [
            "alpha-active", "beta-deferred"], gaps2
        assert gaps2.get("deferred_skills") in ([], None), gaps2
    finally:
        shutil.rmtree(d)


def test_coverage_gaps_legacy_assertion_backlog():
    """RM-003 pass 5 / AC18: prose-only evals appear in the migration backlog.

    Additive to the three required arrays; the run-log schema is not extended.
    """
    d = tempfile.mkdtemp()
    try:
        gaps = report.coverage_gaps(d)
        assert gaps["legacy_assertion_count"] == len(gaps["legacy_assertion_evals"])
        assert gaps["legacy_assertion_count"] > 0, "the un-migrated evals must be visible"
        backlog = gaps["legacy_assertion_evals"]
        assert all(x["legacy_assertion"] is True for x in backlog)
        keys = {(x["skill"], x["eval_id"]) for x in backlog}
        # The typed canaries are migrated and must NOT be in the backlog.
        for migrated in (("authoring-skills", 1), ("observing-runs", 1),
                         ("designing-architecture", 1), ("implementing-features", 1),
                         ("reviewing-code", 1), ("triaging-requirements", 1),
                         ("writing-unit-tests", 1),
                         # RM-021 batch 3 (2026-09-28) migrated the test trio.
                         ("writing-unit-tests", 2), ("writing-unit-tests", 3),
                         ("writing-unit-tests", 4), ("writing-integration-tests", 1),
                         ("writing-integration-tests", 2), ("writing-integration-tests", 3),
                         ("writing-integration-tests", 4), ("writing-e2e-tests", 1),
                         ("writing-e2e-tests", 2), ("writing-e2e-tests", 3),
                         ("writing-e2e-tests", 4)):
            assert migrated not in keys, migrated
        # A known prose-only eval is present with a migrate-on-touch reason.
        assert ("debugging-test-failures", 1) in keys, sorted(keys)
        entry = next(x for x in backlog
                     if x["skill"] == "debugging-test-failures" and x["eval_id"] == 1)
        assert "migrate on touch" in entry["reason"], entry
    finally:
        shutil.rmtree(d)


def test_failure_taxonomy_splits_infra_and_content():
    """RM-021 (2026-09-28): infra errors (dead sessions) must be separable from
    content misses, with the upstream error signature aggregated by NAME (not
    one entry per ref) and the refs kept as a bounded sample."""
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "run-2026-09-28.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-09-28T06:00:00Z", "run_id": "a",
                                 "kind": "eval", "skill": "alpha", "outcome": "error",
                                 "eval_pass": False,
                                 "detail": "dead session: UnknownError ref=err_1"}) + "\n")
            fh.write(json.dumps({"ts": "2026-09-28T06:01:00Z", "run_id": "b",
                                 "kind": "eval", "skill": "beta", "outcome": "failure",
                                 "eval_pass": False, "detail": "missing: x"}) + "\n")
            fh.write(json.dumps({"ts": "2026-09-28T06:02:00Z", "run_id": "c",
                                 "kind": "eval", "skill": "gamma", "outcome": "success",
                                 "eval_pass": True, "detail": None}) + "\n")
        sd = os.path.join(d, "eval-streams")
        os.makedirs(sd)
        dead = ('{"type":"error","sessionID":"s1","error":{"name":"UnknownError",'
                '"data":{"message":"Unexpected server error.","ref":"err_1"}}}\n')
        acted = ('{"type":"tool_use","sessionID":"s2","part":{"type":"tool","tool":"read",'
                 '"state":{"status":"completed"}}}\n'
                 '{"type":"text","sessionID":"s2","part":{"type":"text","text":"x"}}\n')
        for name, body in (("alpha__1-a.jsonl", dead), ("beta__1-b.jsonl", acted),
                           ("alpha__1-c.jsonl", dead)):
            with open(os.path.join(sd, name), "w", encoding="utf-8") as fh:
                fh.write(body)
        out = report.failure_taxonomy(d)
        assert out["records"] == 3 and out["pass"] == 1, out
        assert out["infra_error"] == 1 and out["content_failure"] == 1, out
        assert out["failure_streams"] == 3, out
        assert out["dead_streams"] == 2 and out["acted_streams"] == 1, out
        assert out["error_signatures"] == {"UnknownError": 2}, out
        assert out["error_ref_count"] == {"UnknownError": 2}, out
        assert out["error_ref_samples"]["UnknownError"][:1] == ["err_1"], out
    finally:
        shutil.rmtree(d)


def test_suite_projection_from_measured_samples():
    """RM-021 (2026-09-29): project tokens/cost/wall-time from measured
    per-eval records (small probe -> extrapolate), with confidence from n."""
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "run-2026-09-29.jsonl"), "w", encoding="utf-8") as fh:
            for i, (ti, to, du) in enumerate([(1000, 200, 60000), (3000, 400, 120000)]):
                fh.write(json.dumps({
                    "ts": "2026-09-29T00:0%d:00Z" % i, "run_id": "r%d" % i,
                    "kind": "eval", "skill": "alpha",
                    "model": "opencode-go/deepseek-v4.1-flash", "outcome": "success",
                    "eval_pass": True, "tokens_in": ti, "tokens_out": to,
                    "duration_ms": du}) + "\n")
        out = report.suite_projection(d, 10, model="opencode-go/deepseek-v4.1-flash",
                                      price_in=0.20, price_out=1.20)
        assert out["samples"] == 2 and out["evals"] == 10, out
        assert out["per_eval"]["tokens_in"] == 2000, out
        assert out["per_eval"]["tokens_out"] == 300, out
        assert out["per_eval"]["duration_ms"] == 90000, out
        assert out["projected"]["tokens_in"] == 20000, out
        assert out["projected"]["wall_minutes"] == 15.0, out
        expected_cost = round(((2000 / 1e6) * 0.20 + (300 / 1e6) * 1.20) * 10, 4)
        assert abs(out["projected"]["cost_usd"] - expected_cost) < 1e-6, out
        assert out["confidence"].startswith("low"), out
        assert report.suite_projection(d, 10, model="nope/other")["samples"] == 0
        # An infra death (outcome=error, ~2s) must not drag the averages down.
        with open(os.path.join(d, "run-2026-09-29.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": "2026-09-29T00:09:00Z", "run_id": "rx", "kind": "eval",
                "skill": "alpha", "model": "opencode-go/deepseek-v4.1-flash",
                "outcome": "error", "eval_pass": False,
                "tokens_in": None, "tokens_out": None, "duration_ms": 2000}) + "\n")
        after = report.suite_projection(d, 10, model="opencode-go/deepseek-v4.1-flash")
        assert after["samples"] == 2, after
        assert after["per_eval"]["duration_ms"] == 90000, after
    finally:
        shutil.rmtree(d)


def main():
    tests = [
        test_aggregate_report_per_run_scores,
        test_coverage_gaps_shape_and_quarantine,
        test_coverage_gaps_default_and_core_arrays,
        test_query_runs_coverage_gaps_cli,
        test_green_run_status_not_achieved_and_recorded,
        test_quota_projection_under_guardrail,
        test_coverage_gaps_deferred_status,
        test_coverage_gaps_legacy_assertion_backlog,
        test_failure_taxonomy_splits_infra_and_content,
        test_suite_projection_from_measured_samples,
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
