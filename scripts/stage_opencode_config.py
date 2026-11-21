#!/usr/bin/env python3
"""Stage the reviewed OpenCode V2 config into the supported global root.

OpenCode's supported install reads `~/.config/opencode` (or the ambient
`XDG_CONFIG_HOME`). The V1→V2 cutover used a versioned config root behind a
wrapper; this script moves the reviewed corpus to the supported root and
backs up the old V1 tree first.

Order (owner-run, from a normal terminal, TUI closed and service stopped):

  python3 scripts/stage_opencode_config.py --backup
  yarn global add @opencode/cli@2.2.6   # same-version official install
  opencode debug paths config           # ~/.config/opencode
  opencode --version                    # 2.2.6

`opencode upgrade 2.2.6 --method yarn` skips when 2.2.6 is already the
running version, so the same-version migration uses the official yarn
install directly. Later versions use `opencode upgrade <target> --method yarn`.

The script copies the versioned config's `opencode.jsonc`, `cli.json`,
`service.json`, and plugins; it links the repo agents/skills/reference through
`install.sh`. The old root is moved to
`~/.config/opencode.v1-backup-<timestamp>` and any SQLite DB copy is written
with mode 0600; nothing is deleted. `--backup` is accepted for compatibility
because backup is already the default behavior.

`--plugins-only` refreshes only the live `plugins/` corpus from the repo,
with an in-config `plugins.v1-backup-<stamp>`; it does not move the config or
DB. The supported upgrade apply does this automatically after shadow repair.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

PLUGIN_DIRS = ("auto-compact-at-threshold", "delegation-observer",
               "delegation-sentinel")
PLUGIN_REL = "./plugins/"
# Match process identity, never the whole command line: the upgrade wrapper,
# its `tee` log path, and the orchestrator all contain the substring
# `opencode` and must not block the drain gate.
OPENCODE_COMMS = frozenset(("opencode", "opencode.exe", "opencode-ai"))
SUPERVISION_SCRIPTS = ("dispatch_agent.py", "observe_completion.py",
                       "watch_agent.py", "session_guard.py")
SUPERVISION_RE = re.compile(
    r"(?:^|\s)(?:\S*/)?("
    + "|".join(re.escape(name) for name in SUPERVISION_SCRIPTS)
    + r")(?=\s|$)")


def now_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")


def default_source(home):
    return os.path.join(home, ".local", "lib", "opencode", v2.VERSION_PIN,
                        "config", "opencode")


def sqlite_backup(source, dest):
    """Delegate to the shared 0600-preserving backup helper."""
    return v2.sqlite_backup(source, dest)


def parse_live_processes(text):
    """Return `ps -eo pid=,comm=,args=` lines that are live OpenCode or
    supervision processes.

    A hit requires either an `opencode`-family executable name (the TUI, the
    service, or the retained V1 binary) or a Python process whose argument
    path is one of the supervision scripts. Shell wrappers, `tee`, `grep`,
    `ps`, and the upgrade orchestrator are intentionally not hits even when
    their paths contain `opencode`.
    """
    hits = []
    for line in (text or "").splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) < 2:
            continue
        comm = fields[1]
        args = fields[2] if len(fields) > 2 else ""
        if comm in OPENCODE_COMMS:
            hits.append(line.strip())
        elif comm.startswith("python") and SUPERVISION_RE.search(args):
            hits.append(line.strip())
    return hits


def live_processes():
    """All live OpenCode or supervision processes (the drain gate)."""
    proc = subprocess.run(["ps", "-eo", "pid=,comm=,args="],
                          capture_output=True, text=True)
    return parse_live_processes(proc.stdout)


def parse_tui_processes(text):
    """Live OpenCode TUI processes: the opencode family minus serve/service.

    Built on `parse_live_processes` (identity by `comm`, not substring). The
    managed service and any `serve`/`--service` invocation are excluded; the
    TUI is the foreground client the operator closes before a detached apply.
    """
    hits = []
    for line in parse_live_processes(text):
        fields = line.strip().split(None, 2)
        comm = fields[1] if len(fields) > 1 else ""
        args = fields[2] if len(fields) > 2 else ""
        if comm not in OPENCODE_COMMS:
            continue
        if re.search(r"(?:^|\s)serve(?:\s|$)|--service\b", args):
            continue
        hits.append(line.strip())
    return hits


def tui_processes():
    """`ps` snapshot of live OpenCode TUI processes (read-only)."""
    proc = subprocess.run(["ps", "-eo", "pid=,comm=,args="],
                          capture_output=True, text=True)
    return parse_tui_processes(proc.stdout)


PLUGIN_IGNORE = shutil.ignore_patterns(
    "node_modules", "*.test.ts", "mutation-check.mjs", ".scratch")


def build_plugins(repo, target):
    plugin_root = os.path.join(target, "plugins")
    os.makedirs(plugin_root, exist_ok=True)
    for name in PLUGIN_DIRS:
        src = os.path.join(repo, "plugins", name)
        if not os.path.isdir(src):
            raise SystemExit(f"missing plugin source: {src}")
        dst = os.path.join(plugin_root, name)
        shutil.copytree(src, dst, ignore=PLUGIN_IGNORE)


def plugin_versions(plugin_root):
    """`{name: {"version", "peer"}}` for the three live plugin dirs."""
    rows = {}
    for name in PLUGIN_DIRS:
        path = os.path.join(plugin_root, name, "package.json")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            rows[name] = {"version": None, "peer": None}
            continue
        peers = data.get("peerDependencies") or {}
        rows[name] = {
            "version": data.get("version"),
            "peer": peers.get("@opencode/plugin"),
        }
    return rows


def verify_plugin_versions(plugin_root, expected):
    """Return named mismatches for the live plugin corpus."""
    problems = []
    for name, row in plugin_versions(plugin_root).items():
        if row["version"] != expected:
            problems.append(
                f"{name}: version {row['version']} != {expected}")
        if row["peer"] is not None and row["peer"] != expected:
            problems.append(
                f"{name}: @opencode/plugin peer {row['peer']} != {expected}")
    return problems


def refresh_plugins(repo, target, expected, dry_run=False, force=False):
    """Replace only the live config `plugins/` with the reviewed repo corpus.

    The whole config and DB are not moved; the old plugin corpus is backed up
    inside the config root as `plugins.v1-backup-<stamp>`. Staging is verified
    against `expected` before the swap, so a broken copy never becomes live.
    Requires OpenCode/supervision processes stopped unless `force`.
    """
    target = os.path.abspath(target)
    if not os.path.isdir(target):
        raise RuntimeError(f"config root missing: {target}")
    if not dry_run and not force:
        running = live_processes()
        if running:
            raise RuntimeError(
                "OpenCode/supervision processes are running: "
                + "; ".join(running[:3])
                + " — close the TUI and run `opencode service stop` first")
    for name in PLUGIN_DIRS:
        src = os.path.join(repo, "plugins", name)
        if not os.path.isdir(src):
            raise RuntimeError(f"missing plugin source: {src}")
    plugin_root = os.path.join(target, "plugins")
    stamp = now_stamp()
    staging = os.path.join(target, f".plugins-staging-{stamp}")
    backup = os.path.join(target, f"plugins.v1-backup-{stamp}")
    if dry_run:
        print(f"would refresh plugins from {repo}/plugins into {plugin_root}")
        print(f"would back up the current corpus to {backup}")
        print(f"would verify version/peer == {expected}")
        return None
    try:
        os.makedirs(staging, exist_ok=True)
        for name in PLUGIN_DIRS:
            src = os.path.join(repo, "plugins", name)
            if not os.path.isdir(src):
                raise RuntimeError(f"missing plugin source: {src}")
            shutil.copytree(src, os.path.join(staging, name),
                            ignore=PLUGIN_IGNORE)
        # Preserve any operator-added plugin entry that is not one of the
        # three reviewed corpus plugins; the refresh owns only those three.
        if os.path.isdir(plugin_root):
            for name in os.listdir(plugin_root):
                if name in PLUGIN_DIRS:
                    continue
                src = os.path.join(plugin_root, name)
                dst = os.path.join(staging, name)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst)
        problems = verify_plugin_versions(staging, expected)
        if problems:
            raise RuntimeError("plugin corpus version mismatch: "
                               + "; ".join(problems))
        if os.path.isdir(plugin_root):
            os.rename(plugin_root, backup)
        os.rename(staging, plugin_root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if os.path.isdir(backup) and not os.path.isdir(plugin_root):
            os.rename(backup, plugin_root)
        raise
    print(f"refreshed plugins from {repo}/plugins")
    print(f"backup: {backup}")
    print(f"verified version/peer == {expected}")
    return backup


def build_config_json(source, target):
    src = os.path.join(source, "opencode.jsonc")
    if os.path.isfile(src):
        try:
            config = json.load(open(src, encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(f"invalid source opencode.jsonc: {exc}")
    else:
        config = {"$schema": "https://opencode.ai/config.json"}
    plugins = [PLUGIN_REL + name for name in PLUGIN_DIRS]
    config["plugins"] = plugins
    with open(os.path.join(target, "opencode.jsonc"), "w",
              encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")


def copy_if_present(source, target, name):
    src = os.path.join(source, name)
    if os.path.isfile(src):
        shutil.copy2(src, os.path.join(target, name))


def link_repo_surfaces(repo, target):
    """Use install.sh so agents/skills/reference follow the repo's rules."""
    env = dict(os.environ)
    env["OPENCODE_SKILLS_DIR"] = os.path.join(target, "skills")
    env["OPENCODE_AGENTS_DIR"] = os.path.join(target, "agents")
    env["OPENCODE_REFERENCE_DIR"] = os.path.join(target, "reference")
    proc = subprocess.run(["bash", os.path.join(repo, "install.sh")],
                          env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("install.sh failed: " + (proc.stderr or proc.stdout))


def stage(args):
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    target = os.path.abspath(args.config_root
                             or os.path.join(home, ".config", "opencode"))
    source = os.path.abspath(args.source or default_source(home))
    if not os.path.isdir(source):
        raise SystemExit(f"source config missing: {source}")
    running = live_processes()
    if running and not args.force and not args.dry_run:
        print("error: OpenCode/supervision processes are running:", file=sys.stderr)
        for line in running[:10]:
            print("  " + line, file=sys.stderr)
        print("close the TUI, run `opencode service stop`, then retry "
              "(or pass --force).", file=sys.stderr)
        return 2
    backup = f"{target}.v1-backup-{now_stamp()}"
    print(f"source:  {source}")
    print(f"target:  {target}")
    print(f"backup:  {backup}")
    if os.path.isdir(target):
        print(f"will move the existing config to {backup}")
    else:
        print("no existing config to back up")
    if args.dry_run:
        print("dry-run: no files written")
        return 0
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    if os.path.isdir(target):
        if os.path.exists(backup):
            raise SystemExit(f"backup already exists: {backup}")
        shutil.move(target, backup)
    os.makedirs(target, exist_ok=True)
    db = os.path.join(home, ".local", "share", "opencode", "opencode.db")
    if os.path.isfile(db):
        os.makedirs(backup, exist_ok=True)
        sqlite_backup(db, os.path.join(backup, "opencode.db"))
        print(f"backed up DB: {backup}/opencode.db")
    build_plugins(args.repo, target)
    build_config_json(source, target)
    for name in ("cli.json", "service.json", ".gitignore"):
        copy_if_present(source, target, name)
    link_repo_surfaces(args.repo, target)
    print("staged the reviewed V2 config")
    print("next: yarn global add @opencode/cli@"
          f"{v2.VERSION_PIN}   # same-version migration")
    print("later: opencode upgrade <target> --method yarn")
    print("verify: opencode debug paths config   # " + target)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Stage the reviewed OpenCode V2 config in the supported root")
    ap.add_argument("--home", default=None)
    ap.add_argument("--config-root", default=None)
    ap.add_argument("--source", default=None,
                    help="versioned config root (default: "
                         "$HOME/.local/lib/opencode/<pin>/config/opencode)")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--backup", action="store_true",
                    help="accepted for compatibility; backup is already the "
                         "default behavior (no-op flag)")
    ap.add_argument("--plugins-only", action="store_true",
                    help="refresh only the live config plugins/ corpus from "
                         "the repo, with an in-config backup; does not move "
                         "the config or DB")
    args = ap.parse_args(argv)
    if args.plugins_only:
        home = os.path.abspath(args.home or os.path.expanduser("~"))
        target = os.path.abspath(args.config_root
                                 or os.path.join(home, ".config", "opencode"))
        try:
            refresh_plugins(args.repo, target, v2.VERSION_PIN,
                            dry_run=args.dry_run, force=args.force)
        except (OSError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0
    return stage(args)


if __name__ == "__main__":
    sys.exit(main())
