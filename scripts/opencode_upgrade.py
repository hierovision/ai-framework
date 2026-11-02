#!/usr/bin/env python3
"""OpenCode upgrade orchestrator — one entry point, canary-gated, reversible.

The adapter (`opencode_v2.py`) owns the pinned version; this script owns the
upgrade workflow around it:

  status    topology + pinned/live/latest + last canary/apply + next command
  doctor    read-only health check of the live install
  check     offline pin seams (--pins-only), registry drift (--remote), or the
            commit-visible canary gate (--pr)
  plan      target compatibility matrix + breaking-change notes; no writes
  prepare   bump every seam, plugin peer/lockfile roots, and the ADR amendment
  canary    install the candidate in scratch + full canary + plugin typechecks
  apply     drained atomic switch + post-switch verification + auto-rollback
  rollback  restore the previous wrapper link and pre-upgrade DB
  prune     remove old scratch prefixes/canary/compat dirs (--keep N)
  upgrade   check -> plan -> canary -> prepare (stop before apply)

The only human-gated step is `apply`: it needs a TTY, a drained process set,
and `--drain-acknowledged`-equivalent consent. A failure after the switch
restores the previous link and the pre-upgrade DB and reports ROLLED BACK.

All writes are under the repo or `$HOME/.local/lib/opencode`; scratch lives in
`.scratch/opencode-v2/`. Secrets are never printed (auth is read by the
canary, not this script).
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402
import opencode_v2_cutover as cutover  # noqa: E402
import opencode_v2_post_smoke as post_smoke  # noqa: E402

STATE_DIR = os.path.join(REPO, ".scratch", "opencode-v2")
STATE_FILE = os.path.join(STATE_DIR, "upgrade-state.json")
CACHE_FILE = os.path.join(STATE_DIR, "version-cache.json")
DEFAULT_PREFIX = os.path.join(REPO, ".scratch", "v2-prefix")
DEFAULT_SCRATCH = os.path.join(REPO, ".scratch", "opencode-v2", "cutover")
V1_BIN = os.path.expanduser(
    "~/.config/yarn/global/node_modules/opencode-ai/bin/opencode.exe")
RELEASES_URL = ("https://api.github.com/repos/anomalyco/opencode/"
                "releases?per_page=100")
CACHE_TTL = 3600
PLUGIN_DIRS = ("auto-compact-at-threshold", "delegation-observer",
               "delegation-sentinel")
TUI_PLUGINS = ("delegation-observer", "delegation-sentinel")


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
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def run(argv, cwd=None, env=None, timeout=120, stream=False):
    """Run a command; stream=True passes stdout/stderr through to the user."""
    if stream:
        return subprocess.run(argv, cwd=cwd, env=env, timeout=timeout)
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def version_key(value):
    return tuple(int(p) for p in re.findall(r"\d+", value)[:3])


def satisfies(current, spec):
    """True when `current` meets a simple exact/`>=`/`*` peer range."""
    spec = (spec or "").strip()
    if not spec or spec == "*":
        return True
    match = re.fullmatch(r">=\s*(\d+\.\d+\.\d+)", spec)
    if match:
        return version_key(current) >= version_key(match.group(1))
    if re.fullmatch(r"\d+\.\d+\.\d+", spec):
        return current == spec
    return True


def parse_version(text):
    match = re.search(r"(\d+\.\d+\.\d+)", text or "")
    return match.group(1) if match else None


def gh_env():
    """`gh` must read the user's config even when the V2 wrapper set XDG."""
    env = dict(os.environ)
    env["GH_CONFIG_DIR"] = os.path.expanduser("~/.config/gh")
    return env


def state_path(repo):
    return os.path.join(repo, ".scratch", "opencode-v2", "upgrade-state.json")


STAGE_ORDER = ("checked", "planned", "canaried", "prepared", "applied")


def read_state(repo):
    return read_json(state_path(repo), {}) or {}


def completed_stages(state):
    """A later recorded stage implies every earlier stage completed."""
    done = set((state.get("stages") or {}).keys())
    for index, stage in enumerate(STAGE_ORDER):
        if stage in done:
            done.update(STAGE_ORDER[:index + 1])
    return done


def write_state(repo, target, stage, detail=None):
    state = read_state(repo)
    if state.get("target") != target:
        state = {"target": target, "stages": {}}
    state["stage"] = stage
    state.setdefault("stages", {})[stage] = {
        "at": now_iso(), "detail": detail or "ok"}
    state["updated"] = now_iso()
    return write_json(state_path(repo), state)


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


def canary_summary(repo=REPO, version=None):
    """Read the canary evidence; None when no evidence exists."""
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
    migration = os.path.join(root, "migration-rehearsal.txt")
    residual = None
    if os.path.isfile(migration):
        match = re.search(r"^source_sessions_not_migrated=(\d+)$",
                          open(migration, encoding="utf-8").read(),
                          re.MULTILINE)
        residual = int(match.group(1)) if match else None
    return {"root": root, "gates": gates, "residual": residual,
            "ok": all(v == "PASS" for v in gates.values())
            and residual == 0}


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
    proc = run(["npm", "view", "@opencode/cli", "version"], timeout=60)
    if proc.returncode != 0:
        return None
    latest = parse_version(proc.stdout)
    if latest:
        write_json(os.path.join(repo, ".scratch", "opencode-v2",
                                "version-cache.json"),
                   {"latest": latest, "at": time.time()})
    return latest


def plugin_peers(version, repo=REPO):
    proc = run(["npm", "view", "@opencode/plugin@" + version,
                "peerDependencies", "--json"], timeout=60)
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
    proc = run(["npm", "view", "@opentui/core", "version"], timeout=60)
    latest = parse_version(proc.stdout) if proc.returncode == 0 else None
    return latest or current_opentui()


# --- status / doctor --------------------------------------------------------

def live_paths(args):
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    link = args.link or os.path.join(home, ".yarn", "bin", "opencode")
    return home, link


def topology(home, link):
    target = os.readlink(link) if os.path.islink(link) else None
    wrapper = None
    config_root = None
    if target and os.path.isfile(target):
        wrapper = open(target, encoding="utf-8", errors="replace").read()
        match = re.search(r'XDG_CONFIG_HOME="([^"]+)"', wrapper)
        config_root = match.group(1) if match else None
    v1_path = os.path.join(home, ".config", "yarn", "global", "node_modules",
                           "opencode-ai", "package.json")
    v1 = read_json(v1_path, {}) or {}
    return {
        "link": link,
        "link_target": target,
        "wrapper": target if wrapper else None,
        "config_root": config_root,
        "v1_rollback": v1.get("version"),
        "v1_package": v1_path if v1 else None,
    }


def status_payload(args):
    home, link = live_paths(args)
    pinned = v2.VERSION_PIN
    live = cutover.version_of(link)
    latest = (args.latest or latest_version(args.repo, refresh=args.refresh)
              if args.remote else args.latest)
    state = read_state(args.repo)
    canary = canary_summary(args.repo, pinned)
    verify = read_json(os.path.join(
        args.repo, ".scratch", "opencode-v2",
        f"upgrade-{pinned}-verify.json"), {}) or {}
    next_command = "up to date"
    if live != pinned:
        next_command = ("python3 scripts/opencode_upgrade.py apply "
                        f"--to {pinned}")
    elif latest and version_key(latest) > version_key(pinned):
        next_command = ("python3 scripts/opencode_upgrade.py upgrade "
                        "--to " + latest)
    elif state.get("stage") and state.get("stage") not in (
            "applied", "rolled-back"):
        next_command = ("python3 scripts/opencode_upgrade.py upgrade "
                        "--resume")
    return {
        "pinned": pinned,
        "live": live,
        "latest": latest,
        "install": topology(home, link),
        "canary": canary,
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
    print(f"  link:          {install['link']}")
    print(f"  link target:   {install['link_target'] or 'missing'}")
    print(f"  config root:   {install['config_root'] or 'unknown'}")
    print(f"  V1 rollback:   {install['v1_rollback'] or 'not installed'}")
    canary = payload["canary"]
    if canary:
        gates = " ".join(f"{k}={v}" for k, v in canary["gates"].items())
        print(f"last canary:   {gates} residual={canary['residual']}")
    else:
        print("last canary:   none")
    if payload["last_apply"]:
        print(f"last apply:    {payload['last_apply'].get('version')} "
              f"rolled_back={payload['last_apply'].get('rolled_back')}")
    state = payload["state"]
    if state:
        print(f"upgrade state: {state.get('target')} at {state.get('stage')}")
    print(f"next:    {payload['next']}")


def doctor(args):
    home, link = live_paths(args)
    checks = []
    checks.append(("link", os.path.exists(link), link))
    target = os.readlink(link) if os.path.islink(link) else None
    checks.append(("link-target", bool(target and os.path.exists(target)),
                   target or "missing"))
    install = topology(home, link)
    checks.append(("config-root", bool(install["config_root"]
                                      and os.path.isdir(
                                          install["config_root"])),
                   install["config_root"] or "missing"))
    live = cutover.version_of(link)
    checks.append(("version", live == v2.VERSION_PIN,
                   f"live={live} pinned={v2.VERSION_PIN}"))
    db = (os.path.join(home, ".local", "share", "opencode", "opencode.db")
          if args.home else v2.DEFAULT_DB)
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
    proc = run([link, "service", "status"], timeout=30) if live else None
    status = (proc.stdout or "").strip() if proc else "no live binary"
    checks.append(("service", proc is not None and proc.returncode == 0,
                   status[:120]))
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
            print(f"FAIL: canary evidence for {v2.VERSION_PIN} "
                  "is missing or failing")
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
        action = ("none" if str(old) == str(new) or satisfies(old, new)
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
    print(f"  python3 scripts/opencode_upgrade.py canary --to {target}")
    print(f"  python3 scripts/opencode_upgrade.py prepare --to {target}")
    print(f"  python3 scripts/opencode_upgrade.py apply --to {target} "
          "--drain-acknowledged")
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
        "The live switch is owner-run with `scripts/opencode_upgrade.py "
        "apply` (drained TTY), which verifies the binary, service, agents, "
        "and plugin loader and rolls back link + DB on failure.\n")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(block)
    return True


def lockfile_delta(repo, paths):
    """Summarize the target entries and transitive churn in lockfiles."""
    rows = []
    for path in paths:
        full = os.path.join(repo, path)
        old_text = run(["git", "-C", repo, "show", f"HEAD:{path}"], timeout=30)
        if old_text.returncode != 0:
            continue
        old = read_json(full) or {}
        try:
            old = json.loads(old_text.stdout)
        except ValueError:
            continue
        new = read_json(full) or {}
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
    for seams, path, old, new in changes:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    for rel, has_cli, has_tui in PLUGIN_JSONS:
        path = os.path.join(args.repo, rel)
        data = read_json(path)
        if not isinstance(data, dict):
            print(f"error: missing {rel}", file=sys.stderr)
            return 2
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
    lock_paths = []
    for name in PLUGIN_DIRS:
        directory = os.path.join(args.repo, "plugins", name)
        lock = os.path.join(directory, "package-lock.json")
        if os.path.isfile(lock):
            lock_paths.append(os.path.relpath(lock, args.repo))
        proc = run(["npm", "install", "--no-audit", "--no-fund", "--silent"],
                   cwd=directory, timeout=300)
        if proc.returncode != 0:
            print(f"error: npm install failed in {directory}: "
                  f"{(proc.stderr or '')[-300:]}", file=sys.stderr)
            return 2
    summary = canary_summary(args.repo, target)
    pending = summary is None
    if pending and not args.allow_pending_canary:
        print("error: canary evidence missing; run "
              "`opencode_upgrade.py canary --to " + target + "` first "
              "(or pass --allow-pending-canary)", file=sys.stderr)
        return 2
    append_adr_amendment(args.repo, target, opentui, summary or {},
                         pending=pending)
    results = check_seams(args.repo, target, opentui)
    failed = [row for row in results if not row[1]]
    print(f"prepared {target} (OpenTUI {opentui}); "
          f"{len(changes)} seam(s), {len(failed)} failure(s)")
    if lock_paths:
        print("lockfile delta:")
        print(lockfile_delta(args.repo, lock_paths))
    for path, ok, detail in failed:
        print(f"  {path}: FAIL {detail}")
    if failed:
        return 1
    write_state(args.repo, target, "prepared")
    if args.open_pr:
        return open_pr(args, target, opentui, summary or {})
    print(f"next: python3 scripts/opencode_upgrade.py apply --to {target} "
          "--drain-acknowledged")
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
        "### Apply (owner, drained TTY)",
        "```sh",
        "opencode service stop",
        f"python3 scripts/opencode_upgrade.py apply --to {target} "
        "--drain-acknowledged",
        "```",
        "",
        "Rollback: `python3 scripts/opencode_upgrade.py rollback --manifest "
        f".scratch/opencode-v2/cutover/upgrade-*-to-{target}.json`",
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


def canary_cmd(args, target):
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
    return [sys.executable, os.path.join(HERE, "opencode_v2_canary.py"),
            "--all", "--version", target, "--skip-install",
            "--prefix", prefix,
            "--opencode-bin", os.path.join(prefix, "bin", "opencode"),
            "--default-bin", link, "--v1-prefix", v1_prefix,
            "--scratch-root", root]


def canary(args):
    target = args.to or v2.VERSION_PIN
    prefix = args.prefix or os.path.join(
        args.repo, ".scratch", "v2-" + target + "-prefix")
    if not args.skip_install:
        install = run(["npm", "install", "--global", "--prefix", prefix,
                       "@opencode/cli@" + target], timeout=600)
        if install.returncode != 0:
            print(f"error: install failed: {(install.stderr or '')[-400:]}",
                  file=sys.stderr)
            return 2
    argv = canary_cmd(args, target)
    print("canary: " + " ".join(argv))
    proc = run(argv, cwd=args.repo, timeout=1800, stream=True)
    if proc.returncode != 0:
        print("canary: FAIL", file=sys.stderr)
        return proc.returncode
    peers = read_json(args.plugin_json) if args.plugin_json else \
        plugin_peers(target, args.repo)
    opentui = resolve_opentui(target, args.opentui, peers or {})
    ok, detail = plugin_compat(args, target, opentui)
    print(detail)
    if not ok:
        print("canary: FAIL — manual plugin migration required",
              file=sys.stderr)
        return 1
    write_state(args.repo, target, "canaried")
    print("canary: PASS")
    return 0


# --- apply / rollback -------------------------------------------------------

def source_prefix(args, target):
    if args.source_prefix:
        return args.source_prefix
    candidate = os.path.join(args.repo, ".scratch", "v2-" + target + "-prefix")
    return candidate if os.path.isdir(candidate) else DEFAULT_PREFIX


def cutover_ns(args, target):
    home, link = live_paths(args)
    current = cutover.version_of(link) or "unknown"
    return argparse.Namespace(
        execute=True, preflight=False, rollback=False, upgrade=True,
        drain_acknowledged=True, framework=args.repo, consumer=None,
        artifact=None, processes_file=args.processes_file,
        source_db=args.source_db or v2.DEFAULT_DB,
        final_backup=args.final_backup,
        source_prefix=source_prefix(args, target),
        config_source=args.config_source,
        scratch_root=args.scratch_root or DEFAULT_SCRATCH,
        home=home, link=link,
        manifest=args.manifest or os.path.join(
            args.scratch_root or DEFAULT_SCRATCH,
            f"upgrade-{current}-to-{target}.json"),
        agent_snapshot=None, agents_dir=None, restore_db=False,
        force=args.force,
    )


def busy_sessions(link):
    proc = run([link, "api", "GET", "/api/session/active"], timeout=30)
    if proc.returncode != 0:
        return []
    try:
        data = (json.loads(proc.stdout) or {}).get("data") or {}
    except ValueError:
        return []
    return [f"{sid} ({entry.get('type')})"
            for sid, entry in data.items()
            if isinstance(entry, dict)]


def wait_for_drain(args, link):
    deadline = time.time() + (args.timeout or 900)
    while True:
        ok, detail = cutover.check_drain(args)
        busy = busy_sessions(link)
        if ok and not busy:
            return True, "drained"
        print(f"waiting for drain: {detail if not ok else ''}"
              f"{' sessions=' + ','.join(busy) if busy else ''}")
        if time.time() >= deadline:
            return False, "timeout"
        time.sleep(max(args.interval, 0))


def verify_live(args, link, target, config_root):
    checks = []
    version = cutover.version_of(link)
    checks.append(("binary", version == target, version or "unknown"))
    if version == target:
        service = run([link, "service", "status"], timeout=30)
        if service.returncode != 0:
            run([link, "service", "start"], timeout=60)
            time.sleep(2)
            service = run([link, "service", "status"], timeout=30)
        checks.append(("service", service.returncode == 0,
                       (service.stdout or "").strip()[:120]))
        info = run([link, "api", "GET", "/api/info"], timeout=60)
        checks.append(("api", info.returncode == 0 and target in info.stdout,
                       (info.stdout or "").strip()[:200]))
        agents = post_smoke.check_agents(REPO, None)
        checks.append(("agents", agents[0], agents[1]))
        plugin = post_smoke.check_plugin(framework=REPO,
                                         config_root=config_root,
                                         binary=link)
        checks.append(("plugin", plugin[0], plugin[1][:240]))
    return checks


def apply(args):
    target = args.to or v2.VERSION_PIN
    dry_run = getattr(args, "dry_run", False)
    if not dry_run and not getattr(args, "drain_acknowledged", False):
        print("error: apply requires --drain-acknowledged (owner consent)",
              file=sys.stderr)
        return 2
    if target != v2.VERSION_PIN:
        print(f"error: apply target {target} != pinned {v2.VERSION_PIN}; "
              "run prepare first", file=sys.stderr)
        return 2
    home, link = live_paths(args)
    if not args.skip_canary:
        summary = canary_summary(args.repo, target)
        if not summary or not summary["ok"]:
            print("error: passing canary evidence missing for "
                  f"{target}; run `opencode_upgrade.py canary --to {target}` "
                  "first (or --skip-canary)", file=sys.stderr)
            return 2
    ns = cutover_ns(args, target)
    if args.stop_service:
        stopped = run([link, "service", "stop"], timeout=60)
        print(f"service stop: {stopped.returncode}")
    if args.wait_for_drain:
        ok, detail = wait_for_drain(args, link)
        if not ok:
            print(f"error: drain wait failed: {detail}", file=sys.stderr)
            return 2
    checks, _home, _link, _current = cutover.upgrade_checks(ns)
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    if any(not ok for _name, ok, _detail in checks):
        return 2
    if dry_run:
        print(f"apply preflight: PASS for {target}; no switch performed")
        return 0
    rc = cutover.upgrade_execute(ns)
    manifest = read_json(ns.manifest, {}) or {}
    if rc != 0:
        if manifest.get("switched"):
            print("switch verification failed; rolling back", file=sys.stderr)
            rb = cutover_ns(args, target)
            rb.manifest = ns.manifest
            cutover.rollback(rb)
            write_state(args.repo, target, "rolled-back")
        return rc
    config_root = (manifest.get("versioned") or {}).get("config_root")
    results = verify_live(args, link, target, config_root)
    artifact = os.path.join(args.repo, ".scratch", "opencode-v2",
                            f"upgrade-{target}-verify.json")
    payload = {"version": target, "checks": {
        name: {"ok": ok, "detail": detail} for name, ok, detail in results},
        "rolled_back": False, "at": now_iso()}
    write_json(artifact, payload)
    for name, ok, detail in results:
        print(f"verify {name}: {'PASS' if ok else 'FAIL'} {detail}")
    if all(ok for _name, ok, _detail in results):
        write_state(args.repo, target, "applied",
                    {"artifact": artifact})
        print(f"UPGRADE OK {target} link={link} evidence={artifact}")
        return 0
    print("post-switch verification failed; rolling back", file=sys.stderr)
    rb = cutover_ns(args, target)
    rb.manifest = ns.manifest
    cutover.rollback(rb)
    payload["rolled_back"] = True
    write_json(artifact, payload)
    write_state(args.repo, target, "rolled-back", {"artifact": artifact})
    print(f"ROLLED BACK to {manifest.get('from_version') or 'previous'}")
    return 1


def rollback(args):
    ns = argparse.Namespace(
        manifest=args.manifest, home=args.home, agent_snapshot=None,
        agents_dir=None, restore_db=True)
    return cutover.rollback(ns)


# --- prune / upgrade --------------------------------------------------------

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
    if target == v2.VERSION_PIN and not args.force:
        _home, link = live_paths(args)
        if cutover.version_of(link) == target:
            print(f"already current: {target}")
            return 0
        write_state(args.repo, target, "prepared")
        if args.apply:
            return apply(args)
        print(f"pinned target already prepared; apply with "
              f"`python3 scripts/opencode_upgrade.py apply --to {target} "
              "--drain-acknowledged`")
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
        return apply(args)
    print(f"ready: run `python3 scripts/opencode_upgrade.py apply --to "
          f"{target} --drain-acknowledged` from a normal terminal after "
          "closing every session")
    return 0


# --- CLI --------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(description="OpenCode upgrade orchestrator")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "check", "plan", "prepare", "canary",
                 "apply", "rollback", "prune", "upgrade"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--to", default=None)
        cmd.add_argument("--repo", default=REPO)
        cmd.add_argument("--home", default=None)
        cmd.add_argument("--link", default=None)
        cmd.add_argument("--prefix", default=None)
        cmd.add_argument("--source-prefix", default=None)
        cmd.add_argument("--source-db", default=None)
        cmd.add_argument("--scratch-root", default=None)
        cmd.add_argument("--processes-file", default=None)
        cmd.add_argument("--final-backup", default=None)
        cmd.add_argument("--config-source", default=None)
        cmd.add_argument("--manifest", default=None)
        cmd.add_argument("--v1-bin", default=None)
        cmd.add_argument("--plugin-json", default=None)
        cmd.add_argument("--releases-file", default=None)
        cmd.add_argument("--opentui", default=None)
        cmd.add_argument("--latest", default=None)
        cmd.add_argument("--refresh", action="store_true")
        cmd.add_argument("--remote", action="store_true")
        cmd.add_argument("--pins-only", action="store_true")
        cmd.add_argument("--pr", action="store_true")
        cmd.add_argument("--drain-acknowledged", action="store_true")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--dry-run", action="store_true")
        cmd.add_argument("--open-pr", action="store_true")
        cmd.add_argument("--skip-install", action="store_true")
        cmd.add_argument("--skip-canary", action="store_true")
        cmd.add_argument("--allow-pending-canary", action="store_true")
        cmd.add_argument("--wait-for-drain", action="store_true")
        cmd.add_argument("--stop-service", action="store_true")
        cmd.add_argument("--timeout", type=int, default=900)
        cmd.add_argument("--interval", type=int, default=5)
        cmd.add_argument("--force", action="store_true")
        cmd.add_argument("--resume", action="store_true")
        cmd.add_argument("--apply", action="store_true")
        cmd.add_argument("--keep", type=int, default=1)
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
    if args.command == "apply":
        return apply(args)
    if args.command == "rollback":
        if not args.manifest:
            print("error: --manifest is required", file=sys.stderr)
            return 2
        return rollback(args)
    if args.command == "prune":
        return prune(args)
    if args.command == "upgrade":
        return upgrade(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
