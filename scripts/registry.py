#!/usr/bin/env python3
"""Skill/agent registry loader + validator (RM-005).

The single source of truth for reading `registry.json` (repo root): every
consumer imports `load()` from this module — no other module hand-parses
the file. `validate()` cross-checks repo reality against the registry
(AC3): orphan dirs, ghost entries, missing fields, unresolvable
boundary refs. `python3 scripts/registry.py --check` is the developer
CLI (enforcement itself lives in validate_skill.py --all, which is the
CI quality gate — the deliberate single enforcement point, RM-005 OQ4).

Registry entry contract (see .opencode/plans/archive/rm-005.md):
  name          skill dir name or persona file stem
  type          "skill" | "persona"
  owner         github handle, e.g. "@hierovision"
  maturity      "L1" provisional | "L2" defined | "L3" evaluated/operated |
                "L4" capable — promoted on EVIDENCE (typed evals green +
                real-loop use + independent review), never by assertion
  status        "active" | "deferred" | "deprecated"
  boundary_ref  file path that must resolve (skill: its SKILL.md;
                persona: agents/<name>.md)
"""
import argparse
import json
import os
import sys

ALLOWED_TYPES = ("skill", "persona")
ALLOWED_MATURITY = ("L1", "L2", "L3", "L4")
ALLOWED_STATUS = ("active", "deferred", "deprecated")
REQUIRED_FIELDS = ("name", "type", "owner", "maturity", "status",
                   "boundary_ref")


def _repo_root_from_here():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def load(path=None):
    """Return the parsed registry dict (version, skills, personas).

    Raises FileNotFoundError with a plain-english pointer when absent —
    the registry is mandatory library state, not optional config.
    """
    path = path or os.path.join(_repo_root_from_here(), "registry.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or "entries" not in data and \
            not (isinstance(data.get("skills"), list)
                 and isinstance(data.get("personas"), list)):
        raise ValueError(
            f"registry {path} must be {{'version': 1, 'skills': [...], "
            f"'personas': [...]}}")
    return data


def _enumerate_reality(skills_root, agents_root):
    skill_dirs = sorted(
        d for d in os.listdir(skills_root)
        if os.path.isdir(os.path.join(skills_root, d)))
    persona_files = sorted(
        f[:-3] for f in os.listdir(agents_root)
        if f.endswith(".md")) if os.path.isdir(agents_root) else []
    return skill_dirs, persona_files


def validate(registry_path=None, skills_root=None, agents_root=None,
             repo_root=None):
    """Return a list of out-of-sync errors (empty = registry is in sync).

    Defect classes, each named in the error text (AC3):
      orphan       a skills/<dir> or agents/<file> with no registry entry
      ghost        an entry whose name has no matching dir/file
      field        a missing/empty required field or an out-of-vocabulary
                   type/maturity/status value
      boundary_ref an entry whose boundary_ref does not resolve to a file
    """
    repo_root = repo_root or _repo_root_from_here()
    if registry_path and os.path.isdir(registry_path):
        # validate(tree_root) convenience: the positional arg is the repo
        # root, the registry lives at its top level.
        repo_root = registry_path
        registry_path = None
    skills_root = skills_root or os.path.join(repo_root, "skills")
    agents_root = agents_root or os.path.join(repo_root, "agents")
    reg_path = registry_path or os.path.join(repo_root, "registry.json")

    try:
        data = load(reg_path)
    except FileNotFoundError:
        return [f"registry file missing at {reg_path}"]
    except (json.JSONDecodeError, ValueError) as e:
        return [f"registry invalid: {e}"]

    skill_dirs, persona_files = _enumerate_reality(skills_root, agents_root)
    skills = data.get("skills") or []
    personas = data.get("personas") or []
    all_e = skills + personas

    errors = []
    seen_skills, seen_personas = set(), set()
    for e in all_e:
        if not isinstance(e, dict):
            errors.append("registry entry is not an object")
            continue
        name = e.get("name")
        etype = e.get("type")
        if not name:
            errors.append("field: entry missing 'name'")
            continue
        for field in REQUIRED_FIELDS:
            if not e.get(field):
                errors.append(f"field: {name} missing '{field}'")
        if etype not in ALLOWED_TYPES:
            errors.append(f"field: {name} has invalid type {etype!r}")
        if e.get("maturity") not in ALLOWED_MATURITY:
            errors.append(
                f"field: {name} has invalid maturity {e.get('maturity')!r}")
        if e.get("status") not in ALLOWED_STATUS:
            errors.append(
                f"field: {name} has invalid status {e.get('status')!r}")
        ref = e.get("boundary_ref")
        if ref and not os.path.isfile(os.path.join(repo_root or ".",
                                                   ref)) \
                and not os.path.isfile(ref):
            errors.append(f"boundary_ref: {name} -> {ref!r} does not resolve")
        if etype == "skill":
            seen_skills.add(name)
        else:
            seen_personas.add(name)

    skill_set, persona_set = set(skill_dirs), set(persona_files)
    for s in sorted(skill_set - seen_skills):
        errors.append(f"orphan: skills/{s}/ has no registry entry")
    for p in sorted(persona_set - seen_personas):
        errors.append(f"orphan: agents/{p}.md has no registry entry")
    for s in sorted(seen_skills - skill_set):
        errors.append(f"ghost: registry entry {s!r} has no skills/{s}/ dir")
    for p in sorted(seen_personas - persona_set):
        errors.append(
            f"ghost: registry entry {p!r} has no agents/{p}.md file")
    return errors


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(
        description="Check the skill/agent registry against repo reality.")
    p.add_argument("--check", action="store_true",
                   help="Validate repo <-> registry sync; exit 1 on defects.")
    p.add_argument("--repo-root", default=None,
                   help="Repo root (default: derived from this script's path).")
    args = p.parse_args(argv)

    root = args.repo_root or _repo_root_from_here()
    errors = validate(
        registry_path=os.path.join(root, "registry.json"),
        skills_root=os.path.join(root, "skills"),
        agents_root=os.path.join(root, "agents"),
        repo_root=root)
    data = load(os.path.join(root, "registry.json"))
    count = len((data.get("skills") or [])) + len((data.get("personas") or []))
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"PASS: registry in sync — {count} entries "
          f"({len(data.get('skills') or [])} skills, "
          f"{len(data.get('personas') or [])} personas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
