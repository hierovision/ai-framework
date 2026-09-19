#!/usr/bin/env python3
"""Manage the eval quarantine list (RM-003 AC9).

An eval that fails on 3 consecutive runs is moved to `quarantined` and
excluded from the default eval run (like `deferred: true`). A success
resets the consecutive-failure counter (so an eval must fail *consecutively*
to be quarantined). Quarantined evals are surfaced by the coverage-gap
report (`coverage-gaps.json` -> `quarantined_evals`).

**CI-owned**: this file is written by the CI eval runs (weekly
`eval-behavioral` + per-change `eval-per-change`). The optional local
Layer 2 advisory pre-push run MUST call `run_behavioral_eval.py
--no-quarantine` so local runs never touch it.

State file: `logs/quarantine.json` (override with `--quarantine-file`).
Entry shape:

    {
      "writing-unit-tests#3": {
        "fail_count": 3, "first_fail": "2026-09-15",
        "last_fail": "2026-09-18", "status": "quarantined"
      }
    }

CLI:
    quarantine.py mark <skill>#<eval_id> [--count N]
    quarantine.py check <skill>#<eval_id>      # exit 0 = quarantined
    quarantine.py list
    quarantine.py clear <skill>#<eval_id>
    [--quarantine-file PATH | --logs-dir DIR]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_QUARANTINE_FILE = os.path.join(REPO_ROOT, "logs", "quarantine.json")

THRESHOLD = 3


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _resolve(path=None, logs_dir=None):
    if path:
        return path
    if logs_dir:
        return os.path.join(logs_dir, "quarantine.json")
    return DEFAULT_QUARANTINE_FILE


def load(path=None):
    """Return the quarantine mapping; missing/corrupt file -> {}."""
    path = path or DEFAULT_QUARANTINE_FILE
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save(path, data):
    path = path or DEFAULT_QUARANTINE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _status_for(count, threshold=THRESHOLD):
    return "quarantined" if count >= threshold else "watching"


def record_failure(path, key, today=None, threshold=THRESHOLD):
    """Increment the consecutive-failure count; return the written entry."""
    today = today or _today()
    data = load(path)
    entry = data.get(key) or {"fail_count": 0, "first_fail": today,
                              "last_fail": today, "status": "watching"}
    entry["fail_count"] = int(entry.get("fail_count", 0)) + 1
    entry.setdefault("first_fail", today)
    entry["last_fail"] = today
    entry["status"] = _status_for(entry["fail_count"], threshold)
    data[key] = entry
    save(path, data)
    return entry


def record_success(path, key):
    """Reset/remove an entry on success (consecutive semantics). Returns True if removed."""
    data = load(path)
    if key in data:
        del data[key]
        save(path, data)
        return True
    return False


def mark(path, key, count=1, today=None, threshold=THRESHOLD):
    """Force `count` failures (CLI `mark`; default 1)."""
    entry = None
    for _ in range(count):
        entry = record_failure(path, key, today=today, threshold=threshold)
    return entry


def clear(path, key):
    return record_success(path, key)


def quarantined_keys(path=None):
    """Return the set of keys whose status is `quarantined`."""
    return {k for k, v in load(path).items()
            if isinstance(v, dict) and v.get("status") == "quarantined"}


def is_quarantined(path, key):
    return key in quarantined_keys(path)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Manage the eval quarantine list.")
    p.add_argument("--quarantine-file", default=None,
                   help="Quarantine file (default repo logs/quarantine.json).")
    p.add_argument("--logs-dir", default=None,
                   help="Logs dir; quarantine file is <logs-dir>/quarantine.json.")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mark", help="Record failure(s) for an eval key.")
    m.add_argument("key", help="<skill>#<eval_id>")
    m.add_argument("--count", type=int, default=1, help="Failures to add (default 1).")

    c = sub.add_parser("check", help="Exit 0 if the key is quarantined.")
    c.add_argument("key")

    sub.add_parser("list", help="Print the quarantine JSON.")

    clr = sub.add_parser("clear", help="Remove an eval key from quarantine.")
    clr.add_argument("key")

    args = p.parse_args(argv)
    path = _resolve(args.quarantine_file, args.logs_dir)

    if args.cmd == "mark":
        entry = mark(path, args.key, count=args.count)
        print(json.dumps({"key": args.key, **entry}))
        return 0
    if args.cmd == "check":
        quarantined = is_quarantined(path, args.key)
        print(json.dumps({"key": args.key, "quarantined": quarantined}))
        return 0 if quarantined else 1
    if args.cmd == "list":
        print(json.dumps(load(path), indent=2, sort_keys=True))
        return 0
    if args.cmd == "clear":
        removed = clear(path, args.key)
        print(json.dumps({"key": args.key, "removed": removed}))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
