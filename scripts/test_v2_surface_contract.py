#!/usr/bin/env python3
"""Contract tests for the foreground-delegation guidance net (RM-069 AC12).

`check_v2_surfaces.py` gained four delegation patterns. These tests prove the
net catches each prohibited form, allows the equivalent permitted wording,
allowlists historical records, and passes on the real tree (i.e. the sweep is
actually done, not merely asserted).

Run: python3 scripts/test_v2_surface_contract.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import check_v2_surfaces as linter  # noqa: E402

FAILS = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} {name}"
          + ("" if condition else f": {detail}"))
    if not condition:
        FAILS.append(name)


def _scan_tree(files):
    root = tempfile.mkdtemp(prefix="surface-contract-")
    try:
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        return linter.scan(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    prohibited = {
        "foreground task": "Run the task in the foreground task lane.",
        "foreground subagent": "A foreground subagent blocks the conversation.",
        "block on child": "Then block on the child until the result lands.",
        "wait for subagent": "Wait for the subagent to finish before replying.",
        "fire and forget": "Delegation here is fire-and-forget.",
        "fire-and-forget": "Use a fire-and-forget dispatch for speed.",
    }
    for name, text in prohibited.items():
        hits = _scan_tree({"skills/x/SKILL.md": text})
        check(f"catches {name}", len(hits) == 1, hits)

    permitted = [
        "Return a background handle and report progress from the event stream.",
        "This slice foregrounds the two load-bearing properties.",
        "The background child is observable; the owner never waits manually.",
        "Steer the running delegate on the same session id.",
    ]
    for text in permitted:
        hits = _scan_tree({"skills/x/SKILL.md": text})
        check(f"allows: {text[:40]}", hits == [], hits)

    historical = _scan_tree({"docs/ADRs/ADR-9999-old.md":
                             "A foreground Task was the old guidance."})
    check("historical records stay allowlisted", historical == [], historical)

    real = linter.scan(REPO)
    check("the active tree has no foreground-delegation guidance", real == [],
          real)

    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
