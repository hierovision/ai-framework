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
`~/.config/opencode.v1-backup-<timestamp>`; nothing is deleted.
"""
import argparse
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

PLUGIN_DIRS = ("auto-compact-at-threshold", "delegation-observer",
               "delegation-sentinel")
PLUGIN_REL = "./plugins/"
PROCESS_PATTERNS = (
    r"opencode(\.exe)?\b",
    r"dispatch_agent\.py",
    r"observe_completion\.py",
    r"watch_agent\.py",
    r"session_guard\.py",
)


def now_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")


def default_source(home):
    return os.path.join(home, ".local", "lib", "opencode", v2.VERSION_PIN,
                        "config", "opencode")


def sqlite_backup(source, dest):
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        for leftover in (dest, dest + "-wal", dest + "-shm"):
            try:
                os.remove(leftover)
            except FileNotFoundError:
                pass
        dst = sqlite3.connect(dest, timeout=30)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def live_processes():
    import re
    proc = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True,
                          text=True)
    hits = []
    for line in (proc.stdout or "").splitlines():
        if "stage_opencode_config.py" in line:
            continue
        if any(re.search(pattern, line) for pattern in PROCESS_PATTERNS):
            hits.append(line.strip())
    return hits


def build_plugins(repo, target):
    plugin_root = os.path.join(target, "plugins")
    os.makedirs(plugin_root, exist_ok=True)
    for name in PLUGIN_DIRS:
        src = os.path.join(repo, "plugins", name)
        if not os.path.isdir(src):
            raise SystemExit(f"missing plugin source: {src}")
        dst = os.path.join(plugin_root, name)
        ignore = shutil.ignore_patterns("node_modules", "*.test.ts",
                                        "mutation-check.mjs")
        shutil.copytree(src, dst, ignore=ignore)


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
                    help="back up the V1 config/DB first (default)")
    args = ap.parse_args(argv)
    return stage(args)


if __name__ == "__main__":
    sys.exit(main())
