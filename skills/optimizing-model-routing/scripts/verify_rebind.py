#!/usr/bin/env python3
"""Verify that a model-rebind pass landed correctly.

Reads an expectation JSON of the shape:

    {
      "bindings":  {"agents/<file>": "<full model id>", ...},
      "forbidden": ["<substring>", ...]
    }

and checks the target repo:

1. every listed agent file exists and its `model:` frontmatter line
   equals the expected id exactly;
2. no forbidden substring (excluded families, removed catalog ids)
   appears anywhere in any agents/*.md file;
3. reference/model-routing.md gained a dated
   `### Routing update - YYYY-MM-DD` section (revise-don't-clobber
   marker; the fixture must not contain one before the pass).

Exit 0 = all checks pass. Exit 1 = one or more failures, each printed.
The verifier is designed to fail on an untouched stale fixture (wrong
bindings, forbidden id present, no update marker) — a green run means
the pass actually landed.

Usage:
  python3 verify_rebind.py --repo <path-to-repo> --expect <expect.json>
"""

import argparse
import glob
import json
import os
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="repo root to verify")
    parser.add_argument("--expect", required=True, help="expectation JSON path")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    with open(args.expect, "r", encoding="utf-8") as fh:
        expect = json.load(fh)
    bindings = expect.get("bindings", {})
    forbidden = expect.get("forbidden", [])

    errors = []

    # 1. agent model lines match the expected bindings.
    for rel, model in sorted(bindings.items()):
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            errors.append(f"{rel}: file missing")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(r"^model:\s*(\S+)\s*$", text, re.MULTILINE)
        if not match:
            errors.append(f"{rel}: no model: line in frontmatter")
        elif match.group(1) != model:
            errors.append(
                f"{rel}: model is {match.group(1)}, expected {model}"
            )

    # 2. forbidden substrings appear in no agent file.
    agents_dir = os.path.join(repo, "agents")
    for path in sorted(glob.glob(os.path.join(agents_dir, "*.md"))):
        rel = os.path.relpath(path, repo)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for needle in forbidden:
            if needle in text:
                errors.append(
                    f"{rel}: contains forbidden id '{needle}' "
                    "(excluded family or removed catalog id)"
                )

    # 3. model-routing.md gained a dated routing-update marker.
    routing = os.path.join(repo, "reference", "model-routing.md")
    if not os.path.isfile(routing):
        errors.append("reference/model-routing.md: file missing")
    else:
        with open(routing, "r", encoding="utf-8") as fh:
            routing_text = fh.read()
        if not re.search(
            r"### Routing update [—-] \d{4}-\d{2}-\d{2}", routing_text
        ):
            errors.append(
                "reference/model-routing.md: no dated "
                "'### Routing update — YYYY-MM-DD' section appended"
            )

    if errors:
        print(f"FAIL: {len(errors)} problem(s) in {repo}")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {len(bindings)} agent binding(s), "
          f"{len(forbidden)} forbidden id(s), update marker verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
