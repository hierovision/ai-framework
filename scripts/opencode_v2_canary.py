#!/usr/bin/env python3
"""OpenCode V2 canary — C5-first, fail-closed, every write under `.scratch/`.

C5 (backup) is the FIRST mutation. Only after a verified consistent SQLite
backup, config backup, and dereferenced V1 agent snapshot may the script
install or invoke V2. Every V2 invocation asserts an explicit scratch
`OPENCODE_DB` plus isolated XDG state/cache/runtime/TMPDIR; the real session
DB is never an implicit default.

Gates (see `docs/ADRs/ADR-0014-opencode-v2-upgrade.md` and
`reference/opencode-integration.md`):
  C1 isolated install/version   C2 service + /api/info        C3 model catalog
  C4 fresh-DB 10/10 stability   C5 backup (first)             C6 V1 rollback
  C7 config/plugin probe        C8 capability audit
  migration  copy-only, 900 s, `session_v2` population + source hash

Usage:
  python3 scripts/opencode_v2_canary.py --all
  python3 scripts/opencode_v2_canary.py --gate C5
  python3 scripts/opencode_v2_canary.py --gate migration

Post-cutover (the live default is already V2), canary the next version against
the V1 rollback binary as the C1 "default":
  python3 scripts/opencode_v2_canary.py --all --skip-install \
    --prefix .scratch/v2-<version>-prefix \
    --opencode-bin .scratch/v2-<version>-prefix/bin/opencode \
    --default-bin ~/.config/yarn/global/node_modules/opencode-ai/bin/opencode.exe \
    --default-version 1.19.4 \
    --v1-prefix .scratch/v1-prefix \
    --scratch-root .scratch/v2-canary-<version>
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import socket
import subprocess
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

DEFAULT_SCRATCH = os.path.join(REPO, ".scratch", "v2-canary")
REAL_DB = v2.DEFAULT_DB
REAL_CONFIG = os.path.expanduser("~/.config/opencode")
AGENTS_DIR = os.path.join(REPO, "agents")
MIGRATION_TIMEOUT = 900


def now_date():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def default_bin_path():
    """The supported default command: the explicit yarn link, never PATH."""
    return os.path.join(os.path.expanduser("~"), ".yarn", "bin", "opencode")


def exact_version(text):
    """Delegate to the shared exact version parser."""
    return v2.parse_opencode_version(text)


def api_version(text):
    """Exact `version` field from an API payload (JSON first, then regex)."""
    try:
        data = json.loads(text or "{}")
        if isinstance(data, dict) and data.get("version"):
            return data["version"]
    except ValueError:
        pass
    match = re.search(r'"version"\s*:\s*"([^"]+)"', text or "")
    return match.group(1) if match else None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def evidence(root, name, text):
    path = os.path.join(root, name)
    write_text(path, text if text.endswith("\n") else text + "\n")
    return path


def sqlite_backup(source, dest):
    """Delegate to the shared 0600-preserving SQLite backup helper."""
    return v2.sqlite_backup(source, dest)


def integrity(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def sql_count(path, table):
    if not path or not os.path.isfile(path):
        return 0
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if not v2.table_exists(con, table):
            return 0
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def config_backup(root):
    """Tar the global config EXCLUDING node_modules (secrets stay inside)."""
    dest = os.path.join(root, "opencode-config.tgz")
    os.makedirs(root, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        for base, dirs, files in os.walk(REAL_CONFIG):
            dirs[:] = [d for d in dirs if d != "node_modules"]
            for name in files:
                path = os.path.join(base, name)
                try:
                    tar.add(path, arcname=os.path.relpath(path, REAL_CONFIG))
                except OSError:
                    continue
    os.chmod(dest, 0o600)
    return dest


def agent_snapshot(root):
    """Dereferenced copies of every V1 agent file (symlinks are not content)."""
    dest = os.path.join(root, "v1-agents")
    os.makedirs(dest, exist_ok=True)
    hashes = {}
    for name in sorted(os.listdir(AGENTS_DIR)):
        if not name.endswith(".md"):
            continue
        src = os.path.join(AGENTS_DIR, name)
        out = os.path.join(dest, name)
        try:
            shutil.copyfile(src, out)
        except OSError:
            continue
        hashes[name] = sha256(out)
    manifest = os.path.join(dest, "hashes.json")
    write_text(manifest, json.dumps(hashes, indent=2, sort_keys=True))
    return dest, hashes


def write_sha_file(root, entries):
    path = os.path.join(root, "backup.sha256")
    lines = [f"{digest}  {os.path.basename(p)}" for p, digest in entries]
    write_text(path, "\n".join(lines) + "\n")
    return path


# --- gates -------------------------------------------------------------------

def gate_c5(args):
    """First mutation: backup DB + config + agent snapshot, verify all."""
    root = args.scratch_root
    os.makedirs(root, exist_ok=True)
    source = os.path.abspath(args.source_db or REAL_DB)
    if not os.path.isfile(source):
        return False, f"source DB missing: {source}"
    db_copy = os.path.join(root, "opencode.db")
    config_tgz = os.path.join(root, "opencode-config.tgz")
    sqlite_backup(source, db_copy)
    config_backup(root)
    snapshot, agent_hashes = agent_snapshot(root)
    db_hash, cfg_hash = sha256(db_copy), sha256(config_tgz)
    check = integrity(db_copy)
    sessions = sql_count(db_copy, "session")
    write_sha_file(root, [(db_copy, db_hash), (config_tgz, cfg_hash)])
    ok = check == "ok"
    lines = [
        f"date={now_date()}",
        f"source_db={source}",
        f"database_backup={db_copy}",
        f"database_size_bytes={os.path.getsize(db_copy)}",
        f"database_sha256={db_hash}",
        f"database_integrity_check={check}",
        f"source_session_rows={sessions}",
        f"config_backup={config_tgz}",
        f"config_sha256={cfg_hash}",
        f"dereferenced_agent_snapshot={snapshot}",
        f"agent_files={len(agent_hashes)}",
        f"agent_hashes_sha256={sha256(os.path.join(snapshot, 'hashes.json'))}",
        f"C5={'PASS' if ok else 'FAIL'}",
    ]
    evidence(root, "C5.txt", "\n".join(lines))
    return ok, "\n".join(lines)


def stop_scratch_services(root):
    """Stop opencode services a gate started under this scratch root.

    C2 and C7 start a service on a free port; leaving it running blocks the
    later drained apply and makes the scratch binary look like the live one.
    Only processes whose XDG_CONFIG_HOME is under `root` are touched.
    """
    root = os.path.abspath(root)
    stopped = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode(
                "utf-8", "replace").split("\0")
            environ = open(f"/proc/{pid}/environ", "rb").read().decode(
                "utf-8", "replace").split("\0")
        except OSError:
            continue
        if not any("opencode" in part for part in cmdline):
            continue
        values = dict(part.split("=", 1) for part in environ if "=" in part)
        xdg = values.get("XDG_CONFIG_HOME")
        if not xdg:
            continue
        xdg = os.path.abspath(xdg)
        if xdg == root or xdg.startswith(root + os.sep):
            try:
                os.kill(int(pid), signal.SIGTERM)
                stopped.append(pid)
            except OSError:
                pass
    for pid in stopped:
        for _ in range(20):
            if not os.path.exists(f"/proc/{pid}"):
                break
            time.sleep(0.05)
        else:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass
    return stopped


def scratch_env(root):
    paths = v2.scratch_env(root)
    return paths


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def v2_run(args, extra_env, argv, timeout=180):
    """Invoke V2 with a scratch DB asserted and isolated XDG/TMP paths."""
    db = os.path.join(args.scratch_root, args.db_name)
    v2.assert_scratch_db(db, args.scratch_root)
    env = dict(os.environ)
    env.update(scratch_env(args.scratch_root))
    env["OPENCODE_DB"] = db
    env["OPENCODE_LOG_LEVEL"] = "ERROR"
    env.update(extra_env or {})
    env["OPENCODE_BIN"] = args.opencode_bin
    binary = args.opencode_bin
    return subprocess.run([binary] + argv, capture_output=True, text=True,
                          env=env, timeout=timeout)


def gate_c1(args):
    root = args.scratch_root
    prefix = args.prefix
    lines = [f"date={now_date()}"]
    if not args.skip_install:
        try:
            proc = subprocess.run(
                ["npm", "install", "--global", "--prefix", prefix,
                 f"@opencode/cli@{args.version}"],
                capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.SubprocessError) as exc:
            lines.append(f"install_error={type(exc).__name__}: {exc}")
            evidence(root, "C1.txt", "\n".join(lines + ["C1=FAIL"]))
            return False, f"install probe failed: {exc}"
        lines.append(f"install_exit={proc.returncode}")
        if proc.returncode != 0:
            evidence(root, "C1.txt", "\n".join(lines + ["C1=FAIL"]))
            return False, (proc.stderr or "")[-400:]
    binary = os.path.join(prefix, "bin", "opencode2")
    if not os.path.isfile(binary):
        binary = os.path.join(prefix, "bin", "opencode")
    if not os.path.isfile(binary):
        evidence(root, "C1.txt", "\n".join(lines + ["C1=FAIL"]))
        return False, "isolated binary missing"
    try:
        iso = subprocess.run([binary, "--version"], capture_output=True,
                             text=True, timeout=30)
        default = subprocess.run([args.default_bin, "--version"],
                                 capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"version_probe_error={type(exc).__name__}: {exc}")
        evidence(root, "C1.txt", "\n".join(lines + ["C1=FAIL"]))
        return False, f"version probe failed: {exc}"
    ok = (iso.returncode == 0 and default.returncode == 0
          and exact_version(iso.stdout) == args.version
          and exact_version(default.stdout) == args.default_version)
    lines += [
        f"isolated_command={binary} --version",
        f"isolated_output={(iso.stdout or '').strip()}",
        f"default_command={args.default_bin} --version",
        f"default_output={(default.stdout or '').strip()}",
        f"C1={'PASS' if ok else 'FAIL'}",
    ]
    evidence(root, "C1.txt", "\n".join(lines))
    return ok, "\n".join(lines)


def gate_c2(args):
    root = args.scratch_root
    try:
        port = str(free_port())
        v2_run(args, {}, ["service", "set", "port", port], timeout=30)
        start = v2_run(args, {}, ["service", "start"], timeout=60)
        status = v2_run(args, {}, ["service", "status"], timeout=60)
        api = v2_run(args, {}, ["api", "GET", "/api/info"], timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        evidence(root, "C2.txt", f"C2=FAIL {type(exc).__name__}: {exc}")
        return False, str(exc)
    ok = status.returncode == 0 and api.returncode == 0 and \
        api_version(api.stdout) == args.version
    text = "\n".join([
        f"date={now_date()}",
        f"service_port={port}",
        f"service_start_exit={start.returncode}",
        f"service_status_exit={status.returncode}",
        (status.stdout or "").strip()[:2000],
        f"api_exit={api.returncode}",
        (api.stdout or "").strip()[:2000],
        f"C2={'PASS' if ok else 'FAIL'}",
    ])
    evidence(root, "C2.txt", text)
    return ok, text


def agent_bindings():
    bindings = {}
    for name in sorted(os.listdir(AGENTS_DIR)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(AGENTS_DIR, name), encoding="utf-8") as fh:
            raw = fh.read()
        fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
        m = re.search(r"^model:\s*(\S+)\s*$", fm, re.MULTILINE)
        if m:
            bindings[name[:-3]] = m.group(1)
    return bindings


def import_current_auth(args, db):
    """Seed the isolated DB from V1 auth.json; never print or persist secrets.

    V2 `auth import` expects an ARRAY of credential rows:
      [{id, integrationID, label, active, value:{type:"key", key}}]
    V1 `auth.json` stores `{provider: {type:"api", key}}`; map `api` -> `key`.
    """
    auth_path = os.path.expanduser("~/.local/share/opencode/auth.json")
    if not os.path.isfile(auth_path):
        return False, "auth.json missing"
    try:
        with open(auth_path, encoding="utf-8") as fh:
            auth = json.load(fh)
    except (OSError, ValueError):
        return False, "auth.json unreadable"
    payload = []
    for provider, entry in (auth or {}).items():
        if not isinstance(entry, dict) or not entry.get("key"):
            continue
        payload.append({
            "id": hashlib.sha256(provider.encode()).hexdigest()[:24],
            "integrationID": provider,
            "label": "default",
            "active": True,
            "value": {"type": "key", "key": entry["key"]},
        })
    if not payload:
        return False, "no importable credentials"
    env = dict(os.environ)
    env.update(scratch_env(args.scratch_root))
    env["OPENCODE_DB"] = db
    env["OPENCODE_LOG_LEVEL"] = "ERROR"
    proc = subprocess.run(
        [args.opencode_bin, "auth", "import", "--standalone"],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
        timeout=120)
    if proc.returncode == 0:
        # A migrated V1 DB may already carry an older, expired credential for
        # the same integration. Make the freshly imported "default" the only
        # active row for each provider (scratch DB only).
        try:
            con = sqlite3.connect(db)
            con.execute("UPDATE credential SET active=0")
            con.execute("UPDATE credential SET active=1 WHERE label='default'")
            con.commit()
            con.close()
        except sqlite3.Error:
            pass
    return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()[:200]


def gate_c3(args):
    root = args.scratch_root
    db = os.path.join(root, "c3-real.db")
    v2.assert_scratch_db(db, root)
    ok_auth, detail = import_current_auth(args, db)
    proc = v2_run(args, {"OPENCODE_DB": db}, ["models", "--standalone"],
                  timeout=120)
    expected = sorted(set(agent_bindings().values()))
    catalog = proc.stdout or ""
    missing = [b for b in expected if b not in catalog]
    ok = ok_auth and proc.returncode == 0 and not missing
    text = "\n".join([
        f"date={now_date()}",
        "credential_source=auth.json piped to isolated DB over stdin",
        f"credential_import_ok={ok_auth}",
        f"credential_import_detail={detail}",
        f"models_exit={proc.returncode}",
        f"expected_bindings={len(expected)}",
        f"missing_bindings={len(missing)}",
        f"missing={','.join(missing)}",
        f"C3={'PASS' if ok else 'FAIL'}",
    ])
    evidence(root, "C3-real.txt", text)
    write_text(os.path.join(root, "models-real.txt"),
               (proc.stdout or "")[:200000])
    return ok, text


def gate_c4(args):
    root = args.scratch_root
    db = os.path.join(root, "c4-stability.db")
    if os.path.exists(db):
        os.remove(db)
    v2.assert_scratch_db(db, root)
    ok_auth, detail = import_current_auth(args, db)
    rows_before = sql_count(db, "session_v2")
    timings, texts = [], []
    ok = ok_auth
    for i in range(10):
        started = time.monotonic()
        try:
            proc = v2_run(args, {"OPENCODE_DB": db},
                          ["run", "--standalone", "--model",
                           "opencode-go/deepseek-v4.1-flash", "--format", "json",
                           "Reply OK"], timeout=180)
        except subprocess.TimeoutExpired:
            ok = False
            timings.append("timeout")
            break
        elapsed = time.monotonic() - started
        timings.append(f"{elapsed:.2f}")
        events, _ = v2.parse_stream(proc.stdout or "")
        text = v2.final_text(events)
        texts.append(text)
        if proc.returncode != 0 or "OK" not in text:
            ok = False
    rows_after = sql_count(db, "session_v2")
    text = "\n".join([
        f"date={now_date()}",
        "mode=fresh isolated DB; migration is a separate gate",
        f"credential_import_ok={ok_auth}",
        f"session_v2_before={rows_before}",
        f"runs={len(timings)}",
        f"timings_s={','.join(timings)}",
        f"texts={json.dumps(texts)}",
        f"session_v2_after={rows_after}",
        f"C4={'PASS' if ok and len(timings) == 10 else 'FAIL'}",
    ])
    evidence(root, "C4.txt", text)
    return ok and len(timings) == 10, text


def gate_c6(args):
    """Rollback drill: isolated V1 1.19.4 reads the restored backup."""
    root = args.scratch_root
    prefix = args.v1_prefix or os.path.join(REPO, ".scratch", "v1-prefix")
    binary = os.path.join(prefix, "bin", "opencode")
    lines = [f"date={now_date()}", f"v1_prefix={prefix}"]
    if not os.path.isfile(binary):
        evidence(root, "C6.txt", "\n".join(lines + ["C6=FAIL (no V1 prefix)"]))
        return False, "V1 prefix missing"
    try:
        ver = subprocess.run([binary, "--version"], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"v1_version_probe_error={type(exc).__name__}: {exc}")
        evidence(root, "C6.txt", "\n".join(lines + ["C6=FAIL"]))
        return False, f"V1 version probe failed: {exc}"
    lines.append(f"v1_version={(ver.stdout or '').strip()}")
    if ver.returncode != 0:
        lines.append(f"v1_version_exit={ver.returncode}")
        evidence(root, "C6.txt", "\n".join(lines + ["C6=FAIL"]))
        return False, f"V1 version probe exited {ver.returncode}"
    backup = os.path.join(root, "opencode.db")
    if not os.path.isfile(backup):
        lines.append("C6=FAIL (no C5 backup)")
        evidence(root, "C6.txt", "\n".join(lines))
        return False, "no C5 backup"
    data_home = os.path.join(root, "c6-data")
    os.makedirs(os.path.join(data_home, "opencode"), exist_ok=True)
    restored = os.path.join(data_home, "opencode", "opencode.db")
    sqlite_backup(backup, restored)
    source_ids = read_ids(backup, "session")
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = data_home
    env["OPENCODE_LOG_LEVEL"] = "ERROR"
    try:
        proc = subprocess.run(
            [binary, "session", "list", "--max-count", "3", "--format", "json"],
            capture_output=True, text=True, env=env, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"C6=FAIL ({exc})")
        evidence(root, "C6.txt", "\n".join(lines))
        return False, str(exc)
    ids = re.findall(r"ses_[A-Za-z0-9]+", proc.stdout or "")
    known = [i for i in ids if i in source_ids]
    ok = (exact_version(ver.stdout) == "1.19.4"
          and proc.returncode == 0 and bool(known))
    lines += [f"session_list_exit={proc.returncode}",
              f"session_ids={known[:3]}",
              f"C6={'PASS' if ok else 'FAIL'}"]
    evidence(root, "C6.txt", "\n".join(lines))
    return ok, "\n".join(lines)


def gate_c7(args):
    """Config/plugin probe under an isolated V2 config root."""
    root = args.scratch_root
    c7 = os.path.join(root, "c7")
    config = os.path.join(c7, "config", "opencode")
    os.makedirs(os.path.join(config, "agents"), exist_ok=True)
    os.makedirs(os.path.join(config, "plugins"), exist_ok=True)
    marker = {
        "$schema": "https://opencode.ai/config.json",
        "agents": {"canary-marker": {
            "description": "C7 marker", "mode": "subagent",
            "permissions": [
                {"action": "shell", "resource": "git status", "effect": "allow"},
                {"action": "shell", "resource": "*", "effect": "deny"},
            ]}},
        "permissions": [{"action": "execute", "resource": "*", "effect": "deny"}],
    }
    write_text(os.path.join(config, "opencode.jsonc"),
               json.dumps(marker, indent=2))
    with open(os.path.join(config, "agents", "canary-marker.md"), "w",
              encoding="utf-8") as fh:
        fh.write("---\ndescription: C7 marker\nmodel: "
                 "opencode-go/kimi-k3.1-pro\nmode: all\npermissions:\n"
                 "  - action: shell\n    resource: \"*\"\n    effect: deny\n"
                 "  - action: edit\n    resource: \"*\"\n    effect: deny\n"
                 "  - action: subagent\n    resource: \"*\"\n    effect: deny\n"
                 "  - action: execute\n    resource: \"*\"\n    effect: deny\n"
                 "---\n")
    with open(os.path.join(config, "plugins", "canary-plugin.js"), "w",
              encoding="utf-8") as fh:
        fh.write("export default { id: 'canary-plugin', setup() {} }\n")
    env = {"XDG_CONFIG_HOME": os.path.join(c7, "config"),
           "OPENCODE_DB": os.path.join(root, "c7.db")}
    v2.assert_scratch_db(env["OPENCODE_DB"], root)
    try:
        port = str(free_port())
        v2_run(args, env, ["service", "set", "port", port], timeout=30)
        start = v2_run(args, env, ["service", "start"], timeout=60)
        cfg = v2_run(args, env, ["debug", "config"], timeout=60)
        plugins = v2_run(args, env, ["plugin", "list"], timeout=60)
        agents = v2_run(args, env, ["api", "GET", "/api/agent"], timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        evidence(root, "C7.txt", f"C7=FAIL ({exc})")
        return False, str(exc)
    marker_agent = "canary-marker" in (cfg.stdout or "")
    marker_agent_api = "canary-marker" in (agents.stdout or "")
    marker_plugin = "canary-plugin" in (plugins.stdout or "")
    ok = (cfg.returncode == 0 and plugins.returncode == 0
          and agents.returncode == 0 and marker_agent and marker_agent_api
          and marker_plugin)
    text = "\n".join([
        f"date={now_date()}",
        f"debug_config_exit={cfg.returncode}",
        f"marker_agent_present={marker_agent}",
        f"plugin_list_exit={plugins.returncode}",
        f"plugin_rows={(plugins.stdout or '').strip()[:200]}",
        f"marker_plugin_present={marker_plugin}",
        f"agent_api_exit={agents.returncode}",
        f"agent_api_has_marker={marker_agent_api}",
        f"C7={'PASS' if ok else 'FAIL'}",
        "global_config_audit=.scratch/v2-canary/global-config-audit.md",
    ])
    evidence(root, "C7.txt", text)
    return ok, text


def gate_c8(args):
    root = args.scratch_root
    patterns = ("todowrite", "lsp", "websearch")
    hits = {}
    for pattern in patterns:
        proc = subprocess.run(
            ["grep", "-R", "-l", "-i", "--exclude-dir=node_modules",
             "--exclude-dir=__pycache__", pattern, "skills", "agents",
             "scripts", "reference", ".github"],
            cwd=REPO, capture_output=True, text=True)
        files = [f for f in (proc.stdout or "").splitlines()
                 if ".opencode/plans" not in f
                 and "opencode_v2_canary.py" not in f]
        hits[pattern] = files
    ok = all(not files for files in hits.values())
    text = "\n".join([
        f"date={now_date()}",
        f"todowrite_files={hits['todowrite']}",
        f"lsp_files={hits['lsp']}",
        f"websearch_files={hits['websearch']}",
        f"C8={'PASS' if ok else 'FAIL'}",
    ])
    evidence(root, "C8.txt", text)
    return ok, text


def migration_membership(src_ids, target_ids, run_ids=()):
    """Measured migration membership (never a vacuous set identity).

    The rehearsal run creates its own target session(s); `run_ids` removes them
    before the phantom check. Structural validity requires a non-empty source,
    at least one migrated source row (zero migration fails even with source
    rows), and no phantom target IDs. Missing source rows are reported for the
    residual-acceptance decision.
    """
    src = set(src_ids)
    raw_target = set(target_ids)
    run = raw_target & set(run_ids)
    target = raw_target - run
    migrated = target & src
    missing = src - target
    phantom = target - src
    zero_migration = bool(src) and not migrated
    ok = bool(src) and not zero_migration and not phantom
    return {"ok": ok, "source": len(src), "target": len(raw_target),
            "run": len(run), "migrated": len(migrated),
            "missing": missing, "phantom": phantom,
            "zero_migration": zero_migration}


def gate_migration(args):
    """Copy-only 900 s rehearsal: population, membership, integrity, hashes."""
    root = args.scratch_root
    source = os.path.abspath(args.source_db or REAL_DB)
    copy = os.path.join(root, "migration-rehearsal.db")
    sqlite_backup(source, copy)
    source_hash = sha256(source)
    copy_initial = sha256(copy)
    src_ids = read_ids(source, "session")
    ok_auth, detail = import_current_auth(args, copy)
    rows_after_auth = sql_count(copy, "session_v2")
    started = time.monotonic()
    try:
        proc = v2_run(args, {"OPENCODE_DB": copy},
                      ["run", "--standalone", "--model",
                       "opencode-go/deepseek-v4.1-flash", "--format", "json",
                       "Reply OK"], timeout=MIGRATION_TIMEOUT)
        elapsed = time.monotonic() - started
    except subprocess.TimeoutExpired:
        evidence(root, "migration-rehearsal.txt",
                 f"date={now_date()}\nmigration=TIMEOUT>{MIGRATION_TIMEOUT}s")
        return False, "migration timeout"
    target_ids = read_ids(copy, "session_v2")
    run_ids = set(re.findall(r'"sessionID"\s*:\s*"([^"]+)"',
                             proc.stdout or ""))
    member = migration_membership(src_ids, target_ids, run_ids)
    missing = sorted(member["missing"])
    phantom = sorted(member["phantom"])
    residual_accepted = v2.migration_residual_accepted(
        REPO, root, args.version, len(missing))
    untouched = sha256(source) == source_hash
    check = integrity(copy)
    ok = (ok_auth and proc.returncode == 0 and untouched and check == "ok"
          and member["ok"] and (not missing or residual_accepted))
    text = "\n".join([
        f"date={now_date()}",
        f"source={source}",
        f"source_sha256={source_hash}",
        f"source_session_rows={member['source']}",
        f"copy={copy}",
        f"copy_initial_sha256={copy_initial}",
        f"migration_exit={proc.returncode}",
        f"migration_stderr={(proc.stderr or '').strip()[:400]}",
        f"migration_elapsed_seconds={elapsed:.2f}",
        f"session_v2_after_auth_import={rows_after_auth}",
        f"target_session_rows={member['target']}",
        f"run_created_ids={member['run']}",
        f"migrated_source_rows={member['migrated']}",
        f"source_sessions_not_migrated={len(missing)}",
        f"target_only_ids={len(phantom)}",
        f"zero_migration={member['zero_migration']}",
        f"migrated_ids_subset_of_source={not phantom}",
        f"residual_accepted={residual_accepted}",
        f"target_integrity_check={check}",
        f"source_backup_sha256_after={sha256(source)}",
        f"source_untouched={untouched}",
        f"migration={'PASS' if ok else 'FAIL'} with fidelity residual "
        f"{len(missing)} (requires classification or owner acceptance)",
    ])
    evidence(root, "migration-rehearsal.txt", text)
    write_text(os.path.join(root, "migration-residual-ids.json"),
               json.dumps(missing, indent=2))
    write_text(os.path.join(root, "migration-phantom-ids.json"),
               json.dumps(phantom, indent=2))
    return ok, text


def read_ids(path, table):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if not v2.table_exists(con, table):
            return set()
        return {r[0] for r in con.execute(f"SELECT id FROM {table}")}
    finally:
        con.close()


GATE_ORDER = [
    ("C5", gate_c5), ("C1", gate_c1), ("C2", gate_c2), ("C3", gate_c3),
    ("C4", gate_c4), ("C6", gate_c6), ("C7", gate_c7), ("C8", gate_c8),
    ("migration", gate_migration),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="OpenCode V2 canary (fail closed).")
    ap.add_argument("--gate", default=None,
                    help="C1..C8 or migration (default with --all: every gate)")
    ap.add_argument("--all", action="store_true", help="run the gate order")
    ap.add_argument("--scratch-root", default=DEFAULT_SCRATCH)
    ap.add_argument("--source-db", default=REAL_DB)
    ap.add_argument("--prefix", default=os.path.join(DEFAULT_SCRATCH,
                                                     "..", "v2-prefix"))
    ap.add_argument("--v1-prefix", default=os.path.join(REPO, ".scratch",
                                                        "v1-prefix"))
    ap.add_argument("--opencode-bin", default=os.path.join(
        REPO, ".scratch", "v2-prefix", "bin", "opencode2"))
    ap.add_argument("--default-bin", default=default_bin_path())
    ap.add_argument("--db-name", default="stability.db")
    ap.add_argument("--version", default=v2.VERSION_PIN,
                    help="candidate @opencode/cli version (default: pin)")
    ap.add_argument("--default-version", default=v2.VERSION_PIN,
                    help="expected version of the current default command "
                         "(supported install: the current pin; pre-cutover: "
                         "1.19.4)")
    ap.add_argument("--skip-install", action="store_true")
    args = ap.parse_args(argv)
    args.scratch_root = os.path.abspath(args.scratch_root)
    os.makedirs(args.scratch_root, exist_ok=True)

    gates = []
    if args.all:
        gates = GATE_ORDER
    elif args.gate:
        match = [g for g in GATE_ORDER if g[0] == args.gate]
        if not match:
            print(f"error: unknown gate {args.gate}", file=sys.stderr)
            return 2
        gates = match
    else:
        print("error: pass --all or --gate", file=sys.stderr)
        return 2

    try:
        for name, fn in gates:
            ok, detail = fn(args)
            print(f"{name}: {'PASS' if ok else 'FAIL'}")
            if not ok:
                print(detail, file=sys.stderr)
                return 1
        return 0
    finally:
        stopped = stop_scratch_services(args.scratch_root)
        if stopped:
            print(f"scratch services stopped: {','.join(stopped)}")


if __name__ == "__main__":
    sys.exit(main())
