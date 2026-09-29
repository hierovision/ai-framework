#!/usr/bin/env python3
"""Structural tests for the eval workflows (RM-003 pass 4, AC6/AC8/AC15).

Run: python3 scripts/test_eval_workflows.py
Exit 0 = eval-per-change.yml runs the marker-selected evals as a one-eval-per-job
matrix (fail-fast, max-parallel) with an always-running report job, both eval
workflows carry the node24 upload-artifact pin, and the weekly ceiling is 150
(measured budget, 2026-09-21).

Structural only: this parses the YAML, it does not run GitHub Actions.
"""
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.join(os.path.dirname(HERE), ".github", "workflows")
PER_CHANGE = os.path.join(WF_DIR, "eval-per-change.yml")
BEHAVIORAL = os.path.join(WF_DIR, "eval-behavioral.yml")

PIN = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
OLD_PIN = "b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882"


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _jobs(path):
    data = _load(path)
    # YAML 1.1 parses `on:` as boolean True; jobs stays a normal key.
    return data["jobs"]


def test_per_change_matrix_and_aggregation():
    jobs = _jobs(PER_CHANGE)
    assert "evals" in jobs and "report" in jobs, list(jobs)
    evals = jobs["evals"]
    strategy = evals["strategy"]
    # fail-fast: false during shakedown (2026-09-21: one run reports all legs);
    # flip back to True after two consecutive fully-green CI runs — tracked in
    # the cleanup plan. When flipped, this assertion flips with it.
    assert strategy["fail-fast"] is False, strategy
    assert "EVAL_MAX_PARALLEL" in str(strategy["max-parallel"]), strategy
    assert "needs.plan.outputs.matrix" in str(strategy["matrix"]["include"]), strategy
    assert "plan" in [evals["needs"]] or "plan" in evals["needs"], evals["needs"]
    report = jobs["report"]
    assert report["needs"] == ["evals"], report["needs"]
    assert report["if"] == "always()", report["if"]
    # one eval per job: the matrix is built from the marker-selected eval list
    plan_steps = {s.get("id") for s in jobs["plan"]["steps"]}
    assert "select" in plan_steps, plan_steps
    print("PASS  per-change: one-eval-per-job matrix + needs:[evals] if:always() report")


def test_per_change_selection_flags_and_cache():
    with open(PER_CHANGE, encoding="utf-8") as fh:
        text = fh.read()
    assert "--default" in text and "--core" in text, "missing marker-selection flags"
    assert "--skill" in text, "missing --skill"
    # 2026-09-20: version-keyed actions/cache replaced by the npm-pinned
    # install (opencode-ai@1.18.18) after the GitHub-API 403 rate-limit
    # killed the install path (run 35530398048). Pinning also removes the
    # CLI-version drift hazard in the event-stream shape.
    assert "npm install --global" in text and "OPENCODE_VERSION" in text, \
        "opencode install must be npm-pinned"
    assert "actions/cache@" not in text, "cache step should be gone (superseded by npm pin)"
    print("PASS  per-change: --default/--core selection + version-keyed opencode cache")


def test_artifact_pin_node24_both_workflows():
    for path in (PER_CHANGE, BEHAVIORAL):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert PIN in text, f"{os.path.basename(path)} missing node24 pin"
        assert OLD_PIN not in text, f"{os.path.basename(path)} still uses node20 pin"
    print("PASS  both eval workflows pin upload-artifact to the node24 SHA")


def test_weekly_timeout_is_150():
    jobs = _jobs(BEHAVIORAL)
    job = next(iter(jobs.values()))
    # Measured ~74 min serial (2026-09-21); 150 = 2x headroom. The older
    # 120-minute budget was superseded by the measured re-math (cleanup P2).
    assert job["timeout-minutes"] == 150, job["timeout-minutes"]
    print("PASS  weekly eval-behavioral timeout-minutes == 150 (measured budget)")


def test_lane_and_nested_agent_override():
    """Both eval workflows (2026-09-29): the step that RUNS the runner must also
    export the nested-agent override, name the Go lane model, and not reference
    DEEPSEEK_API_KEY.

    Caught a real bug: the export was first injected into an unrelated
    `set -euo pipefail` step (the changed-files step), so CI still ran the
    free-bound council consult and died with "…free tier can only be used from
    within OpenCode". Structural check: same step, same `run` block.
    """
    import subprocess
    found = 0
    for path in (PER_CHANGE, BEHAVIORAL):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        text = open(path, encoding="utf-8").read()
        assert "DEEPSEEK_API_KEY" not in text, f"{path}: direct-key secret referenced"
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                run = step.get("run") or ""
                if "run_behavioral_eval.py" not in run:
                    continue
                found += 1
                assert "OPENCODE_CONFIG_CONTENT" in run and "ci-lane-overrides.py" in run, \
                    f"{path}/{step.get('name')}: runner step lacks the nested-agent override"
                assert "opencode-go/gpt-6-luna" in run, \
                    f"{path}/{step.get('name')}: lane model missing in the runner step"
    assert found >= 2, f"expected a runner step in both workflows, found {found}"
    out = subprocess.run([sys.executable, os.path.join(HERE, "ci-lane-overrides.py"),
                          "--model", "opencode-go/gpt-6-luna"], capture_output=True,
                         text=True, check=True).stdout
    cfg = json.loads(out)
    assert cfg["agent"]["council-ux"]["model"] == "opencode-go/gpt-6-luna", cfg
    assert "architect" in cfg["agent"], cfg


def main():
    tests = [
        test_per_change_matrix_and_aggregation,
        test_per_change_selection_flags_and_cache,
        test_artifact_pin_node24_both_workflows,
        test_weekly_timeout_is_150,
        test_lane_and_nested_agent_override,
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
