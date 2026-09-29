#!/usr/bin/env python3
"""Emit CI-only agent model overrides for the eval lane (opencode config JSON).

Why (2026-09-29): the eval lane runs on a Go flat-rate model, but a skill can
spawn a nested subagent (e.g. `designing-architecture` Step 5b consults the
`council` lens agents; `validating-ui` consults `council-ux`). Those agents are
bound to FREE-tier models, and in CI the free tier rejects calls made outside
the OpenCode client:

    AI_APICallError: OpenCode's free tier can only be used from within OpenCode

which kills the eval session ("dead session: UnknownError"). The workflows
therefore inject `OPENCODE_CONFIG_CONTENT` with the lane model for every agent
whose binding ends in `-free`. Local runs keep the free tier; only CI is
overridden.

Usage:  ci-lane-overrides.py --model opencode-go/gpt-6-luna [--repo .]
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
    return {"agent": agents}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="Lane model id to bind in CI.")
    ap.add_argument("--repo", default=os.getcwd())
    a = ap.parse_args(argv)
    print(json.dumps(overrides(a.repo, a.model), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
