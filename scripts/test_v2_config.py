#!/usr/bin/env python3
"""Fixtures proving the two offline V2 linters FAIL CLOSED.

  * `check_v2_config.py` accepts a native V2 agent and rejects a V1 fixture
    (`name:`, `permission:`, `bash`, `write`, `task`), and the `--baseline`
    comparison rejects an added shell allow.
  * `check_v2_surfaces.py` rejects each V1 token in an active file and ignores
    the historical allowlist (ADRs/plans/tests).

Run: python3 scripts/test_v2_config.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)

V2_AGENT = """---
description: Native V2 agent
model: opencode-go/deepseek-v4.1-flash
mode: all
permissions:
  - action: shell
    resource: "*"
    effect: allow
  - action: edit
    resource: "*"
    effect: allow
  - action: subagent
    resource: "*"
    effect: allow
  - action: execute
    resource: "*"
    effect: deny
---
Body.
"""

V1_AGENT = """---
name: legacy
description: Legacy V1 agent
model: opencode-go/deepseek-v4.1-flash
permission:
  bash:
    "*": deny
  write: deny
  task: deny
---
Body.
"""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(dirpath, name, text):
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_v2_config_accepts_native():
    mod = _load("check_v2_config", os.path.join(HERE, "check_v2_config.py"))
    d = tempfile.mkdtemp(prefix="v2cfg-")
    try:
        _write(d, "architect.md", V2_AGENT)
        errors = mod.check_agent(os.path.join(d, "architect.md"))
        assert errors == [], errors
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_v2_config_rejects_v1_fixture():
    mod = _load("check_v2_config", os.path.join(HERE, "check_v2_config.py"))
    d = tempfile.mkdtemp(prefix="v2cfg-")
    try:
        path = _write(d, "legacy.md", V1_AGENT)
        errors = mod.check_agent(path)
        text = "\n".join(errors)
        for token in ("name", "permission", "bash", "write", "task",
                      "permissions"):
            assert token in text, (token, errors)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_v2_config_rejects_added_allow():
    """AC9: an added shell allow against the V1 baseline fails."""
    mod = _load("check_v2_config", os.path.join(HERE, "check_v2_config.py"))
    d = tempfile.mkdtemp(prefix="v2base-")
    try:
        _write(d, "planner.md", V2_AGENT.replace(
            'resource: "*"\n    effect: allow',
            'resource: "rm -rf *"\n    effect: allow'))
        # Fabricate the baseline through the same parser (no git dependency).
        original = mod.v1_shell_allows
        mod.v1_shell_allows = lambda path, ref: {"ls", "cat *"}
        try:
            errors = mod.check_baseline(d, "main")
        finally:
            mod.v1_shell_allows = original
        assert any("added shell allow" in e for e in errors), errors
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_surfaces_rejects_each_v1_token():
    mod = _load("check_v2_surfaces", os.path.join(HERE, "check_v2_surfaces.py"))
    d = tempfile.mkdtemp(prefix="v2surf-")
    try:
        os.makedirs(os.path.join(d, "scripts"))
        _write(d, "scripts/live.sh",
               "opencode run --dir . hi\n"
               "curl --attach http://x\n"
               "opencode --log-level debug\n"
               "opencode --print-logs\n"
               "GET /session/status\n"
               "npm i opencode-ai@1.19.4\n"
               "npm i @opencode-ai/plugin\n"
               "subagent_type: x\n"
               "task_id: y\n"
               "permission.external_directory\n")
        hits = mod.scan(d)
        labels = " ".join(hits)
        for label in ("--dir", "--attach", "--log-level", "--print-logs",
                      "/session/status", "opencode-ai@", "@opencode-ai/plugin",
                      "subagent_type", "task_id",
                      "permission.external_directory"):
            assert label in labels, (label, hits)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_surfaces_allowlists_history_and_tests():
    mod = _load("check_v2_surfaces", os.path.join(HERE, "check_v2_surfaces.py"))
    d = tempfile.mkdtemp(prefix="v2surf-")
    try:
        os.makedirs(os.path.join(d, "docs", "ADRs"))
        os.makedirs(os.path.join(d, "scripts"))
        _write(d, "docs/ADRs/ADR-0001.md", "opencode run --dir was V1\n")
        _write(d, "scripts/test_old.py", "assert '--attach' not in src\n")
        assert mod.scan(d) == [], mod.scan(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_repo_agents_are_native():
    proc = subprocess.run([sys.executable, os.path.join(HERE,
                                                         "check_v2_config.py")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
