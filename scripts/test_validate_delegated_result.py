#!/usr/bin/env python3
"""Tests for scripts/validate_delegated_result.py (RM-023).

Run: python3 scripts/test_validate_delegated_result.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
VALIDATOR = os.path.join(HERE, "validate_delegated_result.py")


def run(args, text=None):
    return subprocess.run([sys.executable, VALIDATOR, *args], input=text,
                          capture_output=True, text=True)


def _tmp(content):
    fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
    fh.write(content)
    fh.close()
    return fh.name


def test_list_contracts():
    r = run(["--list-contracts"])
    assert r.returncode == 0, r.stderr
    names = r.stdout.split()
    for name in ("council-lens", "implement-handoff", "design-consult"):
        assert name in names, f"{name} missing from {r.stdout!r}"


def test_empty_is_invalid():
    path = _tmp("   \n\n\t\n")
    try:
        r = run(["--contract", "council-lens", "--file", path])
        assert r.returncode != 0, "empty result passed"
        assert "empty" in r.stdout.lower(), r.stdout
    finally:
        os.unlink(path)


def test_missing_marker_is_invalid_and_names_it():
    path = _tmp("# Lens result\n\n## Findings\n- one\n")
    try:
        r = run(["--contract", "council-lens", "--file", path])
        assert r.returncode != 0, "missing-marker result passed"
        assert "Recommendation" in r.stdout, r.stdout
    finally:
        os.unlink(path)


def test_valid_passes():
    path = _tmp("## Findings\n- one\n\n## Recommendation\n- do x\n")
    try:
        r = run(["--contract", "council-lens", "--file", path])
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        os.unlink(path)


def test_unknown_contract_is_invalid():
    path = _tmp("## Findings\n## Recommendation\n")
    try:
        r = run(["--contract", "no-such-contract", "--file", path])
        assert r.returncode != 0, "unknown contract accepted"
    finally:
        os.unlink(path)


def test_custom_markers_override():
    path = _tmp("alpha here, beta there\n")
    try:
        r = run(["--markers", "alpha,beta", "--file", path])
        assert r.returncode == 0, r.stdout + r.stderr
        r2 = run(["--markers", "alpha,gamma", "--file", path])
        assert r2.returncode != 0 and "gamma" in r2.stdout, r2.stdout
    finally:
        os.unlink(path)


def test_stdin_valid():
    r = run(["--contract", "implement-handoff", "--stdin"],
            text="## Verification\nok\n## Handoff\ndone\n")
    assert r.returncode == 0, r.stdout + r.stderr


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
    print(f"all {len(tests)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
