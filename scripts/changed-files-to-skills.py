#!/usr/bin/env python3
"""Map changed file paths to skill names (RM-003 AC7 / Layer 3 per-change gate).

Deterministic, first-match-wins mapping. Three classes:

  evaluable      a skill's behavioral surface changed -> run that skill's evals
  smoke          CI/harness infra changed; no owning behavioral eval ->
                 run the bounded smoke subset (see references/per-change-eval-sla.md)
  non_evaluable  docs/config only; no behavioral surface -> run 0 evals

Mapping table (evaluated in order; FIRST MATCH WINS, no fall-through):

  | pattern                              | class         | result                         |
  |--------------------------------------|---------------|--------------------------------|
  | skills/<name>/**                     | evaluable     | <name>                         |
  | reference/model-routing.md           | evaluable     | optimizing-model-routing       |
  | agents/*.md                          | evaluable     | optimizing-model-routing       |
  | docs/**                              | non_evaluable | skip (0 evals)                 |
  | reference/** (except model-routing)  | non_evaluable | skip (0 evals)                 |
  | .opencode/**                         | non_evaluable | skip (0 evals)                 |
  | README.md / LICENSE / .gitignore     | non_evaluable | skip (0 evals)                 |
  | .github/workflows/** / scripts/**    | smoke         | bounded smoke subset           |
  | *.md outside skills/** and docs/**   | non_evaluable | skip (0 evals)                 |
  | (anything unmatched)                 | smoke         | bounded smoke subset (fallback)|

Notes:
- `skills/<name>/**` covers every skill-internal file (scripts, evals,
  fixtures, references); explicit per-file skill rows are deliberately
  omitted as redundant (see the plan's mapping-table notes).
- Repo-root CI-infra (`.github/workflows/`, `scripts/`) maps to the smoke
  subset and is flagged in coverage-gaps as "harness change with no owning
  behavioral eval" -- it never maps to a skill eval.
- A docs-only change yields `[]` (0 evals).

CLI:
  changed-files-to-skills.py <path> [<path> ...]
      Prints a JSON array of evaluable skill names (deduped, first-seen
      order). Smoke / non-evaluable inputs contribute no skill name.
  changed-files-to-skills.py --format object <path> ...
      Prints {"files": [...], "skills": [...], "class": "...",
               "smoke": bool, "non_evaluable": bool, "entries": [...]}
      so the workflow can tell smoke (bounded subset) from non-evaluable
      (exit early, 0 evals).
  changed-files-to-skills.py --stdin
      Read newline-separated paths from stdin instead of argv.
"""
import argparse
import json
import re
import sys

SKILL_RE = re.compile(r"^skills/([^/]+)/")
TOP_LEVEL_NON_EVALUABLE = {"README.md", "LICENSE", ".gitignore"}


def classify(path):
    """Return (klass, skill, reason) for one path. First matching rule wins."""
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not p:
        return None

    m = SKILL_RE.match(p)
    if m:
        return ("evaluable", m.group(1), "skills/<name>/**")

    if p == "reference/model-routing.md":
        return ("evaluable", "optimizing-model-routing", "reference/model-routing.md")

    if re.match(r"^agents/[^/]+\.md$", p):
        return ("evaluable", "optimizing-model-routing", "agents/*.md")

    if p.startswith("docs/"):
        return ("non_evaluable", None, "docs/**")

    if p.startswith("reference/"):
        return ("non_evaluable", None, "reference/** (except model-routing.md)")

    if p.startswith(".opencode/"):
        return ("non_evaluable", None, ".opencode/**")

    if p in TOP_LEVEL_NON_EVALUABLE:
        return ("non_evaluable", None, "top-level config")

    if p.startswith(".github/workflows/") or p.startswith("scripts/"):
        return ("smoke", None, "ci-infra (no owning behavioral eval)")

    if p.endswith(".md"):
        return ("non_evaluable", None, "*.md outside skills/** and docs/**")

    # Ambiguous: a bounded smoke subset is the safe fallback (plan Risks).
    return ("smoke", None, "unmatched -> smoke fallback")


def analyze(paths):
    """Return the mapping result for a list of paths (order preserved)."""
    entries = []
    skills = []  # first-seen order (deterministic for a given path list)
    smoke = False
    non_evaluable = False
    for raw in paths:
        result = classify(raw)
        if result is None:
            continue
        klass, skill, reason = result
        entries.append({"path": raw.strip(), "class": klass,
                        "skill": skill, "reason": reason})
        if klass == "evaluable":
            if skill not in skills:
                skills.append(skill)
        elif klass == "smoke":
            smoke = True
        else:
            non_evaluable = True

    if skills:
        overall = "evaluable"
    elif smoke:
        overall = "smoke"
    elif non_evaluable:
        overall = "non_evaluable"
    else:
        overall = "non_evaluable"

    return {
        "class": overall,
        "skills": skills,
        "smoke": smoke,
        "non_evaluable": non_evaluable,
        "entries": entries,
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Changed files -> eval skill mapping.")
    p.add_argument("paths", nargs="*", help="Changed file paths.")
    p.add_argument("--stdin", action="store_true",
                   help="Read newline-separated paths from stdin.")
    p.add_argument("--format", choices=("list", "object"), default="list",
                   help="'list' (default) prints the JSON skill array; "
                        "'object' prints the full classification.")
    args = p.parse_args(argv)

    raw_paths = list(args.paths)
    if args.stdin:
        raw_paths.extend(sys.stdin.read().splitlines())

    result = analyze(raw_paths)
    if args.format == "object":
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result["skills"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
