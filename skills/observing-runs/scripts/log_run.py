#!/usr/bin/env python3
"""Append one run-log record to a JSONL file (one line per run).

This is the SINGLE SOURCE OF TRUTH for the run-log schema (see
references/schema.md). Every consumer (skills, agents, the RM-002 eval
runner, RM-009 ROI / RM-011 drift scripts) MUST call this helper rather
than redefining field names.

ROI guardrail (see SKILL.md / the plan):
  - Append-only, non-blocking, out-of-context: this script writes exactly
    one line to disk and NEVER reads any prior log content back. Logs are
    never fed into an agent's live prompt.
  - Per-run granularity: one record per run, NOT per internal sub-step.
  - Symlink-safe: paths are resolved via realpath(argv[0]) so a symlinked
    install (e.g. ~/.config/opencode/skills/observing-runs) resolves to the
    real script directory (matches the library's ESM/CLI run-as-main rule).
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

# Real, symlink-safe script location.
SCRIPT_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
# repo root = two levels up from skills/observing-runs/scripts/
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_LOGS_DIR = os.environ.get("OBSERVE_LOG_DIR", os.path.join(REPO_ROOT, "logs"))

# Fields that MUST be present in the caller's record (no safe default).
REQUIRED_FIELDS = ("kind", "outcome")

# Field -> type (or tuple of allowed types). Used for validation + defaults.
FIELD_TYPES = {
    "ts": str,
    "run_id": str,
    "kind": str,
    "skill": (str, type(None)),
    "agent": (str, type(None)),
    "model": (str, type(None)),
    "tokens_in": int,
    "tokens_out": int,
    "duration_ms": int,
    "outcome": str,
    "eval_pass": (bool, type(None)),
    "detail": (str, type(None)),
}

# Allowed enum values.
KIND_VALUES = ("skill", "agent", "eval")
OUTCOME_VALUES = ("success", "failure", "error", "stopped")
DETAIL_MAX = 512


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_record(rec):
    """Return (ok, error_message). `rec` is the caller-supplied mapping."""
    if not isinstance(rec, dict):
        return False, "record must be a JSON object"
    for f in REQUIRED_FIELDS:
        if f not in rec or rec[f] is None:
            return False, f"required field '{f}' is missing or null"
    for f, allowed in FIELD_TYPES.items():
        if f not in rec:
            continue
        v = rec[f]
        if not isinstance(v, allowed):
            return False, f"field '{f}' has wrong type (expected {allowed})"
    if rec.get("kind") not in KIND_VALUES:
        return False, f"kind must be one of {KIND_VALUES}"
    if rec.get("outcome") not in OUTCOME_VALUES:
        return False, f"outcome must be one of {OUTCOME_VALUES}"
    if rec.get("detail") is not None and len(rec["detail"]) > DETAIL_MAX:
        return False, f"detail exceeds {DETAIL_MAX} char cap"
    return True, ""


def build_record(rec):
    """Return a complete, well-formed record (fills defaults)."""
    out = {}
    for f, allowed in FIELD_TYPES.items():
        if f in rec and rec[f] is not None:
            out[f] = rec[f]
    out.setdefault("ts", utc_now_iso())
    out.setdefault("run_id", str(uuid.uuid4()))
    out.setdefault("skill", None)
    out.setdefault("agent", None)
    out.setdefault("model", None)
    out.setdefault("tokens_in", 0)
    out.setdefault("tokens_out", 0)
    out.setdefault("duration_ms", 0)
    out.setdefault("eval_pass", None)
    out.setdefault("detail", None)
    return out


def log_record(rec, logs_dir=None):
    """Validate + append one line. Returns the written path. Raises on error."""
    ok, err = validate_record(rec)
    if not ok:
        raise ValueError(err)
    record = build_record(rec)
    logs_dir = logs_dir or DEFAULT_LOGS_DIR
    os.makedirs(logs_dir, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(logs_dir, f"run-{date}.jsonl")
    # Append-only single write; never reads the file back (out-of-context guard).
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
    return path


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Append one run-log record (JSONL).")
    p.add_argument("--record", required=True,
                   help="JSON object with the run-log fields (kind + outcome required).")
    p.add_argument("--logs-dir", default=None,
                   help="Override log directory (default: repo-root logs/).")
    p.add_argument("--selftest", action="store_true",
                   help="Write a temp record to a temp dir, print, remove; exit 0 if OK.")
    args = p.parse_args(argv)

    try:
        rec = json.loads(args.record)
    except json.JSONDecodeError as e:
        print(f"error: --record is not valid JSON: {e}", file=sys.stderr)
        return 2

    if args.selftest:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="observe-selftest-")
        try:
            path = log_record(rec, logs_dir=tmp)
            with open(path, encoding="utf-8") as fh:
                print(fh.read().strip())
            os.remove(path)
            os.rmdir(tmp)
        except Exception as e:  # noqa: BLE001
            print(f"selftest failed: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        path = log_record(rec, logs_dir=args.logs_dir)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
