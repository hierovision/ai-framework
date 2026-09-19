#!/usr/bin/env python3
"""Aggregate run-log JSONL files and prune old daily files.

Reads logs/run-<date>.jsonl files produced by log_run.py and reports:
  - per-skill token totals (cost/task) = tokens_in + tokens_out
  - mean duration_ms (latency) per skill
  - eval-pass rate (eval_pass==true over eval-kind rows), overall + per skill

Plus a `prune` subcommand for bounded retention (RM-001 Retention):
  query_runs.py prune --older-than 30d [--archive] [--dry-run]
deletes (or gzips) daily files older than the window, keeps newer ones.

This is an OPT-IN, out-of-band reader — invoked on demand / by CI / by
ROI scripts, never per agent turn. It does NOT write logs back into any
agent context.
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# Real, symlink-safe module location. `__file__` is correct BOTH when this
# runs as a script and when it is imported as a module: sys.argv[0] points at
# the *importer* in the imported case, which made the default logs dir
# argv[0]-dependent (same defect family as log_run.py — RM-002 AC5, 2026-09-16).
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
# repo root = scripts -> observing-runs -> skills -> repo (THREE levels up;
# the pre-2026-09-16 code took two and landed at skills/).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
DEFAULT_LOGS_DIR = os.environ.get("OBSERVE_LOG_DIR", os.path.join(REPO_ROOT, "logs"))

RUN_FILE_RE = re.compile(r"^run-(\d{4}-\d{2}-\d{2})\.jsonl$")

# RM-003 AC3: model tiers excluded from the default CI eval run (free-tier policy).
EVAL_TIERS_EXCLUDED = ("go", "zen")

# RM-003 pass 4 / AC12: the six core skills whose default evals run on a
# harness change. Canonical single source of truth, imported by
# scripts/changed-files-to-skills.py and validate_skill.py so the harness
# target, the coverage report, and marker validation cannot drift.
CORE_SKILLS = (
    "authoring-skills",
    "designing-architecture",
    "implementing-features",
    "reviewing-code",
    "triaging-requirements",
    "writing-unit-tests",
)


def _iter_records(logs_dir):
    if not os.path.isdir(logs_dir):
        return
    for name in sorted(os.listdir(logs_dir)):
        if not RUN_FILE_RE.match(name):
            continue
        path = os.path.join(logs_dir, name)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _as_known_int(value):
    """Return `value` as a real measured int, or None when unknown.

    Legacy compatibility (2026-09-13): writers before 2026-09-06 defaulted
    unknown `tokens_in`/`tokens_out`/`duration_ms` to literal `0`. Writers now
    emit `null`. Because `0` carried no information (missing != zero), a literal
    `0` is treated as unknown so legacy records cannot skew cost/latency
    aggregates. Documented in references/schema.md.

    Sunset: legacy records age out of the 30-day retention window by
    ~2026-10-06; this shim can be removed after that date.
    """
    if isinstance(value, bool):  # bool is an int subclass; never a measurement
        return None
    if isinstance(value, int) and value != 0:
        return value
    return None


def aggregate(logs_dir):
    """Return a dict of aggregate stats.

    Missing != zero: tokens_in/out and duration_ms default None when unknown.
    Totals sum known components only; cost_per_task divides by runs with any
    known token component (None when no run has known tokens); mean_duration
    divides by runs with known duration (None when none known).

    Legacy records that stored literal `0` for unknown are coerced to unknown
    by `_as_known_int` (see its docstring) so they do not skew the aggregates.
    """
    per_skill = {}  # skill -> {runs, tokens, tokens_known_runs, dur_sum, dur_known_runs}
    eval_rows = 0
    eval_pass = 0

    def skill_bucket(key):
        b = per_skill.get(key)
        if b is None:
            b = {"runs": 0, "tokens": 0, "tokens_known_runs": 0,
                 "dur_sum": 0, "dur_known_runs": 0}
            per_skill[key] = b
        return b

    for rec in _iter_records(logs_dir):
        kind = rec.get("kind")
        skill = rec.get("skill") or "(none)"
        ti = _as_known_int(rec.get("tokens_in"))
        to = _as_known_int(rec.get("tokens_out"))
        dur = _as_known_int(rec.get("duration_ms"))
        b = skill_bucket(skill)
        b["runs"] += 1
        if ti is not None or to is not None:
            b["tokens"] += (ti if ti is not None else 0) + (to if to is not None else 0)
            b["tokens_known_runs"] += 1
        if dur is not None:
            b["dur_sum"] += dur
            b["dur_known_runs"] += 1

        if kind == "eval":
            # eval_pass=None rows are per-attempt reliability annotations
            # (a retried transient failure) — they consume tokens/cost and
            # are counted above, but never count toward the pass rate.
            ep = rec.get("eval_pass")
            if ep is None:
                continue
            eval_rows += 1
            if ep is True:
                eval_pass += 1

    skills = []
    for skill, b in sorted(per_skill.items()):
        skills.append({
            "skill": skill,
            "runs": b["runs"],
            "tokens_total": b["tokens"],
            "cost_per_task": (b["tokens"] / b["tokens_known_runs"]) if b["tokens_known_runs"] else None,
            "mean_duration_ms": (b["dur_sum"] / b["dur_known_runs"]) if b["dur_known_runs"] else None,
        })

    result = {
        "skills": skills,
        "eval_pass_rate": (eval_pass / eval_rows) if eval_rows else None,
        "eval_rows": eval_rows,
        "eval_passed": eval_pass,
    }
    return result


def _iter_eval_manifests(skills_root):
    """Yield (skill, manifest_dict) for every skills/*/evals/evals.json."""
    if not os.path.isdir(skills_root):
        return
    for name in sorted(os.listdir(skills_root)):
        path = os.path.join(skills_root, name, "evals", "evals.json")
        if not os.path.isfile(path):
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            yield name, data


def coverage_gaps(logs_dir, skills_root=None):
    """RM-003 AC3 coverage-gap report.

    The three required arrays (the contract):
      zero_eval_skills         skills with an evals manifest but zero kind=eval
                               records in the (retention-limited) log window
      deferred_evals           evals flagged deferred:true (excluded by default)
      free_tier_excluded_evals evals whose model_tier is go|zen (excluded in CI)
    Plus:
      quarantined_evals        evals at status=quarantined in quarantine.json
      no_default_marker        skills without a `"default": true` eval
      core_covered             six core skills that resolve a `"core": true`
                               canary `{skill, eval_id}`
      core_uncovered           core skills lacking a core-marked eval
      smoke_uncovered          skills outside the fixed six-core harness set
                               (a harness change does not run them)
    """
    if skills_root is None:
        skills_root = os.path.join(REPO_ROOT, "skills")

    eval_record_skills = set()
    for rec in _iter_records(logs_dir):
        if rec.get("kind") == "eval" and rec.get("skill"):
            eval_record_skills.add(rec["skill"])

    zero_eval_skills, deferred_evals, free_tier_excluded_evals = [], [], []
    no_default_marker = []
    manifests = {}
    for skill, data in _iter_eval_manifests(skills_root):
        manifests[skill] = data
        default_tier = data.get("default_model_tier", "free")
        if skill not in eval_record_skills:
            zero_eval_skills.append(skill)
        evals = data.get("evals", [])
        if not any(e.get("default") for e in evals):
            no_default_marker.append(skill)
        for e in evals:
            tier = e.get("default_model_tier", default_tier)
            item = {"skill": skill, "eval_id": e.get("id"), "model_tier": tier}
            if e.get("deferred"):
                deferred_evals.append({**item,
                                       "reason": "deferred:true excluded from default run"})
            elif tier in EVAL_TIERS_EXCLUDED:
                free_tier_excluded_evals.append(
                    {**item, "reason": f"model_tier={tier} excluded by CI free-tier policy"}
                )

    core_covered, core_uncovered = [], []
    for skill in CORE_SKILLS:
        data = manifests.get(skill)
        marked = ([e for e in data.get("evals", []) if e.get("core")]
                  if data is not None else [])
        if marked:
            core_covered.append({"skill": skill, "eval_id": marked[0].get("id")})
        else:
            core_uncovered.append(skill)

    smoke_uncovered = sorted(s for s in manifests if s not in set(CORE_SKILLS))

    quarantined_evals = []
    quarantine_path = os.path.join(logs_dir, "quarantine.json")
    if os.path.isfile(quarantine_path):
        try:
            qdata = json.load(open(quarantine_path, encoding="utf-8"))
        except json.JSONDecodeError:
            qdata = {}
        if isinstance(qdata, dict):
            for key, entry in sorted(qdata.items()):
                if isinstance(entry, dict) and entry.get("status") == "quarantined":
                    quarantined_evals.append({"key": key, **entry})

    return {
        "zero_eval_skills": sorted(zero_eval_skills),
        "deferred_evals": deferred_evals,
        "free_tier_excluded_evals": free_tier_excluded_evals,
        "quarantined_evals": quarantined_evals,
        "no_default_marker": sorted(no_default_marker),
        "core_covered": core_covered,
        "core_uncovered": core_uncovered,
        "smoke_uncovered": smoke_uncovered,
    }


def _parse_older_than(spec):
    """Parse '30d' (days) into a number of seconds. Default unit days."""
    m = re.match(r"^(\d+)\s*(d|h|m|s)?$", spec.strip())
    if not m:
        raise ValueError(f"invalid --older-than: {spec!r} (expected e.g. '30d')")
    n = int(m.group(1))
    unit = m.group(2) or "d"
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * mult


def _daily_files(logs_dir):
    out = []
    if not os.path.isdir(logs_dir):
        return out
    for name in sorted(os.listdir(logs_dir)):
        m = RUN_FILE_RE.match(name)
        if not m:
            continue
        out.append((name, os.path.join(logs_dir, name), m.group(1)))
    return out


def prune(logs_dir, older_than, archive=False, dry_run=False):
    """Delete (or gzip) daily files older than `older_than` seconds.

    Returns (removed, kept) counts.
    """
    now = time.time()
    cutoff = now - older_than
    removed = 0
    kept = 0
    archive_dir = os.path.join(logs_dir, "archive")
    for name, path, _date in _daily_files(logs_dir):
        mtime = os.path.getmtime(path)
        if mtime < cutoff:
            if dry_run:
                kept += 1
                continue
            if archive:
                os.makedirs(archive_dir, exist_ok=True)
                dest = os.path.join(archive_dir, name + ".gz")
                with open(path, "rb") as src, gzip.open(dest, "wb") as dst:
                    dst.writelines(src)
                os.remove(path)
            else:
                os.remove(path)
            removed += 1
        else:
            kept += 1
    return removed, kept


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--logs-dir", default=None, help="Log directory (default repo logs/).")

    p = argparse.ArgumentParser(description="Aggregate / prune run-log JSONL.",
                                parents=[parent])
    sub = p.add_subparsers(dest="cmd")

    pa = sub.add_parser("aggregate", parents=[parent], help="Print aggregated stats as JSON.")
    pa.add_argument("--print", action="store_true", help="Also pretty-print to stdout.")

    pp = sub.add_parser("prune", parents=[parent], help="Delete/gzip daily files older than window.")
    pp.add_argument("--older-than", required=True, help="e.g. '30d' (days).")
    pp.add_argument("--archive", action="store_true",
                    help="gzip to logs/archive/ instead of deleting.")
    pp.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")

    pc = sub.add_parser("coverage-gaps", parents=[parent],
                        help="Report eval coverage gaps (RM-003 AC3).")
    pc.add_argument("--skills-root", default=None,
                    help="Skills root (default <repo>/skills).")
    pc.add_argument("--print", action="store_true", help="Also pretty-print to stdout.")

    args = p.parse_args(argv)
    logs_dir = args.logs_dir or DEFAULT_LOGS_DIR

    if args.cmd == "coverage-gaps":
        result = coverage_gaps(logs_dir, skills_root=getattr(args, "skills_root", None))
        if getattr(args, "print", False):
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result))
        return 0

    if args.cmd == "prune":
        try:
            secs = _parse_older_than(args.older_than)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        removed, kept = prune(logs_dir, secs, archive=args.archive, dry_run=args.dry_run)
        verb = "would-remove" if args.dry_run else ("archived" if args.archive else "removed")
        print(json.dumps({"action": verb, "removed": removed, "kept": kept}))
        return 0

    # default: aggregate
    result = aggregate(logs_dir)
    if getattr(args, "print", False):
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
