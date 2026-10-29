#!/usr/bin/env python3
"""Offline linter for active V1-only OpenCode surfaces.

Fails on a live surface that still emits a V1 flag/endpoint/package/tool name:

  `opencode run --dir`, `--attach`, `--log-level`, `--print-logs`,
  `/session/status`, `opencode-ai@`, `@opencode-ai/plugin`, `subagent_type`,
  `task_id`, `permission.external_directory`.

A fixed allowlist keeps historical records and test fixtures out of the net:
`docs/ADRs/`, `docs/ROADMAP.md`, `docs/roadmap-detail/`, `.opencode/plans/`,
the linter itself, and test files (their job is to assert absence). The
reference page is NOT allowlisted — it must be V2-only.

Exit 0 clean, 1 violation.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)

PATTERNS = (
    (r"opencode\s+run\s+[^\n]*--dir", "opencode run --dir"),
    (r"--attach\b", "--attach"),
    (r"--log-level\b", "--log-level"),
    (r"--print-logs\b", "--print-logs"),
    (r"/session/status\b", "/session/status"),
    (r"opencode-ai@", "opencode-ai@"),
    (r"@opencode-ai/plugin", "@opencode-ai/plugin"),
    (r"subagent_type", "subagent_type"),
    (r"\btask_id\b", "task_id"),
    (r"permission\.external_directory", "permission.external_directory"),
)
SCAN_DIRS = ("agents", "scripts", "skills", "reference", "docs",
             ".github", ".opencode", "plugins")
SCAN_FILES = ("README.md", "install.sh", "AGENTS.md")
ALLOW_PREFIXES = (
    ".opencode/plans/",
    "docs/ADRs/",
    "docs/roadmap-detail/",
    ".scratch/",
    "scripts/test_",
    "scripts/check_v2_surfaces.py",
    "scripts/opencode_v2_consumer.py",
    "skills/authoring-skills/scripts/test_runner.py",
    "skills/authoring-skills/evals/fixtures/",
    "skills/*/evals/fixtures/",
    ".opencode/package.json",
    ".opencode/package-lock.json",
)
ALLOW_FILES = {"docs/ROADMAP.md"}


def allowed(rel):
    if rel in ALLOW_FILES:
        return True
    for prefix in ALLOW_PREFIXES:
        if prefix.endswith("*"):
            if rel.startswith(prefix[:-1]):
                return True
        elif rel.startswith(prefix):
            return True
    return False


def iter_files(root):
    for name in SCAN_FILES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            yield os.path.relpath(path, root)
    for sub in SCAN_DIRS:
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("node_modules", "__pycache__", ".git")]
            for name in filenames:
                if name.endswith((".pyc", ".png", ".jpg", ".gz", ".db")):
                    continue
                yield os.path.relpath(os.path.join(dirpath, name), root)


def scan(root):
    hits = []
    for rel in iter_files(root):
        if allowed(rel.replace(os.sep, "/")):
            continue
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for pattern, label in PATTERNS:
                if re.search(pattern, line):
                    hits.append(f"{rel}:{lineno}: {label}")
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description="V1 surface linter.")
    ap.add_argument("--root", default=REPO)
    args = ap.parse_args(argv)
    hits = scan(args.root)
    if hits:
        print(f"FAIL: {len(hits)} V1-only surface(s)")
        for hit in hits:
            print(f"  - {hit}")
        return 1
    print("OK: no active V1-only OpenCode surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
