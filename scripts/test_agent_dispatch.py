#!/usr/bin/env python3
"""RED-first structural tests for the agent-teams dispatch contract.

Offline: parses persona frontmatter, the dispatch-policy doc, the dated
opencode facts, the RM-032 roadmap row, and the CI wiring. No model calls,
no network.

Plans: .opencode/plans/agent-teams-dispatch.md (ACs 1-3, 7-10) and
.opencode/plans/agent-persona-expansion.md (ACs 1-5, 8).
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
# The 7-persona expansion (plan agent-persona-expansion): role → default
# binding per the role rows in reference/model-routing.md.
EXPECTED_PERSONAS = {
    "reviewer": "opencode/nemotron-3-ultra-free",
    "test-writer": "opencode/nemotron-3-ultra-free",
    "debugger": "opencode/nemotron-3-ultra-free",
    "vision-critic-fast": "opencode-go/minimax-m3",
    "vision-critic-final": "deepseek/deepseek-flash",
    "skill-author": "opencode/nemotron-3-ultra-free",
    "skill-reviewer": "opencode/nemotron-3-ultra-free",
}
# Single-shot roles: no dispatch authority at all (the one encoded rule).
NEW_LEAVES = ("reviewer", "skill-reviewer",
              "vision-critic-fast", "vision-critic-final")
# Loop workers: judgment-led, no task allow-list.
NEW_WORKERS = ("test-writer", "debugger", "skill-author")
DENY_ALL_PERSONAS = (
    "planner", "council-architecture", "council-performance",
    "council-product", "council-security", "council-ux",
) + NEW_LEAVES


def _norm(text):
    return re.sub(r"\s+", " ", text or "")


def _personas():
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    return [e["name"] for e in registry["personas"]]


def _frontmatter(name):
    path = os.path.join(REPO, "agents", name + ".md")
    assert os.path.isfile(path), f"agents/{name}.md missing"
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


def test_new_personas_files_and_bindings():
    """AC1: the seven files exist with mode all and the routing-role default
    binding."""
    for name, model in EXPECTED_PERSONAS.items():
        fm = _frontmatter(name)
        assert fm.get("name") == name, (name, fm.get("name"))
        assert fm.get("mode") == "all", (name, fm.get("mode"))
        assert fm.get("model") == model, (name, fm.get("model"), model)


# Owning-skill pointer per new persona (ADR-0006: a persona is a thin
# binding that points at the skill that owns the process).
OWNING_SKILLS = {
    "reviewer": ("reviewing-code",),
    "test-writer": ("writing-unit-tests", "writing-integration-tests",
                    "writing-e2e-tests"),
    "debugger": ("debugging-test-failures",),
    "vision-critic-fast": ("correcting-ui", "capturing-ui-evidence",
                           "validating-ui"),
    "vision-critic-final": ("validating-ui", "capturing-ui-evidence"),
    "skill-author": ("authoring-skills", "sourcing-external-skills"),
    "skill-reviewer": ("validating-against-official-docs",),
}


def test_new_personas_cite_owning_skills():
    """AC1 (thin binding): each persona points at the skill(s) owning its
    process — the pointer is the binding, the process stays in the skill."""
    for name, skills in OWNING_SKILLS.items():
        path = os.path.join(REPO, "agents", name + ".md")
        assert os.path.isfile(path), f"agents/{name}.md missing"
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        for skill in skills:
            assert skill in body, f"{name}: missing owning-skill pointer {skill!r}"


def test_new_personas_registered_l1():
    """AC2: registry entries exist at L1 with a resolvable boundary."""
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    by_name = {e["name"]: e for e in registry["personas"]}
    for name in EXPECTED_PERSONAS:
        entry = by_name.get(name)
        assert entry is not None, f"{name}: no registry persona entry"
        assert entry.get("type") == "persona", (name, entry)
        assert entry.get("maturity") == "L1", (name, entry)
        assert entry.get("status") == "active", (name, entry)
        assert entry.get("boundary_ref") == f"agents/{name}.md", (name, entry)


def test_new_workers_judgment_led():
    """AC3: the three loop workers carry no task allow-list."""
    for name in NEW_WORKERS:
        fm = _frontmatter(name)
        task = (fm.get("permission") or {}).get("task")
        assert task is None, f"{name}: unexpected permission.task={task!r}"


def test_new_leaf_permission_posture():
    """AC3: vision critics deny edit/write/bash; reviewers deny edit/write
    and carry a read-only bash map with a catch-all."""
    for name in ("vision-critic-fast", "vision-critic-final"):
        perm = _frontmatter(name).get("permission") or {}
        for key in ("edit", "write", "bash"):
            assert perm.get(key) == "deny", (name, key, perm.get(key))
    for name in ("reviewer", "skill-reviewer"):
        perm = _frontmatter(name).get("permission") or {}
        assert perm.get("edit") == "deny", (name, perm)
        assert perm.get("write") == "deny", (name, perm)
        bash = perm.get("bash")
        assert isinstance(bash, dict), (name, bash)
        assert bash.get("*") == "ask", (name, bash)
        assert bash.get("ls *") == "allow", (name, bash)
        assert bash.get("git commit*") == "deny", (name, bash)


def test_concepts_role_vocabulary():
    """AC5: docs/CONCEPTS.md names the expanded cast and carries no model
    IDs (roles-not-IDs)."""
    with open(os.path.join(REPO, "docs", "CONCEPTS.md"), encoding="utf-8") as fh:
        text = _norm(fh.read())
    for name in EXPECTED_PERSONAS:
        assert name in text, f"docs/CONCEPTS.md missing persona {name!r}"
    for token in ("opencode-go/", "deepseek/", "nemotron", "minimax",
                  "glm-", "kimi-"):
        assert token not in text, f"docs/CONCEPTS.md carries a model ID: {token!r}"


def test_roadmap_rm033_row():
    """AC8: docs/ROADMAP.md carries the RM-033 row."""
    path = os.path.join(REPO, "docs", "ROADMAP.md")
    with open(path, encoding="utf-8") as fh:
        row = next((l for l in fh if l.startswith("| RM-033 ")), None)
    assert row is not None, "RM-033 row missing"
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert cells[3] in ("1", "2"), f"RM-033 priority is {cells[3]!r}"


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
                   "reference/delegated-result-contract.md",
                   # the expanded cast (AC4: leaf roster + composition examples)
                   "reviewer", "test-writer", "debugger", "skill-author",
                   "skill-reviewer", "vision-critic-fast",
                   "vision-critic-final"):
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
