#!/usr/bin/env python3
"""Run the behavioral (fresh-agent) eval suite and gate on regressions.

For every skill's `evals/evals.json`, launch a fresh agent session with the
skill installed, capture its final output, and assert each
`expected_behavior` entry is present (case-insensitive substring). Any miss
fails the build and writes an `eval_pass=false` run-log record via RM-001's
`log_run.py` (single source of truth — the schema is NOT redefined here).

Offline gate: the assertion logic + listing/subset logic are pure and
testable without a model (see test_runner.py, which injects a stub agent).
The real agent invocation (`invoke_opencode`) is only used in CI, where the
model-access credential (a repository secret) is present.

Free-tier adherence (GitHub Free, private repo): the companion workflow runs
WEEKLY (not nightly) and supports `--limit` / `--skill` subset sharding so a
full run stays within the 2,000 min/month cap.

Deferral: evals flagged `deferred: true` (real-browser / harness-unavailable)
are excluded from the default run. `default_model_tier` (top-level) selects the
tier; both are additive, backward-compatible extensions to the eval protocol.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))  # skills/authoring-skills/scripts
SKILLS_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OBSERVE_SCRIPTS = os.path.join(SKILLS_ROOT, "observing-runs", "scripts")
if OBSERVE_SCRIPTS not in sys.path:
    sys.path.insert(0, OBSERVE_SCRIPTS)
import log_run  # RM-001 single source of truth (AC2)

DETAIL_MAX = log_run.DETAIL_MAX


def load_skill_evals(skills_root):
    """Yield normalized eval entries from every skill's evals/evals.json."""
    out = []
    if not os.path.isdir(skills_root):
        return out
    for name in sorted(os.listdir(skills_root)):
        ev_path = os.path.join(skills_root, name, "evals", "evals.json")
        if not os.path.isfile(ev_path):
            continue
        try:
            data = json.load(open(ev_path, encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        tier = data.get("default_model_tier", "free")
        for e in data.get("evals", []):
            out.append({
                "skill": name,
                "eval_id": e.get("id"),
                "prompt": e.get("prompt", ""),
                "expected_behavior": e.get("expected_behavior", []),
                "deferred": bool(e.get("deferred", False)),
                "model_tier": e.get("default_model_tier", tier),
                "files": e.get("files", []),
            })
    return out


def filter_evals(evals, include_deferred=False, limit=None, skill=None, ci_mode=False):
    out = []
    for e in evals:
        if e["deferred"]:
            if not include_deferred:
                continue
        elif ci_mode and e["model_tier"] in ("go", "zen"):
            continue  # paid tiers excluded from CI by rm-002 Model-cost policy
        out.append(e)
    if skill:
        out = [e for e in out if e["skill"] == skill]
    if limit is not None:
        out = out[:limit]
    return out


def assert_behavior(expected, output):
    """Return the list of expected strings NOT found (case-insensitive substring)."""
    out_l = (output or "").lower()
    return [exp for exp in expected if exp.lower() not in out_l]


def run_eval(e, get_output, logs_dir=None):
    """Run one eval via `get_output(e)`, assert, and write a run-log record.

    Returns (passed, missing, record_path).
    """
    output = get_output(e)
    missing = assert_behavior(e["expected_behavior"], output)
    passed = not missing
    detail = None
    if missing:
        detail = ("missing expected_behavior: " + " | ".join(missing))[:DETAIL_MAX]
    rec = {
        "kind": "eval",
        "skill": e["skill"],
        "agent": None,
        "model": e["model_tier"],
        "outcome": "success" if passed else "failure",
        "eval_pass": passed,
        "detail": detail,
    }
    path = log_run.log_record(rec, logs_dir=logs_dir)
    return passed, missing, path


def invoke_opencode(e):
    """Real fresh-agent invocation (CI only; needs the model credential).

    Best-effort: copy the eval's fixture files to a temp working dir, prompt a
    fresh `opencode` session with the skill installed, return its final output.
    Exact headless subcommand / skill-install semantics depend on opencode's
    current CLI (see plan OQ1) — verify before relying on this in production.
    """
    tmp = tempfile.mkdtemp(prefix="beval-")
    try:
        for rel in e["files"]:
            src = os.path.join(SKILLS_ROOT, e["skill"], "evals", rel)
            if os.path.exists(src):
                dst = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)
        # The model credential must already be in the environment (repo secret);
        # it is consumed here, never echoed.
        proc = subprocess.run(
            ["opencode", "run", "--skill", e["skill"], e["prompt"]],
            cwd=tmp, capture_output=True, text=True,
            env=os.environ,
        )
        return proc.stdout + proc.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Run behavioral eval suite.")
    p.add_argument("--list", action="store_true",
                   help="Print the included eval set and exit (no agent calls).")
    p.add_argument("--include-deferred", action="store_true",
                   help="Also include evals flagged deferred:true.")
    p.add_argument("--limit", type=int, default=None,
                   help="Run only the first N included evals (subset sharding).")
    p.add_argument("--skill", default=None,
                   help="Run only evals for this skill (subset sharding).")
    p.add_argument("--logs-dir", default=None,
                   help="Log directory (default repo logs/).")
    p.add_argument("--skills-root", default=SKILLS_ROOT,
                   help="Override the skills root (testing).")
    p.add_argument("--ci", action="store_true",
                   help="Enforce free-tier-only (skip go/zen evals); also auto-enabled "
                        "by AI_FRAMEWORK_FREE_TIER or CI env.")
    p.add_argument("--stub-output", default=None,
                   help="Hermetic test mode: use this fixed output for every eval "
                        "instead of invoking opencode. 'ALL' passes every eval; "
                        "':MISS:' prefix marks an intentionally-failing run.")
    args = p.parse_args(argv)

    all_evals = load_skill_evals(args.skills_root)
    ci_mode = args.ci or bool(os.environ.get("AI_FRAMEWORK_FREE_TIER")) or bool(os.environ.get("CI"))
    selected = filter_evals(all_evals, include_deferred=args.include_deferred,
                            limit=args.limit, skill=args.skill, ci_mode=ci_mode)

    if args.list:
        print(f"included evals: {len(selected)}")
        for e in selected:
            tag = "deferred" if e["deferred"] else "eval"
            print(f"  [{tag}] {e['skill']}#{e['eval_id']} (tier={e['model_tier']})")
        return 0

    if not selected:
        print("no evals selected", file=sys.stderr)
        return 0

    def get_output(e):
        if args.stub_output is not None:
            if args.stub_output.startswith(":MISS:"):
                # omit the first expected behavior to force a failure
                return "\n".join(e["expected_behavior"][1:])
            return "\n".join(e["expected_behavior"])  # ALL
        return invoke_opencode(e)

    failed = 0
    for e in selected:
        passed, missing, path = run_eval(e, get_output, logs_dir=args.logs_dir)
        status = "PASS" if passed else "FAIL"
        print(f"{status}  {e['skill']}#{e['eval_id']}  -> {path}")
        if not passed:
            failed += 1
            for m in missing:
                print(f"      missing: {m[:120]}")

    if failed:
        print(f"\n{failed} eval(s) failed regression gate", file=sys.stderr)
        return 1
    print("\nall included evals passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
