#!/usr/bin/env python3
"""Structural tests for the scheduled security workflow (RM-076 P3-6/P3-8).

Run: python3 scripts/test_security_workflows.py

Parses `.github/workflows/security.yml` and `ci.yml` — structural only, no
GitHub Actions execution. Asserts the weekly/dispatch-only trigger set, one
shared intake snapshot, four active audit legs plus the retired status, the
main-restricted environment secret boundary, least-privilege permissions,
SHA-pinned actions, `persist-credentials: false`, 30-day retention, the
sanitized artifact allowlist, local-only posture, and absence of PR/issue
creation or consumer code execution. Also canaries the artifact serializer with
secret-shaped values and local paths.
"""
import copy
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

WF_DIR = os.path.join(REPO, ".github", "workflows")
SECURITY = os.path.join(WF_DIR, "security.yml")
CI = os.path.join(WF_DIR, "ci.yml")
FIXTURES = os.path.join(HERE, "fixtures", "consumer-security")
ACTIVE = ["excel-daily-monitor", "marvin-slack", "pt",
          "paragon-learning-network"]
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
ALLOWED_ARTIFACTS = re.compile(
    r"^\.scratch/consumer-security-sweep/artifacts/"
    r"(?:advisories-|sweep-(?:\$\{\{ matrix\.slug \}\}-)?)[^/]*"
    r"(?:\.json|\.md)$")
SIX_MODULES = (
    "test_consumer_security_sweep.py",
    "test_fetch_advisories.py",
    "test_security_register.py",
    "test_security_handoffs.py",
    "test_repo_posture.py",
    "test_security_workflows.py",
)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def triggers(doc):
    return doc.get("on", doc.get(True)) or {}


def job_steps(job):
    return job.get("steps") or []


def all_uses(doc):
    for job in (doc.get("jobs") or {}).values():
        for step in job_steps(job):
            if "uses" in step:
                yield step["uses"]


def all_run_text(doc):
    return "\n".join(
        str(step.get("run", ""))
        for job in (doc.get("jobs") or {}).values()
        for step in job_steps(job))


def upload_steps(doc):
    return [
        step for job in (doc.get("jobs") or {}).values()
        for step in job_steps(job)
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]


def checkout_steps(doc):
    return [
        step for job in (doc.get("jobs") or {}).values()
        for step in job_steps(job)
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]


def test_trigger_set_is_weekly_and_dispatch_only():
    doc = load(SECURITY)
    on = triggers(doc)
    assert "pull_request" not in on and "pull_request_target" not in on, on
    assert set(on) == {"schedule", "workflow_dispatch"}, sorted(on)
    assert on["schedule"] == [{"cron": "0 7 * * 1"}], on["schedule"]


def test_one_intake_and_four_active_audit_legs():
    jobs = load(SECURITY)["jobs"]
    assert set(jobs) == {"intake", "audit", "fleet"}, sorted(jobs)
    matrix = jobs["audit"]["strategy"]["matrix"]["slug"]
    assert matrix == ACTIVE, matrix
    assert "pln" not in matrix, "retired pln must not have an audit leg"
    assert jobs["audit"]["needs"] == "intake"
    assert set(jobs["fleet"]["needs"]) == {"intake", "audit"}
    assert jobs["fleet"]["if"] == "always()"


def test_intake_checkouts_every_active_consumer_read_only():
    doc = load(SECURITY)
    repositories = sorted(
        step["with"]["repository"] for step in checkout_steps(doc)
        if "repository" in step.get("with", {}))
    assert repositories == sorted(
        ["hierovision/excel-daily-monitor", "hierovision/marvin-slack",
         "hierovision/phasetimer",
         "Stonegate-Software/paragon-learning-network"]), repositories
    for step in checkout_steps(doc):
        assert step["with"].get("persist-credentials") is False, step


def test_credential_is_environment_scoped_and_fails_closed():
    jobs = load(SECURITY)["jobs"]
    assert jobs["intake"]["environment"] == "consumer-security"
    for name in ("audit", "fleet"):
        assert "environment" not in jobs[name], name
    secret = "${{ secrets.CONSUMER_SECURITY_READ_TOKEN }}"
    intake_text = json.dumps(jobs["intake"])
    audit_text = json.dumps(jobs["audit"])
    fleet_text = json.dumps(jobs["fleet"])
    assert secret in intake_text
    assert secret not in audit_text and secret not in fleet_text
    fail_closed = "\n".join(
        step.get("run", "") for step in job_steps(jobs["intake"])
        if "Fail closed" in step.get("name", ""))
    assert 'if [ -z "${CONSUMER_SECURITY_READ_TOKEN}" ]' in fail_closed
    assert "exit 1" in fail_closed
    for step in job_steps(jobs["intake"]):
        if "Fail closed" in step.get("name", ""):
            assert step["env"]["CONSUMER_SECURITY_READ_TOKEN"] == secret
            break
    else:  # pragma: no cover
        raise AssertionError("fail-closed credential step missing")


def test_shared_snapshot_and_threshold_gate():
    jobs = load(SECURITY)["jobs"]
    audit_text = json.dumps(jobs["audit"])
    fleet_text = json.dumps(jobs["fleet"])
    intake_name = "consumer-security-intake-${{ github.run_id }}"
    assert intake_name in audit_text and intake_name in fleet_text
    for text in (audit_text, fleet_text):
        assert "--controls docs/security/controls.json" in text
    assert "--consumer" in audit_text and "matrix.slug" in audit_text
    assert "--check --fail-on high,critical" in audit_text
    assert "--check --fail-on high,critical" in fleet_text
    assert "--consumer" not in fleet_text


def test_posture_is_local_only():
    text = json.dumps(load(SECURITY))
    assert "check_repo_posture.py --local" in text
    assert "--consumer-inventory" not in text
    assert "--repo" not in text
    assert "ADMIN" not in text and "GH_PAT" not in text


def test_permissions_are_read_only_and_actions_are_pinned():
    doc = load(SECURITY)
    assert doc["permissions"] == {"contents": "read"}, doc["permissions"]
    for target in all_uses(doc):
        assert SHA_PIN.match(target), target
    assert not re.search(r"@(v\d|main|master)\b", "\n".join(all_uses(doc)))


def test_retention_and_sanitized_artifact_allowlist():
    doc = load(SECURITY)
    uploads = upload_steps(doc)
    assert len(uploads) == 3, len(uploads)
    for step in uploads:
        assert step["with"]["retention-days"] == 30, step
        paths = str(step["with"]["path"]).splitlines()
        for path in paths:
            path = path.strip()
            assert path and ALLOWED_ARTIFACTS.match(path), path
    text = json.dumps(doc)
    for forbidden in ("audit/", "package.json", "lockfile", ".env", ".git"):
        for step in uploads:
            assert forbidden not in str(step["with"]["path"]), (forbidden, step)


def test_no_pr_issue_creation_or_consumer_execution():
    text = all_run_text(load(SECURITY))
    for forbidden in ("gh pr create", "gh issue create", "pull_request",
                      "npm ", "npm\n", "yarn ", "pnpm ", "npm ci",
                      "npm audit", "DEEPSEEK", "OPENCODE", "OPENAI"):
        assert forbidden not in text, forbidden
    for step in upload_steps(load(SECURITY)):
        assert "name" in step["with"]


def test_ci_runs_the_six_modules_and_default_register_check():
    text = all_run_text(load(CI))
    for module in SIX_MODULES:
        assert module in text, module
    assert "python3 scripts/check_security_register.py" in text
    assert "security.yml" not in text  # the scheduled job is not PR-evaluated


def test_artifact_serializer_canaries():
    for bad in ("ghp_" + "a" * 36, "/home/owner/.env",
                "sk-" + "b" * 24, "xoxb-1234567890-abcdef"):
        try:
            sweep.assert_sanitized(bad, "canary")
        except sweep.SchemaError:
            continue
        raise AssertionError(f"serializer accepted canary {bad!r}")

    with open(os.path.join(FIXTURES, "snapshot.json"), encoding="utf-8") as fh:
        snapshot = json.load(fh)
    tampered = copy.deepcopy(snapshot)
    tampered["queries"][0]["package"] = "ghp_" + "c" * 36
    try:
        sweep.build_report(FIXTURES, sweep.load_inventory(),
                           controls_path=os.path.join(
                               FIXTURES, "controls.json"),
                           snapshot_path=_write_temp_snapshot(tampered))
    except sweep.SchemaError:
        pass
    else:
        raise AssertionError("secret-shaped canary reached the serialized report")

    report = sweep.build_report(
        FIXTURES, sweep.load_inventory(),
        controls_path=os.path.join(FIXTURES, "controls.json"))
    rendered = sweep.render_json(report) + sweep.render_markdown(report)
    for canary in ("ghp_", "sk-", "/home/", "C:\\\\Users", ".env"):
        assert canary not in rendered, canary


def _write_temp_snapshot(snapshot):
    scratch = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(scratch, exist_ok=True)
    path = os.path.join(scratch, "workflow-canary-snapshot.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)
    return path


def main():
    tests = [
        test_trigger_set_is_weekly_and_dispatch_only,
        test_one_intake_and_four_active_audit_legs,
        test_intake_checkouts_every_active_consumer_read_only,
        test_credential_is_environment_scoped_and_fails_closed,
        test_shared_snapshot_and_threshold_gate,
        test_posture_is_local_only,
        test_permissions_are_read_only_and_actions_are_pinned,
        test_retention_and_sanitized_artifact_allowlist,
        test_no_pr_issue_creation_or_consumer_execution,
        test_ci_runs_the_six_modules_and_default_register_check,
        test_artifact_serializer_canaries,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
