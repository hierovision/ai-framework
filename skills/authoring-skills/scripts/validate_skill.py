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
            for e in ev.get("evals", []):
                for f in e.get("files", []):
                    p = os.path.join(skill_dir, "evals", f)
                    if not os.path.isfile(p):
                        errors.append(f"evals.json files[] entry does not resolve: {f}")
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
        here = os.path.dirname(os.path.abspath(__file__))
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
