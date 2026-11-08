#!/usr/bin/env python3
"""Hermetic tests for sanctioned advisory intake (RM-076 P3-3).

Run: python3 scripts/test_fetch_advisories.py

Covers npm/Yarn-v1/pnpm lockfile readers, mocked OSV transport, provenance and
query/result correlation, the socket guard and its negative control, input
immutability, exact-version framework propagation, and atomic writes.
"""
import contextlib
import hashlib
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
import fetch_advisories as fetch  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "consumer-security")
SCRATCH = os.path.join(REPO, ".scratch", "test-tmp")
COMMITS = {
    "excel-daily-monitor": "1" * 40,
    "marvin-slack": "2" * 40,
    "pt": "3" * 40,
    "paragon-learning-network": "4" * 40,
}
YARN_LOCK = """# yarn lockfile v1

"example-shared@^1.0.0":
  version "1.0.0"
  dependencies:
    example-transitive "^2.0.0"

"example-transitive@^2.0.0":
  version "2.0.0"

"example-tool@^0.1.0":
  version "0.1.0"
  dependencies:
    example-tooling-core "^1.0.0"

"example-tooling-core@^1.0.0":
  version "1.0.0"

"example-ui@^4.0.0":
  version "4.5.6"
"""
PNPM_LOCK = """lockfileVersion: '9.0'

importers:

  .:
    dependencies:
      example-next:
        specifier: ^3.0.0
        version: 3.1.0
    devDependencies:
      example-build:
        specifier: ^1.0.0
        version: 1.0.0

packages:

  example-build@1.0.0:
    resolution: {integrity: sha512-fake}
    dev: true

  example-next@3.1.0:
    resolution: {integrity: sha512-fake}
"""


class Skipped(Exception):
    """An explicit, reported skip; never a silent pass."""


def tempdir():
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(dir=SCRATCH)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def build_audit_tree(root):
    write(os.path.join(root, "excel-daily-monitor", "package.json"), json.dumps({
        "name": "excel-daily-monitor",
        "dependencies": {"example-runtime": "^1.0.0"},
        "devDependencies": {"example-dev": "^0.9.0"},
    }))
    write(os.path.join(root, "excel-daily-monitor", "package-lock.json"),
          json.dumps({
              "lockfileVersion": 3,
              "packages": {
                  "": {"name": "excel-daily-monitor"},
                  "node_modules/example-runtime": {"version": "1.2.3"},
                  "node_modules/example-dev": {"version": "0.9.0",
                                               "dev": True},
              },
          }))
    write(os.path.join(root, "marvin-slack", "package.json"), json.dumps({
        "name": "marvin-slack",
        "dependencies": {"example-slack": "^2.0.0"},
    }))
    write(os.path.join(root, "marvin-slack", "package-lock.json"), json.dumps({
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "marvin-slack"},
            "node_modules/example-slack": {"version": "2.0.0"},
        },
    }))
    write(os.path.join(root, "pt", "package.json"), json.dumps({
        "name": "pt",
        "dependencies": {"example-shared": "^1.0.0",
                         "example-ui": "^4.0.0"},
        "devDependencies": {"example-tool": "^0.1.0"},
    }))
    write(os.path.join(root, "pt", "yarn.lock"), YARN_LOCK)
    write(os.path.join(root, "paragon-learning-network", "package.json"),
          json.dumps({
              "name": "paragon-learning-network",
              "dependencies": {"example-next": "^3.0.0"},
              "devDependencies": {"example-build": "^1.0.0"},
          }))
    write(os.path.join(root, "paragon-learning-network", "pnpm-lock.yaml"),
          PNPM_LOCK)
    write(os.path.join(root, "revisions.json"), json.dumps({
        "schema_version": 1,
        "revisions": [{"repo": slug, "commit": commit}
                      for slug, commit in COMMITS.items()],
    }))


def osv_response(count, advisories=None):
    advisories = advisories or {}
    return {"results": [
        {"vulns": advisories.get(index, [])} for index in range(count)
    ]}


def static_queries(consumers, audit_dir):
    """Extract what build_snapshot would query, without an OSV response."""
    queries = []
    for record in sweep.active_consumers(consumers):
        consumer_dir = os.path.join(audit_dir, record["slug"])
        manifest = fetch.read_manifest(
            os.path.join(consumer_dir, "package.json"))
        runtime, dev = fetch._names_from_manifest(manifest)
        ws_runtime, ws_dev = fetch.read_workspace_manifests(manifest, consumer_dir)
        runtime |= ws_runtime
        dev |= ws_dev
        for lockfile in record["lockfile_paths"]:
            queries.extend(
                fetch.read_lockfile(record["package_manager"],
                                    os.path.join(consumer_dir, lockfile),
                                    runtime, dev))
    return queries


@contextlib.contextmanager
def network_guard():
    def deny(*_args, **_kwargs):
        raise AssertionError("network access attempted")
    with mock.patch.object(socket, "socket", deny), \
            mock.patch.object(socket, "create_connection", deny), \
            mock.patch.object(socket, "getaddrinfo", deny):
        yield


def test_three_lockfile_formats_and_scopes():
    temp = tempdir()
    try:
        build_audit_tree(temp)
        consumers = sweep.load_inventory()
        rows = static_queries(consumers, temp)
        found = {(name, version): scope for name, version, scope in rows}
        assert found[("example-runtime", "1.2.3")] == "runtime"
        assert found[("example-dev", "0.9.0")] == "dev"
        assert found[("example-slack", "2.0.0")] == "runtime"
        assert found[("example-next", "3.1.0")] == "runtime"
        assert found[("example-build", "1.0.0")] == "dev"
        assert found[("example-shared", "1.0.0")] == "runtime"
        assert found[("example-transitive", "2.0.0")] == "runtime"
        assert found[("example-tool", "0.1.0")] == "dev"
        assert found[("example-tooling-core", "1.0.0")] == "dev"
        assert found[("example-ui", "4.5.6")] == "runtime"
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_snapshot_provenance_and_correlation():
    temp = tempdir()
    try:
        build_audit_tree(temp)
        consumers = sweep.load_inventory()
        count = len(static_queries(consumers, temp))
        osv_path = os.path.join(temp, "osv.json")
        write(osv_path, json.dumps(osv_response(count, {
            1: [{"id": "GHSA-test", "aliases": ["CVE-2026-9999"],
                 "database_specific": {"severity": "HIGH"},
                 "affected": [{"package": {"ecosystem": "npm",
                                           "name": "example-runtime"},
                               "ranges": [{"type": "SEMVER",
                                           "events": [{"fixed": "1.2.4"}]}]}]}],
        })))
        snapshot = fetch.build_snapshot(
            temp, consumers, as_of="2026-11-07T00:00:00Z", osv_json=osv_path)
        assert set(snapshot) == {
            "schema_version", "as_of", "source", "revisions", "queries",
            "results"}
        assert snapshot["source"] == "https://api.osv.dev/v1/querybatch"
        assert snapshot["as_of"] == "2026-11-07T00:00:00Z"
        assert snapshot["revisions"] == [
            {"repo": slug, "commit": COMMITS[slug]}
            for slug in sorted(COMMITS)
        ]
        assert len(snapshot["results"]) == len(snapshot["queries"]) == count
        assert [row["query_index"] for row in snapshot["queries"]] == \
            list(range(count))
        assert [row["query_index"] for row in snapshot["results"]] == \
            list(range(count))
        advisory = snapshot["results"][1]["advisories"][0]
        assert advisory == {"id": "GHSA-test",
                            "aliases": ["CVE-2026-9999"],
                            "severity": "high", "fixed": ["1.2.4"]}
        assert all(
            row["advisories"] == []
            for index, row in enumerate(snapshot["results"]) if index != 1)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_osv_fixture_normalizes_allowlisted_fields():
    with open(os.path.join(FIXTURES, "osv-response.json"),
              encoding="utf-8") as fh:
        response = json.load(fh)
    queries = [{"package": "example-dev"},
               {"package": "example-runtime"},
               {"package": "example-slack"}]
    results = fetch._normalize_response(response, queries)
    assert results[0]["advisories"] == []
    assert results[1]["advisories"] == [{
        "id": "GHSA-excel-critical", "aliases": ["CVE-2026-0001"],
        "severity": "critical", "fixed": ["1.2.4"]}]
    assert results[2]["advisories"] == [{
        "id": "GHSA-marvin-high", "aliases": [], "severity": "high",
        "fixed": []}]


def test_socket_guard_and_negative_control():
    temp = tempdir()
    try:
        build_audit_tree(temp)
        consumers = sweep.load_inventory()
        count = len(static_queries(consumers, temp))
        osv_path = os.path.join(temp, "osv.json")
        write(osv_path, json.dumps(osv_response(count)))
        with network_guard():
            snapshot = fetch.build_snapshot(
                temp, consumers, as_of="2026-11-07T00:00:00Z",
                osv_json=osv_path)
            assert len(snapshot["results"]) == count
        try:
            with network_guard():
                fetch._post_batch([{"query": {}}])
        except AssertionError as exc:
            assert "network access attempted" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("transport guard did not fire")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def git_status():
    """Porcelain status of the repository, or None when git is unavailable."""
    try:
        proc = subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                              capture_output=True, text=True, check=False)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _hashes(root):
    digests = {}
    for dirpath, _, filenames in os.walk(root):
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                digests[os.path.relpath(path, root)] = \
                    hashlib.sha256(fh.read()).hexdigest()
    return digests


def test_cli_writes_only_the_explicit_output():
    temp = tempdir()
    try:
        audit = os.path.join(temp, "audit")
        build_audit_tree(audit)
        consumers = sweep.load_inventory()
        count = len(static_queries(consumers, audit))
        osv_path = os.path.join(temp, "osv.json")
        write(osv_path, json.dumps(osv_response(count)))
        out = os.path.join(temp, "out", "snapshot.json")
        before = _hashes(audit)
        rc = fetch.main(["--from-audit", audit, "--out", out, "--dry-run",
                         "--osv-json", osv_path,
                         "--as-of", "2026-11-07T00:00:00Z"])
        assert rc == 0
        assert _hashes(audit) == before, "input files were mutated"
        with open(out, encoding="utf-8") as fh:
            snapshot = json.load(fh)
        assert snapshot["as_of"] == "2026-11-07T00:00:00Z"
        assert not [name for name in os.listdir(temp)
                    if name.startswith(".snapshot-")]
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_dry_run_leaves_git_status_unchanged():
    before = git_status()
    if before is None:
        raise Skipped("git is unavailable; cannot assert a status delta")
    temp = tempdir()
    try:
        audit = os.path.join(temp, "audit")
        build_audit_tree(audit)
        consumers = sweep.load_inventory()
        count = len(static_queries(consumers, audit))
        osv_path = os.path.join(temp, "osv.json")
        write(osv_path, json.dumps(osv_response(count)))
        out = os.path.join(temp, "out", "snapshot.json")
        rc = fetch.main(["--from-audit", audit, "--out", out, "--dry-run",
                         "--osv-json", osv_path,
                         "--as-of", "2026-11-07T00:00:00Z"])
        assert rc == 0
        after = git_status()
        assert after is not None, "git status became unavailable during the run"
        assert before == after, "dry run changed git-visible status"
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_atomic_write_failure_leaves_no_temp():
    temp = tempdir()
    try:
        out = os.path.join(temp, "snapshot.json")
        with mock.patch.object(fetch.os, "replace",
                               side_effect=OSError("disk full")):
            try:
                fetch.write_atomic(out, "{}\n")
            except OSError:
                pass
            else:
                raise AssertionError("write_atomic swallowed a write failure")
        assert not [name for name in os.listdir(temp)
                    if name.startswith(".snapshot-")]
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_framework_propagation_requires_exact_version():
    temp = tempdir()
    try:
        build_audit_tree(temp)
        framework = os.path.join(temp, "framework-lock.json")
        write(framework, json.dumps({
            "lockfileVersion": 3,
            "packages": {
                "node_modules/example-runtime": {"version": "1.2.3"},
                "node_modules/example-dev": {"version": "1.0.0"},
            },
        }))
        consumers = sweep.load_inventory()
        count = len(static_queries(consumers, temp))
        osv_path = os.path.join(temp, "osv.json")
        write(osv_path, json.dumps(osv_response(count)))
        snapshot = fetch.build_snapshot(
            temp, consumers, as_of="2026-11-07T00:00:00Z", osv_json=osv_path,
            framework_lockfiles=[framework])
        origins = {(row["repo"], row["package"]): row["origin"]
                   for row in snapshot["queries"]}
        assert origins[("excel-daily-monitor", "example-runtime")] == \
            "framework-propagated"
        assert origins[("excel-daily-monitor", "example-dev")] == \
            "consumer-local"
        assert origins[("pt", "example-shared")] == "consumer-local"
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_no_package_manager_invocation_in_source():
    with open(fetch.__file__, encoding="utf-8") as fh:
        source = fh.read()
    for command in ('subprocess.run(["npm"', 'subprocess.run(["yarn"',
                    'subprocess.run(["pnpm"', '"install"', '"audit"'):
        assert command not in source, command


def main():
    tests = [
        test_three_lockfile_formats_and_scopes,
        test_snapshot_provenance_and_correlation,
        test_osv_fixture_normalizes_allowlisted_fields,
        test_socket_guard_and_negative_control,
        test_cli_writes_only_the_explicit_output,
        test_dry_run_leaves_git_status_unchanged,
        test_atomic_write_failure_leaves_no_temp,
        test_framework_propagation_requires_exact_version,
        test_no_package_manager_invocation_in_source,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Skipped as exc:
            print(f"SKIP  {test.__name__}: {exc}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
