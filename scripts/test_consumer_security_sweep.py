#!/usr/bin/env python3
"""Hermetic tests for the offline consumer security sweep (RM-076 P3-1/P3-2).

Run: python3 scripts/test_consumer_security_sweep.py

Covers the inventory contract, the `--list` golden output, the canonical
golden report, byte determinism, immutable finding identity, consumer views,
partial-fleet rejection, the register gate, and the socket/sanitizer negative
controls.
"""
import contextlib
import copy
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest.mock as mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "consumer-security")
SCRATCH = os.path.join(REPO, ".scratch", "test-tmp")
EXPECTED_SLUGS = [
    "excel-daily-monitor", "marvin-slack", "pln", "pt",
    "paragon-learning-network",
]
EXPECTED_LOCKFILES = {
    "excel-daily-monitor": ["package-lock.json"],
    "marvin-slack": ["package-lock.json"],
    "pln": ["yarn.lock"],
    "pt": ["yarn.lock"],
    "paragon-learning-network": ["pnpm-lock.yaml"],
}


def tempdir():
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(dir=SCRATCH)


def snapshot_path():
    return os.path.join(FIXTURES, "snapshot.json")


def controls_path():
    return os.path.join(FIXTURES, "controls.json")


def build(**kwargs):
    return sweep.build_report(
        FIXTURES, sweep.load_inventory(), controls_path=controls_path(), **kwargs)


@contextlib.contextmanager
def network_guard():
    def deny(*_args, **_kwargs):
        raise AssertionError("network access attempted")
    with mock.patch.object(socket, "socket", deny), \
            mock.patch.object(socket, "create_connection", deny), \
            mock.patch.object(socket, "getaddrinfo", deny):
        yield


def test_inventory_exact_fleet():
    consumers = sweep.load_inventory()
    assert [row["slug"] for row in consumers] == EXPECTED_SLUGS
    records = {row["slug"]: row for row in consumers}
    assert records["pt"]["aliases"] == ["phasetimer"]
    assert records["pt"]["repository"] == "hierovision/phasetimer"
    assert records["pln"]["status"] == "retired"
    assert records["pln"]["sweep_cadence"] == "decommission-only"
    for slug in EXPECTED_SLUGS:
        assert records[slug]["lockfile_paths"] == EXPECTED_LOCKFILES[slug], slug
        if slug != "pln":
            assert records[slug]["status"] == "active"
            assert records[slug]["sweep_cadence"] == "weekly"
    assert sweep.resolve_slug("phasetimer", consumers) == "pt"


def test_list_golden_output():
    proc = subprocess.run([sys.executable, os.path.join(
        HERE, "consumer_security_sweep.py"), "--list"],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "\n".join(EXPECTED_SLUGS) + "\n", repr(proc.stdout)
    proc = subprocess.run([sys.executable, os.path.join(
        HERE, "consumer_security_sweep.py"), "--list", "--json"],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == EXPECTED_SLUGS


def test_golden_report_matches_checked_in_expectation():
    with open(os.path.join(FIXTURES, "expected-sweep.json"),
              encoding="utf-8") as fh:
        expected = json.load(fh)
    assert build() == expected


def test_two_runs_are_byte_identical():
    first = sweep.render_json(build())
    second = sweep.render_json(build())
    assert first == second
    assert sweep.render_markdown(build()) == sweep.render_markdown(build())
    assert sweep.render_json(build()).endswith("\n")


def test_socket_guard_and_negative_control():
    with network_guard():
        report = build()  # must not attempt any socket operation
        assert report["findings"]
    try:
        with network_guard():
            socket.create_connection(("127.0.0.1", 9))
    except AssertionError as exc:
        assert "network access attempted" in str(exc)
    else:  # pragma: no cover - the guard must be demonstrably active
        raise AssertionError("socket guard did not fire on the negative control")


def test_finding_identity_is_immutable():
    baseline = build()
    original = baseline["findings"][0]["sweep_id"]
    with open(snapshot_path(), encoding="utf-8") as fh:
        snapshot = json.load(fh)
    for result in snapshot["results"]:
        for advisory in result["advisories"]:
            advisory["fixed"] = ["9.9.9"]
    temp = tempdir()
    try:
        modified_path = os.path.join(temp, "snapshot.json")
        with open(modified_path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        modified = sweep.build_report(
            FIXTURES, sweep.load_inventory(), controls_path=controls_path(),
            snapshot_path=modified_path)
        assert [f["sweep_id"] for f in modified["findings"]] == \
            [f["sweep_id"] for f in baseline["findings"]]
        assert original == modified["findings"][0]["sweep_id"]
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_consumer_view_is_isolated():
    report = build(consumer="pt")
    assert [row["slug"] for row in report["consumers"]] == ["pt"]
    assert report["findings"]
    assert {finding["repo"] for finding in report["findings"]} == {"pt"}


def test_partial_fleet_input_fails():
    with open(snapshot_path(), encoding="utf-8") as fh:
        snapshot = json.load(fh)
    snapshot["revisions"] = [row for row in snapshot["revisions"]
                             if row["repo"] != "marvin-slack"]
    temp = tempdir()
    try:
        path = os.path.join(temp, "snapshot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        try:
            sweep.build_report(FIXTURES, sweep.load_inventory(),
                               controls_path=controls_path(), snapshot_path=path)
        except sweep.SchemaError as exc:
            assert "marvin-slack" in str(exc)
        else:
            raise AssertionError("partial fleet input was accepted")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_gate_honors_acceptance_and_fails_open_findings():
    with open(os.path.join(FIXTURES, "register.json"), encoding="utf-8") as fh:
        register = json.load(fh)
    report = build()
    failures = sweep.gate_failures(report, register)
    reasons = {(finding["repo"], reason) for finding, reason in failures}
    assert reasons == {("excel-daily-monitor", "open fix"),
                       ("pt", "open fix")}, reasons
    high = [
        (finding, reason) for finding, reason in failures
        if finding["severity"] in ("high", "critical")
    ]
    assert len(high) == 1 and high[0][0]["severity"] == "critical"


def test_expired_acceptance_fails():
    with open(snapshot_path(), encoding="utf-8") as fh:
        snapshot = json.load(fh)
    snapshot["as_of"] = "2027-03-01T00:00:00Z"
    temp = tempdir()
    try:
        path = os.path.join(temp, "snapshot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        report = sweep.build_report(
            FIXTURES, sweep.load_inventory(), controls_path=controls_path(),
            snapshot_path=path)
        with open(os.path.join(FIXTURES, "register.json"),
                  encoding="utf-8") as fh:
            register = json.load(fh)
        failures = sweep.gate_failures(report, register)
        assert "expired acceptance" in {reason for _, reason in failures}
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sanitizer_rejects_secret_and_absolute_path():
    for bad in ("ghp_" + "a" * 36, "/home/owner/secret.txt",
                "sk-" + "b" * 24, "C:\\Users\\owner\\file"):
        try:
            sweep.assert_sanitized(bad, "field")
        except sweep.SchemaError:
            continue
        raise AssertionError(f"sanitizer accepted {bad!r}")
    with open(snapshot_path(), encoding="utf-8") as fh:
        snapshot = json.load(fh)
    snapshot["queries"][0]["package"] = "ghp_" + "c" * 36
    temp = tempdir()
    try:
        path = os.path.join(temp, "snapshot.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        try:
            sweep.build_report(FIXTURES, sweep.load_inventory(),
                               controls_path=controls_path(), snapshot_path=path)
        except sweep.SchemaError:
            pass
        else:
            raise AssertionError("secret-shaped package name reached the report")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_markdown_is_sanitized():
    markdown = sweep.render_markdown(build())
    for needle in ("/home/", "ghp_", "sk-", "BEGIN PRIVATE KEY", "C:\\Users"):
        assert needle not in markdown, needle


def main():
    tests = [
        test_inventory_exact_fleet,
        test_list_golden_output,
        test_golden_report_matches_checked_in_expectation,
        test_two_runs_are_byte_identical,
        test_socket_guard_and_negative_control,
        test_finding_identity_is_immutable,
        test_consumer_view_is_isolated,
        test_partial_fleet_input_fails,
        test_gate_honors_acceptance_and_fails_open_findings,
        test_expired_acceptance_fails,
        test_sanitizer_rejects_secret_and_absolute_path,
        test_markdown_is_sanitized,
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
