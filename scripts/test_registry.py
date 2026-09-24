#!/usr/bin/env python3
"""Deterministic tests for the skill/agent registry (RM-005 AC1/AC2/AC3).

Run: python3 scripts/test_registry.py
Exit 0 = the registry exists, its entry shape is closed, and the loader's
`validate()` catches every out-of-sync defect class (orphan skill dir,
ghost entry, missing field, unresolvable boundary_ref) with a named error.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(REPO_ROOT, "registry.json")
_REG = importlib.util.spec_from_file_location("registry", os.path.join(HERE, "registry.py"))


def _entry(name, type_="skill", owner="@hierovision", maturity="L2",
           status="active", boundary_ref=None):
    e = {"name": name, "type": type_, "owner": owner, "maturity": maturity,
         "status": status}
    if boundary_ref is not None:
        e["boundary_ref"] = boundary_ref
    return e


def _make_tree(entries, skills=("demo",), agents=("demo-planner",)):
    """A throwaway repo tree: skills/<s>/SKILL.md, agents/<a>.md, registry.json."""
    d = tempfile.mkdtemp(prefix="registry-")
    os.makedirs(os.path.join(d, "skills"))
    os.makedirs(os.path.join(d, "agents"))
    for s in skills:
        os.makedirs(os.path.join(d, "skills", s))
        with open(os.path.join(d, "skills", s, "SKILL.md"), "w") as fh:
            fh.write("---\nname: %s\ndescription: test fixture skill.\n---\n# T\n" % s)
    for a in agents:
        with open(os.path.join(d, "agents", a + ".md"), "w") as fh:
            fh.write("---\nname: %s\ndescription: persona.\n---\n# P\n" % a)
    with open(os.path.join(d, "registry.json"), "w") as fh:
        json.dump(entries, fh)
    return d


def _default_entries(skills, agents):
    return {
        "version": 1,
        "skills": [
            _entry(s, "skill",
                   boundary_ref=os.path.join("skills", s, "SKILL.md"))
            for s in skills],
        "personas": [
            _entry(a, "persona", maturity="L3",
                   boundary_ref=os.path.join("agents", a + ".md"))
            for a in agents],
    }


def test_repo_registry_complete_and_valid():
    """AC1/AC2: the real registry parses, covers every skill dir + persona
    file, and every required field is present with a resolvable boundary."""
    reg = importlib.util.module_from_spec(_REG)
    _REG.loader.exec_module(reg)
    entries = reg.load()
    assert isinstance(entries, dict) and entries.get("version") == 1, entries
    all_e = entries["skills"] + entries["personas"]
    skill_dirs = sorted(os.listdir(os.path.join(REPO_ROOT, "skills")))
    persona_files = sorted(
        f[:-3] for f in os.listdir(os.path.join(REPO_ROOT, "agents"))
        if f.endswith(".md"))
    assert sorted(e["name"] for e in entries["skills"]) == skill_dirs
    assert sorted(e["name"] for e in entries["personas"]) == persona_files
    assert len(all_e) == 33, len(all_e)
    for e in all_e:
        for field in ("name", "type", "owner", "maturity", "status",
                      "boundary_ref"):
            assert e.get(field), (e.get("name"), field)
        assert e["type"] in ("skill", "persona")
        assert e["maturity"] in ("L1", "L2", "L3", "L4")
        assert e["status"] in ("active", "deferred", "deprecated")
        assert os.path.isfile(os.path.join(REPO_ROOT, e["boundary_ref"])), e
    print("PASS  registry complete: 23 skills + 10 personas, fields + boundaries valid")


def test_validate_detects_sync_defects():
    """AC3: each defect class is named — orphan, ghost, missing field,
    unresolvable boundary_ref."""
    reg_mod = importlib.util.module_from_spec(_REG)
    _REG.loader.exec_module(reg_mod)
    # orphan: a skill dir with no registry entry
    entries = _default_entries(skills=("alpha", "beta"), agents=("p1",))
    del entries["skills"][1]  # beta unregistered
    d = _make_tree(entries, skills=("alpha", "beta"), agents=("p1",))
    try:
        errors = reg_mod.validate(d)
        assert any("orphan" in e for e in errors), errors
    finally:
        shutil.rmtree(d)
    # ghost: an entry with no matching dir
    entries = _default_entries(skills=("alpha",), agents=("p1",))
    entries["skills"].append(_entry("ghost-skill", "skill",
                                    boundary_ref="skills/ghost/SKILL.md"))
    d = _make_tree(entries, skills=("alpha",), agents=("p1",))
    try:
        errors = reg_mod.validate(registry_path=os.path.join(d, "registry.json"),
                                  skills_root=os.path.join(d, "skills"),
                                  agents_root=os.path.join(d, "agents"),
                                  repo_root=d)
        assert any("ghost" in e for e in errors), errors
    finally:
        shutil.rmtree(d)
    # missing field
    entries = _default_entries(skills=("alpha",), agents=("p1",))
    del entries["skills"][0]["maturity"]
    d = _make_tree(entries, skills=("alpha",), agents=("p1",))
    try:
        errors = reg_mod.validate(registry_path=os.path.join(d, "registry.json"),
                                  skills_root=os.path.join(d, "skills"),
                                  agents_root=os.path.join(d, "agents"),
                                  repo_root=d)
        assert any("maturity" in e for e in errors), errors
    finally:
        shutil.rmtree(d)
    # unresolvable boundary_ref
    entries = _default_entries(skills=("alpha",), agents=("p1",))
    entries["skills"][0]["boundary_ref"] = "skills/alpha/NOPE.md"
    d = _make_tree(entries, skills=("alpha",), agents=("p1",))
    try:
        errors = reg_mod.validate(registry_path=os.path.join(d, "registry.json"),
                                  skills_root=os.path.join(d, "skills"),
                                  agents_root=os.path.join(d, "agents"),
                                  repo_root=d)
        assert any("boundary_ref" in e for e in errors), errors
    finally:
        shutil.rmtree(d)
    # missing registry file is a named defect, not a crash (the real error
    # path a consumer repo hits before first registration)
    d = _make_tree(_default_entries(skills=(), agents=()), skills=(), agents=())
    os.remove(os.path.join(d, "registry.json"))
    try:
        errors = reg_mod.validate(d)
        assert any("registry file missing" in e for e in errors), errors
    finally:
        shutil.rmtree(d)
    # in-sync tree validates clean
    entries = _default_entries(skills=("alpha", "beta"), agents=("p1", "p2"))
    d = _make_tree(entries, skills=("alpha", "beta"), agents=("p1", "p2"))
    try:
        errors = reg_mod.validate(registry_path=os.path.join(d, "registry.json"),
                                  skills_root=os.path.join(d, "skills"),
                                  agents_root=os.path.join(d, "agents"),
                                  repo_root=d)
        assert errors == [], errors
    finally:
        shutil.rmtree(d)
    print("PASS  registry sync defects detected: orphan/ghost/field/boundary_ref")


def test_check_cli():
    """AC1: the --check CLI exits 0 on the real repo and 1 with a defect."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "registry.py"),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    d = _make_tree(_default_entries(skills=("alpha",), agents=("p1",)),
                   skills=("alpha", "beta"), agents=("p1",))
    try:
        r2 = subprocess.run(
            [sys.executable, os.path.join(HERE, "registry.py"), "--check",
             "--repo-root", d], capture_output=True, text=True)
        assert r2.returncode == 1, r2.stdout + r2.stderr
    finally:
        shutil.rmtree(d)
    print("PASS  registry --check CLI: 0 in-sync, 1 with an orphan")


def main():
    tests = [
        test_repo_registry_complete_and_valid,
        test_validate_detects_sync_defects,
        test_check_cli,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
