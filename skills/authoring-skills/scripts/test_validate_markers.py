#!/usr/bin/env python3
"""Marker-rule tests for validate_skill.py (RM-003 pass 4 / AC12).

Run: python3 skills/authoring-skills/scripts/test_validate_markers.py
Exit 0 = the two-tier marker rules are enforced:
  - at most one `"default": true` per evals.json
  - `"core": true` only on the default or first eval in file order
  - the six core skills must carry `"core": true`
  - both markers must be booleans
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "validate_skill", os.path.join(HERE, "validate_skill.py"))
validate_skill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_skill)

FRONTMATTER = (
    "---\nname: {name}\ndescription: marker validation fixture skill\n---\n\nbody\n"
)


def _make_skill(name, evals):
    root = tempfile.mkdtemp(prefix="marker-skill-")
    d = os.path.join(root, name)
    os.makedirs(os.path.join(d, "evals"))
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write(FRONTMATTER.format(name=name))
    with open(os.path.join(d, "evals", "evals.json"), "w", encoding="utf-8") as fh:
        json.dump({"evals": evals}, fh)
    return d


def _ev(eid, **markers):
    base = {"id": eid, "prompt": "p", "expected_behavior": ["x"]}
    base.update(markers)
    # Pass 5 Layer-1 rule: a marked eval must also carry a typed `expect`
    # block, so every marked fixture in this suite asserts the typed shape.
    if markers:
        base["expect"] = {"text": ["x"]}
    return base


def test_valid_markers_pass():
    d = _make_skill("acme", [_ev(1, default=True, core=True), _ev(2)])
    try:
        errors, _ = validate_skill.validate(d)
        assert errors == [], errors
    finally:
        shutil.rmtree(d)


def test_duplicate_default_rejected():
    d = _make_skill("acme", [_ev(1, default=True), _ev(2, default=True)])
    try:
        errors, _ = validate_skill.validate(d)
        assert any("default" in e for e in errors), errors
    finally:
        shutil.rmtree(d)


def test_core_on_non_default_non_first_rejected():
    d = _make_skill("acme", [_ev(1), _ev(2, core=True)])
    try:
        errors, _ = validate_skill.validate(d)
        assert any("core" in e for e in errors), errors
    finally:
        shutil.rmtree(d)


def test_core_skill_must_carry_core():
    d = _make_skill("writing-unit-tests", [_ev(1), _ev(2)])
    try:
        errors, _ = validate_skill.validate(d)
        assert any("core" in e for e in errors), errors
    finally:
        shutil.rmtree(d)


def test_non_boolean_marker_rejected():
    d = _make_skill("acme", [{"id": 1, "prompt": "p",
                              "expected_behavior": ["x"], "default": "yes"}])
    try:
        errors, _ = validate_skill.validate(d)
        assert any("default" in e for e in errors), errors
    finally:
        shutil.rmtree(d)


def test_all_exit_code_honors_registry_errors():
    """Regression (2026-09-28): `--all` must exit 1 on registry errors.

    A `failed = False` reset sitting before the per-skill loop erased the
    registry failure, so `--all` printed `FAIL  registry` but exited 0.
    The fake registry module isolates the registry path; `validate` is
    stubbed so only registry errors can influence the exit code.
    """
    import contextlib
    import io
    import types

    fake = types.ModuleType("registry")
    fake.validate = lambda: ["orphan: skills/zzz/ has no registry entry"]
    fake.load = lambda: {"skills": [], "personas": []}
    had = sys.modules.get("registry")
    sys.modules["registry"] = fake
    old_validate = validate_skill.validate
    validate_skill.validate = lambda d: ([], [])
    old_argv = sys.argv
    sys.argv = ["validate_skill.py", "--all"]
    buf = io.StringIO()
    code = None
    try:
        with contextlib.redirect_stdout(buf):
            try:
                validate_skill.main()
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = old_argv
        validate_skill.validate = old_validate
        if had is None:
            sys.modules.pop("registry", None)
        else:
            sys.modules["registry"] = had
    assert code == 1, f"expected exit 1 on registry errors, got {code!r}"
    assert "FAIL  registry" in buf.getvalue(), buf.getvalue()


def main():
    tests = [
        test_valid_markers_pass,
        test_duplicate_default_rejected,
        test_core_on_non_default_non_first_rejected,
        test_core_skill_must_carry_core,
        test_non_boolean_marker_rejected,
        test_all_exit_code_honors_registry_errors,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
