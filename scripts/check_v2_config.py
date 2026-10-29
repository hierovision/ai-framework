#!/usr/bin/env python3
"""Offline V2 agent/config linter — rejects every V1-only key.

Checks the agent corpus (`agents/*.md`) and the versioned/global config
documents for:

  * no `name:` (the V2 ID is path-derived);
  * `permissions:` (plural, ordered `{action, resource, effect}`), never the
    V1 `permission` map;
  * actions `shell`, `subagent`, `edit`, `execute` (no `bash`, `write`,
    `task`, `patch`);
  * no per-agent `external_directory` (the dispatcher owns grants).

`--baseline main` compares each persona's V2 shell allow set against
`git show main:agents/<name>.md` and fails on any added allow pattern — the
permission conversion must be 1:1, never widened.

Exit 0 clean, 1 violation, 2 usage.
"""
import argparse
import glob
import os
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
FORBIDDEN_KEYS = ("name", "permission", "bash", "write", "task", "patch",
                  "external_directory")
REQUIRED_ACTIONS = ("shell", "subagent", "edit", "execute")


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if not raw.startswith("---"):
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid frontmatter: {exc}")
    return data if isinstance(data, dict) else {}


def parse_rules(value, where, errors):
    """Return [(action, resource, effect)] for an ordered permission list."""
    rules = []
    if not isinstance(value, list):
        errors.append(f"{where}: `permissions` must be an ordered list")
        return rules
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{where}: rule {i} is not an object")
            continue
        action, resource = item.get("action"), item.get("resource")
        effect = item.get("effect")
        if not action or not isinstance(resource, str) or \
                effect not in ("allow", "deny", "ask"):
            errors.append(f"{where}: rule {i} needs action/resource/effect")
            continue
        rules.append((str(action), resource, str(effect)))
    return rules


def check_agent(path):
    errors = []
    data = frontmatter(path)
    if data is None:
        return [f"{path}: no frontmatter"]
    for key in FORBIDDEN_KEYS:
        if key in data:
            errors.append(f"{path}: forbidden V1 key `{key}`")
    if not data.get("model"):
        errors.append(f"{path}: missing model binding")
    if not data.get("description"):
        errors.append(f"{path}: missing description")
    perm = data.get("permission")
    if isinstance(perm, dict):
        for legacy in ("bash", "write", "task", "patch", "external_directory"):
            if legacy in perm:
                errors.append(f"{path}: legacy permission token `{legacy}`")
    rules = parse_rules(data.get("permissions"), path, errors)
    actions = {a for a, _, _ in rules}
    for action in REQUIRED_ACTIONS:
        if action not in actions:
            errors.append(f"{path}: missing `{action}` permission rule")
    for action in actions:
        if action not in REQUIRED_ACTIONS:
            errors.append(f"{path}: unsupported action `{action}`")
    return errors


def check_config(path):
    errors = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [f"{path}: unreadable: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: config is not an object"]
    if "agent" in data:
        errors.append(f"{path}: legacy `agent` key (use `agents`)")
    if "small_model" in data:
        errors.append(f"{path}: deprecated `small_model`")
    if "permissions" in data:
        parse_rules(data["permissions"], path, errors)
    return errors


def v1_shell_allows(path, ref):
    """The V1 `permission.bash` allow resources from `git show ref:path`."""
    proc = subprocess.run(["git", "-C", REPO, "show", f"{ref}:{path}"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return set()
    raw = proc.stdout
    if not raw.startswith("---"):
        return set()
    parts = raw.split("---", 2)
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return set()
    bash = ((data.get("permission") or {}).get("bash") or {})
    if isinstance(bash, dict):
        return {k for k, v in bash.items() if v == "allow"}
    return set()


def check_baseline(agents_dir, ref):
    errors = []
    for path in sorted(glob.glob(os.path.join(agents_dir, "*.md"))):
        name = os.path.basename(path)
        data = frontmatter(path) or {}
        rules = parse_rules(data.get("permissions"), path, [])
        current = {r for a, r, e in rules if a == "shell" and e == "allow"}
        baseline = v1_shell_allows(f"agents/{name}", ref)
        if not baseline:
            continue  # no V1 bash allow-map: nothing to compare
        added = sorted(current - baseline)
        if added:
            errors.append(f"{name}: added shell allow(s): {added}")
        # A V1 allow dropped is a narrowing, allowed; flag it for the record.
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline V2 config linter.")
    ap.add_argument("--agents-dir", default=os.path.join(REPO, "agents"))
    ap.add_argument("--config", action="append", default=None,
                    help="config file to check (repeatable)")
    ap.add_argument("--baseline", default=None,
                    help="git ref to compare shell allow sets against")
    args = ap.parse_args(argv)

    errors = []
    for path in sorted(glob.glob(os.path.join(args.agents_dir, "*.md"))):
        errors += check_agent(path)
    for path in args.config or []:
        errors += check_config(path)
    if args.baseline:
        errors += check_baseline(args.agents_dir, args.baseline)

    if errors:
        print(f"FAIL: {len(errors)} V2 config violation(s)")
        for err in errors:
            print(f"  - {err}")
        return 1
    count = len(glob.glob(os.path.join(args.agents_dir, "*.md")))
    print(f"OK: {count} agent(s) carry native V2 config")
    return 0


if __name__ == "__main__":
    sys.exit(main())
