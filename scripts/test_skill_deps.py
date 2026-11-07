#!/usr/bin/env python3
"""Skill-dependency containment tests (RM-073 P1-6).

Run: python3 scripts/test_skill_deps.py

Proves the skill-local npm surfaces are pinned and contained:
  - `playwright` (and `axe-core`) are exact versions, not caret ranges;
  - each skill's `package-lock.json` is TRACKED and not gitignored;
  - no `skills/*/node_modules` entry resolves outside this repo (the old
    cross-repo symlink into a consumer checkout is gone);
  - `auditing-accessibility` resolves axe-core from `AXE_CORE_PATH` or its own
    pinned install, NEVER from the process CWD: a poisoned
    `<cwd>/node_modules/axe-core` loses in every case.

Hermetic: temp dirs under `.scratch/test-tmp`; node only, no network, no
browser.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKILLS = os.path.join(REPO, "skills")
AUDIT = os.path.join(SKILLS, "auditing-accessibility", "scripts", "audit.mjs")
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
PINNED_SURFACES = ("capturing-ui-evidence", "auditing-accessibility", "validating-ui")


def _scratch():
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="skill-deps-", dir=base)


def _node(code, cwd, env_extra=None):
    env = dict(os.environ)
    env.pop("AXE_CORE_PATH", None)
    env.pop("NODE_PATH", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([os.environ.get("NODE", "node"), "--input-type=module",
                           "-e", code], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def test_manifests_pin_exact_versions():
    for name in PINNED_SURFACES:
        path = os.path.join(SKILLS, name, "package.json")
        assert os.path.isfile(path), f"missing {path}"
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        deps = dict(data.get("dependencies") or {})
        deps.update(data.get("devDependencies") or {})
        assert deps, f"{name}/package.json pins nothing"
        for dep, version in deps.items():
            assert EXACT.match(str(version)), f"{name}: {dep} is {version!r}, not exact"
    with open(os.path.join(SKILLS, "auditing-accessibility", "package.json"),
              encoding="utf-8") as fh:
        a11y = json.load(fh)["dependencies"]
    assert "axe-core" in a11y and "playwright" in a11y, a11y


def test_lockfiles_are_tracked_and_not_ignored():
    for name in PINNED_SURFACES:
        for filename in ("package.json", "package-lock.json"):
            rel = os.path.join("skills", name, filename)
            path = os.path.join(REPO, rel)
            assert os.path.isfile(path), f"missing {rel} (run npm install --package-lock-only)"
            tracked = subprocess.run(["git", "-C", REPO, "ls-files", "--error-unmatch", rel],
                                     capture_output=True, text=True)
            assert tracked.returncode == 0, \
                f"{rel} is not tracked (git add it; the lock is the pin surface)"
            ignored = subprocess.run(["git", "-C", REPO, "check-ignore", "-q", rel])
            assert ignored.returncode == 1, f"{rel} is gitignored"


def test_no_node_modules_resolves_outside_repo():
    repo_real = os.path.realpath(REPO) + os.sep
    for skill in sorted(os.listdir(SKILLS)):
        nm = os.path.join(SKILLS, skill, "node_modules")
        if not os.path.exists(nm):
            continue
        entries = [nm] + [os.path.join(nm, e) for e in os.listdir(nm)]
        for entry in entries:
            if not os.path.islink(entry):
                continue
            target = os.path.realpath(entry)
            assert target.startswith(repo_real), \
                f"{entry} resolves outside the repo: {target}"


def _poisoned_cwd(work):
    poison = os.path.join(work, "consumer")
    axe_dir = os.path.join(poison, "node_modules", "axe-core")
    os.makedirs(axe_dir)
    poisoned = os.path.join(axe_dir, "axe.min.js")
    with open(poisoned, "w", encoding="utf-8") as fh:
        fh.write("POISONED-CONSUMER-AXE")
    return poison, poisoned


IMPORT_RESOLVER = (
    "import { pathToFileURL } from 'node:url';"
    "const m = await import(pathToFileURL(%r).href);"
    "const src = await m.readAxeCoreSource();"
    "process.stdout.write(src);"
)


def test_axe_core_path_wins_over_poisoned_cwd():
    work = _scratch()
    try:
        poison, _ = _poisoned_cwd(work)
        pinned = os.path.join(work, "axe-pinned.js")
        with open(pinned, "w", encoding="utf-8") as fh:
            fh.write("PINNED-BY-AXE-CORE-PATH")
        code = IMPORT_RESOLVER % AUDIT
        r = _node(code, poison, {"AXE_CORE_PATH": pinned,
                                 "NODE_PATH": os.path.join(poison, "node_modules")})
        assert r.returncode == 0, r.stderr
        assert r.stdout == "PINNED-BY-AXE-CORE-PATH", r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_skill_local_pin_wins_over_poisoned_cwd():
    work = _scratch()
    try:
        poison, _ = _poisoned_cwd(work)
        # A relocated copy of the real resolver: same code, controlled deps.
        skill = os.path.join(work, "skill")
        scripts = os.path.join(skill, "scripts")
        os.makedirs(scripts)
        shutil.copy(AUDIT, os.path.join(scripts, "audit.mjs"))
        axe_dir = os.path.join(skill, "node_modules", "axe-core")
        os.makedirs(axe_dir)
        with open(os.path.join(axe_dir, "axe.min.js"), "w", encoding="utf-8") as fh:
            fh.write("SKILL-PINNED-AXE")
        code = IMPORT_RESOLVER % os.path.join(scripts, "audit.mjs")
        r = _node(code, poison, {"NODE_PATH": os.path.join(poison, "node_modules")})
        assert r.returncode == 0, r.stderr
        assert r.stdout == "SKILL-PINNED-AXE", r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_no_resolvable_axe_never_falls_back_to_cwd():
    work = _scratch()
    try:
        poison, _ = _poisoned_cwd(work)
        skill = os.path.join(work, "bare-skill")
        scripts = os.path.join(skill, "scripts")
        os.makedirs(scripts)
        shutil.copy(AUDIT, os.path.join(scripts, "audit.mjs"))
        code = IMPORT_RESOLVER % os.path.join(scripts, "audit.mjs")
        r = _node(code, poison, {"NODE_PATH": os.path.join(poison, "node_modules")})
        assert r.returncode != 0, f"resolved something unexpected: {r.stdout}"
        assert "POISONED-CONSUMER-AXE" not in r.stdout
        assert "AXE_CORE_PATH" in r.stderr or "npm ci" in r.stderr, r.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    tests = [
        test_manifests_pin_exact_versions,
        test_lockfiles_are_tracked_and_not_ignored,
        test_no_node_modules_resolves_outside_repo,
        test_axe_core_path_wins_over_poisoned_cwd,
        test_skill_local_pin_wins_over_poisoned_cwd,
        test_no_resolvable_axe_never_falls_back_to_cwd,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"{'FAIL' if failed else 'OK'}: {len(tests) - failed}/{len(tests)} skill-dependency tests")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
