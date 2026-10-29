#!/usr/bin/env python3
"""Emit CI-only agent model overrides for the eval lane (opencode config JSON).

Why (2026-09-29): the eval lane runs on a Go flat-rate model, but a skill can
spawn a nested subagent (e.g. `designing-architecture` Step 5b consults the
`council` lens agents; `validating-ui` consults `council-ux`). A nested
FREE-tier-bound agent is rejected in CI:

    AI_APICallError: OpenCode's free tier can only be used from within OpenCode

which kills the eval session ("dead session: UnknownError"). The workflows
therefore generate an isolated XDG_CONFIG_HOME root with the lane model for
every agent whose binding ends in `-free`.

Since the Go-first flip (2026-10-03, plan go-first-model-bindings) every
framework persona is Go-bound, so for THIS repo the output is an empty
`agent` map — the loop stays as a forward-compatible guard for consumer
repos whose installed wrappers are still free-bound. Local runs keep the
configured tier; only CI is overridden.

Usage:  ci-lane-overrides.py --model opencode-go/deepseek-v4.1-flash [--repo .]
Output: one-line JSON of the override document.
        ci-lane-overrides.py --model ... --xdg-root DIR [--allow-dir DIR]
Output: writes DIR/opencode/opencode.jsonc (deny-first grants + agent/skill
        links) and prints the path; export XDG_CONFIG_HOME=DIR.
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import shutil
import sys

import opencode_v2 as v2


def overrides(repo, lane_model, allow_dirs=None):
    agents = {}
    for path in sorted(glob.glob(os.path.join(repo, "agents", "*.md"))):
        raw = open(path, encoding="utf-8").read()
        fm = raw.split("---", 2)[1] if raw.startswith("---") else ""
        m = re.search(r"^model:\s*(\S+)\s*$", fm, re.MULTILINE)
        if not m:
            continue
        bound = m.group(1)
        if bound.endswith("-free"):
            agents[os.path.basename(path)[:-3]] = {"model": lane_model}
    # V2 config uses `agents` + ordered `permissions` rules. Deny-first is
    # mandatory: V2's external_directory default is allow, so a catch-all deny
    # must precede every explicit root (last matching rule wins).
    permissions = [{"action": "external_directory", "resource": "*",
                    "effect": "deny"}]
    roots = ["/tmp", os.path.expanduser("~/.config/opencode")]
    roots += [os.environ.get("RUNNER_TEMP")]
    roots += list(allow_dirs or [])
    seen = set()
    for root in roots:
        if not root:
            continue
        root = os.path.abspath(os.path.expanduser(root))
        if root in seen:
            continue
        seen.add(root)
        permissions.append({"action": "external_directory",
                            "resource": os.path.join(root, "**"),
                            "effect": "allow"})
    return {"agents": agents, "permissions": permissions}


def decide(rules, path):
    """Last-match external_directory decision (the V2 rule contract)."""
    result = "allow"  # V2's default when no rule matches
    for rule in rules:
        if rule.get("action") != "external_directory":
            continue
        if fnmatch.fnmatch(path, rule.get("resource") or ""):
            result = rule.get("effect", result)
    return result


def write_config(root, repo, lane_model, allow_dirs=None):
    """Write the proven generated XDG_CONFIG_HOME root (agents + skills)."""
    root = os.path.abspath(root)
    config_dir = os.path.join(root, "opencode")
    if os.path.isdir(config_dir):
        shutil.rmtree(config_dir)
    agents_dir = os.path.join(repo, "agents")
    skills_dir = os.path.join(repo, "skills")
    cfg = overrides(repo, lane_model, allow_dirs=list(allow_dirs or []) +
                    [root])
    v2.write_temp_config(root, cfg, agents_dir=agents_dir,
                         skills_dir=skills_dir)
    return os.path.join(config_dir, "opencode.jsonc")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="Lane model id to bind in CI.")
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--xdg-root", default=None,
                    help="Write the generated V2 config root here; the caller "
                         "exports XDG_CONFIG_HOME to it (no OPENCODE_CONFIG_CONTENT).")
    ap.add_argument("--allow-dir", action="append", default=None,
                    help="Extra external_directory allow root (repeatable).")
    a = ap.parse_args(argv)
    if a.xdg_root:
        path = write_config(a.xdg_root, a.repo, a.model, a.allow_dir)
        print(json.dumps({"config": path}, separators=(",", ":")))
        return 0
    print(json.dumps(overrides(a.repo, a.model, allow_dirs=a.allow_dir),
                     separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
