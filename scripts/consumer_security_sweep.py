#!/usr/bin/env python3
"""Deterministic offline consumer security sweep (RM-076 P3-1…P3-3, P3-6).

    python3 scripts/consumer_security_sweep.py --list
    python3 scripts/consumer_security_sweep.py --from-audit DIR \
        --out sweep.json --markdown-out sweep.md
    python3 scripts/consumer_security_sweep.py --from-audit DIR \
        --consumer pt --check --fail-on high,critical

The sweep is offline by construction: it reads an OSV snapshot produced by
`scripts/fetch_advisories.py`, sanitized control observations, and the tracked
consumer inventory. It never imports or invokes the advisory fetcher, never
touches the network, and never reads the wall clock — `as_of` and both source
hashes come from the input bytes, so two runs over the same fixtures are
byte-identical.

Findings are immutable. Remediation state (`disposition`, `owner`, `date`,
`review_on`, `note`) lives in the tracked register and is joined by
`sweep_id`; the severity gate reads the register and fails closed on a
missing, invalid, or expired disposition.

Exit codes: 0 = report produced / gate passed; 1 = gate or coverage failure;
2 = the sweep could not run (malformed or missing input).
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DEFAULT_INVENTORY = os.path.join(REPO_ROOT, "reference", "consumer-repos.md")
DEFAULT_REGISTER = os.path.join(REPO_ROOT, "docs", "security", "register.json")

SEVERITIES = ("critical", "high", "medium", "low", "unknown")
SCOPES = ("runtime", "dev")
ORIGINS = ("framework-propagated", "consumer-local")
STATUSES = ("active", "retired")
CADENCES = ("weekly", "decommission-only")
PACKAGE_MANAGERS = ("npm", "yarn", "pnpm")
CONTROL_PREFIXES = {
    "framework/": "framework-propagated",
    "consumer-local/": "consumer-local",
}
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SECRET_SHAPES = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
)
ABSOLUTE_PATH_SHAPES = (
    re.compile(r"^/"),
    re.compile(r"^~[/\\]"),
    re.compile(r"^[A-Za-z]:[\\/]"),
    re.compile(r"(?:^|[/\\])(?:home|Users)[/\\]"),
    re.compile(r"^/tmp/"),
)
INVENTORY_KEYS = {
    "slug", "repository", "aliases", "status", "stack",
    "package_manager", "lockfile_paths", "sweep_cadence",
}
SNAPSHOT_KEYS = {"schema_version", "as_of", "source", "revisions",
                 "queries", "results"}
QUERY_KEYS = {"query_index", "repo", "ecosystem", "package", "installed",
              "scope", "origin", "lockfile", "query"}
RESULT_KEYS = {"query_index", "advisories"}
ADVISORY_KEYS = {"id", "aliases", "severity", "fixed"}
CONTROLS_KEYS = {"schema_version", "controls"}
CONTROL_KEYS = {"repo", "control_id", "severity", "scope", "origin"}
FINDING_ID_KEYS = ("repo", "advisory_id", "control_id", "package", "installed",
                   "severity", "scope", "origin", "lockfile")
REPORT_KEYS = {"schema_version", "as_of", "source", "consumers", "findings"}


class SchemaError(ValueError):
    """Input does not match the closed schema."""


# --------------------------------------------------------------------------
# Sanitization
# --------------------------------------------------------------------------

def sanitization_failure(value):
    """Return a reason string when `value` may not leave the host, else None."""
    for pattern in SECRET_SHAPES:
        if pattern.search(value):
            return "secret-shaped value"
    if "://" not in value:
        for pattern in ABSOLUTE_PATH_SHAPES:
            if pattern.search(value):
                return "absolute local path"
    return None


def assert_sanitized(value, where):
    if not isinstance(value, str):
        raise SchemaError(f"{where}: expected a string, got {type(value).__name__}")
    reason = sanitization_failure(value)
    if reason:
        raise SchemaError(f"{where}: rejected {reason}")


def walk_sanitized(node, where):
    if isinstance(node, str):
        assert_sanitized(node, where)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            walk_sanitized(item, f"{where}[{index}]")
    elif isinstance(node, dict):
        for key, item in node.items():
            assert_sanitized(key, f"{where}.<key>")
            walk_sanitized(item, f"{where}.{key}")


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------

def _closed(obj, keys, where):
    if not isinstance(obj, dict):
        raise SchemaError(f"{where}: expected an object")
    extra = sorted(set(obj) - keys)
    missing = sorted(keys - set(obj))
    if extra:
        raise SchemaError(f"{where}: unknown field(s) {extra}")
    if missing:
        raise SchemaError(f"{where}: missing field(s) {missing}")


def load_inventory(path=DEFAULT_INVENTORY):
    """Parse the single `json consumer-inventory-v1` fenced block."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    blocks, current, info = [], None, ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if current is None:
                current, info = [], stripped[3:].strip()
            else:
                if info:
                    blocks.append((info, "\n".join(current)))
                current = None
        elif current is not None:
            current.append(line)
    inventory_blocks = [body for tag, body in blocks
                        if tag == "json consumer-inventory-v1"]
    if len(inventory_blocks) != 1:
        raise SchemaError(
            f"{path}: expected exactly one 'json consumer-inventory-v1' block, "
            f"found {len(inventory_blocks)}")
    doc = json.loads(inventory_blocks[0])
    _closed(doc, {"schema_version", "consumers"}, "inventory")
    if doc["schema_version"] != 1:
        raise SchemaError("inventory: schema_version must be 1")
    consumers = doc["consumers"]
    if not isinstance(consumers, list) or not consumers:
        raise SchemaError("inventory: consumers must be a non-empty list")
    slugs, aliases = [], set()
    for index, record in enumerate(consumers):
        where = f"inventory.consumers[{index}]"
        _closed(record, INVENTORY_KEYS, where)
        for field in ("slug", "repository", "stack"):
            assert_sanitized(record[field], f"{where}.{field}")
        if not record["slug"] or "/" in record["slug"]:
            raise SchemaError(f"{where}.slug must be a bare slug")
        if record["slug"] in slugs:
            raise SchemaError(f"{where}.slug duplicated: {record['slug']}")
        if record["status"] not in STATUSES:
            raise SchemaError(f"{where}.status invalid: {record['status']}")
        if record["package_manager"] not in PACKAGE_MANAGERS:
            raise SchemaError(
                f"{where}.package_manager invalid: {record['package_manager']}")
        if record["sweep_cadence"] not in CADENCES:
            raise SchemaError(
                f"{where}.sweep_cadence invalid: {record['sweep_cadence']}")
        expected_cadence = ("weekly" if record["status"] == "active"
                            else "decommission-only")
        if record["sweep_cadence"] != expected_cadence:
            raise SchemaError(
                f"{where}: {record['status']} requires cadence "
                f"{expected_cadence}")
        if not (isinstance(record["lockfile_paths"], list)
                and record["lockfile_paths"]):
            raise SchemaError(f"{where}.lockfile_paths must be non-empty")
        for lockfile in record["lockfile_paths"]:
            assert_sanitized(lockfile, f"{where}.lockfile_paths")
            if os.path.isabs(lockfile) or ".." in lockfile.split("/"):
                raise SchemaError(
                    f"{where}.lockfile_paths must be repo-root relative")
        if not isinstance(record["aliases"], list):
            raise SchemaError(f"{where}.aliases must be a list")
        for alias in record["aliases"]:
            assert_sanitized(alias, f"{where}.aliases")
            if alias in aliases:
                raise SchemaError(f"{where}.aliases duplicated: {alias}")
            aliases.add(alias)
        slugs.append(record["slug"])
    clash = sorted(set(slugs) & aliases)
    if clash:
        raise SchemaError(f"inventory: alias collides with slug: {clash}")
    return consumers


def resolve_slug(value, consumers):
    for record in consumers:
        if value == record["slug"]:
            return record["slug"]
    for record in consumers:
        if value in record["aliases"]:
            return record["slug"]
    raise SchemaError(f"unknown consumer slug or alias: {value}")


def active_consumers(consumers):
    return [record for record in consumers if record["status"] == "active"]


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

def _read_json_bytes(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError(f"{path}: not valid UTF-8 JSON ({exc})") from exc


def _check_snapshot(snapshot, consumers, consumer):
    _closed(snapshot, SNAPSHOT_KEYS, "snapshot")
    if snapshot["schema_version"] != 1:
        raise SchemaError("snapshot: schema_version must be 1")
    if not TIMESTAMP_RE.match(snapshot["as_of"]):
        raise SchemaError("snapshot: as_of must be UTC RFC 3339 with Z")
    assert_sanitized(snapshot["source"], "snapshot.source")
    if snapshot["source"] != "https://api.osv.dev/v1/querybatch":
        raise SchemaError(
            "snapshot: source must be the sanctioned OSV batch endpoint")

    revisions = snapshot["revisions"]
    if not isinstance(revisions, list) or not revisions:
        raise SchemaError("snapshot.revisions must be a non-empty list")
    seen = {}
    for index, revision in enumerate(revisions):
        where = f"snapshot.revisions[{index}]"
        _closed(revision, {"repo", "commit"}, where)
        repo = resolve_slug(revision["repo"], consumers)
        if repo in seen:
            raise SchemaError(f"{where}: duplicate revision for {repo}")
        if not REVISION_RE.match(revision["commit"]):
            raise SchemaError(f"{where}.commit must be 40 lowercase hex")
        seen[repo] = revision["commit"]

    required = ([consumer] if consumer else
                [record["slug"] for record in active_consumers(consumers)])
    missing = [slug for slug in required if slug not in seen]
    if missing:
        raise SchemaError(f"snapshot.revisions missing active repo(s): {missing}")

    queries = snapshot["queries"]
    if not isinstance(queries, list):
        raise SchemaError("snapshot.queries must be a list")
    query_order = []
    for index, query in enumerate(queries):
        where = f"snapshot.queries[{index}]"
        _closed(query, QUERY_KEYS, where)
        if query["query_index"] != index:
            raise SchemaError(f"{where}.query_index must be {index}")
        repo = resolve_slug(query["repo"], consumers)
        record = next(r for r in consumers if r["slug"] == repo)
        if record["status"] != "active":
            raise SchemaError(f"{where}: retired repo {repo} cannot carry queries")
        if query["ecosystem"] != "npm":
            raise SchemaError(f"{where}.ecosystem must be npm")
        if query["scope"] not in SCOPES:
            raise SchemaError(f"{where}.scope invalid: {query['scope']}")
        if query["origin"] not in ORIGINS:
            raise SchemaError(f"{where}.origin invalid: {query['origin']}")
        if not query["package"] or not query["installed"]:
            raise SchemaError(f"{where}: package/installed must be non-empty")
        if query["lockfile"] not in record["lockfile_paths"]:
            raise SchemaError(
                f"{where}: lockfile {query['lockfile']} not declared for {repo}")
        assert_sanitized(query["package"], f"{where}.package")
        assert_sanitized(query["installed"], f"{where}.installed")
        assert_sanitized(query["lockfile"], f"{where}.lockfile")
        expected_query = {
            "package": {"ecosystem": "npm", "name": query["package"]},
            "version": query["installed"],
        }
        if query["query"] != expected_query:
            raise SchemaError(f"{where}.query does not match its fields")
        query_order.append((repo, query["package"], query["installed"],
                            query["scope"], query["origin"], query["lockfile"]))
    if query_order != sorted(query_order):
        raise SchemaError("snapshot.queries are not in canonical sorted order")

    results = snapshot["results"]
    if not isinstance(results, list) or len(results) != len(queries):
        raise SchemaError("snapshot.results must have exactly one entry per query")
    for index, result in enumerate(results):
        where = f"snapshot.results[{index}]"
        _closed(result, RESULT_KEYS, where)
        if result["query_index"] != index:
            raise SchemaError(f"{where}.query_index must be {index}")
        advisories = result["advisories"]
        if not isinstance(advisories, list):
            raise SchemaError(f"{where}.advisories must be a list")
        for a_index, advisory in enumerate(advisories):
            a_where = f"{where}.advisories[{a_index}]"
            _closed(advisory, ADVISORY_KEYS, a_where)
            assert_sanitized(advisory["id"], f"{a_where}.id")
            if advisory["severity"] not in SEVERITIES:
                raise SchemaError(f"{a_where}.severity invalid")
            for alias in advisory["aliases"]:
                assert_sanitized(alias, f"{a_where}.aliases")
            for fixed in advisory["fixed"]:
                assert_sanitized(fixed, f"{a_where}.fixed")
            if advisory["aliases"] != sorted(advisory["aliases"]):
                raise SchemaError(f"{a_where}.aliases are not sorted")
            if advisory["fixed"] != sorted(advisory["fixed"]):
                raise SchemaError(f"{a_where}.fixed are not sorted")


def _check_controls(controls, consumers, consumer):
    _closed(controls, CONTROLS_KEYS, "controls")
    if controls["schema_version"] != 1:
        raise SchemaError("controls: schema_version must be 1")
    rows = controls["controls"]
    if not isinstance(rows, list):
        raise SchemaError("controls.controls must be a list")
    seen = set()
    for index, row in enumerate(rows):
        where = f"controls.controls[{index}]"
        _closed(row, CONTROL_KEYS, where)
        repo = resolve_slug(row["repo"], consumers)
        if consumer and repo != consumer:
            continue
        if (repo, row["control_id"]) in seen:
            raise SchemaError(
                f"{where}: duplicate control_id for {repo}: {row['control_id']}")
        seen.add((repo, row["control_id"]))
        if row["severity"] not in SEVERITIES:
            raise SchemaError(f"{where}.severity invalid")
        if row["scope"] not in SCOPES:
            raise SchemaError(f"{where}.scope invalid")
        if row["origin"] not in ORIGINS:
            raise SchemaError(f"{where}.origin invalid")
        prefix_origin = next(
            (origin for prefix, origin in CONTROL_PREFIXES.items()
             if row["control_id"].startswith(prefix)), None)
        if prefix_origin is None:
            raise SchemaError(
                f"{where}.control_id must start with framework/ or consumer-local/")
        if prefix_origin != row["origin"]:
            raise SchemaError(
                f"{where}.origin {row['origin']} disagrees with control_id prefix")


# --------------------------------------------------------------------------
# Report construction
# --------------------------------------------------------------------------

def sweep_id(finding):
    canonical = {key: finding[key] for key in FINDING_ID_KEYS}
    body = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_report(audit_dir, consumers, consumer=None, controls_path=None,
                 snapshot_path=None):
    """Return the sweep report dict. Pure: no clock, no network, no writes."""
    if consumer:
        consumer = resolve_slug(consumer, consumers)
    snapshot_path = snapshot_path or os.path.join(audit_dir, "snapshot.json")
    controls_path = controls_path or os.path.join(audit_dir, "controls.json")
    snapshot_bytes, snapshot = _read_json_bytes(snapshot_path)
    controls_bytes, controls = _read_json_bytes(controls_path)
    _check_snapshot(snapshot, consumers, consumer)
    _check_controls(controls, consumers, consumer)

    revisions = {resolve_slug(row["repo"], consumers): row["commit"]
                 for row in snapshot["revisions"]}
    report_consumers = []
    for record in consumers:
        if consumer and record["slug"] != consumer:
            continue
        report_consumers.append({
            "slug": record["slug"],
            "repository": record["repository"],
            "status": record["status"],
            "audit_status": ("audited" if record["status"] == "active"
                             else "decommission-only"),
            "commit": revisions.get(record["slug"]),
        })

    findings = []
    for query in snapshot["queries"]:
        repo = resolve_slug(query["repo"], consumers)
        if consumer and repo != consumer:
            continue
        advisories = snapshot["results"][query["query_index"]]["advisories"]
        for advisory in advisories:
            finding = {
                "sweep_id": None,
                "repo": repo,
                "advisory_id": advisory["id"],
                "control_id": None,
                "package": query["package"],
                "installed": query["installed"],
                "fixed": list(advisory["fixed"]),
                "severity": advisory["severity"],
                "scope": query["scope"],
                "origin": query["origin"],
                "lockfile": query["lockfile"],
            }
            finding["sweep_id"] = sweep_id(finding)
            findings.append(finding)
    for row in controls["controls"]:
        repo = resolve_slug(row["repo"], consumers)
        if consumer and repo != consumer:
            continue
        finding = {
            "sweep_id": None,
            "repo": repo,
            "advisory_id": None,
            "control_id": row["control_id"],
            "package": None,
            "installed": None,
            "fixed": [],
            "severity": row["severity"],
            "scope": row["scope"],
            "origin": row["origin"],
            "lockfile": None,
        }
        finding["sweep_id"] = sweep_id(finding)
        findings.append(finding)

    by_id = {}
    for finding in findings:
        existing = by_id.get(finding["sweep_id"])
        if existing is not None and existing != finding:
            raise SchemaError(
                f"sweep_id collision: {finding['sweep_id']}")
        by_id[finding["sweep_id"]] = finding
    findings = [by_id[key] for key in sorted(by_id)]

    report = {
        "schema_version": 1,
        "as_of": snapshot["as_of"],
        "source": {
            "kind": "osv-snapshot",
            "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
            "controls_sha256": hashlib.sha256(controls_bytes).hexdigest(),
        },
        "consumers": report_consumers,
        "findings": findings,
    }
    walk_sanitized(report, "report")
    return report


def render_json(report):
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _md(value):
    return str(value).replace("|", "\\|")


def render_markdown(report):
    counts = {row["slug"]: 0 for row in report["consumers"]}
    for finding in report["findings"]:
        counts[finding["repo"]] += 1
    lines = [
        f"# Consumer security sweep — {report['as_of']}",
        "",
        f"Source: {report['source']['kind']}",
        f"Snapshot SHA-256: {report['source']['snapshot_sha256']}",
        f"Controls SHA-256: {report['source']['controls_sha256']}",
        "",
        "## Consumers",
        "",
        "| Slug | Repository | Status | Audit | Commit | Findings |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["consumers"]:
        commit = row["commit"] or "—"
        lines.append(
            f"| {row['slug']} | {row['repository']} | {row['status']} | "
            f"{row['audit_status']} | {commit} | {counts[row['slug']]} |")
    lines += [
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("None.")
    else:
        lines += [
            "| Sweep ID | Repo | Advisory | Control | Package | Installed | "
            "Fixed | Severity | Scope | Origin | Lockfile |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for finding in report["findings"]:
            fixed = ", ".join(finding["fixed"]) or "—"
            lines.append(
                f"| {finding['sweep_id']} | {finding['repo']} | "
                f"{_md(finding['advisory_id'] or '—')} | "
                f"{_md(finding['control_id'] or '—')} | "
                f"{_md(finding['package'] or '—')} | "
                f"{_md(finding['installed'] or '—')} | {_md(fixed)} | "
                f"{finding['severity']} | {finding['scope']} | "
                f"{finding['origin']} | {_md(finding['lockfile'] or '—')} |")
    lines += [
        "",
        "Finding identity is immutable; disposition, owner, review date, and "
        "rationale live in the tracked register (`docs/security/register.json`).",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------

def _threshold_set(fail_on):
    requested = [token.strip() for token in fail_on.split(",") if token.strip()]
    unknown = [token for token in requested if token not in SEVERITIES]
    if unknown:
        raise SchemaError(f"--fail-on has unknown severity: {unknown}")
    if not requested:
        raise SchemaError("--fail-on needs at least one severity")
    return set(requested)


def gate_failures(report, register):
    """Return finding IDs that fail closed under the register dispositions."""
    as_of = report["as_of"][:10]
    rows = {row["sweep_id"]: row for row in register["findings"]}
    failures = []
    for finding in report["findings"]:
        row = rows.get(finding["sweep_id"])
        reason = None
        if row is None:
            reason = "missing disposition"
        elif row.get("disposition") == "accepted":
            review_on = row.get("review_on")
            if not review_on or review_on < as_of:
                reason = "expired acceptance"
        elif row.get("disposition") == "fix":
            reason = "open fix"
        elif row.get("disposition") == "decommission":
            continue  # a valid decommission row passes the threshold gate
        else:
            reason = "invalid disposition"
        if reason:
            failures.append((finding, reason))
    return failures


def coverage_failures(report, register):
    reported = [finding["sweep_id"] for finding in report["findings"]]
    rows = {row["sweep_id"]: row for row in register["findings"]}
    missing = [sid for sid in reported if sid not in rows]
    return missing


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _write(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.tmp-{os.getpid()}"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_register(path):
    _, register = _read_json_bytes(path)
    return register


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--list", action="store_true",
                        help="print canonical slugs, one per line")
    parser.add_argument("--json", action="store_true",
                        help="with --list, print a JSON array")
    parser.add_argument("--from-audit", metavar="DIR")
    parser.add_argument("--snapshot", metavar="PATH",
                        help="override DIR/snapshot.json")
    parser.add_argument("--controls", metavar="PATH",
                        help="control observations (default DIR/controls.json)")
    parser.add_argument("--consumer", metavar="SLUG",
                        help="emit only this consumer (active slugs only)")
    parser.add_argument("--out", metavar="PATH")
    parser.add_argument("--markdown-out", metavar="PATH")
    parser.add_argument("--register", default=DEFAULT_REGISTER,
                        help="disposition register for --check / gate")
    parser.add_argument("--check", action="store_true",
                        help="require register coverage and run the gate")
    parser.add_argument("--fail-on", metavar="LIST",
                        help="comma-separated severities (e.g. high,critical)")
    args = parser.parse_args(argv)

    try:
        consumers = load_inventory(args.inventory)
        if args.list:
            slugs = [record["slug"] for record in consumers]
            if args.json:
                sys.stdout.write(json.dumps(slugs, indent=2) + "\n")
            else:
                for slug in slugs:
                    print(slug)
            return 0
        if not args.from_audit:
            parser.error("--from-audit is required unless --list is used")
        report = build_report(
            args.from_audit,
            consumers,
            consumer=args.consumer,
            controls_path=args.controls,
            snapshot_path=args.snapshot,
        )
        if args.out:
            _write(args.out, render_json(report))
        if args.markdown_out:
            _write(args.markdown_out, render_markdown(report))

        if args.check or args.fail_on:
            register = _load_register(args.register)
            missing = coverage_failures(report, register)
            if missing:
                print(f"REGISTER GAP: {len(missing)} finding(s) have no row",
                      file=sys.stderr)
                for sid in missing:
                    print(f"  {sid}", file=sys.stderr)
                return 1
            if args.fail_on:
                thresholds = _threshold_set(args.fail_on)
                failures = [
                    (finding, reason)
                    for finding, reason in gate_failures(report, register)
                    if finding["severity"] in thresholds
                    or (finding["severity"] == "unknown" and "high" in thresholds)
                ]
                if failures:
                    print(f"SEVERITY GATE: {len(failures)} open finding(s)",
                          file=sys.stderr)
                    for finding, reason in failures:
                        print(f"  {finding['repo']} {finding['severity']} "
                              f"{finding['sweep_id']} — {reason}", file=sys.stderr)
                    return 1
        return 0
    except (SchemaError, OSError) as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
