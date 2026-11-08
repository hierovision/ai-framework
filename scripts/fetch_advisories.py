#!/usr/bin/env python3
"""Sanctioned advisory intake — the only advisory-network step (RM-076 P3-3).

    python3 scripts/fetch_advisories.py --dry-run \
        --from-audit .scratch/consumer-security-sweep/audit \
        --out .scratch/consumer-security-sweep/audit/snapshot.json

Reads each active consumer's `package.json`, its inventory-declared root
lockfile, and the workspace manifests that lockfile references. It never
installs, resolves, audits, fixes, or executes a package manager. The only
network traffic is a POST to the OSV batch endpoint
(`https://api.osv.dev/v1/querybatch`); everything else is local file IO.

Dry-run is the only mode. It permits exactly one write: the explicit `--out`
snapshot. Manifests, lockfiles, package-manager state, and git-visible status
do not change. `--osv-json PATH` is the mocked-transport seam used by the
hermetic tests (it also runs the real parser and serializer without a socket).

The snapshot is allowlisted: `schema_version`, `as_of`, `source`, `revisions`,
`queries`, `results`. Verbose OSV bodies, references, headers, and response
metadata are dropped before serialization.

Exit codes: 0 = snapshot written; 2 = intake could not run (bad input,
missing lockfile, transport failure).
"""
import argparse
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

INVENTORY = sweep.DEFAULT_INVENTORY
OSV_ENDPOINT = "https://api.osv.dev/v1/querybatch"
OSV_MAX_BATCH = 1000
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
FRAMEWORK_LOCKFILES = (
    os.path.join("skills", "auditing-accessibility", "package-lock.json"),
    os.path.join("skills", "capturing-ui-evidence", "package-lock.json"),
    os.path.join("skills", "validating-ui", "package-lock.json"),
)
SEVERITY_ORDER = ("critical", "high", "medium", "low", "unknown")


class IntakeError(RuntimeError):
    """Intake cannot produce a trustworthy snapshot."""


# --------------------------------------------------------------------------
# Lockfile readers
# --------------------------------------------------------------------------

def _names_from_manifest(manifest):
    runtime, dev = set(), set()
    for key in ("dependencies", "optionalDependencies", "peerDependencies"):
        runtime.update((manifest.get(key) or {}).keys())
    dev.update((manifest.get("devDependencies") or {}).keys())
    return runtime, dev


def read_manifest(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"{path}: cannot read package manifest ({exc})") from exc


def read_npm_lock(path):
    """Return [(name, version, scope)] from package-lock v1/v2/v3."""
    doc = read_manifest(path)
    packages = doc.get("packages")
    rows = []
    if isinstance(packages, dict):
        for key, entry in packages.items():
            if not key or not isinstance(entry, dict):
                continue
            if "node_modules/" not in key:
                continue  # workspace root records carry no installed package
            name = key.rsplit("node_modules/", 1)[1]
            version = entry.get("version")
            if not name or not version:
                continue
            scope = "dev" if entry.get("dev") is True else "runtime"
            rows.append((name, str(version), scope))
        return rows

    def walk(dependencies, dev=False):
        for name, entry in (dependencies or {}).items():
            if not isinstance(entry, dict):
                continue
            version = entry.get("version")
            entry_dev = dev or entry.get("dev") is True
            if name and version:
                rows.append((name, str(version),
                             "dev" if entry_dev else "runtime"))
            walk(entry.get("dependencies"), entry_dev)

    walk(doc.get("dependencies"))
    return rows


_YARN_KEY = re.compile(r'"?(?P<spec>[^",\s]+)"?')
_YARN_NAME = re.compile(r"^(?P<name>@[^@/]+/[^@]+|[^@]+)@")
_YARN_VERSION = re.compile(r'^\s+version\s+"(?P<version>[^"]+)"')
_YARN_DEP = re.compile(r'^\s{4}"?(?P<name>@[^@\s"]+/[^@\s"]+|[^@\s"]+)"?\s')


def read_yarn_lock(path, runtime_seeds, dev_seeds):
    """Return [(name, version, scope)] from a Yarn v1 lockfile."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise IntakeError(f"{path}: cannot read yarn.lock ({exc})") from exc
    blocks = []
    current = None
    for line in lines:
        if line and not line.startswith((" ", "\t", "#")):
            specs = [match.group("spec")
                     for match in _YARN_KEY.finditer(line.rstrip(":"))]
            names = set()
            for spec in specs:
                found = _YARN_NAME.match(spec)
                if found:
                    names.add(found.group("name"))
            current = {"names": sorted(names), "version": None, "deps": {}}
            blocks.append(current)
            continue
        if current is None:
            continue
        version = _YARN_VERSION.match(line)
        if version:
            current["version"] = version.group("version")
            continue
        dependency = _YARN_DEP.match(line)
        if dependency and current["version"] is not None:
            current["deps"].setdefault(current["version"], set()).add(
                dependency.group("name"))
            continue
    edges = {}
    versions = {}
    for block in blocks:
        if not block["version"]:
            continue
        for name in block["names"]:
            versions.setdefault(name, set()).add(block["version"])
            edges.setdefault(name, set()).update(
                block["deps"].get(block["version"], set()))
    if not versions:
        return []

    def reach(seeds):
        seen, stack = set(), list(seeds)
        while stack:
            name = stack.pop()
            if name in seen or name not in versions:
                continue
            seen.add(name)
            stack.extend(edges.get(name, ()))
        return seen

    runtime = reach(runtime_seeds)
    dev = reach(dev_seeds)
    rows = []
    for name, found_versions in versions.items():
        scope = "dev" if name in dev and name not in runtime else "runtime"
        for version in sorted(found_versions):
            rows.append((name, version, scope))
    return rows


def _pnpm_entry(key):
    key = key.strip().strip("'\"")
    key = re.sub(r"\(.*\)$", "", key) if key.endswith(")") else key
    if key.startswith("/"):
        body = key[1:]
        if body.startswith("@"):
            parts = body.rsplit("/", 1)
        else:
            parts = body.rsplit("/", 1)
        if len(parts) == 2:
            name, version = parts
        else:
            name, _, version = body.rpartition("@")
    elif "@" in key:
        name, version = key.rsplit("@", 1)
    else:
        return None
    version = version.split("_")[0].split("(")[0]
    if not name or not re.match(r"^\d", version):
        return None
    return name, version


def read_pnpm_lock(path, runtime_seeds, dev_seeds):
    """Return [(name, version, scope)] from pnpm-lock.yaml (v6/v9 shapes)."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise IntakeError(f"{path}: cannot read pnpm-lock.yaml ({exc})") from exc
    rows = []
    section = None
    entry = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            entry = None
            continue
        if section not in ("packages", "snapshots"):
            continue
        if indent == 2 and stripped.endswith(":"):
            entry = _pnpm_entry(stripped[:-1])
            if entry:
                name, version = entry
                scope = "dev" if name in dev_seeds and name not in runtime_seeds \
                    else "runtime"
                rows.append([name, version, scope])
            continue
        if entry and indent >= 4 and stripped.startswith("dev:"):
            is_dev = stripped.split(":", 1)[1].strip().lower() == "true"
            if is_dev and rows:
                rows[-1][2] = "dev"
    return [tuple(row) for row in rows]


def read_workspace_manifests(root_manifest, consumer_dir):
    """Yield (runtime_names, dev_names) from referenced workspace manifests."""
    workspaces = root_manifest.get("workspaces")
    patterns = []
    if isinstance(workspaces, list):
        patterns = workspaces
    elif isinstance(workspaces, dict):
        patterns = workspaces.get("packages") or []
    runtime, dev = set(), set()
    for pattern in patterns:
        if not isinstance(pattern, str) or os.path.isabs(pattern):
            continue
        for manifest_path in sorted(
                glob.glob(os.path.join(consumer_dir, pattern, "package.json"))):
            manifest = read_manifest(manifest_path)
            found_runtime, found_dev = _names_from_manifest(manifest)
            runtime.update(found_runtime)
            dev.update(found_dev)
    return runtime, dev


def read_lockfile(package_manager, path, runtime_seeds, dev_seeds):
    if package_manager == "npm":
        return read_npm_lock(path)
    if package_manager == "yarn":
        return read_yarn_lock(path, runtime_seeds, dev_seeds)
    if package_manager == "pnpm":
        return read_pnpm_lock(path, runtime_seeds, dev_seeds)
    raise IntakeError(f"unsupported package manager: {package_manager}")


# --------------------------------------------------------------------------
# Framework propagation
# --------------------------------------------------------------------------

def framework_packages(paths):
    """Exact (name, version) pairs present in a framework production lockfile."""
    found = set()
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            for name, version, scope in read_npm_lock(path):
                if scope == "runtime":
                    found.add((name, version))
        except IntakeError:
            continue
    return found


# --------------------------------------------------------------------------
# OSV intake
# --------------------------------------------------------------------------

def _severity_of(vuln):
    for key in ("database_specific", "ecosystem_specific"):
        value = (vuln.get(key) or {}).get("severity")
        if isinstance(value, str) and value.lower() in sweep.SEVERITIES:
            return value.lower()
    return "unknown"


def _fixed_versions(vuln, package):
    fixed = set()
    for affected in vuln.get("affected") or []:
        pkg = affected.get("package") or {}
        if pkg.get("name") != package or pkg.get("ecosystem") != "npm":
            continue
        for entry in affected.get("ranges") or []:
            for event in entry.get("events") or []:
                version = event.get("fixed")
                if version:
                    fixed.add(str(version))
    return sorted(fixed)


def _advisory(vuln, package):
    return {
        "id": str(vuln["id"]),
        "aliases": sorted({str(alias) for alias in vuln.get("aliases") or []}),
        "severity": _severity_of(vuln),
        "fixed": _fixed_versions(vuln, package),
    }


def _normalize_response(response, queries):
    """Map an OSV batch response onto one result per query, allowlisted."""
    results = response.get("results")
    if not isinstance(results, list) or len(results) != len(queries):
        raise IntakeError(
            "OSV response does not align with the submitted query batch")
    normalized = []
    for index, query in enumerate(queries):
        result = results[index]
        if not isinstance(result, dict):
            raise IntakeError("OSV response result entry is not an object")
        vulns = result.get("vulns") or []
        advisories = {}
        for vuln in vulns:
            if not isinstance(vuln, dict) or "id" not in vuln:
                continue
            advisory = _advisory(vuln, query["package"])
            advisories[advisory["id"]] = advisory
        normalized.append({
            "query_index": index,
            "advisories": [advisories[key] for key in sorted(advisories)],
        })
    return normalized


def _post_batch(queries):
    body = json.dumps({"queries": [query["query"] for query in queries]},
                      sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        OSV_ENDPOINT, data=body, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Revision discovery
# --------------------------------------------------------------------------

def _git_head(directory):
    # Only a checkout of this repository itself supplies a revision; a plain
    # fixture directory inside another worktree must not inherit its HEAD.
    if not os.path.exists(os.path.join(directory, ".git")):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", directory, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False)
    except OSError:
        return None
    commit = proc.stdout.strip()
    if proc.returncode == 0 and COMMIT_RE.match(commit):
        return commit
    return None


def resolve_revisions(audit_dir, consumers):
    fallback = {}
    fallback_path = os.path.join(audit_dir, "revisions.json")
    if os.path.isfile(fallback_path):
        doc = read_manifest(fallback_path)
        for row in doc.get("revisions") or []:
            fallback[row.get("repo")] = row.get("commit")
    revisions = []
    for record in sweep.active_consumers(consumers):
        slug = record["slug"]
        commit = _git_head(os.path.join(audit_dir, slug)) or fallback.get(slug)
        if not commit or not COMMIT_RE.match(str(commit)):
            raise IntakeError(
                f"{slug}: no 40-hex revision (git checkout or revisions.json)")
        revisions.append({"repo": slug, "commit": commit})
    return sorted(revisions, key=lambda row: row["repo"])


# --------------------------------------------------------------------------
# Snapshot construction
# --------------------------------------------------------------------------

def build_snapshot(audit_dir, consumers, as_of=None, osv_json=None,
                   framework_lockfiles=None):
    """Return the allowlisted snapshot dict. One write is the caller's job."""
    framework = framework_packages(framework_lockfiles or [])
    queries = []
    for record in sweep.active_consumers(consumers):
        slug = record["slug"]
        consumer_dir = os.path.join(audit_dir, slug)
        manifest = read_manifest(os.path.join(consumer_dir, "package.json"))
        runtime_seeds, dev_seeds = _names_from_manifest(manifest)
        ws_runtime, ws_dev = read_workspace_manifests(manifest, consumer_dir)
        runtime_seeds |= ws_runtime
        dev_seeds |= ws_dev
        for lockfile in record["lockfile_paths"]:
            path = os.path.join(consumer_dir, lockfile)
            if not os.path.isfile(path):
                raise IntakeError(f"{slug}: declared lockfile missing: {lockfile}")
            rows = read_lockfile(record["package_manager"], path,
                                 runtime_seeds, dev_seeds)
            for name, version, scope in rows:
                origin = ("framework-propagated"
                          if (name, version) in framework else "consumer-local")
                queries.append({
                    "repo": slug,
                    "ecosystem": "npm",
                    "package": name,
                    "installed": version,
                    "scope": scope,
                    "origin": origin,
                    "lockfile": lockfile,
                })

    unique = {}
    for query in queries:
        key = (query["repo"], query["package"], query["installed"],
               query["scope"], query["origin"], query["lockfile"])
        unique[key] = query
    ordered = [unique[key] for key in sorted(unique)]
    for index, query in enumerate(ordered):
        query["query_index"] = index
        query["query"] = {
            "package": {"ecosystem": "npm", "name": query["package"]},
            "version": query["installed"],
        }

    revisions = resolve_revisions(audit_dir, consumers)
    if osv_json:
        with open(osv_json, encoding="utf-8") as fh:
            response = json.load(fh)
        results = _normalize_response(response, ordered)
    else:
        if len(ordered) > OSV_MAX_BATCH:
            raise IntakeError(
                f"{len(ordered)} queries exceed the {OSV_MAX_BATCH}-query batch "
                "limit; split the intake before adding chunking")
        results = _normalize_response(_post_batch(ordered), ordered)

    snapshot = {
        "schema_version": 1,
        "as_of": as_of or _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "source": OSV_ENDPOINT,
        "revisions": revisions,
        "queries": [{
            key: query[key] for key in
            ("query_index", "repo", "ecosystem", "package", "installed",
             "scope", "origin", "lockfile", "query")
        } for query in ordered],
        "results": results,
    }
    if not AS_OF_RE.match(snapshot["as_of"]):
        raise IntakeError("--as-of must be UTC RFC 3339 with Z")
    sweep.walk_sanitized(snapshot, "snapshot")
    return snapshot


def write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=".snapshot-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-audit", required=True, metavar="DIR")
    parser.add_argument("--out", required=True, metavar="PATH",
                        help="the single permitted write")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="default and only mode; no package-manager mutation")
    parser.add_argument("--as-of", metavar="TIMESTAMP",
                        help="UTC RFC 3339 with Z (default: now)")
    parser.add_argument("--osv-json", metavar="PATH",
                        help="mocked OSV batch response (test seam)")
    parser.add_argument("--framework-lockfile", action="append", default=None,
                        metavar="PATH",
                        help="framework production lockfile (repeatable)")
    parser.add_argument("--inventory", default=INVENTORY)
    args = parser.parse_args(argv)
    try:
        consumers = sweep.load_inventory(args.inventory)
        snapshot = build_snapshot(
            args.from_audit,
            consumers,
            as_of=args.as_of,
            osv_json=args.osv_json,
            framework_lockfiles=args.framework_lockfile,
        )
        write_atomic(args.out, json.dumps(
            snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"OK: snapshot {snapshot['as_of']} — "
              f"{len(snapshot['queries'])} queries, "
              f"{len(snapshot['revisions'])} revisions -> {args.out}")
        return 0
    except (IntakeError, sweep.SchemaError, OSError) as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
