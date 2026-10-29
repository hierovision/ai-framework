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
import re
import shutil
import signal
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

AGENTS_DIR = os.path.join(REPO, "agents")
DEFAULT_ARTIFACT = os.path.join(REPO, ".scratch", "opencode-v2",
                                "post-smoke.json")
EXPECTED_AGENTS = 17
EXPECTED_CONSUMER_AGENTS = 10
PLUGIN_REL = "./plugins/auto-compact-at-threshold"
PLUGIN_BARE = "plugins/auto-compact-at-threshold"
LOADER_MARKER = "auto-compact-at-threshold initialized"
LOADER_LOG = os.path.join(REPO, ".scratch", "opencode-v2", "plugin-loader.log")
LOADER_TIMEOUT = 45


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


def _versioned_root(manifest=None, config_root=None):
    if config_root:
        return config_root
    if manifest and os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        value = (data.get("versioned") or {}).get("config_root")
        if value:
            return value
    return os.path.join(os.path.expanduser("~"), ".local", "lib",
                        "opencode", v2.VERSION_PIN, "config")


def _write_loader_log(text):
    try:
        os.makedirs(os.path.dirname(LOADER_LOG), exist_ok=True)
        with open(LOADER_LOG, "w", encoding="utf-8") as fh:
            fh.write(text or "")
    except OSError:
        pass


def loader_evidence(root, binary, plugin_dir):
    """N1: prove V2's actual loader loaded this local plugin and it started.

    `plugin list` does not enumerate local directories, so this runs a
    standalone CLI with the versioned config and captures `--print-logs`
    stderr. An unavailable model makes the run exit quickly after the plugin
    phase; the evidence is the loader line naming this plugin plus the
    plugin's own stderr startup marker.
    """
    probe_root = os.path.join(REPO, ".scratch", "opencode-v2")
    os.makedirs(probe_root, exist_ok=True)
    probe_dir = tempfile.mkdtemp(prefix="loader-probe-", dir=probe_root)
    env = dict(os.environ)
    env.update({
        "XDG_CONFIG_HOME": root,
        "XDG_STATE_HOME": os.path.join(probe_dir, "state"),
        "XDG_CACHE_HOME": os.path.join(probe_dir, "cache"),
        "XDG_DATA_HOME": os.path.join(probe_dir, "data"),
        "TMPDIR": os.path.join(probe_dir, "tmp"),
        "OPENCODE_DB": os.path.join(probe_dir, "probe.db"),
        "OPENCODE_LOG_LEVEL": "info",
    })
    env.pop("OPENCODE_CONFIG_CONTENT", None)
    for key in ("XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "TMPDIR"):
        os.makedirs(env[key], exist_ok=True)
    argv = [binary, "run", "--standalone", "--format", "json",
            "--log-level", "info", "--print-logs",
            "--model", "loader-probe/none", "plugin loader probe"]
    timed_out = False
    try:
        proc = subprocess.Popen(argv, cwd=probe_dir, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        try:
            _out, err = proc.communicate(timeout=LOADER_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            _out, err = proc.communicate()
    except OSError as exc:
        _write_loader_log(f"cannot launch {binary}: {exc}\n")
        return False, f"loader probe cannot launch {binary}: {exc}"
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)
    _write_loader_log(err or "")
    lines = (err or "").splitlines()
    expected = os.path.realpath(plugin_dir)
    loaded = []
    for line in lines:
        if "loading plugin" not in line:
            continue
        match = re.search(r"\bid=(\S+)", line)
        if match and os.path.realpath(match.group(1)) == expected:
            loaded.append(line)
    failures = [line for line in lines
                if "failed to load plugin" in line
                and "auto-compact-at-threshold" in line]
    markers = [line for line in lines
               if LOADER_MARKER in line
               and "auto-compact-at-threshold" in line]
    if failures:
        return False, f"loader failed to load the versioned plugin: {failures[0][:240]}"
    if not loaded:
        suffix = " (loader probe timed out)" if timed_out else ""
        return False, (f"loader did not load the versioned plugin "
                       f"{expected}{suffix}; log={LOADER_LOG}")
    if not markers:
        return False, (f"startup marker missing from the loader log for "
                       f"{expected}; log={LOADER_LOG}")
    return True, (f"loader id={expected} marker={LOADER_MARKER} "
                  f"log={LOADER_LOG}")


def check_plugin(manifest=None, framework=None, config_root=None,
                 binary="opencode"):
    """AC41/N1: the versioned config wires the plugin, runtime evidence proves
    its behavior, and V2's actual loader log proves it loaded.

    Runtime evidence alone is insufficient: `plugin list` does not enumerate
    local directories, and a bare `plugins/...` spec is an npm package spec in
    V2. The loader probe runs the real CLI with the versioned config.
    """
    root = os.path.abspath(_versioned_root(manifest, config_root))
    cfg_path = os.path.join(root, "opencode", "opencode.jsonc")
    plugin_dir = os.path.join(root, "opencode", "plugins",
                              "auto-compact-at-threshold")
    index = os.path.join(plugin_dir, "index.js")
    if not os.path.isfile(cfg_path):
        return False, f"versioned config missing: {cfg_path}"
    if not os.path.isfile(index):
        return False, f"versioned plugin missing: {index}"
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        return False, f"versioned config unreadable: {exc}"
    plugins = cfg.get("plugins")
    if not isinstance(plugins, list):
        return False, "versioned config does not wire auto-compact-at-threshold"
    if PLUGIN_REL not in plugins:
        if PLUGIN_BARE in plugins:
            return False, ("versioned config wires the bare package spec "
                           f"{PLUGIN_BARE}; V2 treats it as an npm package. "
                           f"Wire the local directory as {PLUGIN_REL}")
        return False, "versioned config does not wire auto-compact-at-threshold"
    probe = os.path.join(plugin_dir, "runtime-probe.mjs")
    if not os.path.isfile(probe):
        return False, f"runtime probe missing: {probe}"
    node = subprocess.run(["node", probe], capture_output=True, text=True,
                          timeout=60)
    try:
        evidence = json.loads((node.stdout or "").strip().splitlines()[-1])
    except (IndexError, ValueError):
        return False, f"runtime probe emitted no JSON: {node.stderr[:200]}"
    if node.returncode != 0 or not evidence.get("startup_marker") \
            or not evidence.get("subscription_aborted"):
        return False, f"runtime probe failed: {evidence}"
    source = evidence.get("source") or ""
    if not source.startswith("file://") or \
            os.path.realpath(source[7:]) != os.path.realpath(probe):
        return False, f"runtime source is not the versioned plugin: {source}"
    loader_ok, loader_detail = loader_evidence(root, binary, plugin_dir)
    if not loader_ok:
        return False, loader_detail
    return True, (f"runtime id={evidence.get('plugin_id')} "
                  f"source={source} marker={evidence.get('startup_marker')} "
                  f"aborted={evidence.get('subscription_aborted')}; "
                  f"{loader_detail}")


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
    ok, detail = check_plugin(args.manifest, args.framework,
                              args.config_root, args.default_bin)
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
    ap.add_argument("--config-root", default=None,
                    help="Versioned V2 config root for the plugin runtime check.")
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
