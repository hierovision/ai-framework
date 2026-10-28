#!/usr/bin/env python3
"""Consumer (Paragon) V2 readiness — commit-bound, read-only on the primary.

`check` validates an isolated consumer worktree:

  * native V2 `opencode.json` — top-level `agents` object, no legacy `agent`
    key, native `agents.title.model` (not `small_model`), bindings retained;
  * agent wrappers — path-derived IDs (no `name:`), ordered `permissions`,
    `shell`/`subagent`/`edit` actions, no `permission`/`bash`/`task`/`write`,
    no per-agent `external_directory`;
  * no V1 plugin package (`@opencode-ai/plugin`);
  * the framework's own consumer binding checker;
  * an isolated V2 smoke (fresh scratch DB + XDG, `--standalone`).

`ready` runs `check`, performs the isolated smoke, and writes a readiness
artifact carrying the framework/consumer commit SHAs and both PR URLs. The
cutover refuses a stale, dirty, missing, or mismatched artifact.

Usage:
  python3 scripts/opencode_v2_consumer.py check <worktree>
  python3 scripts/opencode_v2_consumer.py ready <worktree> \
      --framework-pr-url URL --consumer-pr-url URL
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import opencode_v2 as v2  # noqa: E402

FRAMEWORK_CHECKER = os.path.join(HERE, "check-consumer-bindings.py")
DEFAULT_ARTIFACT = os.path.join(REPO, ".scratch", "opencode-v2",
                                "consumer-readiness.json")
LEGACY_AGENT_KEY = re.compile(r'"agent"\s*:')
LEGACY_PLUGIN = "@opencode-ai/plugin"
V2_PLUGIN = "@opencode/plugin"
V1_TOOL_TOKENS = ("bash", "task", "write")


def git(path, *args):
    return subprocess.run(["git", "-C", path] + list(args),
                          capture_output=True, text=True)


def head_sha(path):
    proc = git(path, "rev-parse", "HEAD")
    if proc.returncode != 0:
        raise RuntimeError(f"{path}: cannot resolve HEAD: {proc.stderr.strip()}")
    return proc.stdout.strip()


def is_worktree(path):
    """True when `path` is a linked worktree, never the repo's primary."""
    proc = git(path, "rev-parse", "--git-common-dir")
    if proc.returncode != 0:
        return False
    common = os.path.realpath(os.path.join(path, proc.stdout.strip()))
    dotgit = os.path.realpath(os.path.join(path, ".git"))
    # A primary checkout has .git == common dir. A linked worktree's .git is a
    # file pointer to <common>/worktrees/<name>.
    return dotgit != common


def worktree_clean(path):
    proc = git(path, "status", "--porcelain")
    return proc.returncode == 0 and not (proc.stdout or "").strip()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if not raw.startswith("---"):
        return raw, ""
    parts = raw.split("---", 2)
    return raw, parts[1] if len(parts) > 2 else ""


def check_config(root):
    errors = []
    path = os.path.join(root, "opencode.json")
    if not os.path.isfile(path):
        return [f"missing {path}"], None
    try:
        data = load_json(path)
    except ValueError as exc:
        return [f"{path}: invalid JSON: {exc}"], None
    if not isinstance(data, dict):
        return [f"{path}: config is not an object"], None
    if "agents" not in data or not isinstance(data.get("agents"), dict):
        errors.append("opencode.json: missing native `agents` object")
    if "agent" in data:
        errors.append("opencode.json: legacy `agent` key present")
    if "small_model" in data:
        errors.append("opencode.json: deprecated `small_model` present "
                      "(use agents.title.model)")
    title = (data.get("agents") or {}).get("title") or {}
    if not (isinstance(title, dict) and title.get("model")):
        errors.append("opencode.json: missing native agents.title.model")
    if "instructions" not in data:
        errors.append("opencode.json: instructions missing")
    for key in ("model",):
        if not data.get(key):
            errors.append(f"opencode.json: `{key}` binding missing")
    return errors, data


def check_wrappers(root):
    errors = []
    d = os.path.join(root, ".opencode", "agents")
    files = sorted(f for f in os.listdir(d) if f.endswith(".md")) \
        if os.path.isdir(d) else []
    if len(files) != 10:
        errors.append(f"expected 10 wrappers in {d}, found {len(files)}")
    for name in files:
        path = os.path.join(d, name)
        raw, fm = frontmatter(path)
        stem = name[:-3]
        if re.search(r"^name\s*:", fm, re.MULTILINE):
            errors.append(f"{name}: carries `name:` (path-derived ID required)")
        if not re.search(r"^model\s*:\s*\S+", fm, re.MULTILINE):
            errors.append(f"{name}: missing model binding")
        if re.search(r"^permission\s*:", fm, re.MULTILINE):
            errors.append(f"{name}: legacy `permission` key")
        if re.search(r"^permissions\s*:", fm, re.MULTILINE) is None:
            errors.append(f"{name}: missing ordered `permissions`")
        for token in ("bash:", "task:", "write:"):
            if re.search(rf"^\s*{re.escape(token)}", fm, re.MULTILINE):
                errors.append(f"{name}: legacy permission token `{token}`")
        if "external_directory" in fm:
            errors.append(f"{name}: per-agent external_directory "
                          "(the dispatcher owns grants)")
        for action in ("shell", "subagent", "edit"):
            if f"action: {action}" not in fm and f'"action": "{action}"' not in fm:
                errors.append(f"{name}: missing `{action}` action")
    return errors


def check_packages(root):
    errors = []
    for rel in (".opencode/package.json", "package.json"):
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            data = load_json(path)
        except ValueError:
            errors.append(f"{rel}: invalid JSON")
            continue
        deps = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps.update(data.get(key) or {})
        if LEGACY_PLUGIN in deps:
            errors.append(f"{rel}: legacy {LEGACY_PLUGIN} dependency")
        if V2_PLUGIN in deps:
            errors.append(f"{rel}: unexpected {V2_PLUGIN} dependency "
                          "(consumer gains no plugin)")
    return errors


def framework_checker(root):
    if os.environ.get("OPENCODE_CONSUMER_SKIP_BINDINGS") == "1":
        return True, "skipped (OPENCODE_CONSUMER_SKIP_BINDINGS=1)"
    proc = subprocess.run([sys.executable, FRAMEWORK_CHECKER, root],
                          capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def isolated_smoke(root, workdir, timeout=180):
    """One standalone V2 run inside the consumer worktree, hermetic paths."""
    scratch = os.path.join(REPO, ".scratch", "opencode-v2", "consumer-smoke")
    os.makedirs(scratch, exist_ok=True)
    db = os.path.join(scratch, "smoke.db")
    v2.assert_scratch_db(db, scratch)
    env = dict(os.environ)
    env.update(v2.scratch_env(scratch))
    env["OPENCODE_DB"] = db
    env["OPENCODE_LOG_LEVEL"] = "ERROR"
    default_v2 = os.path.join(REPO, ".scratch", "v2-prefix", "bin",
                              "opencode2")
    binary = env.get("OPENCODE_BIN") or (
        default_v2 if os.path.isfile(default_v2) else "opencode")
    # Seed the scratch DB from the current V1 auth.json (the credential store
    # moved into the selected DB in V2). No secret is printed or persisted.
    auth_path = os.path.expanduser("~/.local/share/opencode/auth.json")
    if os.path.isfile(auth_path):
        try:
            with open(auth_path, encoding="utf-8") as fh:
                auth = json.load(fh)
            payload = [{
                "id": hashlib.sha256(provider.encode()).hexdigest()[:24],
                "integrationID": provider,
                "label": "default",
                "active": True,
                "value": {"type": "key", "key": entry["key"]},
            } for provider, entry in (auth or {}).items()
                if isinstance(entry, dict) and entry.get("key")]
            if payload:
                subprocess.run([binary, "auth", "import", "--standalone"],
                               input=json.dumps(payload), capture_output=True,
                               text=True, env=env, timeout=120)
                con = sqlite3.connect(db)
                con.execute("UPDATE credential SET active=0")
                con.execute("UPDATE credential SET active=1 WHERE label='default'")
                con.commit()
                con.close()
        except (OSError, ValueError, sqlite3.Error):
            pass
    try:
        proc = subprocess.run(
            [binary, "run", "--standalone", "--model",
             "opencode-go/deepseek-v4.1-flash", "--format", "json", "Reply OK"],
            cwd=workdir, env=env, capture_output=True, text=True,
            timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"smoke failed: {exc}"
    events, _ = v2.parse_stream(proc.stdout or "")
    text = v2.final_text(events)
    ok = proc.returncode == 0 and "OK" in text
    return ok, (proc.stderr or text)[:400]


def check(root, smoke=False):
    errors = []
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return [f"{root}: not a directory"], None
    if not is_worktree(root):
        errors.append(f"{root}: not an isolated worktree "
                      "(refusing the primary checkout)")
    cfg_errors, data = check_config(root)
    errors += cfg_errors
    errors += check_wrappers(root)
    errors += check_packages(root)
    ok, detail = framework_checker(root)
    if not ok:
        errors.append(f"framework checker failed: {detail[-400:]}")
    if smoke and not errors:
        smoke_ok, smoke_detail = isolated_smoke(root, root)
        if not smoke_ok:
            errors.append(f"isolated V2 smoke failed: {smoke_detail}")
    return errors, data


def write_artifact(path, framework_sha, consumer_sha, framework_pr,
                   consumer_pr, extra=None):
    payload = {
        "created": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "framework_sha": framework_sha,
        "consumer_sha": consumer_sha,
        "framework_pr_url": framework_pr,
        "consumer_pr_url": consumer_pr,
    }
    payload.update(extra or {})
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return payload


def verify_artifact(path, framework_sha, consumer_sha):
    """Cutover gate: stale/missing/mismatched evidence fails closed."""
    if not os.path.isfile(path):
        return False, f"readiness artifact missing: {path}"
    try:
        data = load_json(path)
    except ValueError as exc:
        return False, f"readiness artifact invalid: {exc}"
    if data.get("framework_sha") != framework_sha:
        return False, (f"readiness framework SHA mismatch: "
                       f"{data.get('framework_sha')} != {framework_sha}")
    if data.get("consumer_sha") != consumer_sha:
        return False, (f"readiness consumer SHA mismatch: "
                       f"{data.get('consumer_sha')} != {consumer_sha}")
    for key in ("framework_pr_url", "consumer_pr_url"):
        if not str(data.get(key) or "").startswith("http"):
            return False, f"readiness artifact missing {key}"
    return True, "ok"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Consumer V2 readiness.")
    ap.add_argument("mode", choices=["check", "ready"])
    ap.add_argument("worktree")
    ap.add_argument("--framework", default=REPO)
    ap.add_argument("--framework-pr-url", default=os.environ.get(
        "FRAMEWORK_PR_URL"))
    ap.add_argument("--consumer-pr-url", default=os.environ.get(
        "CONSUMER_PR_URL"))
    ap.add_argument("--artifact", default=DEFAULT_ARTIFACT)
    ap.add_argument("--skip-smoke", action="store_true")
    args = ap.parse_args(argv)

    errors, _ = check(args.worktree, smoke=(args.mode == "ready"
                                            and not args.skip_smoke))
    for err in errors:
        print(f"  - {err}")
    if errors:
        print(f"FAIL: {args.worktree}: {len(errors)} readiness violation(s)")
        return 1
    if args.mode == "check":
        print(f"OK: {args.worktree}: native V2 config, wrappers, packages, "
              f"bindings")
        return 0
    if not (args.framework_pr_url and args.consumer_pr_url):
        print("error: ready requires --framework-pr-url and --consumer-pr-url",
              file=sys.stderr)
        return 2
    if not is_worktree(args.worktree) or not worktree_clean(args.worktree):
        print("error: readiness requires a clean isolated consumer worktree",
              file=sys.stderr)
        return 2
    payload = write_artifact(
        args.artifact, head_sha(args.framework), head_sha(args.worktree),
        args.framework_pr_url, args.consumer_pr_url)
    print(f"READY: {args.artifact}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
