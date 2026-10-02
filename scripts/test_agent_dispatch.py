#!/usr/bin/env python3
"""RED-first structural tests for the agent-teams dispatch contract.

Offline: parses persona frontmatter, the dispatch-policy doc, the dated
opencode facts, the RM-032 roadmap row, and the CI wiring. No model calls,
no network.

Plan: .opencode/plans/agent-teams-dispatch.md (ACs 1-3, 7-10).
Run: python3 scripts/test_agent_dispatch.py
"""
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)

# Composition is judgment-led (2026-10-02 user directive): orchestrators
# carry no `permission.task` allow-list.
ORCHESTRATORS = ("architect", "curator", "implementer", "council")
# Leaf personas: no dispatch authority at all (the one encoded rule).
DENY_ALL_PERSONAS = (
    "planner", "council-architecture", "council-performance",
    "council-product", "council-security", "council-ux",
)


def _norm(text):
    return re.sub(r"\s+", " ", text or "")


def _personas():
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    return [e["name"] for e in registry["personas"]]


def _frontmatter(name):
    path = os.path.join(REPO, "agents", name + ".md")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    assert raw.startswith("---"), f"{name}: no frontmatter"
    return yaml.safe_load(raw.split("---", 2)[1])


def _allowed(task):
    """(allowed_set, deny_catch_all_ok) for a `permission.task` value.

    A map must catch-all deny and then allow specific globs; a bare
    `deny` scalar denies everything (leaf).
    """
    if isinstance(task, str):
        return (set(), task == "deny")
    if not isinstance(task, dict):
        return (None, False)
    return ({k for k, v in task.items() if v == "allow" and k != "*"},
            task.get("*") == "deny")


def test_all_personas_dispatchable():
    """AC1: every persona in registry.json carries `mode: all`."""
    for name in _personas():
        fm = _frontmatter(name)
        assert fm.get("mode") == "all", f"{name}: mode={fm.get('mode')!r}, want all"


def test_orchestrators_carry_no_task_allowlist():
    """AC2: composition is judgment-led — no orchestrator has a task
    allow-list to work around (2026-10-02 user directive)."""
    for name in ORCHESTRATORS:
        fm = _frontmatter(name)
        task = (fm.get("permission") or {}).get("task")
        assert task is None, f"{name}: unexpected permission.task={task!r}"


def test_leaf_dispatch_denied():
    """AC2: planner and every council-* lens deny `task` (the one encoded
    rule)."""
    for name in DENY_ALL_PERSONAS:
        fm = _frontmatter(name)
        task = (fm.get("permission") or {}).get("task")
        assert task is not None, f"{name}: leaf needs task deny"
        allowed, denied = _allowed(task)
        assert denied and allowed == set(), (name, task)


def test_agent_teams_doc_contract():
    """AC3+AC7: topology, bounds, lane policy, relay paths, citations."""
    path = os.path.join(REPO, "reference", "agent-teams.md")
    assert os.path.isfile(path), "reference/agent-teams.md missing (AC3)"
    with open(path, encoding="utf-8") as fh:
        text = _norm(fh.read()).lower()
    for heading in ("## Topology and bounds", "## Composition",
                    "## Lane policy", "## Question relay", "## Attribution",
                    "## Integration"):
        assert heading.lower() in text, f"missing heading: {heading}"
    for phrase in ("orchestrator", "worker", "depth ≤ 2", "fan-out ≤ 6",
                   "judgment-led", "nested-capable", "run-vehicle",
                   "free-bound", "task_id", "description", "--session",
                   "resume", "kind=agent", "log_run", "rm-022", "rm-023",
                   "rm-024", "rm-025", "reference/subagent-supervision.md",
                   "reference/delegated-result-contract.md"):
        assert phrase in text, f"missing phrase: {phrase}"


def test_opencode_integration_dated_block():
    """AC8: dated mode / task / model / session-store facts."""
    path = os.path.join(REPO, "reference", "opencode-integration.md")
    with open(path, encoding="utf-8") as fh:
        text = _norm(fh.read()).lower()
    assert "2026-10-02" in text, "dated 2026-10-02 block missing"
    for phrase in ("mode", "permission.task", "frontmatter", "model",
                   "json blob", "nested", "free tier"):
        assert phrase in text, f"missing phrase: {phrase}"


def test_roadmap_rm032_row():
    """AC9: docs/ROADMAP.md carries the RM-032 row at priority 1."""
    path = os.path.join(REPO, "docs", "ROADMAP.md")
    with open(path, encoding="utf-8") as fh:
        row = next((l for l in fh if l.startswith("| RM-032 ")), None)
    assert row is not None, "RM-032 row missing"
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert cells[3] == "1", f"RM-032 priority is {cells[3]!r}, want '1'"


def test_ci_wiring():
    """AC10: both new suites run in the quality-gates job."""
    path = os.path.join(REPO, ".github", "workflows", "ci.yml")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for cmd in ("python3 scripts/test_agent_dispatch.py",
                "python3 scripts/test_dispatch_agent.py"):
        assert cmd in text, f"ci.yml missing: {cmd}"


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
