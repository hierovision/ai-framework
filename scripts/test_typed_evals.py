#!/usr/bin/env python3
"""Deterministic tests for the typed-eval Layer-1 enforcement (RM-003 pass 5,
AC17/AC19).

Run: python3 scripts/test_typed_evals.py
Exit 0 = the closed `expect` schema is enforced, a NEW or CHANGED eval without
`expect` is rejected (compare-vs-base semantics), an eval carrying a
`default`/`core` marker without `expect` is rejected by both validators, and a
missing base ref degrades honestly (skip by default; hard error with
`--require-base`).

No model, no network: the git comparisons run against throwaway repos.
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
SKILLS_ROOT = os.path.join(REPO_ROOT, "skills")
VALIDATE_SKILL = os.path.join(
    SKILLS_ROOT, "authoring-skills", "scripts", "validate_skill.py")
VERIFY_MJS = os.path.join(HERE, "verify.mjs")
CHECK_TYPED = os.path.join(HERE, "check_typed_evals.py")

_SPEC = importlib.util.spec_from_file_location("check_typed_evals", CHECK_TYPED)
cke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cke)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _git(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args),
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout


def _make_repo():
    """A throwaway git repo with one skill manifest at a base commit."""
    repo = tempfile.mkdtemp(prefix="typed-evals-")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    skills = os.path.join(repo, "skills")
    manifest = os.path.join(skills, "demo-skill", "evals", "evals.json")
    _write_json(manifest, {
        "skill_name": "demo-skill",
        "evals": [
            {"id": 1, "prompt": "legacy prompt",
             "expected_behavior": ["does a thing"]},
            {"id": 2, "prompt": "typed prompt",
             "expect": {"text": ["does a typed thing"]}},
        ],
    })
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo, skills, manifest


def test_expect_schema_closed_shape():
    ok = {"action": [{"tool": "write", "args": {"filePath": "*SKILL.md"}}],
          "artifact": [{"path": "SKILL.md", "phrases": ["name:"]}],
          "text": ["open question"]}
    assert cke.validate_expect(ok) == [], cke.validate_expect(ok)

    # unknown top-level key is rejected
    assert cke.validate_expect({"text": ["x"], "exit_code": [0]}), "unknown key must fail"
    # empty block is rejected
    assert cke.validate_expect({}), "empty expect must fail"
    # action entry needs a tool and rejects unknown keys
    assert cke.validate_expect({"action": [{"args": {"filePath": "x"}}]})
    assert cke.validate_expect({"action": [{"tool": "write", "nope": 1}]})
    # artifact needs path + non-empty phrases
    assert cke.validate_expect({"artifact": [{"path": "x"}]})
    assert cke.validate_expect({"artifact": [{"path": "x", "phrases": []}]})
    # text must be non-empty strings
    assert cke.validate_expect({"text": [""]})
    assert cke.validate_expect({"text": ["ok"]}) == []
    print("PASS  expect schema: closed shape rejects unknown/empty/malformed")


def test_changed_and_new_eval_require_expect():
    repo, skills, manifest = _make_repo()
    try:
        # Eval 1: CHANGED but still legacy -> must be rejected.
        # Eval 2: unchanged typed -> must NOT be flagged.
        # Eval 3: NEW legacy -> must be rejected.
        # Eval 4: NEW typed -> must NOT be flagged.
        # Eval 5: CHANGED legacy that now gains expect -> must NOT be flagged.
        _write_json(manifest, {
            "skill_name": "demo-skill",
            "evals": [
                {"id": 1, "prompt": "legacy prompt CHANGED",
                 "expected_behavior": ["does a thing"]},
                {"id": 2, "prompt": "typed prompt",
                 "expect": {"text": ["does a typed thing"]}},
                {"id": 3, "prompt": "new legacy",
                 "expected_behavior": ["new thing"]},
                {"id": 4, "prompt": "new typed",
                 "expect": {"text": ["new typed thing"]}},
                {"id": 5, "prompt": "legacy prompt",
                 "expected_behavior": ["does a thing"],
                 "expect": {"artifact": [{"path": "out.md", "phrases": ["x"]}]}},
            ],
        })
        errors, warnings = cke.collect_errors(
            "HEAD", skills_root=skills, repo_root=repo)
        joined = "\n".join(errors)
        assert "id=1" in joined, ("changed legacy eval must be rejected", errors)
        assert "id=3" in joined, ("new legacy eval must be rejected", errors)
        assert "id=2" not in joined, ("unchanged typed eval must pass", errors)
        assert "id=4" not in joined, ("new typed eval must pass", errors)
        assert "id=5" not in joined, ("changed eval gaining expect must pass", errors)
        print("PASS  --base: changed/new evals need expect; typed and unchanged pass")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_base_semantics_unchanged_legacy_is_not_flagged():
    repo, skills, _manifest = _make_repo()
    try:
        # No working-tree change at all -> the legacy eval 1 is unchanged and
        # must NOT be flagged (the rule is new-or-changed, not all evals).
        errors, _warnings = cke.collect_errors(
            "HEAD", skills_root=skills, repo_root=repo)
        assert errors == [], errors
        print("PASS  --base: an untouched legacy eval is not flagged")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_unresolvable_base_degrades_honestly():
    repo, skills, _manifest = _make_repo()
    try:
        errors, warnings = cke.collect_errors(
            "deadbeefdeadbeef", skills_root=skills, repo_root=repo)
        assert errors == [], errors
        assert any("not resolvable" in w for w in warnings), warnings
        errors2, _ = cke.collect_errors(
            "deadbeefdeadbeef", skills_root=skills, repo_root=repo,
            require_base=True)
        assert errors2 and "not resolvable" in errors2[0], errors2
        print("PASS  --base: missing ref skips by default, errors with --require-base")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_check_typed_cli_exit_codes():
    repo, _skills, _manifest = _make_repo()
    try:
        r = subprocess.run(
            [sys.executable, CHECK_TYPED, "--base", "HEAD", "--repo-root", repo],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        r2 = subprocess.run(
            [sys.executable, CHECK_TYPED, "--base", "deadbeef", "--repo-root", repo,
             "--require-base"],
            capture_output=True, text=True)
        assert r2.returncode == 2, r2.stdout + r2.stderr
        print("PASS  check_typed_evals.py CLI exit codes (0 / 2 strict)")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def _make_skill(root, name, eval_entry):
    d = os.path.join(root, name)
    os.makedirs(os.path.join(d, "evals"), exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            f"name: {name}\n"
            "description: A test skill used by the typed-eval suite.\n"
            "---\n\n# Test\n")
    _write_json(os.path.join(d, "evals", "evals.json"),
                {"skill_name": name, "evals": [eval_entry]})


def test_validate_skill_marker_and_expect_enforcement():
    root = tempfile.mkdtemp(prefix="typed-skill-")
    try:
        # marker without expect -> rejected
        _make_skill(root, "marked-legacy", {
            "id": 1, "prompt": "p", "default": True,
            "expected_behavior": ["x"]})
        r = subprocess.run([sys.executable, VALIDATE_SKILL,
                            os.path.join(root, "marked-legacy")],
                           capture_output=True, text=True)
        assert r.returncode == 1 and "expect" in (r.stdout + r.stderr), r.stdout
        # marker with a valid typed expect -> accepted
        _make_skill(root, "marked-typed", {
            "id": 1, "prompt": "p", "default": True,
            "expect": {"text": ["x"]}})
        r2 = subprocess.run([sys.executable, VALIDATE_SKILL,
                             os.path.join(root, "marked-typed")],
                            capture_output=True, text=True)
        assert r2.returncode == 0, r2.stdout + r2.stderr
        # malformed expect -> rejected
        _make_skill(root, "bad-expect", {
            "id": 1, "prompt": "p", "expect": {"exit_code": [0]}})
        r3 = subprocess.run([sys.executable, VALIDATE_SKILL,
                             os.path.join(root, "bad-expect")],
                            capture_output=True, text=True)
        assert r3.returncode == 1 and "unknown key" in (r3.stdout + r3.stderr), r3.stdout
        # neither expect nor expected_behavior -> rejected
        _make_skill(root, "empty-assertion", {"id": 1, "prompt": "p"})
        r4 = subprocess.run([sys.executable, VALIDATE_SKILL,
                             os.path.join(root, "empty-assertion")],
                            capture_output=True, text=True)
        assert r4.returncode == 1, r4.stdout + r4.stderr
        print("PASS  validate_skill.py: marker-without-expect + expect shape enforced")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_verify_mjs_expect_enforcement():
    root = tempfile.mkdtemp(prefix="typed-verify-")
    try:
        skills = os.path.join(root, "skills")
        _make_skill(skills, "marked-legacy", {
            "id": 1, "prompt": "p", "core": True,
            "expected_behavior": ["x"]})
        r = subprocess.run(["node", VERIFY_MJS, "--skills-root", skills],
                           capture_output=True, text=True)
        assert r.returncode == 1 and "expect" in (r.stdout + r.stderr), r.stdout
        # replace with a valid typed marker -> pass
        _make_skill(skills, "marked-legacy", {
            "id": 1, "prompt": "p", "core": True,
            "expect": {"artifact": [{"path": "a.md", "phrases": ["hi"]}]}})
        r2 = subprocess.run(["node", VERIFY_MJS, "--skills-root", skills],
                            capture_output=True, text=True)
        assert r2.returncode == 0, r2.stdout + r2.stderr
        # malformed expect shape -> fail
        _make_skill(skills, "marked-legacy", {
            "id": 1, "prompt": "p",
            "expect": {"text": ["ok"], "network": ["x"]}})
        r3 = subprocess.run(["node", VERIFY_MJS, "--skills-root", skills],
                            capture_output=True, text=True)
        assert r3.returncode == 1 and "unknown key" in (r3.stdout + r3.stderr), r3.stdout
        print("PASS  verify.mjs: marker-without-expect + expect shape enforced")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    tests = [
        test_expect_schema_closed_shape,
        test_changed_and_new_eval_require_expect,
        test_base_semantics_unchanged_legacy_is_not_flagged,
        test_unresolvable_base_degrades_honestly,
        test_check_typed_cli_exit_codes,
        test_validate_skill_marker_and_expect_enforcement,
        test_verify_mjs_expect_enforcement,
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
