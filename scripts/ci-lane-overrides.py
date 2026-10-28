#!/usr/bin/env python3
"""Emit CI-only agent model overrides for the eval lane (opencode config JSON).

Why (2026-09-29): the eval lane runs on a Go flat-rate model, but a skill can
spawn a nested subagent (e.g. `designing-architecture` Step 5b consults the
`council` lens agents; `validating-ui` consults `council-ux`). A nested
FREE-tier-bound agent is rejected in CI:

    AI_APICallError: OpenCode's free tier can only be used from within OpenCode

which kills the eval session ("dead session: UnknownError"). The workflows
therefore inject `OPENCODE_CONFIG_CONTENT` with the lane model for every agent
whose binding ends in `-free`.

Since the Go-first flip (2026-10-03, plan go-first-model-bindings) every
framework persona is Go-bound, so for THIS repo the output is an empty
`agent` map — the loop stays as a forward-compatible guard for consumer
repos whose installed wrappers are still free-bound. Local runs keep the
configured tier; only CI is overridden.

Usage:  ci-lane-overrides.py --model opencode-go/deepseek-v4.1-flash [--repo .]
Output: one-line JSON for OPENCODE_CONFIG_CONTENT.
"""
import argparse
import glob
import json
import os
import re


def overrides(repo, lane_model):
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
    # V2 config uses `agents` + ordered `permissions` rules. The allow roots
    # are the ephemeral runner scratch and the installed config tree (skills
    # resolve from there). Unmatched paths keep V2's default.
    permissions = [
        {"action": "external_directory", "resource": "/tmp/**",
         "effect": "allow"},
        {"action": "external_directory",
         "resource": os.path.expanduser("~/.config/opencode") + "/**",
         "effect": "allow"},
    ]
    return {"agents": agents, "permissions": permissions}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="Lane model id to bind in CI.")
    ap.add_argument("--repo", default=os.getcwd())
    a = ap.parse_args(argv)
    print(json.dumps(overrides(a.repo, a.model), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
