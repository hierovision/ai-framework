#!/usr/bin/env python3
"""OpenCode upgrade orchestrator — one entry point, canary-gated, truthful.

The adapter (`opencode_v2.py`) owns the pinned version; this script owns the
upgrade workflow around it:

  status    topology + pinned/live/latest + last canary/apply + next command
  doctor    read-only health check of the live install
  check     offline pin seams (--pins-only), registry drift (--remote), or the
            local/manual canary gate (--pr; not CI-enforced)
  plan      target compatibility matrix + breaking-change notes; no writes
  prepare   bump every seam, plugin peer/lockfile roots, and the ADR amendment
  canary    install the candidate in scratch + full canary + plugin typechecks
  prune     remove old scratch prefixes/canary/compat dirs (--keep N)
  upgrade   check -> plan -> canary -> prepare; with --apply it runs the drained
            supported upgrade (resolve V2, repair the default shadow, verify)

`upgrade --apply --drain-acknowledged` is the only mutating apply step. It does
not require or check a TTY. It resolves the installed V2 target and atomically
repairs the default `opencode` shadow before the smoke. A failed verification
leaves the target and repaired default in place, records `verified: false`, and
prints the manual rollback guidance (ADR-0017); there is no automatic rollback.

All writes are under the repo or `$HOME/.local/lib/opencode`; scratch lives in
`.scratch/opencode-v2/`. Secrets are never printed (auth is read by the
canary, not this script).
"""
import argparse
import contextlib
import datetime
import fcntl
import glob
import json
import os
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402
import opencode_v2_post_smoke as post_smoke  # noqa: E402
import stage_opencode_config as stage_config  # noqa: E402

RELEASES_URL = ("https://api.github.com/repos/anomalyco/opencode/"
                "releases?per_page=100")
CACHE_TTL = 3600
PLUGIN_DIRS = ("auto-compact-at-threshold", "delegation-observer",
               "delegation-sentinel")
TUI_PLUGINS = ("delegation-observer", "delegation-sentinel")
V1_BIN = os.path.expanduser(
    "~/.config/yarn/global/node_modules/opencode-ai/bin/opencode.exe")
MIGRATION_APPLY_TIMEOUT = 900
MIGRATION_APPLY_POLL_INTERVAL = 0.5


# --- small helpers -----------------------------------------------------------

def now_date():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, payload):
    """Atomically write JSON: temp file in the target dir + os.replace."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}.{time.time_ns()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


@contextlib.contextmanager
def file_lock(path, timeout=10):
    """Bounded exclusive lock for state/artifact read-modify-write cycles."""
    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    fh = open(lock_path, "a+")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for {lock_path}")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def run(argv, cwd=None, env=None, timeout=120, stream=False):
    """Run a command; stream=True passes stdout/stderr through to the user."""
    if stream:
        return subprocess.run(argv, cwd=cwd, env=env, timeout=timeout)
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def version_key(value):
    return tuple(int(p) for p in re.findall(r"\d+", value)[:3])


def _caret_bounds(version):
    major, minor, patch = (int(p) for p in version.split("."))
    if major > 0:
        return version, f"{major + 1}.0.0"
    if minor > 0:
        return version, f"0.{minor + 1}.0"
    return version, f"0.0.{patch + 1}"


def _tilde_bounds(version):
    major, minor, _patch = (int(p) for p in version.split("."))
    return version, f"{major}.{minor + 1}.0"


def satisfies(current, spec):
    """True when `current` meets an exact, `>=`, caret, tilde, or x-range spec.

    Unknown or open-ended specs are conservatively treated as unsatisfied so a
    real bump is not mislabeled `none`.
    """
    spec = (spec or "").strip()
    if not spec or spec == "*":
        return True
    if re.fullmatch(r"\d+\.\d+\.\d+", spec):
        return current == spec
    match = re.fullmatch(r">=\s*(\d+\.\d+\.\d+)", spec)
    if match:
        return version_key(current) >= version_key(match.group(1))
    match = re.fullmatch(r"\^(\d+\.\d+\.\d+)", spec)
    if match:
        low, high = _caret_bounds(match.group(1))
        return version_key(low) <= version_key(current) < version_key(high)
    match = re.fullmatch(r"~(\d+\.\d+\.\d+)", spec)
    if match:
        low, high = _tilde_bounds(match.group(1))
        return version_key(low) <= version_key(current) < version_key(high)
    match = re.fullmatch(r"(\d+)\.(?:x|\*)(?:\.(?:x|\*))?", spec)
    if match:
        major = int(match.group(1))
        return version_key(current)[0] == major
    parts = spec.split()
    if len(parts) == 2 and all(re.fullmatch(r"(?:>=|<)\s*\d+\.\d+\.\d+",
                                            part) for part in parts):
        lower = [p for p in parts if p.startswith(">=")]
        upper = [p for p in parts if p.startswith("<")]
        if not lower or not upper:
            return False
        low = version_key(re.fullmatch(r">=\s*(\d+\.\d+\.\d+)",
                                       lower[0]).group(1))
        high = version_key(re.fullmatch(r"<\s*(\d+\.\d+\.\d+)",
                                        upper[0]).group(1))
        return low <= version_key(current) < high
    return False


def parse_version(text):
    """Delegate to the shared exact version parser."""
    return v2.parse_opencode_version(text)


def gh_env():
    """`gh` must read the user's config even when the V2 wrapper set XDG."""
    env = dict(os.environ)
    env["GH_CONFIG_DIR"] = os.path.expanduser("~/.config/gh")
    return env


def state_path(repo):
    return os.path.join(repo, ".scratch", "opencode-v2", "upgrade-state.json")


STAGE_ORDER = ("planned", "canaried", "prepared", "applied")
RESUMABLE_STAGES = ("planned", "canaried", "prepared")


def read_state(repo):
    return read_json(state_path(repo), {}) or {}


def completed_stages(state):
    """A later recorded stage implies every earlier stage completed."""
    done = set((state.get("stages") or {}).keys())
    for index, stage in enumerate(STAGE_ORDER):
        if stage in done:
            done.update(STAGE_ORDER[:index + 1])
    return done


def write_state(repo, target, stage, detail=None, force=False):
    """Record a stage, preserving its first record unless `force` updates it.

    The stage never regresses on a re-run; `updated` always reflects the latest
    write, while the per-stage `at`/`detail` record stays at its first value
    unless `force=True` asks for an explicit update.
    """
    path = state_path(repo)
    with file_lock(path):
        state = read_state(repo)
        if state.get("target") != target:
            state = {"target": target, "stages": {}}
        order = list(STAGE_ORDER)
        current = state.get("stage")
        if (not force and current in order and stage in order
                and order.index(stage) < order.index(current)):
            stage = current  # never regress applied -> canaried on a re-run
        state["stage"] = stage
        stages = state.setdefault("stages", {})
        if force or stage not in stages:
            stages[stage] = {"at": now_iso(), "detail": detail or "ok"}
        state["updated"] = now_iso()
        return write_json(path, state)


# --- version seams -----------------------------------------------------------

SEAMS = [
    {"path": "scripts/opencode_v2.py",
     "pattern": r'VERSION_PIN = "(?P<version>\d+\.\d+\.\d+)"',
     "replacement": 'VERSION_PIN = "{version}"', "kind": "cli"},
    {"path": "README.md",
     "pattern": r'OpenCode V2 `(?P<version>\d+\.\d+\.\d+)`',
     "replacement": 'OpenCode V2 `{version}`', "kind": "cli"},
    {"path": "README.md",
     "pattern": r'@opencode/cli@(?P<version>\d+\.\d+\.\d+)',
     "replacement": '@opencode/cli@{version}', "kind": "cli"},
    {"path": "README.md",
     "pattern": r'prints `opencode v(?P<version>\d+\.\d+\.\d+)`',
     "replacement": 'prints `opencode v{version}`', "kind": "cli"},
    {"path": "reference/opencode-integration.md",
     "pattern": r'`(?P<version>\d+\.\d+\.\d+)` upgrade passed',
     "replacement": '`{version}` upgrade passed', "kind": "cli"},
    {"path": "reference/opencode-integration.md",
     "pattern": r'\.scratch/v2-canary-(?P<version>\d+\.\d+\.\d+)/',
     "replacement": '.scratch/v2-canary-{version}/', "kind": "cli"},
    {"path": "reference/opencode-integration.md",
     "pattern": r'Package: `@opencode/cli@(?P<version>\d+\.\d+\.\d+)`',
     "replacement": 'Package: `@opencode/cli@{version}`', "kind": "cli"},
    {"path": "reference/opencode-integration.md",
     "pattern": r'prints `opencode v(?P<version>\d+\.\d+\.\d+)`',
     "replacement": 'prints `opencode v{version}`', "kind": "cli"},
    {"path": "reference/opencode-integration.md",
     "pattern": r'^- `@opencode/plugin@(?P<version>\d+\.\d+\.\d+)`',
     "replacement": '- `@opencode/plugin@{version}`', "kind": "cli",
     "flags": re.MULTILINE},
    {"path": "plugins/delegation-observer/README.md",
     "pattern": r'(@opencode/plugin`\s*\n\s*)(?P<version>\d+\.\d+\.\d+)',
     "replacement": r'\g<1>{version}', "kind": "cli"},
    {"path": "plugins/delegation-observer/README.md",
     "pattern": r'(`@opentui/core`/`solid` )(?P<version>\d+\.\d+\.\d+)',
     "replacement": r'\g<1>{opentui}', "kind": "opentui"},
    {"path": "plugins/delegation-sentinel/README.md",
     "pattern": r'(`@opencode/plugin` )(?P<version>\d+\.\d+\.\d+)',
     "replacement": r'\g<1>{version}', "kind": "cli"},
    {"path": "plugins/delegation-sentinel/README.md",
     "pattern": r'(`@opentui/core`/`solid` )(?P<version>\d+\.\d+\.\d+)',
     "replacement": r'\g<1>{opentui}', "kind": "opentui"},
]

PLUGIN_JSONS = [
    ("plugins/auto-compact-at-threshold/package.json", True, False),
    ("plugins/delegation-observer/package.json", True, True),
    ("plugins/delegation-sentinel/package.json", True, True),
]


def seam_value(seam, version, opentui):
    return version if seam["kind"] == "cli" else opentui


def check_seams(repo=REPO, version=None, opentui=None):
    """Return [(path, ok, detail)] for every active pin seam."""
    version = version or v2.VERSION_PIN
    opentui = opentui or current_opentui(repo)
    results = []
    for seam in SEAMS:
        path = os.path.join(repo, seam["path"])
        expected = seam_value(seam, version, opentui)
        if not os.path.isfile(path):
            results.append((seam["path"], False, "missing"))
            continue
        text = open(path, encoding="utf-8").read()
        matches = [m.group("version")
                   for m in re.finditer(seam["pattern"], text,
                                        seam.get("flags", 0))]
        if not matches:
            results.append((seam["path"], False,
                            f"no `{seam['pattern']}` match"))
        elif any(value != expected for value in matches):
            results.append((seam["path"], False,
                            f"{matches} != {expected}"))
        else:
            results.append((seam["path"], True, expected))
    results.extend(check_plugin_jsons(repo, version, opentui))
    results.extend(check_lockfiles(repo, version, opentui))
    results.extend(check_adr_amendment(repo, version))
    return results


def current_plugin(repo=REPO):
    return read_json(os.path.join(
        repo, "plugins", "delegation-observer", "package.json"), {}) or {}


def current_opentui(repo=REPO):
    peers = current_plugin(repo).get("peerDependencies") or {}
    return peers.get("@opentui/core", "0.8.1")


def check_plugin_jsons(repo=REPO, version=None, opentui=None):
    version = version or v2.VERSION_PIN
    opentui = opentui or current_opentui(repo)
    results = []
    for rel, has_cli, has_tui in PLUGIN_JSONS:
        path = os.path.join(repo, rel)
        data = read_json(path)
        if not isinstance(data, dict):
            results.append((rel, False, "missing/unreadable"))
            continue
        problems = []
        if data.get("version") != version:
            problems.append(f"version={data.get('version')}")
        deps = data.get("dependencies") or {}
        peers = data.get("peerDependencies") or {}
        if has_cli and deps.get("@opencode/plugin") != version \
                and peers.get("@opencode/plugin") != version:
            problems.append("@opencode/plugin mismatch")
        if has_tui:
            if peers.get("@opentui/core") != opentui:
                problems.append("@opentui/core mismatch")
            if peers.get("@opentui/solid") != opentui:
                problems.append("@opentui/solid mismatch")
        results.append((rel, not problems,
                        ", ".join(problems) if problems else version))
    return results


def check_lockfiles(repo=REPO, version=None, opentui=None):
    """Verify the resolved lockfile roots, not only the declared package.json."""
    version = version or v2.VERSION_PIN
    opentui = opentui or current_opentui(repo)
    results = []
    for name in PLUGIN_DIRS:
        rel = f"plugins/{name}/package-lock.json"
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        data = read_json(path)
        if not isinstance(data, dict):
            results.append((rel, False, "unreadable"))
            continue
        problems = []
        packages = data.get("packages") or {}
        root = packages.get("", {})
        if root.get("version") != version:
            problems.append(f"root version={root.get('version')}")
        resolved = (packages.get("node_modules/@opencode/plugin") or {}).get(
            "version")
        if resolved != version:
            problems.append(f"@opencode/plugin={resolved}")
        if name in TUI_PLUGINS:
            peers = root.get("peerDependencies") or {}
            if peers.get("@opentui/core") != opentui:
                problems.append(f"@opentui/core={peers.get('@opentui/core')}")
            if peers.get("@opentui/solid") != opentui:
                problems.append(f"@opentui/solid={peers.get('@opentui/solid')}")
        results.append((rel, not problems,
                        ", ".join(problems) if problems else version))
    return results


def adr_path(repo=REPO):
    return os.path.join(repo, "docs", "ADRs",
                        "ADR-0014-opencode-v2-upgrade.md")


def check_adr_amendment(repo=REPO, version=None):
    version = version or v2.VERSION_PIN
    path = adr_path(repo)
    if not os.path.isfile(path):
        return [(os.path.relpath(path, repo), False, "missing")]
    text = open(path, encoding="utf-8").read()
    found = re.findall(
        r'\*\*\d{4}-\d{2}-\d{2} amendment — version pin '
        r'(?P<version>\d+\.\d+\.\d+)\.\*\*', text)
    rel = os.path.relpath(path, repo)
    if not found:
        return [(rel, False, "no dated version amendment")]
    if found[-1] != version:
        return [(rel, False, f"latest amendment {found[-1]} != {version}")]
    return [(rel, True, version)]


def _evidence_field(text, name, cast=str):
    match = re.search(rf"^{re.escape(name)}=(.+)$", text, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def canary_summary(repo=REPO, version=None):
    """Read the canary evidence; None when no evidence exists.

    `ok` requires every C1-C8 gate plus a measured migration verdict: PASS, an
    intact target, an untouched source, no zero migration, no phantom target
    IDs, and an accepted residual (a positive residual needs the dated shared
    classification record).
    """
    version = version or v2.VERSION_PIN
    root = os.path.join(repo, ".scratch", "v2-canary-" + version)
    if not os.path.isdir(root):
        return None
    gates = {}
    for name, filename in (("C1", "C1.txt"), ("C2", "C2.txt"),
                           ("C3", "C3-real.txt"), ("C4", "C4.txt"),
                           ("C5", "C5.txt"), ("C6", "C6.txt"),
                           ("C7", "C7.txt"), ("C8", "C8.txt")):
        path = os.path.join(root, filename)
        if os.path.isfile(path):
            gates[name] = "PASS" if f"{name}=PASS" in open(
                path, encoding="utf-8").read() else "FAIL"
        else:
            gates[name] = "MISSING"
    migration_path = os.path.join(root, "migration-rehearsal.txt")
    migration = {"verdict": None, "residual": None, "target_only": None,
                 "zero_migration": None, "integrity": None,
                 "source_untouched": None}
    if os.path.isfile(migration_path):
        text = open(migration_path, encoding="utf-8").read()
        verdict = re.search(r"^migration=(PASS|FAIL)\b", text, re.MULTILINE)
        migration["verdict"] = verdict.group(1) if verdict else None
        migration["residual"] = _evidence_field(
            text, "source_sessions_not_migrated", int)
        migration["target_only"] = _evidence_field(
            text, "target_only_ids", int)
        zero = _evidence_field(text, "zero_migration")
        migration["zero_migration"] = (
            zero == "True" if zero in ("True", "False") else None)
        migration["integrity"] = _evidence_field(
            text, "target_integrity_check")
        untouched = _evidence_field(text, "source_untouched")
        migration["source_untouched"] = (
            untouched == "True" if untouched in ("True", "False") else None)
    residual = migration["residual"]
    accepted = False
    migration_ok = (
        migration["verdict"] == "PASS"
        and migration["integrity"] == "ok"
        and migration["source_untouched"] is True
        and migration["zero_migration"] is False
        and migration["target_only"] == 0
        and residual == 0
    )
    required = (
        ("migration verdict", migration["verdict"]),
        ("zero_migration", migration["zero_migration"]),
        ("target_only_ids", migration["target_only"]),
        ("target_integrity_check", migration["integrity"]),
        ("source_untouched", migration["source_untouched"]),
        ("source_sessions_not_migrated", migration["residual"]),
    )
    missing_fields = [name for name, value in required if value is None]
    failing_gates = [name for name, value in gates.items()
                     if value != "PASS"]
    if missing_fields:
        reason = (
            "legacy/incomplete canary evidence (missing: "
            + ", ".join(missing_fields) + "); run `" + canary_command(version)
            + "` to regenerate fresh hardened evidence")
    elif failing_gates:
        reason = ("canary gates failing (" + ", ".join(failing_gates)
                  + "); run `" + canary_command(version) + "`")
    elif not migration_ok:
        reason = (
            "migration evidence failing (verdict="
            f"{migration['verdict']}, residual={residual}, "
            f"target_only={migration['target_only']}, "
            f"zero_migration={migration['zero_migration']}); run `"
            + canary_command(version) + "`")
    else:
        reason = None
    return {"root": root, "gates": gates, "residual": residual,
            "residual_accepted": accepted, "migration": migration,
            "schema_complete": not missing_fields,
            "missing_fields": missing_fields, "reason": reason,
            "ok": all(v == "PASS" for v in gates.values()) and migration_ok}


# --- registry / release intelligence ----------------------------------------

def cached_latest(repo=REPO):
    data = read_json(os.path.join(repo, ".scratch", "opencode-v2",
                                  "version-cache.json"), {}) or {}
    if data.get("latest") and time.time() - data.get("at", 0) < CACHE_TTL:
        return data["latest"]
    return None


def latest_version(repo=REPO, refresh=False, offline=False):
    if not refresh:
        cached = cached_latest(repo)
        if cached:
            return cached
    if offline:
        return None
    try:
        proc = run(["npm", "view", "@opencode/cli", "version"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    latest = parse_version(proc.stdout)
    if latest:
        write_json(os.path.join(repo, ".scratch", "opencode-v2",
                                "version-cache.json"),
                   {"latest": latest, "at": time.time()})
    return latest


def plugin_peers(version, repo=REPO):
    try:
        proc = run(["npm", "view", "@opencode/plugin@" + version,
                    "peerDependencies", "--json"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout or "{}")
    except ValueError:
        return None


def fetch_releases(timeout=30):
    req = urllib.request.Request(
        RELEASES_URL, headers={"User-Agent": "opencode-upgrade"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except Exception:
        return []


def breaking_notes(releases, current, target):
    rows = []
    for release in releases or []:
        tag = (release.get("tag_name") or "").lstrip("v")
        if not re.fullmatch(r"\d+\.\d+\.\d+", tag):
            continue
        if not (version_key(current) < version_key(tag)
                <= version_key(target)):
            continue
        body = release.get("body") or ""
        match = re.search(r"^#{2,4} Breaking changes\s*$", body,
                          re.MULTILINE | re.IGNORECASE)
        if not match:
            continue
        tail = body[match.end():]
        stop = re.search(r"^#{2,3} ", tail, re.MULTILINE)
        section = (tail[:stop.start()] if stop else tail).strip()
        rows.append((tag, section))
    return rows


def resolve_opentui(version, override=None, peers=None):
    if override:
        return override
    peers = peers if peers is not None else plugin_peers(version)
    spec = (peers or {}).get("@opentui/core")
    if not spec:
        return current_opentui()
    exact = re.fullmatch(r"\d+\.\d+\.\d+", spec)
    if exact:
        return spec
    try:
        proc = run(["npm", "view", "@opentui/core", "version"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return current_opentui()
    latest = parse_version(proc.stdout) if proc.returncode == 0 else None
    return latest or current_opentui()


# --- status / doctor --------------------------------------------------------

def live_paths(args):
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    link = args.link or os.path.join(home, ".yarn", "bin", "opencode")
    return home, link


def version_of(binary):
    """Exact version via the shared parser; timeouts/spawn errors yield None."""
    try:
        proc = run([binary, "--version"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return v2.parse_opencode_version(proc.stdout)


YARN_LINK_NAME = "opencode2"


def config_root_of(binary):
    """Exact config-root probe; timeouts/spawn errors yield None."""
    try:
        proc = run([binary, "debug", "paths", "config"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (proc.stdout or "").strip() if proc.returncode == 0 else None


def target_package(home):
    """(package_dir, package_bin, package_json_version) for the V2 package."""
    package_dir = os.path.join(home, ".config", "yarn", "global",
                               "node_modules", "@opencode", "cli")
    package_bin = os.path.join(package_dir, "bin", "opencode.exe")
    data = read_json(os.path.join(package_dir, "package.json"), {}) or {}
    version = data.get("version") if isinstance(data, dict) else None
    return package_dir, package_bin, version


def target_package_info(home, target):
    """Installed V2 package metadata; `version` is None when it is absent."""
    package_dir, package_bin, version = target_package(home)
    return {"version": version, "requested": target, "path": package_dir,
            "binary": package_bin}


def resolve_target_binary(home, target):
    """Return (candidate, evidence) for the first binary reporting `target`.

    Order is the Yarn V2 link (`~/.yarn/bin/opencode2`) then the installed
    package binary. Both packages publish an `opencode` bin; the retained V1
    package is never a valid target.
    """
    yarn_link = os.path.join(home, ".yarn", "bin", YARN_LINK_NAME)
    _package_dir, package_bin, _version = target_package(home)
    evidence = []
    for candidate in (yarn_link, package_bin):
        exists = os.path.exists(candidate)
        version = version_of(candidate) if exists else None
        evidence.append({"path": candidate, "exists": exists,
                         "version": version})
        if exists and version == target:
            return candidate, evidence
    return None, evidence


def repair_default_link(home, link, resolved):
    """Atomically point `link` at the resolved V2 binary.

    Prefer a relative `opencode2` target when it is the resolved binary, so the
    shadow tracks Yarn's own V2 link; otherwise link to the package binary.
    """
    link_dir = os.path.dirname(link)
    os.makedirs(link_dir, exist_ok=True)
    yarn_link = os.path.join(link_dir, YARN_LINK_NAME)
    if (os.path.exists(yarn_link)
            and os.path.abspath(yarn_link) == os.path.abspath(resolved)):
        desired = YARN_LINK_NAME
    else:
        desired = resolved
    tmp = f"{link}.shadow-tmp.{os.getpid()}"
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    os.symlink(desired, tmp)
    os.replace(tmp, link)
    return desired


def prepare_shadow(home, link, target):
    """Resolve the V2 target, prove its config root, then repair the default.

    Fails closed (no link change) when no candidate reports `target` or the
    target's config root is not the supported `~/.config/opencode`.
    """
    expected = os.path.join(home, ".config", "opencode")
    resolved, evidence = resolve_target_binary(home, target)
    result = {"target": target, "link": link, "resolved": resolved,
              "candidates": evidence, "expected_config": expected,
              "config_root": None, "default_version": None,
              "failure_stage": None}
    if resolved is None:
        result["failure_stage"] = "target-binary"
        return result
    config_root = config_root_of(resolved)
    result["config_root"] = config_root
    if (config_root is None
            or os.path.realpath(config_root) != os.path.realpath(expected)):
        result["failure_stage"] = "config-root"
        return result
    try:
        result["link_target"] = repair_default_link(home, link, resolved)
    except OSError as exc:
        result["failure_stage"] = "repair"
        result["detail"] = str(exc)
        return result
    result["default_version"] = version_of(link)
    return result


def shadow_state(home, link, target):
    """Diagnostic view of the installed target vs the default command."""
    expected = os.path.join(home, ".config", "opencode")
    package_dir, package_bin, package_version = target_package(home)
    resolved, candidates = resolve_target_binary(home, target)
    installed = target if resolved else None
    default_exists = os.path.lexists(link)
    default_version = version_of(link) if default_exists else None
    default_config = config_root_of(link) if default_exists else None
    target_config = config_root_of(resolved) if resolved else None
    supported_config = (target_config is not None
                        and os.path.realpath(target_config)
                        == os.path.realpath(expected))
    shadow_ok = bool(installed) and default_version == target and supported_config
    return {
        "target_installed": installed,
        "target_package": {"version": package_version, "path": package_dir,
                           "binary": package_bin},
        "target_binary": resolved,
        "candidates": candidates,
        "default_link": link,
        "default_link_target": os.readlink(link) if os.path.islink(link) else None,
        "default_version": default_version,
        "config_root": default_config or target_config,
        "target_config_root": target_config,
        "expected_config": expected,
        "supported_config": supported_config,
        "shadow_ok": shadow_ok,
    }


def repair_command(target):
    return ("python3 scripts/opencode_upgrade.py upgrade --to " + target
            + " --apply --drain-acknowledged")


def canary_command(target):
    return ("python3 scripts/opencode_upgrade.py canary --to " + target)


def print_canary_prerequisite(repo, target):
    """Print the canary prerequisite when evidence is absent/failing/legacy.

    Returns True when the caller should stop at the canary step, False when
    evidence is fresh and passing.
    """
    summary = canary_summary(repo, target)
    if summary is not None and summary["ok"]:
        return False
    reason = (summary or {}).get("reason") or (
        "no canary evidence at .scratch/v2-canary-" + target + "/")
    print(f"canary prerequisite: {reason}")
    print(f"run: {canary_command(target)}")
    return True


def link_state(link):
    """Complete on-disk state of a default `opencode` link."""
    exists = os.path.lexists(link)
    raw = os.readlink(link) if os.path.islink(link) else None
    resolved = os.path.realpath(link) if exists else None
    version = version_of(link) if exists else None
    kind = None
    if version:
        kind = "v1" if version_key(version)[0] <= 1 else "v2"
    elif resolved and "opencode-ai" in resolved:
        kind = "v1"
    return {"path": link, "target": raw, "resolved": resolved,
            "version": version, "kind": kind, "exists": exists}


def find_v1_backup(home):
    """Newest actual V1 config backup (`~/.config/opencode.v1-backup-*`)."""
    if not home:
        return None
    backups = sorted(glob.glob(os.path.join(
        home, ".config", "opencode.v1-backup-*")))
    if not backups:
        return None
    root = backups[-1]
    db = os.path.join(root, "opencode.db")
    return {"root": root, "db": db if os.path.isfile(db) else None}


def rollback_plan(link, previous_default, backup, method, home=None,
                  config_backup=None, db=None):
    """Truthful rollback guidance for the pre-repair default.

    A V2 previous default is reinstalled with the supported upgrade command.
    A V1 previous default is restored by recreating the original link and using
    the actual `~/.config/opencode.v1-backup-*` tree. The pre-apply snapshot is
    cited only for the copies that were actually created. A missing/
    unclassifiable previous default gets an explicit unknown branch.
    """
    prev = previous_default or {}
    copies = []
    if config_backup:
        copies.append(f"config: {config_backup}")
    if db:
        copies.append(f"DB: {db}")
    if backup and copies:
        snapshot = f"the pre-apply snapshot at {backup} ({', '.join(copies)})"
        pre_desc = f"the pre-apply snapshot at {backup} is the V2-era snapshot"
    elif backup:
        snapshot = f"the pre-apply snapshot at {backup} (no config/DB copy)"
        pre_desc = f"the pre-apply snapshot at {backup} contains no config/DB copy"
    else:
        snapshot = "no pre-upgrade snapshot was created"
        pre_desc = "no pre-upgrade snapshot was created"
    if prev.get("kind") == "v1":
        restore = prev.get("resolved") or prev.get("target")
        commands = []
        if restore and os.path.abspath(restore) != os.path.abspath(link):
            commands.append(
                f"ln -sfn {shlex.quote(restore)} {shlex.quote(link)}")
        v1 = find_v1_backup(home)
        if v1:
            db_text = v1["db"] or "no DB copy recorded in that backup"
            guidance = (
                f"previous default was V1 ({prev.get('version')}): restore "
                f"the original link and the actual V1 config backup at "
                f"{v1['root']} (DB: {db_text}); {pre_desc}, not a V1 backup; "
                "the retained V1 package is opencode-ai, so a V2 "
                "`opencode upgrade` cannot reinstall it")
        else:
            guidance = (
                f"previous default was V1 ({prev.get('version')}): no V1 "
                f"config/DB backup was found under "
                f"~/.config/opencode.v1-backup-*; {pre_desc} (a first install "
                "has no older V1 backup). Restore the original link and "
                "reinstall/restore the retained V1 package manually; a V2 "
                "`opencode upgrade` cannot reinstall it")
        return {"kind": "v1", "previous_default": prev, "v1_backup": v1,
                "commands": commands, "guidance": guidance}
    if prev.get("kind") == "v2":
        previous_version = prev.get("version")
        command = (f"{link} upgrade {previous_version or '<previous>'} "
                   f"--method {method}")
        guidance = (f"previous default was V2: {command}; restore {snapshot}")
        return {"kind": "v2", "previous_default": prev,
                "commands": [command] if previous_version else [],
                "guidance": guidance}
    if backup:
        guidance = (
            "previous default is missing or unclassifiable; no automatic "
            f"package rollback is available — restore the default link and "
            f"{snapshot} manually")
    else:
        guidance = (
            "previous default is missing or unclassifiable; no automatic "
            "package rollback is available — restore the default link and "
            "the config/DB backup manually; no pre-upgrade snapshot was "
            "created")
    return {"kind": "unknown", "previous_default": prev,
            "commands": [], "guidance": guidance}


def rollback_lines(rollback):
    """Flatten rollback guidance plus its exact commands for printing."""
    lines = [rollback.get("guidance", "")]
    lines.extend(rollback.get("commands") or [])
    return [line for line in lines if line]


def artifact_verified(data):
    """Normalize an artifact's result; None when it is not an artifact."""
    if not isinstance(data, dict):
        return None
    if "verified" in data:
        return data.get("verified") is True
    checks = data.get("checks") or {}
    checks_ok = (isinstance(checks, dict) and bool(checks)
                 and all(isinstance(row, dict) and row.get("ok") is True
                         for row in checks.values()))
    return checks_ok and data.get("rolled_back") is False


def last_verify_verified(repo, target):
    """Read the last verify result, normalizing legacy artifacts.

    Returns None when no artifact exists. A modern artifact's `verified` field
    is authoritative. A legacy artifact (no `verified`) counts as verified only
    when every recorded check passed and the run was not rolled back; a legacy
    failed artifact stays unverified so the apply fast path re-runs the smoke.
    """
    data = read_json(os.path.join(repo, ".scratch", "opencode-v2",
                                  f"upgrade-{target}-verify.json"))
    return artifact_verified(data)


def archive_artifact(path):
    """Preserve any predecessor before it is overwritten.

    Unverified predecessors keep the `.failed-<UTC stamp>` name; verified
    predecessors use the neutral `.previous-<UTC stamp>` name. The archive keeps
    the exact bytes.
    """
    if not os.path.isfile(path):
        return None
    verified = artifact_verified(read_json(path)) is True
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")
    suffix = ".previous-" if verified else ".failed-"
    archive = f"{path}{suffix}{stamp}"
    n = 1
    while os.path.exists(archive):
        archive = f"{path}{suffix}{stamp}-{n}"
        n += 1
    os.replace(path, archive)
    return archive


def write_apply_artifact(path, payload):
    """Archive a predecessor artifact, then write the new apply evidence."""
    with file_lock(path):
        archive_artifact(path)
        return write_json(path, payload)


def topology(home, link):
    """The supported install: the explicit default link + ~/.config/opencode.

    The link (not `PATH`) is authoritative: apply repairs and smokes this exact
    path, so status/doctor must diagnose the same binary even when `PATH`
    points elsewhere. The retired-wrapper scan is removed: it read the entire
    200-259MB executable, and the supported install is never a wrapper.
    """
    command = link
    exists = os.path.lexists(command)
    resolved = os.path.realpath(command) if exists else None
    config_path = None
    if exists:
        try:
            probe = run([command, "debug", "paths", "config"], timeout=30)
            config_path = ((probe.stdout or "").strip()
                           if probe.returncode == 0 else None)
        except (OSError, subprocess.TimeoutExpired):
            config_path = None
    expected = os.path.join(home, ".config", "opencode")
    supported = (config_path is not None
                 and os.path.realpath(config_path) == os.path.realpath(expected))
    v1_path = os.path.join(home, ".config", "yarn", "global", "node_modules",
                           "opencode-ai", "package.json")
    v1 = read_json(v1_path, {}) or {}
    return {
        "command": command,
        "resolved": resolved,
        "link": link,
        "link_target": os.readlink(link) if os.path.islink(link) else None,
        "wrapper": None,
        "config_root": config_path,
        "supported": supported,
        "expected_config": expected,
        "v1_rollback": v1.get("version"),
        "v1_package": v1_path if v1 else None,
    }


def status_payload(args):
    home, link = live_paths(args)
    pinned = v2.VERSION_PIN
    install = topology(home, link)
    shadow = shadow_state(home, link, pinned)
    live = version_of(install["command"]) if install["command"] else None
    latest = (args.latest or latest_version(args.repo, refresh=args.refresh)
              if args.remote else args.latest)
    state = read_state(args.repo)
    canary = canary_summary(args.repo, pinned)
    verify = read_json(os.path.join(
        args.repo, ".scratch", "opencode-v2",
        f"upgrade-{pinned}-verify.json"), {}) or {}
    next_command = "up to date"
    repair_needed = (bool(shadow["target_installed"])
                     and shadow["supported_config"]
                     and not shadow["shadow_ok"])
    canary_blocker = canary is None or not canary["ok"]
    apply_next = (repair_needed
                  or (bool(shadow["target_installed"])
                      and install["supported"] and live == pinned))
    if not install["supported"] and not repair_needed:
        next_command = ("migrate: python3 scripts/stage_opencode_config.py "
                        "--backup; opencode upgrade " + pinned
                        + " --method yarn")
    elif canary_blocker and apply_next:
        next_command = canary_command(pinned)
    elif repair_needed:
        next_command = repair_command(pinned)
    elif live != pinned:
        next_command = f"opencode upgrade {pinned} --method yarn"
    elif latest and version_key(latest) > version_key(pinned):
        next_command = ("python3 scripts/opencode_upgrade.py upgrade "
                        "--to " + latest)
    elif (state.get("target") and state.get("target") != pinned
          and state.get("stage") in RESUMABLE_STAGES):
        next_command = ("python3 scripts/opencode_upgrade.py upgrade --to "
                        + state["target"] + " --resume")
    return {
        "pinned": pinned,
        "live": live,
        "latest": latest,
        "install": install,
        "target_installed": shadow["target_installed"],
        "default_version": shadow["default_version"],
        "shadow_ok": shadow["shadow_ok"],
        "shadow": shadow,
        "canary": canary,
        "canary_blocker": canary_blocker,
        "canary_reason": (canary or {}).get("reason"),
        "last_apply": verify or None,
        "state": state or None,
        "next": next_command,
    }


def print_status(payload, json_mode=False):
    if json_mode:
        print(json.dumps(payload, indent=2))
        return
    install = payload["install"]
    print(f"pinned:  {payload['pinned']}")
    print(f"live:    {payload['live'] or 'unknown'}")
    print(f"latest:  {payload['latest'] or 'unknown (use --remote)'}")
    print("install:")
    print(f"  command:       {install['command']}")
    print(f"  resolved:      {install['resolved']}")
    print(f"  config root:   {install['config_root'] or 'unknown'}")
    print(f"  supported:     {'yes' if install['supported'] else 'no'}")
    print(f"  target pkg:    {payload['target_installed'] or 'not installed'}")
    print(f"  default:       {payload['default_version'] or 'unknown'}")
    print(f"  shadow ok:     {'yes' if payload['shadow_ok'] else 'no'}")
    print(f"  V1 rollback:   {install['v1_rollback'] or 'not installed'}")
    canary = payload["canary"]
    if canary:
        gates = " ".join(f"{k}={v}" for k, v in canary["gates"].items())
        print(f"last canary:   {gates} "
              f"migration={canary['migration']['verdict']} "
              f"residual={canary['residual']}")
        if canary.get("reason"):
            print(f"canary:        {canary['reason']}")
    else:
        print("last canary:   none")
    if payload["last_apply"]:
        apply = payload["last_apply"]
        print(f"last apply:    {apply.get('version')} "
              f"verified={apply.get('verified')} "
              f"rolled_back={apply.get('rolled_back')}")
    state = payload["state"]
    if state:
        print(f"upgrade state: {state.get('target')} at {state.get('stage')}")
    print(f"next:    {payload['next']}")


def observer_plugin(command):
    """The live plugin record for delegation-observer, if the API responds."""
    proc = run([command, "api", "GET", "/api/plugin"], timeout=60)
    if proc.returncode != 0:
        return None, "api unavailable"
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        return None, "api returned non-JSON"
    rows = data.get("data") if isinstance(data, dict) else data
    for row in rows or []:
        if isinstance(row, dict) and row.get("id") == "delegation-observer":
            features = row.get("features") or {}
            state = (row.get("state") or {}).get("status")
            return row, f"tui={features.get('tui')} state={state}"
    return None, "delegation-observer absent"


def doctor(args):
    home, link = live_paths(args)
    install = topology(home, link)
    shadow = shadow_state(home, link, v2.VERSION_PIN)
    checks = []
    checks.append(("command", bool(install["command"]),
                   install["command"] or "not found"))
    checks.append(("config-root", install["supported"],
                   f"{install['config_root']} (expected "
                   f"{install['expected_config']})"))
    checks.append(("target-package", bool(shadow["target_installed"]),
                   f"{shadow['target_installed'] or 'not installed'} "
                   f"({shadow['target_package']['path']})"))
    checks.append(("shadow", shadow["shadow_ok"],
                   f"default={shadow['default_version']} "
                   f"target={shadow['target_installed'] or 'not installed'}"))
    live = version_of(install["command"]) if install["command"] else None
    checks.append(("version", live == v2.VERSION_PIN,
                   f"live={live} pinned={v2.VERSION_PIN}"))
    db = db_source_path(home)
    ok = False
    detail = db
    if os.path.isfile(db):
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            con.close()
        except sqlite3.Error as exc:
            detail = f"{db}: {exc}"
    checks.append(("db-integrity", ok, detail))
    if install["command"]:
        try:
            proc = run([install["command"], "service", "status"], timeout=30)
            status = (proc.stdout or "").strip()
            checks.append(("service", proc.returncode == 0, status[:120]))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(("service", False,
                           f"{type(exc).__name__}: {exc}"))
        try:
            _row, observer = observer_plugin(install["command"])
            checks.append(("observer", "tui=True" in observer, observer))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(("observer", False,
                           f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(("service", False, "no command"))
        checks.append(("observer", False, "no command"))
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    return 0 if all(ok for _n, ok, _d in checks) else 1


# --- check / plan -----------------------------------------------------------

def check(args):
    if args.pr:
        adr = check_adr_amendment(args.repo, v2.VERSION_PIN)
        summary = canary_summary(args.repo, v2.VERSION_PIN)
        adr_file = adr_path(args.repo)
        text = (open(adr_file, encoding="utf-8").read()
                if os.path.isfile(adr_file) else "")
        ok = (all(row[1] for row in adr) and summary is not None
              and summary["ok"]
              and ("C1–C8" in text or "C1-C8" in text))
        if args.json:
            print(json.dumps({
                "pr": True, "ok": ok, "pinned": v2.VERSION_PIN,
                "residual": (summary or {}).get("residual"),
                "adr": [{"path": path, "ok": pass_, "detail": detail}
                        for path, pass_, detail in adr]}, indent=2))
        elif not ok:
            reason = ((summary or {}).get("reason")
                      or "canary evidence is missing or failing")
            print(f"FAIL: canary evidence for {v2.VERSION_PIN}: {reason}")
        else:
            print(f"PASS: canary evidence for {v2.VERSION_PIN} "
                  f"residual={summary['residual']}")
        return 0 if ok else 1
    results = check_seams(args.repo)
    failed = [row for row in results if not row[1]]
    latest = None
    update = False
    if args.remote:
        latest = latest_version(args.repo, refresh=args.refresh)
        if not latest:
            if args.json:
                print(json.dumps({"pinned": v2.VERSION_PIN,
                                  "latest": None, "error": "registry"}))
            else:
                print("FAIL: cannot read the registry")
            return 2
        update = version_key(latest) > version_key(v2.VERSION_PIN)
    if args.json:
        print(json.dumps({
            "pinned": v2.VERSION_PIN, "latest": latest,
            "update_available": update, "seams_ok": not failed,
            "seams": [{"path": path, "ok": pass_, "detail": detail}
                      for path, pass_, detail in results]}, indent=2))
    else:
        if args.remote:
            print(f"pinned={v2.VERSION_PIN} latest={latest}")
        for path, pass_, detail in results:
            print(f"{path}: {'PASS' if pass_ else 'FAIL'} {detail}")
        if update:
            print(f"update available: {latest}")
        elif not failed:
            print(f"PASS: {len(results)} pin seam(s) consistent "
                  f"at {v2.VERSION_PIN}")
    if failed:
        return 2 if args.remote else 1
    return 1 if update else 0


def plan(args):
    target = args.to or latest_version(args.repo, refresh=args.refresh)
    if not target:
        print("error: no target version (pass --to or --latest)",
              file=sys.stderr)
        return 2
    if target == v2.VERSION_PIN and not args.force:
        print(f"already current: {target}")
        return 0
    peers = read_json(args.plugin_json) if args.plugin_json \
        else plugin_peers(target, args.repo)
    if peers is None and not args.plugin_json:
        print("error: cannot read @opencode/plugin peer deps; pass "
              "--plugin-json or retry", file=sys.stderr)
        return 2
    if not isinstance(peers, dict) or not peers:
        print("error: empty peer-dependency payload for @opencode/plugin@"
              + target, file=sys.stderr)
        return 2
    opentui = resolve_opentui(target, args.opentui, peers)
    current = current_plugin(args.repo).get("peerDependencies") or {}
    rows = [
        ("CLI", v2.VERSION_PIN, target),
        ("@opencode/plugin", current.get("@opencode/plugin", "?"), target),
        ("@opentui/core", current.get("@opentui/core", "?"), opentui),
        ("@opentui/solid", current.get("@opentui/solid", "?"), opentui),
        ("solid-js", current.get("solid-js", "?"),
         peers.get("solid-js") or "?"),
    ]
    peer_specs = {
        "@opentui/core": peers.get("@opentui/core"),
        "@opentui/solid": peers.get("@opentui/solid"),
        "solid-js": peers.get("solid-js"),
    }
    releases = (read_json(args.releases_file) if args.releases_file
                else fetch_releases())
    notes = breaking_notes(releases, v2.VERSION_PIN, target)
    seams = [row for row in check_seams(args.repo, target, opentui)
             if not row[1]]
    if args.json:
        print(json.dumps({"target": target, "opentui": opentui,
                          "matrix": rows, "breaking": notes,
                          "seams": seams}, indent=2))
        return 0
    print(f"target: {target}  (pinned {v2.VERSION_PIN})")
    print("\ncompatibility:")
    for name, old, new in rows:
        compare = peer_specs.get(name) or new
        action = ("none" if str(old) == str(new) or satisfies(old, compare)
                  else "bump")
        print(f"  {name:<18} {old!s:<10} -> {new!s:<10} {action}")
    if notes:
        print("\nbreaking changes:")
        for tag, section in notes:
            print(f"  v{tag}:")
            for line in section.splitlines():
                print(f"    {line}")
    else:
        print("\nbreaking changes: none found in the release range")
    print(f"\npin seams to change: {len(seams)}")
    for path, _ok, detail in seams:
        print(f"  {path}: {detail}")
    print("\nnext:")
    print(f"  python3 scripts/opencode_upgrade.py upgrade --to {target}")
    print(f"  # or: opencode upgrade {target} --method yarn")
    return 0


# --- prepare ----------------------------------------------------------------

def seam_changes(repo=REPO, version=None, opentui=None):
    version = version or v2.VERSION_PIN
    opentui = opentui or current_opentui(repo)
    by_path = {}
    for seam in SEAMS:
        by_path.setdefault(seam["path"], []).append(seam)
    changes = []
    for rel, seams in by_path.items():
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        old = open(path, encoding="utf-8").read()
        new = old
        for seam in seams:
            new = re.sub(seam["pattern"],
                         seam["replacement"].format(version=version,
                                                    opentui=opentui), new,
                         flags=seam.get("flags", 0))
        if new != old:
            changes.append((seams, path, old, new))
    return changes


def append_adr_amendment(repo, version, opentui, summary, pending=False):
    path = adr_path(repo)
    text = open(path, encoding="utf-8").read()
    marker = f"version pin {version}.**"
    if marker in text:
        return False
    if pending:
        line = ("canary pending — run `opencode_upgrade.py canary` before "
                "applying")
    else:
        gates = " ".join(f"{k}={v}" for k, v in summary["gates"].items())
        line = (f"canary {gates}; migration residual {summary['residual']}")
    block = (
        f"\n**{now_date()} amendment — version pin {version}.** The pin moves "
        f"to `{version}`; `@opencode/plugin` is `{version}` and OpenTUI is "
        f"`{opentui}`. {line} (evidence `.scratch/v2-canary-{version}/`). "
        "The live switch is owner-run with `python3 scripts/opencode_upgrade.py "
        f"upgrade --to {version} --apply --drain-acknowledged`; it verifies "
        "the binary, config root, service, agents, and plugin loader. A failed "
        "verification leaves the repaired install in place and records "
        "`verified: false` with manual rollback guidance — there is no "
        "automatic rollback.\n")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(block)
    return True


def lockfile_delta(repo, paths):
    """Summarize the target entries and transitive churn in lockfiles."""
    rows = []
    for path in paths:
        old_text = run(["git", "-C", repo, "show", f"HEAD:{path}"], timeout=30)
        if old_text.returncode != 0:
            continue
        try:
            old = json.loads(old_text.stdout)
        except ValueError:
            continue
        new = read_json(os.path.join(repo, path)) or {}
        old_pkgs = old.get("packages") or {}
        new_pkgs = new.get("packages") or {}
        changed = sum(1 for key in set(old_pkgs) | set(new_pkgs)
                      if old_pkgs.get(key, {}).get("version")
                      != new_pkgs.get(key, {}).get("version"))
        target = [key for key in new_pkgs
                  if key.endswith(("@opencode/plugin", "@opentui/core",
                                   "@opentui/solid"))]
        rows.append(f"  {path}: {changed} package version(s) changed; "
                    f"target roots={len(target)}")
    return "\n".join(rows)


def prepare_failure_artifact(repo, target, stage, exc, completed, restored,
                             lockfiles=None):
    """Durable record of a prepare failure after mutation began."""
    path = os.path.join(repo, ".scratch", "opencode-v2",
                        f"prepare-{target}-failure.json")
    payload = {
        "target": target,
        "stage": stage,
        "exception": f"{type(exc).__name__}: {exc}",
        "completed": completed,
        "restored": restored,
        "lockfiles": lockfiles or [],
        "guidance": ("restore the listed files (for example "
                     "`git checkout -- <path>`) or the pre-prepare tree; "
                     "state remains at its prior completed stage"),
        "at": now_iso(),
    }
    write_json(path, payload)
    return path


def prepare(args):
    target = args.to or v2.VERSION_PIN
    peers = read_json(args.plugin_json) if args.plugin_json else \
        plugin_peers(target, args.repo)
    opentui = resolve_opentui(target, args.opentui, peers or {})
    changes = seam_changes(args.repo, target, opentui)
    plan_lines = []
    for seams, path, old, new in changes:
        for before, after in zip(old.splitlines(), new.splitlines()):
            if before != after:
                plan_lines.append(f"  {os.path.relpath(path, args.repo)}: "
                                  f"{before.strip()} -> {after.strip()}")
    if args.dry_run:
        print(f"would pin {target} (OpenTUI {opentui})")
        print("\n".join(plan_lines) or "  (no seam changes)")
        return 0
    summary = canary_summary(args.repo, target)
    pending = summary is None
    if (summary is None or not summary["ok"]) \
            and not args.allow_pending_canary:
        state = "missing" if summary is None else "not passing"
        print("error: canary evidence " + state + " for " + target
              + "; run `opencode_upgrade.py canary --to " + target
              + "` first (or pass --allow-pending-canary)", file=sys.stderr)
        return 2
    completed = []
    originals = {}
    lock_paths = []
    stage = "seams"
    try:
        for seams, path, old, new in changes:
            originals.setdefault(path, old)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
            completed.append({"action": "seam",
                              "path": os.path.relpath(path, args.repo)})
        stage = "plugin-json"
        for rel, has_cli, has_tui in PLUGIN_JSONS:
            path = os.path.join(args.repo, rel)
            data = read_json(path)
            if not isinstance(data, dict):
                raise RuntimeError(f"missing {rel}")
            originals.setdefault(path, open(path, encoding="utf-8").read())
            data["version"] = target
            if has_cli:
                for key in ("dependencies", "peerDependencies"):
                    if isinstance(data.get(key), dict) \
                            and "@opencode/plugin" in data[key]:
                        data[key]["@opencode/plugin"] = target
            if has_tui:
                peers = data.get("peerDependencies")
                if isinstance(peers, dict):
                    peers["@opentui/core"] = opentui
                    peers["@opentui/solid"] = opentui
            write_json(path, data)
            completed.append({"action": "plugin-json", "path": rel})
        stage = "npm-install"
        for name in PLUGIN_DIRS:
            directory = os.path.join(args.repo, "plugins", name)
            lock = os.path.join(directory, "package-lock.json")
            if os.path.isfile(lock):
                lock_paths.append(os.path.relpath(lock, args.repo))
            proc = run(["npm", "install", "--no-audit", "--no-fund",
                        "--silent"], cwd=directory, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"npm install failed in {directory}: "
                    f"{(proc.stderr or '')[-300:]}")
            completed.append({"action": "npm-install",
                              "path": os.path.relpath(directory, args.repo)})
        stage = "adr-amendment"
        adr = adr_path(args.repo)
        if os.path.isfile(adr):
            originals.setdefault(adr, open(adr, encoding="utf-8").read())
        append_adr_amendment(args.repo, target, opentui, summary or {},
                             pending=pending)
        completed.append({"action": "adr-amendment",
                          "path": os.path.relpath(adr, args.repo)})
        stage = "verify"
        results = check_seams(args.repo, target, opentui)
        failed = [row for row in results if not row[1]]
        stage = "lockfile-delta"
        delta = lockfile_delta(args.repo, lock_paths) if lock_paths else ""
        print(f"prepared {target} (OpenTUI {opentui}); "
              f"{len(changes)} seam(s), {len(failed)} failure(s)")
        if delta:
            print("lockfile delta:")
            print(delta)
        for path, ok, detail in failed:
            print(f"  {path}: FAIL {detail}")
        if failed:
            raise RuntimeError("seam verification failed: " + ", ".join(
                path for path, _ok, _detail in failed))
        stage = "state"
        write_state(args.repo, target, "prepared")
    except (OSError, subprocess.SubprocessError, RuntimeError,
            ValueError) as exc:
        restored = []
        for path, original in originals.items():
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(original)
                restored.append(os.path.relpath(path, args.repo))
            except OSError:
                pass
        artifact = prepare_failure_artifact(
            args.repo, target, stage, exc, completed, restored,
            lockfiles=lock_paths)
        print(f"error: prepare failed at {stage}: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        print(f"prepare failure artifact: {artifact}", file=sys.stderr)
        print("state preserved at its prior completed stage; restore guidance "
              "is in the artifact", file=sys.stderr)
        return 1
    if args.open_pr:
        return open_pr(args, target, opentui, summary or {})
    print(f"next: opencode upgrade {target} --method yarn")
    return 0


def pr_body(target, opentui, summary, notes):
    gates = " ".join(f"{k}={v}" for k, v in (summary.get("gates") or {}).items())
    lines = [
        f"## OpenCode {target} upgrade",
        "",
        f"Bumps `@opencode/cli` to `{target}`, `@opencode/plugin` to "
        f"`{target}`, and OpenTUI to `{opentui}`.",
        "",
        "### Canary",
        f"- {gates or 'missing'}; migration residual "
        f"{summary.get('residual')}",
        "",
        "### Breaking changes",
    ]
    for tag, section in notes or []:
        lines.append(f"- v{tag}: {section.splitlines()[0] if section else ''}")
    if not notes:
        lines.append("- none found in the release range")
    lines += [
        "",
        "### Apply (owner, supported install)",
        "```sh",
        "opencode service stop",
        f"python3 scripts/opencode_upgrade.py upgrade --to {target} "
        "--apply --drain-acknowledged",
        "```",
        "",
        "Rollback: `opencode upgrade <previous> --method yarn` and restore "
        "the pre-upgrade DB/config backup under `.scratch/opencode-v2/`.",
        "",
    ]
    return "\n".join(lines)


def open_pr(args, target, opentui, summary):
    notes = breaking_notes(fetch_releases(), v2.VERSION_PIN, target)
    body_path = os.path.join(args.repo, ".scratch", "opencode-v2",
                             f"pr-body-{target}.md")
    os.makedirs(os.path.dirname(body_path), exist_ok=True)
    with open(body_path, "w", encoding="utf-8") as fh:
        fh.write(pr_body(target, opentui, summary, notes))
    files = [seam["path"] for seam in SEAMS] + [row[0] for row in PLUGIN_JSONS]
    files.append(os.path.relpath(adr_path(args.repo), args.repo))
    lockfiles = [os.path.relpath(p, args.repo) for p in glob.glob(
        os.path.join(args.repo, "plugins", "*", "package-lock.json"))]
    files += lockfiles
    subprocess.run(["git", "-C", args.repo, "add"] + files, check=False)
    staged = run(["git", "-C", args.repo, "diff", "--cached", "--quiet"],
                 timeout=30)
    if staged.returncode != 0:
        commit = run(["git", "-C", args.repo, "commit", "-m",
                      f"chore(opencode): pin {target}"], timeout=120)
        if commit.returncode != 0:
            print(f"error: commit failed: {(commit.stderr or '')[-300:]}",
                  file=sys.stderr)
            return 2
    push = run(["git", "-C", args.repo, "push", "-u", "origin", "HEAD"],
               timeout=180)
    if push.returncode != 0:
        print(f"error: push failed: {(push.stderr or '')[-300:]}",
              file=sys.stderr)
        return 2
    branch = run(["git", "-C", args.repo, "branch", "--show-current"],
                 timeout=30).stdout.strip()
    title = f"chore(opencode): pin {target}"
    existing = run(["gh", "pr", "list", "--head", branch, "--json", "url",
                    "--jq", ".[0].url"], cwd=args.repo, env=gh_env(),
                   timeout=60)
    if existing.returncode == 0 and existing.stdout.strip():
        print(f"PR already open: {existing.stdout.strip()}")
        return 0
    created = run(["gh", "pr", "create", "--base", "main", "--head", branch,
                   "--title", title, "--body-file", body_path],
                  cwd=args.repo, env=gh_env(), timeout=120)
    if created.returncode != 0:
        print(f"error: gh pr create failed: "
              f"{(created.stderr or '')[-300:]}", file=sys.stderr)
        return 2
    print(created.stdout.strip())
    return 0


# --- canary / plugin compatibility -----------------------------------------

def plugin_compat(args, target, opentui):
    root = os.path.join(args.repo, ".scratch", "plugin-compat-" + target)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "plugins"), exist_ok=True)
    os.symlink(os.path.join(args.repo, "scripts"),
               os.path.join(root, "scripts"))
    lines = [f"date={now_date()}", f"target={target}",
             f"opentui={opentui}"]
    ok = True
    for name in PLUGIN_DIRS:
        src = os.path.join(args.repo, "plugins", name)
        dst = os.path.join(root, "plugins", name)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "node_modules", ".git"))
        data_path = os.path.join(dst, "package.json")
        data = read_json(data_path, {}) or {}
        data["version"] = target
        for key in ("dependencies", "peerDependencies"):
            if isinstance(data.get(key), dict):
                if "@opencode/plugin" in data[key]:
                    data[key]["@opencode/plugin"] = target
                if name in TUI_PLUGINS:
                    if "@opentui/core" in data[key]:
                        data[key]["@opentui/core"] = opentui
                    if "@opentui/solid" in data[key]:
                        data[key]["@opentui/solid"] = opentui
        write_json(data_path, data)
        install = run(["npm", "install", "--no-audit", "--no-fund",
                       "--silent"], cwd=dst, timeout=300)
        lines.append(f"{name}_install={install.returncode}")
        if install.returncode != 0:
            ok = False
            continue
        commands = ([["npm", "run", "typecheck"], ["npm", "test"]]
                    if name in TUI_PLUGINS else [["node", "test.mjs"]])
        for command in commands:
            proc = run(command, cwd=dst, timeout=300)
            lines.append(f"{name}_{'_'.join(command)}={proc.returncode}")
            if proc.returncode != 0:
                ok = False
                detail = (proc.stderr or proc.stdout or "").strip()
                lines.append(f"{name}_detail={detail[-400:]}")
    path = os.path.join(args.repo, ".scratch", "v2-canary-" + target,
                        "plugin-compat.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + f"\nplugin_compat={'PASS' if ok else 'FAIL'}\n")
    return ok, "\n".join(lines)


def default_bin_path(args):
    """The explicit default binary: --default-bin, --link, then the yarn link."""
    home = os.path.abspath(getattr(args, "home", None)
                           or os.path.expanduser("~"))
    return (getattr(args, "default_bin", None)
            or getattr(args, "link", None)
            or os.path.join(home, ".yarn", "bin", "opencode"))


def measure_default_version(args):
    """Measure the explicit default binary's exact version before canary.

    A V1 default (1.19.4) or a prior V2 (2.2.5) is measured here; an
    unmeasurable default fails closed with a named error.
    """
    binary = default_bin_path(args)
    try:
        proc = run([binary, "--version"], timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, (f"cannot measure default binary {binary}: "
                      f"{type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        return None, (f"default binary {binary} --version exited "
                      f"{proc.returncode}")
    version = v2.parse_opencode_version(proc.stdout)
    if not version:
        return None, (f"cannot parse default binary version from {binary}: "
                      f"{(proc.stdout or '').strip()!r}")
    return version, None


def canary_cmd(args, target, default_version=None):
    if default_version is None:
        default_version, error = measure_default_version(args)
        if error:
            raise RuntimeError(error)
    prefix = args.prefix or os.path.join(
        args.repo, ".scratch", "v2-" + target + "-prefix")
    v1_prefix = os.path.join(args.repo, ".scratch", "v1-prefix")
    os.makedirs(os.path.join(v1_prefix, "bin"), exist_ok=True)
    v1_bin = args.v1_bin or V1_BIN
    link = os.path.join(v1_prefix, "bin", "opencode")
    if os.path.isfile(v1_bin):
        if os.path.islink(link) or os.path.isfile(link):
            os.unlink(link)
        os.symlink(v1_bin, link)
    root = os.path.join(args.repo, ".scratch", "v2-canary-" + target)
    default_bin = default_bin_path(args)
    return [sys.executable, os.path.join(HERE, "opencode_v2_canary.py"),
            "--all", "--version", target,
            "--default-version", default_version,
            "--skip-install", "--prefix", prefix,
            "--opencode-bin", os.path.join(prefix, "bin", "opencode"),
            "--default-bin", default_bin, "--v1-prefix", v1_prefix,
            "--scratch-root", root]


def tui_setup_ok(log_text):
    """Every TUI plugin must complete setup, not merely be discovered."""
    return all(f"stage=setup plugin={name}" in log_text
               for name in TUI_PLUGINS)


def tui_smoke(args, target, opentui):
    """Start the candidate TUI in a PTY for a few seconds; prove setup.

    The 2.2.5 migration exposed a class of failure the typecheck missed: the
    TUI entrypoint was discovered but its setup/registration behavior differed.
    This runs the real candidate with the scratch plugin corpus and asserts
    the loader's `stage=setup` completion lines. A missing/broken `script`
    (util-linux) is a named canary failure, not an exception.
    """
    root = os.path.join(args.repo, ".scratch", "plugin-compat-" + target)
    config = os.path.join(root, "opencode")
    os.makedirs(config, exist_ok=True)
    write_json(os.path.join(config, "opencode.jsonc"), {
        "$schema": "https://opencode.ai/config.json",
        "plugins": ["../plugins/" + name for name in PLUGIN_DIRS],
    })
    binary = os.path.join(args.prefix or os.path.join(
        args.repo, ".scratch", "v2-" + target + "-prefix"), "bin", "opencode")
    log_path = os.path.join(args.repo, ".scratch", "v2-canary-" + target,
                            "tui-smoke.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    evidence = os.path.join(args.repo, ".scratch", "v2-canary-" + target,
                            "tui-smoke.txt")

    def emit(text, reason=None):
        detail = "\n".join([
            f"date={now_date()}",
            f"target={target}",
            f"opentui={opentui}",
            f"tui_binary={binary}",
            f"tui_setup={'PASS' if reason is None and tui_setup_ok(text) else 'FAIL'}",
            f"observer_setup={'PASS' if reason is None and 'stage=setup plugin=delegation-observer' in text else 'FAIL'}",
            f"sentinel_setup={'PASS' if reason is None and 'stage=setup plugin=delegation-sentinel' in text else 'FAIL'}",
        ] + ([f"reason={reason}"] if reason else []))
        with open(evidence, "w", encoding="utf-8") as fh:
            fh.write(detail + "\n")
        return reason is None and tui_setup_ok(text), detail

    script_bin = shutil.which("script")
    if not script_bin:
        return emit("", reason="script-not-available")
    env = dict(os.environ)
    env.update({
        "XDG_CONFIG_HOME": root,
        "OPENCODE_DB": os.path.join(root, "tui-smoke.db"),
        "OPENCODE_LOG_LEVEL": "debug",
    })
    command = " ".join(shlex.quote(part) for part in [
        binary, "--standalone", "--log-level", "debug", "--print-logs"])
    try:
        proc = subprocess.Popen([script_bin, "-qec", command, log_path],
                                env=env, start_new_session=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as exc:
        return emit("", reason=f"script-spawn-error: {exc}")
    try:
        proc.wait(timeout=getattr(args, "tui_timeout", 20))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    text = ""
    if os.path.isfile(log_path):
        text = open(log_path, encoding="utf-8", errors="replace").read()
    return emit(text)


def canary(args):
    target = args.to or v2.VERSION_PIN
    default_version, error = measure_default_version(args)
    if error:
        print(f"canary: FAIL — {error}", file=sys.stderr)
        return 1
    prefix = args.prefix or os.path.join(
        args.repo, ".scratch", "v2-" + target + "-prefix")
    if not args.skip_install:
        try:
            install = run(["npm", "install", "--global", "--prefix", prefix,
                           "@opencode/cli@" + target], timeout=600)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"error: install spawn failed: {exc}", file=sys.stderr)
            return 2
        if install.returncode != 0:
            print(f"error: install failed: {(install.stderr or '')[-400:]}",
                  file=sys.stderr)
            return 2
    argv = canary_cmd(args, target, default_version=default_version)
    print("canary: " + " ".join(argv))
    try:
        proc = run(argv, cwd=args.repo, timeout=1800, stream=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"canary: FAIL — canary probe error: {exc}", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print("canary: FAIL", file=sys.stderr)
        return proc.returncode
    peers = read_json(args.plugin_json) if args.plugin_json else \
        plugin_peers(target, args.repo)
    opentui = resolve_opentui(target, args.opentui, peers or {})
    try:
        ok, detail = plugin_compat(args, target, opentui)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"canary: FAIL — plugin compatibility probe error: {exc}",
              file=sys.stderr)
        return 1
    print(detail)
    if not ok:
        print("canary: FAIL — manual plugin migration required",
              file=sys.stderr)
        return 1
    try:
        tui_ok, tui_detail = tui_smoke(args, target, opentui)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"canary: FAIL — TUI probe error: {exc}", file=sys.stderr)
        return 1
    print(tui_detail)
    if not tui_ok:
        print("canary: FAIL — TUI plugin setup is incomplete",
              file=sys.stderr)
        return 1
    write_state(args.repo, target, "canaried")
    print("canary: PASS")
    return 0


# --- apply / rollback -------------------------------------------------------

# --- supported upgrade: backup / official command / post-smoke ---------------

def sqlite_backup(source, dest):
    """Delegate to the shared 0600-preserving backup helper."""
    return v2.sqlite_backup(source, dest)


def db_source_path(home):
    """The DB the apply snapshots: env override first, then the explicit HOME."""
    return v2.db_path_for_home(home)


def pre_upgrade_backup(args, target):
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")
    root = os.path.join(args.repo, ".scratch", "opencode-v2",
                        "pre-upgrade-" + stamp)
    os.makedirs(root, exist_ok=True)
    source_db = db_source_path(home)
    db = os.path.join(root, "opencode.db")
    if os.path.isfile(source_db):
        sqlite_backup(source_db, db)
    else:
        db = None  # first install: no DB existed, so cite no backup path
    source_config = os.path.join(home, ".config", "opencode")
    target_config = os.path.join(root, "config")
    config = None
    config_error = None
    if os.path.isdir(source_config):
        try:
            shutil.copytree(source_config, target_config, symlinks=True,
                            ignore=shutil.ignore_patterns("node_modules"))
            config = target_config
        except OSError as exc:
            config_error = f"{type(exc).__name__}: {exc}"
    write_json(os.path.join(root, "backup.json"), {
        "db": db if db and os.path.isfile(db) else None,
        "config": config,
        "config_error": config_error,
        "at": now_iso(),
    })
    return root, db


def resume_migration(args, home, link):
    """Re-arm the real DB cursor, start the repaired V2 service, wait, verify.

    This runs only in the explicit owner-run apply, after the drain/backup and
    the shadow repair, before the post-smoke. Vendor behavior: a completed
    `kv.migration.v1-v2` row never imports V1 sessions created below an old
    cursor, so the apply must re-arm `{"phase":"sessions"}` (no cursor) and
    wait for the service to write `{"phase":"completed"}`. The result is
    recorded in the apply artifact; any failure/timeout stops the service and
    is a truthful apply failure, never a residual acceptance.
    """
    db = db_source_path(home)
    result = {
        "db": db, "skipped": None, "error": None, "ok": False,
        "verified": False, "armed": False, "phase": None,
        "timed_out": False, "elapsed_seconds": 0.0,
        "service_start_exit": None,
        "source_session_rows": 0, "pre_existing_v2_rows": 0,
        "target_session_rows": 0, "migrated_source_rows": 0,
        "missing_source_rows": 0, "missing_baseline_rows": 0,
        "target_only_ids": 0, "run_created_ids": 0,
    }
    if not db or not os.path.isfile(db):
        result.update({"ok": True, "verified": True,
                       "skipped": "source DB absent"})
        return result
    try:
        src_ids = v2.read_ids(db, "session")
        baseline_ids = v2.read_ids(db, "session_v2")
        result["source_session_rows"] = len(src_ids)
        result["pre_existing_v2_rows"] = len(baseline_ids)
        if not src_ids:
            result.update({"ok": True, "verified": True,
                           "skipped": "no V1 sessions"})
            return result
        result["armed"] = v2.arm_migration_phase(db)
        start = run([link, "service", "start"], timeout=60)
        result["service_start_exit"] = start.returncode
        if start.returncode != 0:
            result["error"] = (
                f"service start exited {start.returncode}: "
                f"{(start.stderr or '').strip()[:240]}")
            return result
        state = v2.wait_for_migration(
            db, MIGRATION_APPLY_TIMEOUT, MIGRATION_APPLY_POLL_INTERVAL)
        result.update({
            "phase": state["phase"],
            "timed_out": state["timed_out"],
            "elapsed_seconds": round(state["elapsed"], 2),
        })
        target_ids = v2.read_ids(db, "session_v2")
        member = v2.migration_membership(
            src_ids, target_ids, baseline_ids=baseline_ids)
        missing_baseline = baseline_ids - target_ids
        result.update({
            "target_session_rows": len(target_ids),
            "migrated_source_rows": len(src_ids & target_ids),
            "missing_source_rows": len(member["missing"]),
            "missing_baseline_rows": len(missing_baseline),
            "target_only_ids": len(member["phantom"]),
            "run_created_ids": member["run"],
        })
        result["ok"] = bool(
            state["completed"] and not member["missing"]
            and not missing_baseline)
        result["verified"] = result["ok"]
        if not result["ok"] and not result["error"]:
            result["error"] = (
                "migration did not complete"
                if not state["completed"] else
                f"{len(member['missing'])} source V1 IDs missing, "
                f"{len(missing_baseline)} baseline V2 IDs missing")
        return result
    except (OSError, subprocess.SubprocessError, sqlite3.Error) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        if not result["ok"]:
            try:
                run([link, "service", "stop"], timeout=60)
            except (OSError, subprocess.SubprocessError):
                pass


def official_upgrade(args, target, command=None):
    """Run the official upgrade through the explicit default link."""
    command = command or default_bin_path(args)
    proc = run([command, "upgrade", target, "--method", args.method],
               timeout=900, stream=True)
    return proc.returncode


def api_version(stdout, target):
    """True only when the API payload's version equals `target` exactly."""
    try:
        data = json.loads(stdout or "{}")
    except ValueError:
        return False, "api returned non-JSON"
    version = data.get("version") if isinstance(data, dict) else None
    return version == target, f"version={version}"


def post_upgrade_smoke(args, target, command=None):
    """Post-apply verification against an explicit, repaired executable."""
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    command = command or default_bin_path(args)
    expected = os.path.join(home, ".config", "opencode")
    checks = []
    live = version_of(command)
    checks.append(("binary", live == target, live or "unknown"))
    config_root = config_root_of(command)
    checks.append(("config-root",
                   config_root is not None
                   and os.path.realpath(config_root) == os.path.realpath(
                       expected),
                   f"{config_root} (expected {expected})"))
    try:
        info = run([command, "api", "GET", "/api/info"], timeout=60)
        api_ok, api_detail = api_version(info.stdout, target)
        checks.append(("api", api_ok and info.returncode == 0, api_detail))
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks.append(("api", False, f"{type(exc).__name__}: {exc}"))
    agents = post_smoke.check_agents_live(command, REPO)
    checks.append(("agents", agents[0], agents[1]))
    plugin = post_smoke.check_plugin(framework=REPO,
                                     config_root=os.path.dirname(expected),
                                     binary=command)
    checks.append(("plugin", plugin[0], plugin[1][:240]))
    _row, observer = observer_plugin(command)
    checks.append(("observer", "tui=True" in observer, observer))
    return checks


def apply_artifact(args, target, home, link, backup, previous_default, stage,
                   checks, verified=False, db=None):
    """Build the apply evidence artifact (success or failure)."""
    current_link = link_state(link)
    backup_meta = (read_json(os.path.join(backup, "backup.json"))
                   if backup else None)
    if isinstance(backup_meta, dict):
        # Metadata is authoritative: a config:null/config_error record means
        # the partial <backup>/config directory is NOT a restore source.
        config_backup = backup_meta.get("config")
        database_backup = backup_meta.get("db") or db
        config_error = backup_meta.get("config_error")
    else:
        # Legacy/pre-metadata backup: infer from the tree.
        backup_meta = None
        config_backup = (os.path.join(backup, "config")
                         if backup and os.path.isdir(
                             os.path.join(backup, "config")) else None)
        database_backup = db
        config_error = None
    return {
        "version": target,
        "verified": verified,
        "rolled_back": False,
        "failure_stage": stage,
        "checks": {name: {"ok": ok, "detail": detail}
                   for name, ok, detail in checks},
        "backup": backup,
        "backup_metadata": backup_meta,
        "config_backup": config_backup,
        "config_backup_error": config_error,
        "database_backup": database_backup,
        "database_source": db_source_path(home) if home else None,
        "target_package": target_package_info(home, target),
        "default_link": current_link,
        "default_version": current_link["version"],
        "previous_default": previous_default,
        "rollback": rollback_plan(link, previous_default, backup,
                                  args.method, home=home,
                                  config_backup=config_backup,
                                  db=database_backup),
        "at": now_iso(),
    }


def apply_supported(args, target):
    if not getattr(args, "drain_acknowledged", False):
        print("error: --apply requires --drain-acknowledged", file=sys.stderr)
        return 2
    if not getattr(args, "skip_canary", False):
        summary = canary_summary(args.repo, target)
        if summary is None:
            print("error: no canary evidence at .scratch/v2-canary-"
                  + target + "/; fresh hardened canary evidence is required. "
                  "Run `" + canary_command(target) + "` before apply.",
                  file=sys.stderr)
            return 2
        if not summary["ok"]:
            print("error: canary prerequisite not met for " + target + ": "
                  + (summary.get("reason") or "canary evidence is not passing"),
                  file=sys.stderr)
            return 2
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    link = args.link or os.path.join(home, ".yarn", "bin", "opencode")
    previous_default = link_state(link)
    if getattr(args, "dry_run", False):
        resolved, _evidence = resolve_target_binary(home, target)
        artifact = os.path.join(args.repo, ".scratch", "opencode-v2",
                                f"upgrade-{target}-verify.json")
        if getattr(args, "stop_service", False):
            print("would stop the service before the drain check")
        print("would check the drain gate (no OpenCode/supervision processes)")
        print("would back up any existing DB/config under .scratch/opencode-v2/")
        if resolved:
            print(f"would reuse the installed {target} V2 package at "
                  f"{resolved}")
        else:
            print(f"would install {target} via the official command")
        print(f"would repair the default {link} shadow to the V2 package")
        print("would re-arm the DB migration cursor, start the repaired V2 "
              "service, wait for migration completion, and verify every "
              "source V1 ID plus the pre-existing V2 baseline")
        print("would run the post-upgrade smoke (binary, config root, API, "
              "agents, plugin loader, observer)")
        print(f"would write {artifact} and update upgrade-state.json")
        return 0
    artifact = os.path.join(args.repo, ".scratch", "opencode-v2",
                            f"upgrade-{target}-verify.json")
    backup = None
    db = None
    migration = None
    stage = "preflight"

    def restore_text():
        meta = (read_json(os.path.join(backup, "backup.json"))
                if backup else None)
        if isinstance(meta, dict):
            # Metadata is authoritative; never fall back to a partial config
            # directory recorded as config:null.
            config_path = meta.get("config")
            database = meta.get("db")
        else:
            config_path = (os.path.join(backup, "config")
                           if backup and os.path.isdir(
                               os.path.join(backup, "config")) else None)
            database = db
        parts = []
        if config_path:
            parts.append(f"config: {config_path}")
        if database:
            parts.append(f"DB: {database}")
        if not parts:
            return "no config/DB pre-upgrade snapshot was created"
        return "restore " + "; ".join(parts)

    def record_failure(failure_stage, checks, extra=None):
        payload = apply_artifact(args, target, home, link, backup,
                                 previous_default, failure_stage, checks,
                                 verified=False, db=db)
        if extra:
            payload.update(extra)
        write_apply_artifact(artifact, payload)
        write_state(args.repo, target, "prepared",
                    {"artifact": artifact, "verified": False}, force=True)
        return payload

    try:
        if getattr(args, "stop_service", False):
            stage = "stop-service"
            stopped = run([link, "service", "stop"], timeout=60)
            print(f"service stop: {stopped.returncode}")
        stage = "drain"
        running = stage_config.live_processes()
        if running and not getattr(args, "force", False):
            print("error: OpenCode/supervision processes are running:",
                  file=sys.stderr)
            for line in running[:10]:
                print("  " + line, file=sys.stderr)
            print("close the TUI and run `opencode service stop`, then retry "
                  "(or --force).", file=sys.stderr)
            return 2
        write_state(args.repo, target, "prepared")
        stage = "backup"
        backup, db = pre_upgrade_backup(args, target)
        stage = "install"
        resolved, _evidence = resolve_target_binary(home, target)
        if resolved is None:
            print(f"installing {target} via the official command",
                  file=sys.stderr)
            rc = official_upgrade(args, target, link)
            if rc != 0:
                payload = record_failure("official-install", [])
                print(f"error: official upgrade exited {rc}", file=sys.stderr)
                for line in rollback_lines(payload["rollback"]):
                    print(f"rollback: {line}", file=sys.stderr)
                return rc
        stage = "shadow"
        shadow = prepare_shadow(home, link, target)
        if shadow["failure_stage"]:
            payload = record_failure(shadow["failure_stage"], [],
                                     extra={"shadow": shadow})
            print(f"error: shadow repair failed at {shadow['failure_stage']}",
                  file=sys.stderr)
            print(f"link: {link}; target package: "
                  f"{payload['target_package']['path']}", file=sys.stderr)
            for line in rollback_lines(payload["rollback"]):
                print(f"rollback: {line}", file=sys.stderr)
            return 1
        stage = "migration"
        migration = resume_migration(args, home, link)
        if not migration["ok"]:
            payload = record_failure("migration", [],
                                     extra={"migration": migration})
            print("error: post-upgrade migration did not complete: "
                  + (migration.get("error") or "unknown"), file=sys.stderr)
            print(f"migration evidence: {artifact}", file=sys.stderr)
            for line in rollback_lines(payload["rollback"]):
                print(f"rollback: {line}", file=sys.stderr)
            print(f"restore: {restore_text()}", file=sys.stderr)
            return 1
        stage = "smoke"
        checks = post_upgrade_smoke(args, target, command=link)
        failed = [name for name, ok, _detail in checks if not ok]
        verified = not failed
        payload = apply_artifact(args, target, home, link, backup,
                                 previous_default, failed[0] if failed else None,
                                 checks, verified=verified, db=db)
        payload["shadow"] = shadow
        payload["migration"] = migration
        write_apply_artifact(artifact, payload)
        for name, ok, detail in checks:
            print(f"verify {name}: {'PASS' if ok else 'FAIL'} {detail}")
        if verified:
            write_state(args.repo, target, "applied", {"artifact": artifact})
            print(f"UPGRADE OK {target} evidence={artifact}")
            return 0
        write_state(args.repo, target, "prepared",
                    {"artifact": artifact, "verified": False}, force=True)
        print("error: post-upgrade smoke failed", file=sys.stderr)
        for line in rollback_lines(payload["rollback"]):
            print(f"rollback: {line}", file=sys.stderr)
        print(f"restore: {restore_text()}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, sqlite3.Error) as exc:
        failure_stage = f"exception:{stage}"
        extra = {"exception": f"{type(exc).__name__}: {exc}"}
        if migration is not None:
            extra["migration"] = migration
        payload = record_failure(failure_stage, [], extra=extra)
        print(f"error: apply aborted during {stage}: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        for line in rollback_lines(payload["rollback"]):
            print(f"rollback: {line}", file=sys.stderr)
        print(f"restore: {restore_text()}", file=sys.stderr)
        return 1


def scratch_dirs(repo):
    base = os.path.join(repo, ".scratch")
    found = []
    for pattern in ("v2-*-prefix", "v2-canary-*", "plugin-compat-*"):
        found.extend(glob.glob(os.path.join(base, pattern)))
    return [p for p in found if os.path.isdir(p) and not os.path.islink(p)]


def prune(args):
    versions = {}
    for path in scratch_dirs(args.repo):
        name = os.path.basename(path)
        match = re.search(r"(\d+\.\d+\.\d+)", name)
        if match:
            versions.setdefault(match.group(1), []).append(path)
    keep = set(sorted(versions, key=version_key)[-(args.keep or 1):])
    keep.add(v2.VERSION_PIN)
    removed = 0
    for version, paths in versions.items():
        if version in keep:
            continue
        for path in paths:
            print(f"{'would remove' if args.dry_run else 'remove'} {path}")
            if not args.dry_run:
                shutil.rmtree(path, ignore_errors=True)
            removed += 1
    print(f"prune: {removed} path(s); kept {sorted(keep, key=version_key)}")
    return 0


def upgrade(args):
    target = args.to or latest_version(args.repo, refresh=args.refresh)
    if not target:
        print("error: no target version", file=sys.stderr)
        return 2
    home, link = live_paths(args)
    install = topology(home, link)
    shadow = None
    if not install["supported"]:
        shadow = shadow_state(home, link, target)
        if not (shadow["target_installed"] and shadow["supported_config"]):
            print("error: this is not the supported install layout; migrate "
                  "first:", file=sys.stderr)
            print("  python3 scripts/stage_opencode_config.py --backup",
                  file=sys.stderr)
            print(f"  opencode upgrade {v2.VERSION_PIN} --method yarn",
                  file=sys.stderr)
            return 2
        if not args.apply:
            if not print_canary_prerequisite(args.repo, target):
                print(f"shadow repair needed: {repair_command(target)}")
            return 0
    live = version_of(install["command"]) if install["command"] else None
    if target == v2.VERSION_PIN and not args.force:
        if shadow is None:
            shadow = shadow_state(home, link, target)
        prior = last_verify_verified(args.repo, target)
        healthy = (live == target and install["supported"]
                   and (shadow["shadow_ok"] or not shadow["target_installed"]))
        if healthy and prior is not False:
            print(f"already current: {target}")
            return 0
        if args.apply:
            return apply_supported(args, target)
        if not print_canary_prerequisite(args.repo, target):
            label = ("verification needed" if shadow["shadow_ok"]
                     else "shadow repair needed")
            print(f"{label}: {repair_command(target)}")
        return 0
    if args.dry_run:
        rc = plan(argparse.Namespace(
            to=target, repo=args.repo, plugin_json=args.plugin_json,
            releases_file=args.releases_file, refresh=args.refresh,
            opentui=args.opentui, force=False, json=False))
        if rc != 0:
            return rc
        resolved, _evidence = resolve_target_binary(home, target)
        artifact = os.path.join(args.repo, ".scratch", "opencode-v2",
                                f"upgrade-{target}-verify.json")
        if getattr(args, "stop_service", False):
            print("would stop the service before the drain check")
        print("would check the drain gate (no OpenCode/supervision processes)")
        print("would back up any existing DB/config under .scratch/opencode-v2/")
        if resolved:
            print(f"would reuse the installed {target} V2 package at {resolved}")
        else:
            print(f"would run: {install['command']} upgrade {target} "
                  f"--method {args.method}")
        print(f"would repair the default {link} shadow to the V2 package")
        print("would re-arm the DB migration cursor, start the repaired V2 "
              "service, wait for migration completion, and verify every "
              "source V1 ID plus the pre-existing V2 baseline")
        print("would run the post-upgrade smoke (binary, config root, API, "
              "agents, plugin loader, observer)")
        print(f"would write {artifact} and update upgrade-state.json")
        return 0
    state = read_state(args.repo)
    stages_done = (completed_stages(state)
                   if state.get("target") == target else set())
    if not args.resume or "planned" not in stages_done:
        rc = plan(argparse.Namespace(
            to=target, repo=args.repo, plugin_json=args.plugin_json,
            releases_file=args.releases_file, refresh=args.refresh,
            opentui=args.opentui, force=False, json=False))
        if rc != 0:
            return rc
        write_state(args.repo, target, "planned")
        stages_done.add("planned")
    if "canaried" not in stages_done:
        rc = canary(args)
        if rc != 0:
            return rc
    if "prepared" not in stages_done:
        rc = prepare(args)
        if rc != 0:
            return rc
    if args.apply:
        return apply_supported(args, target)
    print(f"ready: run `opencode upgrade {target} --method {args.method}` "
          "from a normal terminal after closing every session")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="OpenCode upgrade orchestrator")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "check", "plan", "prepare", "canary",
                 "prune", "upgrade"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--to", default=None)
        cmd.add_argument("--repo", default=REPO)
        cmd.add_argument("--home", default=None)
        cmd.add_argument("--link", default=None)
        cmd.add_argument("--prefix", default=None)
        cmd.add_argument("--v1-bin", default=None)
        cmd.add_argument("--plugin-json", default=None)
        cmd.add_argument("--releases-file", default=None)
        cmd.add_argument("--opentui", default=None)
        cmd.add_argument("--latest", default=None)
        cmd.add_argument("--refresh", action="store_true")
        cmd.add_argument("--remote", action="store_true")
        cmd.add_argument("--pins-only", action="store_true")
        cmd.add_argument("--pr", action="store_true")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--dry-run", action="store_true")
        cmd.add_argument("--open-pr", action="store_true")
        cmd.add_argument("--skip-install", action="store_true")
        cmd.add_argument("--skip-canary", action="store_true")
        cmd.add_argument("--allow-pending-canary", action="store_true")
        cmd.add_argument("--stop-service", action="store_true")
        cmd.add_argument("--drain-acknowledged", action="store_true")
        cmd.add_argument("--force", action="store_true")
        cmd.add_argument("--resume", action="store_true")
        cmd.add_argument("--apply", action="store_true")
        cmd.add_argument("--keep", type=int, default=1)
        cmd.add_argument("--method", default="yarn",
                         choices=("curl", "npm", "pnpm", "bun", "yarn", "vp",
                                  "brew", "winget"),
                         help="supported OpenCode upgrade method")
        cmd.add_argument("--default-bin", default=None,
                         help="current default opencode for canary C1")
        cmd.add_argument("--tui-timeout", type=int, default=20)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "status":
        payload = status_payload(args)
        print_status(payload, args.json)
        return 0
    if args.command == "doctor":
        return doctor(args)
    if args.command == "check":
        return check(args)
    if args.command == "plan":
        return plan(args)
    if args.command == "prepare":
        return prepare(args)
    if args.command == "canary":
        return canary(args)
    if args.command == "prune":
        return prune(args)
    if args.command == "upgrade":
        return upgrade(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
