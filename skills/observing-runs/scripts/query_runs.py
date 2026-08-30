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

SCRIPT_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_LOGS_DIR = os.environ.get("OBSERVE_LOG_DIR", os.path.join(REPO_ROOT, "logs"))

RUN_FILE_RE = re.compile(r"^run-(\d{4}-\d{2}-\d{2})\.jsonl$")


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


def aggregate(logs_dir):
    """Return a dict of aggregate stats."""
    per_skill = {}  # skill -> {runs, tokens, dur_sum}
    eval_rows = 0
    eval_pass = 0

    def skill_bucket(key):
        b = per_skill.get(key)
        if b is None:
            b = {"runs": 0, "tokens": 0, "dur_sum": 0}
            per_skill[key] = b
        return b

    for rec in _iter_records(logs_dir):
        kind = rec.get("kind")
        skill = rec.get("skill") or "(none)"
        tokens = (rec.get("tokens_in") or 0) + (rec.get("tokens_out") or 0)
        dur = rec.get("duration_ms") or 0
        b = skill_bucket(skill)
        b["runs"] += 1
        b["tokens"] += tokens
        b["dur_sum"] += dur

        if kind == "eval":
            eval_rows += 1
            if rec.get("eval_pass") is True:
                eval_pass += 1

    skills = []
    for skill, b in sorted(per_skill.items()):
        skills.append({
            "skill": skill,
            "runs": b["runs"],
            "tokens_total": b["tokens"],
            "cost_per_task": (b["tokens"] / b["runs"]) if b["runs"] else 0,
            "mean_duration_ms": (b["dur_sum"] / b["runs"]) if b["runs"] else 0,
        })

    result = {
        "skills": skills,
        "eval_pass_rate": (eval_pass / eval_rows) if eval_rows else None,
        "eval_rows": eval_rows,
        "eval_passed": eval_pass,
    }
    return result


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

    args = p.parse_args(argv)
    logs_dir = args.logs_dir or DEFAULT_LOGS_DIR

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
