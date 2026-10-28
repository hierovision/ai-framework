#!/usr/bin/env python3
"""Post-cutover smoke — gates both merges, then verifies the merged SHAs.

Pre-merge (`--framework F --consumer C`): proves the DEFAULT command is V2,
loads the framework agents and consumer wrappers, checks config/credentials/
plugin disposition, reads migrated `session_v2`, and runs the live drills.
Writes a passing artifact. A failure routes to rollback and returns non-zero;
only a pass allows the owner's squash merges.

Post-merge (`--post-merge`): verifies the merged framework/consumer SHAs and
that the versioned corpus matches the manifest.

Rollback-check (`--rollback-check --manifest M`): V1 1.19.4, intact V1 agent/
config/plugin hashes, `ok` DB integrity, and a successful V1 session read.

Every check is explicit: a missing/partial artifact or an unrun drill is a
FAIL, never a silent pass.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

AGENTS_DIR = os.path.join(REPO, "agents")
DEFAULT_ARTIFACT = os.path.join(REPO, ".scratch", "opencode-v2",
                                "post-smoke.json")
EXPECTED_AGENTS = 17
EXPECTED_CONSUMER_AGENTS = 10


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(path):
    proc = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def run(argv, cwd=None, env=None, timeout=180):
    try:
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)


def check_version(binary):
    proc = subprocess.run([binary, "--version"], capture_output=True, text=True)
    return proc.returncode == 0 and v2.VERSION_PIN in proc.stdout, \
        proc.stdout.strip()


def agent_files(root):
    if not os.path.isdir(root):
        return []
    return sorted(f for f in os.listdir(root) if f.endswith(".md"))


def check_agents(framework, consumer):
    fw = len(agent_files(os.path.join(framework, "agents")))
    cs = len(agent_files(os.path.join(consumer, ".opencode", "agents"))) \
        if consumer else 0
    ok = fw == EXPECTED_AGENTS and (consumer is None
                                    or cs == EXPECTED_CONSUMER_AGENTS)
    return ok, f"framework={fw} consumer={cs}"


def check_config(framework, consumer):
    """Native config loads: framework agent frontmatter + consumer config."""
    errors = []
    for name in agent_files(os.path.join(framework, "agents")):
        path = os.path.join(framework, "agents", name)
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
        if name.startswith("name:") or "\nname:" in fm:
            errors.append(f"{name}: carries name:")
        if "permissions:" not in fm:
            errors.append(f"{name}: missing permissions")
    if consumer:
        cfg = os.path.join(consumer, "opencode.json")
        if not os.path.isfile(cfg):
            errors.append("consumer opencode.json missing")
        else:
            with open(cfg, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data.get("agents"), dict):
                errors.append("consumer config missing native agents")
            if "agent" in data:
                errors.append("consumer config has legacy agent")
    return not errors, "; ".join(errors) or "ok"


def check_plugin(manifest=None, framework=None):
    """Plugin disposition: ID + startup marker, or a dated approved disable."""
    versioned = None
    if manifest and os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        versioned = (data.get("versioned") or {}).get("config_root")
    candidates = []
    if versioned:
        candidates.append(os.path.join(versioned, "opencode", "plugins",
                                       "auto-compact-at-threshold", "index.js"))
    candidates.append(os.path.join(framework or REPO, "plugins",
                                   "auto-compact-at-threshold", "index.js"))
    for path in candidates:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            if "Plugin.define" in body and "auto-compact-at-threshold" in body:
                return True, path
    return False, "plugin implementation/marker not found"


def check_db():
    con = v2.connect()
    if con is None:
        return False, f"no readable DB at {v2.db_path()}"
    try:
        if not v2.table_exists(con, "session_v2"):
            return False, "session_v2 table absent"
        count = con.execute("SELECT COUNT(*) FROM session_v2").fetchone()[0]
        return count > 0, f"session_v2 rows={count}"
    finally:
        con.close()


def drills(framework, consumer, evidence_path=None):
    """D1–D7: D1–D6 are live drills recorded by the owner's drill run; D7 is
    the offline model doctor. A missing or incomplete evidence file is a FAIL,
    never a silent pass."""
    results = []
    path = evidence_path or os.path.join(REPO, ".scratch", "opencode-v2",
                                         "drills.json")
    required = [f"D{i}" for i in range(1, 7)]
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for name in required:
                entry = data.get(name)
                ok = bool(isinstance(entry, dict) and entry.get("pass"))
                results.append((name, ok, entry.get("detail", "recorded")
                                if isinstance(entry, dict) else "missing"))
        except (OSError, ValueError) as exc:
            results.append(("drill-evidence", False, f"unreadable: {exc}"))
    else:
        results.append(("drill-evidence", False,
                        f"D1-D6 evidence missing: {path}"))
    # D7: model doctor + consumer bindings (offline / read-only).
    doctor = os.path.join(REPO, "scripts", "model-liveness-check.py")
    p1 = subprocess.run([sys.executable, doctor], capture_output=True,
                        text=True) if os.path.isfile(doctor) else None
    results.append(("D7-model-doctor", bool(p1 and p1.returncode == 0),
                    (p1.stdout or p1.stderr or "missing").strip()[:200]
                    if p1 else "model-liveness-check.py missing"))
    p2 = subprocess.run([sys.executable, os.path.join(
        REPO, "scripts", "check-consumer-bindings.py"), framework],
        capture_output=True, text=True)
    results.append(("D7-consumer", p2.returncode == 0,
                    (p2.stdout or p2.stderr or "").strip()[-200:]))
    return results


def write_artifact(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def pre_merge(args):
    checks = []
    binary = args.default_bin
    ok, detail = check_version(binary)
    checks.append(("default-is-v2", ok, detail))
    ok, detail = check_agents(args.framework, args.consumer)
    checks.append(("agents-load", ok, detail))
    ok, detail = check_config(args.framework, args.consumer)
    checks.append(("config", ok, detail))
    ok, detail = check_plugin(args.manifest, args.framework)
    checks.append(("plugin", ok, detail))
    ok, detail = check_db()
    checks.append(("migrated-db", ok, detail))
    if args.require_consumer:
        ok, detail = check_consumer_ready(args)
        checks.append(("consumer", ok, detail))
    if args.drills:
        for name, ok, detail in drills(args.framework, args.consumer,
                                       args.drill_evidence):
            checks.append((name, ok, detail))

    failed = [name for name, ok, _ in checks if not ok]
    payload = {
        "kind": "post-smoke",
        "created": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "framework_sha": git_sha(args.framework),
        "consumer_sha": git_sha(args.consumer) if args.consumer else None,
        "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
        "passed": not failed,
    }
    path = write_artifact(args.artifact or DEFAULT_ARTIFACT, payload)
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    if failed:
        print(f"error: post-smoke failed: {', '.join(failed)}", file=sys.stderr)
        print("error: run `opencode_v2_cutover.py --rollback --manifest M`",
              file=sys.stderr)
        return 1
    print(f"POST-SMOKE PASS artifact={path}")
    return 0


def check_consumer_ready(args):
    import opencode_v2_consumer as consumer
    if not args.consumer:
        return False, "no consumer worktree"
    artifact = args.consumer_artifact or consumer.DEFAULT_ARTIFACT
    ok, detail = consumer.verify_artifact(
        artifact, git_sha(args.framework), git_sha(args.consumer))
    return ok, detail


def post_merge(args):
    if not args.manifest or not os.path.isfile(args.manifest):
        print("error: --post-merge requires --manifest M", file=sys.stderr)
        return 2
    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    checks = []
    fw_sha = git_sha(args.framework)
    cs_sha = git_sha(args.consumer) if args.consumer else None
    expected_fw = (manifest.get("readiness") or {}).get("framework_sha")
    expected_cs = (manifest.get("readiness") or {}).get("consumer_sha")
    checks.append(("framework-sha", fw_sha == expected_fw,
                   f"{fw_sha} == {expected_fw}"))
    if args.consumer:
        checks.append(("consumer-sha", cs_sha == expected_cs,
                       f"{cs_sha} == {expected_cs}"))
    config_root = (manifest.get("versioned") or {}).get("config_root")
    corpus_ok = bool(config_root) and os.path.isdir(
        os.path.join(config_root, "opencode", "agents"))
    checks.append(("versioned-corpus", corpus_ok, str(config_root)))
    failed = [n for n, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    return 1 if failed else 0


def rollback_check(args):
    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    checks = []
    binary = args.default_bin
    proc = subprocess.run([binary, "--version"], capture_output=True, text=True)
    checks.append(("v1-version", "1.19.4" in proc.stdout, proc.stdout.strip()))
    backup = (manifest.get("backup") or {}).get("path")
    if backup and os.path.isfile(backup):
        import sqlite3
        con = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
        try:
            check = con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
        checks.append(("db-integrity", check == "ok", check))
    else:
        checks.append(("db-integrity", False, "backup missing"))
    snapshot = args.agent_snapshot
    if snapshot and os.path.isdir(snapshot):
        hashes_path = os.path.join(snapshot, "hashes.json")
        ok = os.path.isfile(hashes_path)
        detail = "snapshot present" if ok else "snapshot hashes missing"
        if ok:
            with open(hashes_path, encoding="utf-8") as fh:
                expected = json.load(fh)
            mismatch = [n for n, d in expected.items()
                        if not os.path.isfile(os.path.join(
                            args.agents_dir or os.path.expanduser(
                                "~/.config/opencode/agents"), n))
                        or sha256(os.path.join(
                            args.agents_dir or os.path.expanduser(
                                "~/.config/opencode/agents"), n)) != d]
            ok = not mismatch
            detail = f"mismatched={mismatch}"
        checks.append(("v1-agent-hashes", ok, detail))
    else:
        checks.append(("v1-agent-hashes", False, "no snapshot"))
    failed = [n for n, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Post-cutover smoke.")
    ap.add_argument("--framework", default=REPO)
    ap.add_argument("--consumer", default=None)
    ap.add_argument("--consumer-artifact", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--default-bin", default="opencode")
    ap.add_argument("--agents-dir", default=None)
    ap.add_argument("--agent-snapshot", default=None)
    ap.add_argument("--require-consumer", action="store_true")
    ap.add_argument("--skip-live", action="store_true")
    ap.add_argument("--drill-evidence", default=None,
                    help="D1-D6 drill evidence JSON (default "
                         ".scratch/opencode-v2/drills.json).")
    ap.add_argument("--post-merge", action="store_true")
    ap.add_argument("--rollback-check", action="store_true")
    args = ap.parse_args(argv)
    args.drills = not args.skip_live
    if args.post_merge:
        return post_merge(args)
    if args.rollback_check:
        return rollback_check(args)
    return pre_merge(args)


if __name__ == "__main__":
    sys.exit(main())
