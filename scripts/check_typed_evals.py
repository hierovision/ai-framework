#!/usr/bin/env python3
"""Enforce that a NEW or CHANGED behavioral eval carries a typed `expect` block.

RM-003 pass 5 (AC17/AC19). The closed typed-assertion taxonomy is `action`
(tool-event predicates over the `opencode run --format json` stream),
`artifact` (a written file + key phrases), and `text` (a key phrase in the
final response). The move-on-touch rule: any eval that is new, changed, or
selected as a canary must migrate to a typed `expect` in the same change.

This script compares every `skills/*/evals/evals.json` against a base git ref
and rejects an eval whose entry is new or changed but has no `expect`. It also
exposes `validate_expect()` — the single-source closed-shape validator that
`validate_skill.py` imports (the JS mirror in `scripts/verify.mjs` keeps Layer 1
hermetic).

CLI:
    python3 scripts/check_typed_evals.py --base main
    python3 scripts/check_typed_evals.py --base HEAD --require-base

Exit codes:
    0  every new/changed eval is typed (or the base ref is unavailable and
       --require-base was not passed — degradation is reported as a warning)
    1  at least one new/changed eval lacks `expect`, or a shape error
    2  --require-base was passed and the base ref does not resolve
"""
import argparse
import json
import os
import subprocess
import sys

# The closed taxonomy. No `exit_code`, `database`, or `network` class exists.
ALLOWED_EXPECT_KEYS = ("action", "artifact", "text")
ALLOWED_ACTION_KEYS = ("tool", "args")
ALLOWED_ARTIFACT_KEYS = ("path", "phrases")


def _is_nonempty_str(v):
    return isinstance(v, str) and bool(v.strip())


def validate_expect(expect, where="expect"):
    """Return a list of closed-shape errors for one `expect` block (empty = ok).

    Closed form: an object with >=1 non-empty `action`/`artifact`/`text`
    entry; unknown keys rejected; per-class field rules enforced.
    """
    errors = []
    if not isinstance(expect, dict):
        return [f"{where} must be an object"]
    unknown = [k for k in expect if k not in ALLOWED_EXPECT_KEYS]
    if unknown:
        errors.append(f"{where} has unknown key(s): {', '.join(sorted(unknown))}")
    present = [k for k in ALLOWED_EXPECT_KEYS if k in expect]
    if not present:
        errors.append(f"{where} must contain at least one of action/artifact/text")
    for key in present:
        value = expect[key]
        if not isinstance(value, list) or not value:
            errors.append(f"{where}.{key} must be a non-empty array")
            continue
        if key == "text":
            for i, item in enumerate(value):
                if not _is_nonempty_str(item):
                    errors.append(f"{where}.text[{i}] must be a non-empty string")
        elif key == "action":
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    errors.append(f"{where}.action[{i}] must be an object")
                    continue
                bad = [k for k in item if k not in ALLOWED_ACTION_KEYS]
                if bad:
                    errors.append(
                        f"{where}.action[{i}] has unknown key(s): {', '.join(sorted(bad))}")
                if not _is_nonempty_str(item.get("tool")):
                    errors.append(f"{where}.action[{i}].tool must be a non-empty string")
                args = item.get("args", {})
                if not isinstance(args, dict):
                    errors.append(f"{where}.action[{i}].args must be an object")
                else:
                    for ak, av in args.items():
                        if not _is_nonempty_str(av):
                            errors.append(
                                f"{where}.action[{i}].args[{ak!r}] must be a "
                                f"non-empty glob string")
        elif key == "artifact":
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    errors.append(f"{where}.artifact[{i}] must be an object")
                    continue
                bad = [k for k in item if k not in ALLOWED_ARTIFACT_KEYS]
                if bad:
                    errors.append(
                        f"{where}.artifact[{i}] has unknown key(s): "
                        f"{', '.join(sorted(bad))}")
                if not _is_nonempty_str(item.get("path")):
                    errors.append(f"{where}.artifact[{i}].path must be a non-empty string")
                phrases = item.get("phrases")
                if (not isinstance(phrases, list) or not phrases
                        or any(not _is_nonempty_str(p) for p in phrases)):
                    errors.append(
                        f"{where}.artifact[{i}].phrases must be a non-empty array "
                        f"of non-empty strings")
    return errors


def has_expect(entry):
    """True when an eval entry carries a non-empty `expect` object."""
    return isinstance(entry, dict) and isinstance(entry.get("expect"), dict) \
        and bool(entry["expect"])


def _repo_root_from_here():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _git_show(repo_root, ref, relpath):
    r = subprocess.run(["git", "-C", repo_root, "show", f"{ref}:{relpath}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def _base_resolves(repo_root, ref):
    if not ref:
        return False
    r = subprocess.run(["git", "-C", repo_root, "rev-parse", "--verify",
                        f"{ref}^{{commit}}"], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def _entries_by_id(manifest):
    out = {}
    for e in manifest.get("evals", []) if isinstance(manifest, dict) else []:
        if isinstance(e, dict) and "id" in e:
            out[e["id"]] = e
    return out


def collect_errors(base_ref, skills_root=None, repo_root=None, require_base=False):
    """Return (errors, warnings) for new/changed evals lacking `expect`."""
    repo_root = repo_root or _repo_root_from_here()
    skills_root = skills_root or os.path.join(repo_root, "skills")
    errors, warnings = [], []

    if not _base_resolves(repo_root, base_ref):
        msg = f"base ref {base_ref!r} is not resolvable in {repo_root}"
        if require_base:
            return [msg], warnings
        warnings.append(
            f"{msg}; skipping typed-eval comparison (pass --require-base to fail)")
        return errors, warnings

    if not os.path.isdir(skills_root):
        return errors, warnings

    for skill in sorted(os.listdir(skills_root)):
        work_path = os.path.join(skills_root, skill, "evals", "evals.json")
        if not os.path.isfile(work_path):
            continue
        try:
            with open(work_path, encoding="utf-8") as fh:
                work = json.load(fh)
        except json.JSONDecodeError:
            continue  # validate_skill.py / verify.mjs own JSON validity
        rel = os.path.relpath(work_path, repo_root)
        base_entries = {}
        base_raw = _git_show(repo_root, base_ref, rel)
        if base_raw:
            try:
                base_entries = _entries_by_id(json.loads(base_raw))
            except json.JSONDecodeError:
                base_entries = {}

        for e in work.get("evals", []):
            if not isinstance(e, dict):
                continue
            eid = e.get("id")
            base_e = base_entries.get(eid)
            if base_e is None:
                status = "new"
            elif base_e != e:
                status = "changed"
            else:
                continue  # untouched legacy eval: migrate-on-touch does not apply
            if not has_expect(e):
                errors.append(
                    f"{rel}: eval id={eid!r} is {status} but has no typed "
                    f"'expect' block — new or changed evals must migrate to "
                    f"typed assertions on touch")
    return errors, warnings


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(
        description="Reject a NEW or CHANGED eval lacking a typed expect block.")
    p.add_argument("--base", default="main",
                   help="Base git ref to compare against (default: main).")
    p.add_argument("--skills-root", default=None,
                   help="Skills root (default <repo>/skills).")
    p.add_argument("--repo-root", default=None,
                   help="Repo root (default: derived from this script's path).")
    p.add_argument("--require-base", action="store_true",
                   help="Fail (exit 2) when the base ref does not resolve instead "
                        "of degrading to a warning.")
    p.add_argument("--quiet", action="store_true", help="Suppress the pass line.")
    args = p.parse_args(argv)

    repo_root = args.repo_root or _repo_root_from_here()
    if args.require_base and not _base_resolves(repo_root, args.base):
        print(f"error: base ref {args.base!r} is not resolvable in {repo_root}",
              file=sys.stderr)
        return 2

    errors, warnings = collect_errors(
        args.base, skills_root=args.skills_root, repo_root=args.repo_root,
        require_base=args.require_base)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        print(
            "FAIL: new or changed evals must carry typed assertions (an 'expect' block "
            "saying what the agent must DO, PRODUCE, or SAY). See "
            "skills/authoring-skills/references/eval-assertions.md — a minimal "
            "valid block: \"expect\": {\"artifact\": [{\"path\": \"**/SKILL.md\", "
            "\"phrases\": [\"name:\"]}]} — meaning the eval passes when the agent "
            "wrote a SKILL.md containing those phrases.",
            file=sys.stderr)
        print(f"({len(errors)} eval(s) rejected)", file=sys.stderr)
        for e in errors:
            print(f"      error: {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"PASS: every new/changed eval vs {args.base!r} carries a typed "
              f"'expect' block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
