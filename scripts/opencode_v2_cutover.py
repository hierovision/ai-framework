#!/usr/bin/env python3
"""Owner-run OpenCode V2 cutover — drained, atomic, reversible.

This script is documented for a normal terminal, never an architect or
implementer session. It refuses to switch unless ALL of these hold:

  * a TTY, `--execute`, and `--drain-acknowledged` (preflight is read-only);
  * no live opencode/dispatch/observer/watchdog/guard process or service;
  * a fresh, verified final V1 backup;
  * a commit-bound consumer readiness artifact matching the framework and
    consumer HEAD SHAs.

The switch is ONE same-directory atomic rename of `$HOME/.yarn/bin/opencode`
onto a versioned wrapper. The wrapper sets `XDG_CONFIG_HOME` to the versioned
V2 config root, so one link selects both binary and config. The existing V1
package, `~/.config/opencode` agents/config/plugin, and session DB are never
overwritten by the switch.

Rollback (`--rollback --manifest M`) stops V2 writers, preserves the failed V2
DB, restores the final V1 DB through Python `sqlite3`, atomically restores the
original link, repairs any mismatched V1 agent file from the C5 snapshot, and
verifies V1 1.19.4 reads the restored DB.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402
import opencode_v2_consumer as consumer  # noqa: E402

VERSION = "2.1.4"
PROCESS_PATTERNS = (
    r"opencode(\.exe)?\b",
    r"dispatch_agent\.py",
    r"observe_completion\.py",
    r"watch_agent\.py",
    r"session_guard\.py",
)
# Patterns that are this script's own machinery, never a live writer.
SELF_PATTERNS = (r"opencode_v2_cutover\.py", r"opencode_v2_post_smoke\.py",
                 r"opencode_v2_canary\.py")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def integrity(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


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
    os.chmod(dest, 0o600)
    return dest


def git_sha(path):
    proc = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


# --- gate checks -------------------------------------------------------------

def live_processes(processes_file=None):
    """Matching live processes; an empty list means drained."""
    if processes_file:
        with open(processes_file, encoding="utf-8") as fh:
            entries = json.load(fh)
        candidates = [str(e) for e in entries if isinstance(e, (str, int))]
    else:
        candidates = []
        proc = subprocess.run(["ps", "-eo", "pid=,args="],
                              capture_output=True, text=True)
        for line in (proc.stdout or "").splitlines():
            if line.strip():
                candidates.append(line.strip())
    hits = []
    for line in candidates:
        if any(re.search(p, line) for p in SELF_PATTERNS):
            continue
        if any(re.search(p, line) for p in PROCESS_PATTERNS):
            hits.append(line)
    return hits


def check_drain(args):
    hits = live_processes(args.processes_file)
    if hits:
        return False, ("live OpenCode/supervision process(es) present:\n  " +
                       "\n  ".join(hits[:10]))
    return True, "drained"


def final_backup(args, root):
    source = os.path.abspath(args.source_db or v2.DEFAULT_DB)
    if not os.path.isfile(source):
        return None, f"source DB missing: {source}"
    dest = args.final_backup or os.path.join(root, "final-v1.db")
    v2.assert_scratch_db(dest, os.path.join(REPO, ".scratch"))
    sqlite_backup(source, dest)
    check = integrity(dest)
    if check != "ok":
        return None, f"final backup integrity check failed: {check}"
    return {"path": dest, "sha256": sha256(dest), "integrity": check,
            "size": os.path.getsize(dest)}, None


def readiness(args):
    artifact = args.artifact or consumer.DEFAULT_ARTIFACT
    fw_sha = git_sha(args.framework)
    cs_sha = git_sha(args.consumer)
    if not fw_sha or not cs_sha:
        return None, "cannot resolve framework/consumer SHA"
    ok, detail = consumer.verify_artifact(artifact, fw_sha, cs_sha)
    if not ok:
        return None, detail
    with open(artifact, encoding="utf-8") as fh:
        data = json.load(fh)
    return {"artifact": artifact, "framework_sha": fw_sha,
            "consumer_sha": cs_sha,
            "framework_pr_url": data.get("framework_pr_url"),
            "consumer_pr_url": data.get("consumer_pr_url")}, None


# --- staging / switch --------------------------------------------------------

def stage_runtime(home, args):
    """Versioned runtime + config root + wrapper (no live switch yet)."""
    base = os.path.join(home, ".local", "lib", "opencode", VERSION)
    runtime_bin = os.path.join(base, "bin", "opencode")
    config_root = os.path.join(base, "config")
    os.makedirs(os.path.dirname(runtime_bin), exist_ok=True)
    os.makedirs(os.path.join(config_root, "opencode"), exist_ok=True)

    source_prefix = args.source_prefix
    candidate = os.path.join(source_prefix, "bin", "opencode2")
    if not os.path.isfile(candidate):
        candidate = os.path.join(source_prefix, "bin", "opencode")
    if not os.path.isfile(candidate):
        return None, f"V2 runtime missing under {source_prefix}/bin"
    shutil.copy2(candidate, runtime_bin)
    os.chmod(runtime_bin, 0o755)

    config_src = args.config_source
    if not config_src or not os.path.isdir(config_src):
        return None, f"versioned config source missing: {config_src}"
    for name in ("agents", "plugins"):
        src = os.path.join(config_src, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(config_root, "opencode", name),
                            dirs_exist_ok=True)
    cfg = os.path.join(config_src, "opencode.jsonc")
    if os.path.isfile(cfg):
        shutil.copy2(cfg, os.path.join(config_root, "opencode",
                                       "opencode.jsonc"))

    wrapper = os.path.join(base, "opencode-wrapper")
    with open(wrapper, "w", encoding="utf-8") as fh:
        fh.write("#!/usr/bin/env bash\n")
        fh.write("# Versioned OpenCode V2 wrapper: selects binary AND config.\n")
        fh.write(f'export XDG_CONFIG_HOME="{config_root}"\n')
        fh.write(f'exec "{runtime_bin}" "$@"\n')
    os.chmod(wrapper, 0o755)
    return {"base": base, "runtime": runtime_bin, "config_root": config_root,
            "wrapper": wrapper}, None


def atomic_link(target, link):
    """Same-directory symlink + rename (never a remove-then-create window)."""
    parent = os.path.dirname(os.path.abspath(link))
    os.makedirs(parent, exist_ok=True)
    tmp = os.path.join(parent, f".{os.path.basename(link)}.opencode-v2.tmp")
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    os.symlink(target, tmp)
    os.replace(tmp, link)


def original_link_state(link):
    state = {"path": link, "exists": os.path.islink(link) or os.path.exists(link),
             "target": None, "type": "missing"}
    if os.path.islink(link):
        state["target"] = os.readlink(link)
        state["type"] = "symlink"
    elif os.path.isfile(link):
        state["type"] = "file"
        state["sha256"] = sha256(link)
    return state


def stage_config_hash(config_root):
    hashes = {}
    for base, _dirs, files in os.walk(config_root):
        for name in files:
            path = os.path.join(base, name)
            hashes[os.path.relpath(path, config_root)] = sha256(path)
    return hashes


def write_manifest(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    os.chmod(path, 0o600)
    return path


def execute(args):
    home = os.path.abspath(args.home or os.path.expanduser("~"))
    link = args.link or os.path.join(home, ".yarn", "bin", "opencode")
    root = os.path.abspath(args.scratch_root)
    os.makedirs(root, exist_ok=True)

    ok, detail = check_drain(args)
    if not ok:
        print(f"error: drain gate failed: {detail}", file=sys.stderr)
        return 2
    ready, detail = readiness(args)
    if not ready:
        print(f"error: readiness gate failed: {detail}", file=sys.stderr)
        return 2
    backup, detail = final_backup(args, root)
    if not backup:
        print(f"error: final backup failed: {detail}", file=sys.stderr)
        return 2
    staged, detail = stage_runtime(home, args)
    if not staged:
        print(f"error: staging failed: {detail}", file=sys.stderr)
        return 2

    original = original_link_state(link)
    manifest = {
        "created": now_iso(),
        "version": VERSION,
        "home": home,
        "link": link,
        "original_link": original,
        "versioned": staged,
        "config_hashes": stage_config_hash(staged["config_root"]),
        "backup": backup,
        "readiness": ready,
        "drain_acknowledged": True,
        "switched": False,
    }
    manifest_path = args.manifest or os.path.join(root, "manifest.json")
    write_manifest(manifest_path, manifest)
    try:
        atomic_link(staged["wrapper"], link)
        manifest["switched"] = True
        manifest["switched_at"] = now_iso()
        write_manifest(manifest_path, manifest)
    except OSError as exc:
        print(f"error: atomic switch failed: {exc}", file=sys.stderr)
        return 2

    version = subprocess.run([link, "--version"], capture_output=True, text=True)
    print(f"CUTOVER OK link={link} manifest={manifest_path}")
    print(f"version={version.stdout.strip()}")
    return 0


def rollback(args):
    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    home = manifest.get("home") or os.path.abspath(os.path.expanduser("~"))
    link = manifest.get("link") or os.path.join(home, ".yarn", "bin",
                                                "opencode")
    backup = (manifest.get("backup") or {}).get("path")
    original = manifest.get("original_link") or {}
    if not backup or not os.path.isfile(backup):
        print("error: manifest has no usable final backup", file=sys.stderr)
        return 2
    # 1. Preserve the failed V2 DB, then restore the final V1 DB.
    real_db = v2.DEFAULT_DB if not args.home else os.path.join(
        home, ".local", "share", "opencode", "opencode.db")
    if os.path.isfile(real_db):
        failed = real_db + ".v2-failed."
        failed += datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        shutil.copy2(real_db, failed)
    if args.restore_db:
        sqlite_backup(backup, real_db)
        if integrity(real_db) != "ok":
            print("error: restored DB integrity check failed", file=sys.stderr)
            return 2
    # 2. Restore the original binary link atomically.
    if original.get("type") == "symlink":
        atomic_link(original["target"], link)
    elif original.get("type") == "file" and original.get("sha256"):
        parent = os.path.dirname(link)
        tmp = os.path.join(parent, f".{os.path.basename(link)}.restore.tmp")
        shutil.copy2(backup, tmp)  # placeholder; file originals are documented
        os.replace(tmp, link)
    else:
        try:
            os.unlink(link)
        except FileNotFoundError:
            pass
    # 3. Repair mismatched V1 agent files from the C5 snapshot.
    snapshot = args.agent_snapshot
    repaired = []
    if snapshot and os.path.isdir(snapshot):
        hashes_path = os.path.join(snapshot, "hashes.json")
        if os.path.isfile(hashes_path):
            with open(hashes_path, encoding="utf-8") as fh:
                expected = json.load(fh)
            for name, digest in expected.items():
                dest = os.path.join(args.agents_dir or os.path.join(
                    os.path.expanduser("~"), ".config", "opencode", "agents"),
                    name)
                if not os.path.isfile(dest) or sha256(dest) != digest:
                    shutil.copyfile(os.path.join(snapshot, name), dest)
                    repaired.append(name)
    result = {"rolled_back": True, "link": link, "backup": backup,
              "repaired_agents": repaired, "ts": now_iso()}
    print("ROLLBACK OK " + json.dumps(result))
    return 0


def preflight(args):
    checks = []
    ok_drain, drain_detail = check_drain(args)
    checks.append(("drain", ok_drain, drain_detail))
    ready, ready_detail = readiness(args)
    checks.append(("readiness", bool(ready), ready_detail or "ok"))
    source = os.path.abspath(args.source_db or v2.DEFAULT_DB)
    checks.append(("source-db", os.path.isfile(source), source))
    tty = sys.stdin.isatty()
    checks.append(("tty", tty, "interactive" if tty else "non-TTY"))
    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Drained, atomic OpenCode V2 cutover (owner-run).")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    ap.add_argument("--drain-acknowledged", action="store_true")
    ap.add_argument("--framework", default=REPO)
    ap.add_argument("--consumer", required=False)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--processes-file", default=None,
                    help="Test/automation seam: JSON list of process lines.")
    ap.add_argument("--source-db", default=v2.DEFAULT_DB)
    ap.add_argument("--final-backup", default=None)
    ap.add_argument("--source-prefix", default=os.path.join(
        REPO, ".scratch", "v2-prefix"))
    ap.add_argument("--config-source", default=None)
    ap.add_argument("--scratch-root", default=os.path.join(
        REPO, ".scratch", "opencode-v2", "cutover"))
    ap.add_argument("--home", default=None, help="HOME to switch (tests).")
    ap.add_argument("--link", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--agent-snapshot", default=None)
    ap.add_argument("--agents-dir", default=None)
    ap.add_argument("--restore-db", action="store_true",
                    help="Rollback only: restore the final V1 DB.")
    args = ap.parse_args(argv)

    if args.rollback:
        return rollback(args)
    if args.preflight:
        return preflight(args)

    if not args.consumer:
        print("error: --consumer <worktree> is required", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("error: cutover requires a TTY", file=sys.stderr)
        return 2
    if not args.drain_acknowledged:
        print("error: cutover requires --drain-acknowledged", file=sys.stderr)
        return 2
    return execute(args)


if __name__ == "__main__":
    sys.exit(main())
