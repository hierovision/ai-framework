#!/usr/bin/env python3
"""Hermetic tests for the disposition register (RM-076 P3-4/P3-8).

Run: python3 scripts/test_security_register.py

Covers the tracked register, a valid fixture register against the golden sweep,
and focused failures for every required field, duplicates, coverage gaps,
enum/date drift, expiry, invalid decommission, historical rows, and sanitizer
rejections.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_security_register as checker  # noqa: E402
import consumer_security_sweep as sweep  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "consumer-security")
SWEEP_FILE = os.path.join(FIXTURES, "expected-sweep.json")
REGISTER_FILE = os.path.join(FIXTURES, "register.json")
REAL_REGISTER = os.path.join(REPO, "docs", "security", "register.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def base_register():
    return copy.deepcopy(load(REGISTER_FILE))


def sweep_findings():
    _, findings = checker.load_sweep(SWEEP_FILE)
    return findings


def validate(register, findings=True, as_of=None):
    return checker.validate(
        register, sweep.load_inventory(),
        sweep_findings() if findings else None,
        as_of if as_of is not None else "2026-11-07")


def assert_fails(register, needle, **kwargs):
    failures = validate(register, **kwargs)
    assert failures, "expected a failure"
    assert any(needle in failure for failure in failures), \
        f"{needle!r} not in {failures}"


def test_valid_fixture_and_tracked_register():
    assert validate(base_register()) == []
    assert validate(load(REAL_REGISTER), findings=False) == []


def test_every_required_field_is_enforced():
    for field in sorted(checker.ROW_KEYS):
        register = base_register()
        del register["findings"][0][field]
        assert_fails(register, f"missing field(s) ['{field}']")


def test_unknown_field_is_rejected():
    register = base_register()
    register["findings"][0]["extra"] = "nope"
    assert_fails(register, "unknown field(s) ['extra']")


def test_unknown_register_field_is_rejected():
    register = base_register()
    register["generated_by"] = "a tool"
    assert_fails(register, "unknown field(s) ['generated_by']")


def test_duplicate_sweep_id_is_rejected():
    register = base_register()
    register["findings"].append(copy.deepcopy(register["findings"][0]))
    assert_fails(register, "duplicate sweep_id")


def test_missing_coverage_is_rejected():
    register = base_register()
    removed = register["findings"].pop(0)["sweep_id"]
    assert_fails(register, f"finding {removed} has no valid register row")


def test_mismatched_coverage_is_rejected():
    register = base_register()
    register["findings"][0]["repo"] = "marvin-slack"
    assert_fails(register, "does not match the sweep finding")


def test_invalid_enums_and_dates_are_rejected():
    for field, value in (("severity", "urgent"), ("scope", "build"),
                         ("origin", "vendor"), ("disposition", "ignore")):
        register = base_register()
        register["findings"][0][field] = value
        assert_fails(register, f"{field} invalid")
    register = base_register()
    register["findings"][0]["date"] = "2026-13-01"
    assert_fails(register, "invalid calendar date")


def test_acceptance_rules():
    register = base_register()
    accepted = next(row for row in register["findings"]
                    if row["disposition"] == "accepted")
    accepted["review_on"] = None
    assert_fails(register, "accepted requires review_on")

    register = base_register()
    accepted = next(row for row in register["findings"]
                    if row["disposition"] == "accepted")
    accepted["review_on"] = accepted["date"]
    assert_fails(register, "review_on must be later than date")

    register = base_register()
    assert_fails(register, "acceptance expired", as_of="2027-03-01")


def test_fix_requires_null_review_on():
    register = base_register()
    fixed = next(row for row in register["findings"]
                 if row["disposition"] == "fix")
    fixed["review_on"] = "2027-02-05"
    assert_fails(register, "fix requires review_on null")


def test_decommission_only_for_retired_pln():
    register = base_register()
    row = next(row for row in register["findings"]
               if row["disposition"] == "decommission")
    row["repo"] = "pt"
    assert_fails(register, "decommission is valid only for retired pln")


def test_exactly_one_finding_id():
    register = base_register()
    register["findings"][0]["control_id"] = "consumer-local/should-not-be-here"
    assert_fails(register, "exactly one of advisory_id/control_id")
    register = base_register()
    register["findings"][0]["advisory_id"] = None
    assert_fails(register, "exactly one of advisory_id/control_id")


def test_historical_extra_row_stays_valid():
    register = base_register()
    register["findings"].append({
        "sweep_id": "f" * 64,
        "repo": "marvin-slack",
        "advisory_id": "GHSA-historical",
        "control_id": None,
        "severity": "low",
        "scope": "dev",
        "origin": "consumer-local",
        "disposition": "accepted",
        "owner": "hierovision",
        "date": "2026-11-07",
        "review_on": "2027-02-05",
        "note": "Historical row absent from this sweep remains valid.",
    })
    register["findings"].sort(key=lambda row: row["sweep_id"])
    assert validate(register) == []


def test_unsorted_rows_are_rejected():
    register = base_register()
    register["findings"].reverse()
    assert_fails(register, "not sorted by sweep_id")


def test_sanitizer_rejects_secrets_and_paths():
    for note in ("token ghp_" + "a" * 36,
                 "see /home/owner/.env"):
        register = base_register()
        register["findings"][0]["note"] = note
        assert_fails(register, "rejected")


def test_empty_note_and_owner_are_rejected():
    register = base_register()
    register["findings"][0]["note"] = "   "
    assert_fails(register, "note must carry a sanitized rationale")
    register = base_register()
    register["findings"][0]["owner"] = ""
    assert_fails(register, "owner must be non-empty")


def test_cli_exit_codes():
    assert checker.main([]) == 0
    assert checker.main(["--register", REGISTER_FILE,
                         "--sweep", SWEEP_FILE]) == 0
    assert checker.main(["--register", os.path.join(FIXTURES, "missing.json")]) == 2


def main():
    tests = [
        test_valid_fixture_and_tracked_register,
        test_every_required_field_is_enforced,
        test_unknown_field_is_rejected,
        test_unknown_register_field_is_rejected,
        test_duplicate_sweep_id_is_rejected,
        test_missing_coverage_is_rejected,
        test_mismatched_coverage_is_rejected,
        test_invalid_enums_and_dates_are_rejected,
        test_acceptance_rules,
        test_fix_requires_null_review_on,
        test_decommission_only_for_retired_pln,
        test_exactly_one_finding_id,
        test_historical_extra_row_stays_valid,
        test_unsorted_rows_are_rejected,
        test_sanitizer_rejects_secrets_and_paths,
        test_empty_note_and_owner_are_rejected,
        test_cli_exit_codes,
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
