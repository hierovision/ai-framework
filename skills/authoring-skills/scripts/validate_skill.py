#!/usr/bin/env python3
"""Validate a skill directory against the spec and library conventions.

Usage:
    python3 validate_skill.py <path-to-skill-dir> [...more]
    python3 validate_skill.py --all   # validates every skills/* in the repo

Checks (spec = opencode Agent Skills + library conventions):
- SKILL.md exists (exact case) and frontmatter parses under STRICT yaml
  (lenient loaders accept things like unquoted ': ' in scalars that
  break other tools' previews/parsers — strict parsing catches them)
- name: present, 1-64 chars, ^[a-z0-9]+(-[a-z0-9]+)*$, matches dir name
- description: present, <=1024 hard cap, warn >900 (headroom convention)
- body: warn >500 lines (progressive-disclosure threshold)
- evals/evals.json: exists (library rule), valid JSON, every files[]
  entry resolves relative to evals/
- evals/evals.json markers (RM-003 pass 4): `default`/`core` are booleans;
  at most one `"default": true`; `"core": true` only on the default or first
  eval in file order; the six core skills must carry `"core": true`
- reference files >100 lines: warn if no '## Contents' TOC heading

Exit 0 = all skills pass (warnings allowed); exit 1 = any error.
"""
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("error: pyyaml required (pip install pyyaml)")
    sys.exit(2)

# RM-003 pass 4: the six-core set is owned by query_runs (single source of
# truth); import it so the harness target and marker validation cannot drift.
_OBSERVE_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "..", "..", "observing-runs", "scripts"))
if _OBSERVE_SCRIPTS not in sys.path:
    sys.path.insert(0, _OBSERVE_SCRIPTS)
from query_runs import CORE_SKILLS  # noqa: E402  (path set above)

# RM-003 pass 5: the closed typed-assertion schema is owned by
# scripts/check_typed_evals.py (single source of truth); import its validator
# so Layer 1 and the pre-commit/CI gate cannot drift. The JS mirror lives in
# scripts/verify.mjs (Layer 1 is hermetic and cannot import Python).
_REPO_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "scripts"))
if _REPO_SCRIPTS not in sys.path:
    sys.path.insert(0, _REPO_SCRIPTS)
try:
    from check_typed_evals import validate_expect, has_expect  # noqa: E402
except Exception:  # pragma: no cover - defensive: repo scripts always present
    validate_expect = has_expect = None

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate(skill_dir):
    errors, warnings = [], []
    name = os.path.basename(os.path.normpath(skill_dir))
    skill_md = os.path.join(skill_dir, "SKILL.md")

    if not os.path.isfile(skill_md):
        return [f"SKILL.md missing (exact case) in {skill_dir}"], []

    raw = open(skill_md, encoding="utf-8").read()
    parts = raw.split("---")
    if len(parts) < 3 or parts[0].strip():
        return ["frontmatter delimiters malformed (expected leading ---)"], []

    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return [f"frontmatter fails STRICT yaml parse: {str(e).splitlines()[0]}"], []
    if not isinstance(fm, dict):
        return ["frontmatter is not a mapping"], []

    fm_name = fm.get("name")
    if not fm_name:
        errors.append("frontmatter missing 'name'")
    else:
        if not NAME_RE.fullmatch(fm_name):
            errors.append(f"name '{fm_name}' fails ^[a-z0-9]+(-[a-z0-9]+)*$")
        if len(fm_name) > 64:
            errors.append(f"name is {len(fm_name)} chars (max 64)")
        if fm_name != name:
            errors.append(f"name '{fm_name}' != directory '{name}'")

    desc = fm.get("description")
    if not desc:
        errors.append("frontmatter missing 'description'")
    else:
        if len(desc) > 1024:
            errors.append(f"description is {len(desc)} chars (hard cap 1024)")
        elif len(desc) > 900:
            warnings.append(f"description is {len(desc)} chars (>900 headroom convention)")

    body_lines = ("---".join(parts[2:])).count("\n")
    if body_lines > 500:
        warnings.append(f"body is ~{body_lines} lines (>500; split into references/)")

    evals_path = os.path.join(skill_dir, "evals", "evals.json")
    if not os.path.isfile(evals_path):
        errors.append("evals/evals.json missing (library rule: evals are mandatory)")
    else:
        try:
            ev = json.load(open(evals_path, encoding="utf-8"))
            entries = ev.get("evals", [])
            defaults, cores = [], []
            for idx, e in enumerate(entries):
                if "default" in e:
                    if not isinstance(e["default"], bool):
                        errors.append(
                            f"evals.json evals[{idx}] 'default' must be a boolean")
                    elif e["default"]:
                        defaults.append(idx)
                if "core" in e:
                    if not isinstance(e["core"], bool):
                        errors.append(
                            f"evals.json evals[{idx}] 'core' must be a boolean")
                    elif e["core"]:
                        cores.append(idx)
                for f in e.get("files", []):
                    p = os.path.join(skill_dir, "evals", f)
                    if not os.path.isfile(p):
                        errors.append(f"evals.json files[] entry does not resolve: {f}")
                # RM-003 pass 5 typed-assertion enforcement (AC12/AC17).
                if "expect" in e:
                    if validate_expect is not None:
                        errors.extend(validate_expect(
                            e["expect"], where=f"evals.json evals[{idx}].expect"))
                if (e.get("default") or e.get("core")) and not (
                        has_expect and has_expect(e)):
                    errors.append(
                        f"evals.json evals[{idx}] carries a default/core marker "
                        f"without a typed 'expect' block (AC12/AC17)")
                if "expect" not in e:
                    eb = e.get("expected_behavior")
                    if (not isinstance(eb, list) or not eb
                            or any(not isinstance(b, str) or not b.strip()
                                   for b in eb)):
                        errors.append(
                            f"evals.json evals[{idx}] needs a non-empty "
                            f"'expected_behavior' when 'expect' is absent")
            if len(defaults) > 1:
                errors.append(
                    f"evals.json has {len(defaults)} 'default': true evals (max one)")
            if len(cores) > 1:
                errors.append(
                    f"evals.json has {len(cores)} 'core': true evals (max one)")
            for idx in cores:
                if idx != 0 and idx not in defaults:
                    errors.append(
                        f"evals.json evals[{idx}] is 'core': true but is not the "
                        f"'default' or first eval in file order")
            if name in CORE_SKILLS and not cores:
                errors.append(
                    f"core skill '{name}' must carry 'core': true on its default eval")
        except json.JSONDecodeError as e:
            errors.append(f"evals/evals.json invalid JSON: {e}")

    refs_dir = os.path.join(skill_dir, "references")
    if os.path.isdir(refs_dir):
        for root, _, files in os.walk(refs_dir):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(root, fn)
                content = open(p, encoding="utf-8").read()
                if content.count("\n") > 100 and "## Contents" not in content:
                    warnings.append(f"{os.path.relpath(p, skill_dir)} >100 lines without a '## Contents' TOC")

    return errors, warnings


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    if args == ["--all"]:
        # realpath so a symlinked install (e.g. ~/.config/opencode/skills/...)
        # still resolves to the real repo's skills/ root (Layer 1 hermeticity:
        # the hook must validate the checkout it was installed into).
        here = os.path.dirname(os.path.realpath(__file__))
        skills_root = os.path.normpath(os.path.join(here, "..", ".."))
        args = sorted(
            os.path.join(skills_root, d)
            for d in os.listdir(skills_root)
            if os.path.isdir(os.path.join(skills_root, d))
        )

    failed = False
    for skill_dir in args:
        errors, warnings = validate(skill_dir)
        name = os.path.basename(os.path.normpath(skill_dir))
        if errors:
            failed = True
            print(f"FAIL  {name}")
            for e in errors:
                print(f"      error: {e}")
        else:
            print(f"OK    {name}")
        for w in warnings:
            print(f"      warn:  {w}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
