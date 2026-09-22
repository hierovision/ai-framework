#!/usr/bin/env python3
"""RM-003 eval report artifact + CI dashboard data.

Extends `skills/observing-runs/scripts/query_runs.py` (the run-log schema
owner) with the RM-003 report surface:

  aggregate          per-skill, per-run eval scores (ts, run_id, pass/fail,
                     duration, tokens, model) + the query_runs rollup
  coverage-gaps      zero-eval skills, deferred evals, free-tier-excluded
                     evals, quarantined evals (delegates to query_runs)
  green-run-status   AC4 dashboard state: the first steady-state green run
                     candidate on main, or "not yet achieved" + reason
  quota-projection   AC11 monthly-minute projection vs the 1,800 min guardrail

The scripts are the single source of truth for the schema; this module never
redefines run-log field names. All CLI output is JSON.

CLI:
  eval-report.py aggregate       --logs-dir logs/ [--out PATH] [--print]
  eval-report.py coverage-gaps   --logs-dir logs/ [--out PATH] [--print]
  eval-report.py green-run-status [--out PATH] [--print] [--record ...]
  eval-report.py quota-projection [--logs-dir logs/] [--out PATH] [--print]
  eval-report.py all             --logs-dir logs/ [--out-dir DIR]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OBSERVE_SCRIPTS = os.path.join(REPO_ROOT, "skills", "observing-runs", "scripts")
if OBSERVE_SCRIPTS not in sys.path:
    sys.path.insert(0, OBSERVE_SCRIPTS)
import query_runs  # run-log schema owner / aggregator (single source of truth)

# AC4 / AC10: first weekly eval-behavioral run on main on/after this date.
GREEN_RUN_EARLIEST = "2026-09-21"
# RM-002's negative-path canary (red counterpart) for reference.
RM002_CANARY_RUN = "35108912831"

# AC11 quota model (pass 4; documented in reference/per-change-eval-sla.md).
# Measured ~100s per fresh-agent eval (PR #23, run 35392700424) supersedes
# the prior imaginary 30s figure.
WEEKLY_MIN_PER_EVAL = 1.67  # ~100s per eval
WEEKS_PER_MONTH = 4
PER_CHANGE_RUN_MIN = 7      # blended 1-2 skill / <=6 harness evals
PRS_PER_MONTH_ASSUMED = 15
GUARDRAIL_LIMIT = 1800      # 90% of GitHub Free 2,000 min/month


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def per_skill_runs(logs_dir):
    """Per-skill list of eval records (the per-run scores)."""
    out = {}
    for rec in query_runs._iter_records(logs_dir):
        if rec.get("kind") != "eval":
            continue
        skill = rec.get("skill") or "(none)"
        out.setdefault(skill, []).append({
            "ts": rec.get("ts"),
            "run_id": rec.get("run_id"),
            "eval_pass": rec.get("eval_pass"),
            "outcome": rec.get("outcome"),
            "model": rec.get("model"),
            "tokens_in": rec.get("tokens_in"),
            "tokens_out": rec.get("tokens_out"),
            "duration_ms": rec.get("duration_ms"),
            "detail": rec.get("detail"),
        })
    return out


def aggregate_report(logs_dir):
    """AC1: per-skill, per-run eval scores + the query_runs rollup."""
    return {
        "generated_at": _now_iso(),
        "logs_dir": os.path.abspath(logs_dir),
        "aggregate": query_runs.aggregate(logs_dir),
        "per_skill": per_skill_runs(logs_dir),
    }


def coverage_gaps(logs_dir, skills_root=None):
    """AC3: delegate to query_runs' coverage-gaps implementation.

    Returns the three required arrays (`zero_eval_skills`, `deferred_evals`,
    `free_tier_excluded_evals`) plus `quarantined_evals`, pass-4
    `no_default_marker`, core coverage (`core_covered` / `core_uncovered`),
    the retained `smoke_uncovered`, and the pass-5 typed-assertion migration
    backlog (`legacy_assertion_evals` / `legacy_assertion_count`).
    """
    return query_runs.coverage_gaps(logs_dir, skills_root=skills_root)


def green_run_status(achieved=False, run_id=None, date=None, branch=None,
                     duration_min=None, all_pass=None, quarantine_flips=None,
                     artifact_url=None, reason=None):
    """AC4: dashboard state for the first steady-state green run."""
    if achieved:
        return {
            "achieved": True,
            "run_id": run_id,
            "date": date,
            "branch": branch,
            "duration_min": duration_min,
            "all_pass": all_pass,
            "quarantine_flips": quarantine_flips,
            "artifact_url": artifact_url,
            "definition": "reference/eval-green-run-definition.md",
            "qualified_at": _now_iso(),
        }
    reason = reason or (
        f"No steady-state green run observed as of {_today()}. Earliest candidate "
        f"is the weekly eval-behavioral run on {GREEN_RUN_EARLIEST} on main "
        f"(subsequent candidate: 2026-09-28). RM-002's negative-path canary run "
        f"{RM002_CANARY_RUN} (2026-09-16) is the red counterpart, not a green run. "
        "Qualification also requires the full included suite to fit the <=120 min "
        "weekly budget (see reference/eval-green-run-definition.md)."
    )
    return {
        "achieved": False,
        "reason": reason,
        "candidate_runs": [],
        "definition": "reference/eval-green-run-definition.md",
        "checked_at": _now_iso(),
    }


def _count_included_evals(skills_root=None):
    skills_root = skills_root or os.path.join(REPO_ROOT, "skills")
    total = 0
    for _skill, data in query_runs._iter_eval_manifests(skills_root):
        default_tier = data.get("default_model_tier", "free")
        for e in data.get("evals", []):
            if e.get("deferred"):
                continue
            if e.get("default_model_tier", default_tier) in query_runs.EVAL_TIERS_EXCLUDED:
                continue
            total += 1
    return total


def quota_projection(skills_root=None):
    """AC11: projected monthly CI minutes vs the 1,800 min guardrail."""
    included = _count_included_evals(skills_root)
    weekly_run = round(included * WEEKLY_MIN_PER_EVAL, 1)
    weekly_month = round(weekly_run * WEEKS_PER_MONTH, 1)
    per_change_month = round(PER_CHANGE_RUN_MIN * PRS_PER_MONTH_ASSUMED, 1)
    projected = round(weekly_month + per_change_month, 1)
    return {
        "weekly_run_min": weekly_run,
        "weekly_min_used": weekly_month,
        "per_change_run_min": PER_CHANGE_RUN_MIN,
        "per_change_min_used": per_change_month,
        "prs_per_month_assumed": PRS_PER_MONTH_ASSUMED,
        "projected_monthly": projected,
        "guardrail_limit": GUARDRAIL_LIMIT,
        "updated": _today(),
    }


def _emit(obj, out_path=None, do_print=False):
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")
        print(out_path)
    if do_print or not out_path:
        print(json.dumps(obj, indent=2))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    # SUPPRESS so a value passed before the subcommand is not clobbered by the
    # subparser's default (argparse parents/subparsers namespace gotcha).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--logs-dir", default=argparse.SUPPRESS,
                        help="Log directory (default repo logs/).")
    common.add_argument("--skills-root", default=argparse.SUPPRESS,
                        help="Skills root (default <repo>/skills).")

    p = argparse.ArgumentParser(description="RM-003 eval report artifact builder.",
                                parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("aggregate", parents=[common], help="Per-run eval report (AC1).")
    a.add_argument("--out", default=None)
    a.add_argument("--print", action="store_true")

    g = sub.add_parser("coverage-gaps", parents=[common], help="Coverage-gap report (AC3).")
    g.add_argument("--out", default=None)
    g.add_argument("--print", action="store_true")

    s = sub.add_parser("green-run-status", parents=[common],
                       help="Green-run dashboard state (AC4).")
    s.add_argument("--out", default="green-run-status.json")
    s.add_argument("--print", action="store_true")
    s.add_argument("--record", action="store_true",
                   help="Record a qualifying green run instead of the not-achieved state.")
    s.add_argument("--run-id", default=None)
    s.add_argument("--date", default=None)
    s.add_argument("--branch", default="main")
    s.add_argument("--duration-min", type=float, default=None)
    s.add_argument("--all-pass", action="store_true")
    s.add_argument("--quarantine-flips", type=int, default=0)
    s.add_argument("--artifact-url", default=None)
    s.add_argument("--reason", default=None)

    q = sub.add_parser("quota-projection", parents=[common],
                       help="Monthly quota projection (AC11).")
    q.add_argument("--out", default=None)
    q.add_argument("--print", action="store_true")

    allp = sub.add_parser("all", parents=[common],
                          help="Write all four artifacts to an output dir.")
    allp.add_argument("--out-dir", default=".")

    args = p.parse_args(argv)
    logs_dir = getattr(args, "logs_dir", None) or os.path.join(REPO_ROOT, "logs")
    skills_root = getattr(args, "skills_root", None)

    if args.cmd == "aggregate":
        _emit(aggregate_report(logs_dir), args.out, args.print)
    elif args.cmd == "coverage-gaps":
        _emit(coverage_gaps(logs_dir, skills_root), args.out, args.print)
    elif args.cmd == "green-run-status":
        if args.record:
            achieved = bool(args.run_id and args.date and args.duration_min is not None)
            status = green_run_status(
                achieved=achieved, run_id=args.run_id, date=args.date,
                branch=args.branch, duration_min=args.duration_min,
                all_pass=args.all_pass, quarantine_flips=args.quarantine_flips,
                artifact_url=args.artifact_url, reason=args.reason)
        else:
            status = green_run_status(reason=args.reason)
        _emit(status, args.out, args.print)
    elif args.cmd == "quota-projection":
        _emit(quota_projection(skills_root), args.out, args.print)
    elif args.cmd == "all":
        out_dir = args.out_dir
        os.makedirs(out_dir, exist_ok=True)
        artifacts = {
            "eval-report.json": aggregate_report(logs_dir),
            "coverage-gaps.json": coverage_gaps(logs_dir, skills_root),
            "green-run-status.json": green_run_status(),
            "quota-projection.json": quota_projection(skills_root),
        }
        for name, obj in artifacts.items():
            path = os.path.join(out_dir, name)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=2)
                fh.write("\n")
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
