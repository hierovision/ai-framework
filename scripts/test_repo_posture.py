#!/usr/bin/env python3
"""Hermetic tests for repo/consumer posture (RM-076 P3-7).

Run: python3 scripts/test_repo_posture.py

Mocks live API responses for enabled, drifted, platform-gated accepted,
expired-accepted, retired, and feature-unavailable-without-acceptance cases.
The local-mode guard proves CI cannot trigger `gh` or a socket; its negative
control proves the guard is active.
"""
import contextlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest.mock as mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_repo_posture as posture  # noqa: E402

SCRATCH = os.path.join(REPO, ".scratch", "test-tmp")
INVENTORY = os.path.join(REPO, "reference", "consumer-repos.md")
REGISTER = os.path.join(REPO, "docs", "security", "register.json")


def tempdir():
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(dir=SCRATCH)


def fake_fetch(*, marvin_updates=True, pt_gated=False, pln_archived=True,
               auth_error_repo=None):
    def _fetch(repo, path):
        if auth_error_repo and auth_error_repo in repo:
            raise posture.CheckError("gh api failed: HTTP 401 Bad credentials")
        if repo.endswith("/pln") and path == "":
            return {"archived": pln_archived}
        if path == "vulnerability-alerts":
            return None
        if path == "automated-security-fixes":
            if "marvin-slack" in repo:
                return {"enabled": marvin_updates}
            return {"enabled": True}
        if path == "":
            analysis = {
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "enabled"},
            }
            if pt_gated and "phasetimer" in repo:
                analysis = {}
            return {"archived": False, "security_and_analysis": analysis}
        raise AssertionError(f"unexpected API path: {path}")

    return _fetch


def run_consumers(register=REGISTER, today="2026-12-01", **kwargs):
    with mock.patch.object(posture, "fetch_consumer", fake_fetch(**kwargs)), \
            contextlib.redirect_stdout(io.StringIO()):
        return posture.main([
            "--consumer-inventory", INVENTORY,
            "--register", register, "--today", today,
        ])


@contextlib.contextmanager
def no_gh_no_network():
    def deny_subprocess(*_args, **_kwargs):
        raise AssertionError("gh/subprocess attempted")

    def deny(*_args, **_kwargs):
        raise AssertionError("network attempted")

    with mock.patch.object(posture.subprocess, "run", deny_subprocess), \
            mock.patch.object(socket, "socket", deny), \
            mock.patch.object(socket, "create_connection", deny), \
            mock.patch.object(socket, "getaddrinfo", deny):
        yield


def test_local_mode_is_static_and_skips_live_settings():
    capture = io.StringIO()
    with no_gh_no_network():
        with contextlib.redirect_stdout(capture):
            rc = posture.main(["--local"])
    output = capture.getvalue()
    assert rc == 0, rc
    assert "SKIP — owner-run" in output
    for line in output.splitlines():
        if line.startswith("PASS"):
            lowered = line.lower()
            assert "live " not in lowered, line
            assert "codeql" not in lowered, line
            assert "dependabot alerts" not in lowered, line


def test_local_guard_negative_control():
    try:
        with no_gh_no_network():
            posture.main(["--repo", "hierovision/ai-framework"])
    except AssertionError as exc:
        assert "gh/subprocess attempted" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("framework mode did not reach the guarded gh call")


def test_enabled_fleet_passes():
    assert run_consumers() == 0


def test_drifted_setting_fails():
    assert run_consumers(marvin_updates=False) == 1


def test_platform_gated_accepted_passes():
    assert run_consumers(pt_gated=True) == 0


def test_platform_gated_expired_acceptance_fails():
    assert run_consumers(pt_gated=True, today="2027-03-01") == 1


def test_feature_unavailable_without_acceptance_fails():
    temp = tempdir()
    try:
        with open(REGISTER, encoding="utf-8") as fh:
            register = json.load(fh)
        register["findings"] = [
            row for row in register["findings"] if row["repo"] != "pt"]
        path = os.path.join(temp, "register.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(register, fh)
        assert run_consumers(register=path, pt_gated=True) == 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_retired_repo_must_stay_archived():
    assert run_consumers(pln_archived=True) == 0
    assert run_consumers(pln_archived=False) == 1


def test_authentication_failure_exits_2():
    assert run_consumers(auth_error_repo="marvin-slack") == 2


def main():
    tests = [
        test_local_mode_is_static_and_skips_live_settings,
        test_local_guard_negative_control,
        test_enabled_fleet_passes,
        test_drifted_setting_fails,
        test_platform_gated_accepted_passes,
        test_platform_gated_expired_acceptance_fails,
        test_feature_unavailable_without_acceptance_fails,
        test_retired_repo_must_stay_archived,
        test_authentication_failure_exits_2,
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
