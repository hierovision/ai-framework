#!/usr/bin/env python3
"""Disposition-register verifier (RM-076 P3-4).

    python3 scripts/check_security_register.py
    python3 scripts/check_security_register.py \
        --register scripts/fixtures/consumer-security/register.json \
        --sweep .scratch/rm-076/a.json

The register is the only home of remediation state. Each row joins an
immutable sweep finding by `sweep_id` and records exactly one of `fix`,
`accepted`, or `decommission`, with an owner, a date, and a sanitized note.
`accepted` rows additionally carry a `review_on` later than `date`; the
supplied sweep's `as_of` (or, with no sweep, the register's `as_of`) decides
expiration, never the wall clock.

Coverage is exact in one direction: every finding in a supplied sweep must
appear exactly once. Rows for older, absent findings stay valid as history.
`decommission` is valid only for the retired `pln` repository.

Exit codes: 0 = valid; 1 = register/coverage failure; 2 = unreadable input.
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

DEFAULT_REGISTER = os.path.join(REPO_ROOT, "docs", "security", "register.json")
REGISTER_KEYS = {"schema_version", "as_of", "findings"}
ROW_KEYS = {
    "sweep_id", "repo", "advisory_id", "control_id", "severity", "scope",
    "origin", "disposition", "owner", "date", "review_on", "note",
}
DISPOSITIONS = ("fix", "accepted", "decommission")
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _iso_date(value, where):
    if not isinstance(value, str) or not re.match(DATE_PATTERN, value):
        raise sweep.SchemaError(f"{where}: expected YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise sweep.SchemaError(f"{where}: invalid calendar date ({exc})") from exc
    return value


SWEEP_FINDING_KEYS = set(sweep.FINDING_ID_KEYS) | {"sweep_id", "fixed"}


def load_sweep(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise sweep.SchemaError(f"{path}: not valid UTF-8 JSON ({exc})") from exc
    sweep._closed(report, sweep.REPORT_KEYS, "sweep")
    if report["schema_version"] != 1:
        raise sweep.SchemaError("sweep: schema_version must be 1")
    if not sweep.TIMESTAMP_RE.match(report["as_of"]):
        raise sweep.SchemaError("sweep: as_of must be UTC RFC 3339 with Z")
    findings = {}
    for index, finding in enumerate(report["findings"]):
        where = f"sweep.findings[{index}]"
        if not isinstance(finding, dict):
            raise sweep.SchemaError(f"{where}: expected an object")
        sweep._closed(finding, SWEEP_FINDING_KEYS, where)
        computed = sweep.sweep_id(finding)
        if finding.get("sweep_id") != computed:
            raise sweep.SchemaError(f"{where}: sweep_id does not match its fields")
        if computed in findings:
            raise sweep.SchemaError(f"{where}: duplicate finding {computed}")
        findings[computed] = finding
    order = [finding["sweep_id"] for finding in report["findings"]]
    if order != sorted(order):
        raise sweep.SchemaError("sweep.findings are not sorted by sweep_id")
    return report, findings


def validate(register, consumers, sweep_findings=None, sweep_as_of=None):
    """Return a list of failure strings (empty means valid)."""
    failures = []
    slugs = [record["slug"] for record in consumers]
    retired = {record["slug"] for record in consumers
               if record["status"] == "retired"}

    def fail(message):
        failures.append(message)

    try:
        sweep._closed(register, REGISTER_KEYS, "register")
    except sweep.SchemaError as exc:
        return [str(exc)]
    if register["schema_version"] != 1:
        return ["register: schema_version must be 1"]
    try:
        register_as_of = _iso_date(register["as_of"], "register.as_of")
        rows = register["findings"]
        if not isinstance(rows, list):
            raise sweep.SchemaError("register.findings must be a list")
    except sweep.SchemaError as exc:
        return [str(exc)]

    as_of = sweep_as_of or register_as_of
    order = [row.get("sweep_id") for row in rows if isinstance(row, dict)]
    if all(isinstance(value, str) for value in order) and order != sorted(order):
        fail("register.findings are not sorted by sweep_id")
    seen = {}
    valid_rows = {}
    for index, row in enumerate(rows):
        where = f"register.findings[{index}]"
        try:
            sweep._closed(row, ROW_KEYS, where)
            sweep.walk_sanitized(row, where)
        except sweep.SchemaError as exc:
            fail(str(exc))
            continue
        sid = row["sweep_id"]
        if not isinstance(sid, str) or not re.match(
                r"^[0-9a-f]{64}$", sid):
            fail(f"{where}.sweep_id must be 64 lowercase hex")
            continue
        if sid in seen:
            fail(f"{where}: duplicate sweep_id {sid}")
            continue
        seen[sid] = row

        if row["repo"] not in slugs:
            fail(f"{where}.repo is not a canonical consumer slug: "
                 f"{row['repo']}")
        if row["severity"] not in sweep.SEVERITIES:
            fail(f"{where}.severity invalid: {row['severity']}")
        if row["scope"] not in sweep.SCOPES:
            fail(f"{where}.scope invalid: {row['scope']}")
        if row["origin"] not in sweep.ORIGINS:
            fail(f"{where}.origin invalid: {row['origin']}")
        if row["disposition"] not in DISPOSITIONS:
            fail(f"{where}.disposition invalid: {row['disposition']}")

        advisory, control = row["advisory_id"], row["control_id"]
        if (advisory is None) == (control is None):
            fail(f"{where}: exactly one of advisory_id/control_id must be set")
        if control is not None:
            prefix_origin = next(
                (origin for prefix, origin in sweep.CONTROL_PREFIXES.items()
                 if isinstance(control, str) and control.startswith(prefix)),
                None)
            if prefix_origin is None:
                fail(f"{where}.control_id must start with framework/ or "
                     f"consumer-local/")
            elif prefix_origin != row["origin"]:
                fail(f"{where}: origin disagrees with control_id prefix")

        if not isinstance(row["owner"], str) or not row["owner"].strip():
            fail(f"{where}.owner must be non-empty")
        if not isinstance(row["note"], str) or not row["note"].strip():
            fail(f"{where}.note must carry a sanitized rationale")
        try:
            date = _iso_date(row["date"], f"{where}.date")
        except sweep.SchemaError as exc:
            fail(str(exc))
            continue

        disposition = row["disposition"]
        review_on = row["review_on"]
        if disposition in ("fix", "decommission"):
            if review_on is not None:
                fail(f"{where}: {disposition} requires review_on null")
        elif disposition == "accepted":
            if review_on is None:
                fail(f"{where}: accepted requires review_on")
            else:
                try:
                    review_on = _iso_date(review_on, f"{where}.review_on")
                except sweep.SchemaError as exc:
                    fail(str(exc))
                    continue
                if review_on <= date:
                    fail(f"{where}.review_on must be later than date")
                elif review_on < as_of:
                    fail(f"{where}: acceptance expired on {review_on} "
                         f"(as_of {as_of})")
        if disposition == "decommission":
            if row["repo"] not in retired or row["repo"] != "pln":
                fail(f"{where}: decommission is valid only for retired pln")
        valid_rows[sid] = row

    if sweep_findings is not None:
        for sid in sorted(sweep_findings):
            row = valid_rows.get(sid)
            if row is None:
                fail(f"coverage: finding {sid} has no valid register row")
                continue
            finding = sweep_findings[sid]
            for field in ("repo", "advisory_id", "control_id", "severity",
                          "scope", "origin"):
                if row.get(field) != finding.get(field):
                    fail(f"coverage: row {sid} field {field} does not match "
                         f"the sweep finding")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", default=DEFAULT_REGISTER)
    parser.add_argument("--sweep", metavar="PATH",
                        help="sweep report whose findings must be covered")
    parser.add_argument("--inventory", default=sweep.DEFAULT_INVENTORY)
    args = parser.parse_args(argv)
    try:
        consumers = sweep.load_inventory(args.inventory)
        with open(args.register, "rb") as fh:
            register = json.loads(fh.read().decode("utf-8"))
        sweep_findings, sweep_as_of = None, None
        if args.sweep:
            report, sweep_findings = load_sweep(args.sweep)
            sweep_as_of = report["as_of"][:10]
        failures = validate(register, consumers, sweep_findings, sweep_as_of)
    except (sweep.SchemaError, OSError, UnicodeDecodeError,
            json.JSONDecodeError) as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 2
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"\nREGISTER INVALID: {len(failures)} problem(s)")
        return 1
    print(f"OK: register valid ({len(register['findings'])} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
