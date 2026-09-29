#!/usr/bin/env python3
"""Merge per-shard eval logs into one logs dir for the report job.

The weekly suite is sharded across jobs (wall time, not cost, is the
constraint: measured 70-300 s per eval). Each shard writes the same
date-stamped `run-<date>.jsonl` filename, so naive artifact merging would
overwrite shards. This concatenates run logs and merges quarantine state
(max consecutive-fail count, latest last_fail, status recomputed) into
`<out-dir>` and moves each shard's `eval-streams/` files in (stream names are
skill-scoped, and shards are disjoint by skill, so they never collide).

CLI: merge-eval-logs.py --out <dir> <shard-logs-dir> [<shard-logs-dir> ...]

Output JSON summary on stdout: {"run_records": N, "streams": N, "quarantine_keys": N}
"""
import argparse
import glob
import json
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import quarantine  # single source of truth for quarantine shape


def merge(out_dir, shard_dirs):
    os.makedirs(out_dir, exist_ok=True)
    run_records = 0
    merged_path = os.path.join(out_dir, "run-merged.jsonl")
    with open(merged_path, "w", encoding="utf-8") as out:
        for d in shard_dirs:
            for path in sorted(glob.glob(os.path.join(d, "run-*.jsonl"))):
                if os.path.abspath(path) == os.path.abspath(merged_path):
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if line.strip():
                            out.write(line if line.endswith("\n") else line + "\n")
                            run_records += 1
    # Quarantine: max fail_count, latest last_fail per key (status recomputed).
    qpath = os.path.join(out_dir, "quarantine.json")
    merged = {}
    for d in shard_dirs:
        for key, entry in quarantine.load(os.path.join(d, "quarantine.json")).items():
            cur = merged.get(key)
            if cur is None:
                merged[key] = dict(entry)
                continue
            count = max(int(cur.get("fail_count", 0)), int(entry.get("fail_count", 0)))
            cur["fail_count"] = count
            cur["first_fail"] = min(filter(None, [cur.get("first_fail"), entry.get("first_fail")]))
            cur["last_fail"] = max(filter(None, [cur.get("last_fail"), entry.get("last_fail")]))
            cur["status"] = quarantine._status_for(count)
    if merged:
        quarantine.save(qpath, merged)
    # Streams: disjoint by skill; copy into one eval-streams/ dir.
    streams = 0
    sdir = os.path.join(out_dir, "eval-streams")
    for d in shard_dirs:
        src = os.path.join(d, "eval-streams")
        if not os.path.isdir(src):
            continue
        os.makedirs(sdir, exist_ok=True)
        for name in sorted(os.listdir(src)):
            shutil.copy2(os.path.join(src, name), os.path.join(sdir, name))
            streams += 1
    return {"run_records": run_records, "streams": streams,
            "quarantine_keys": len(merged)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args(argv)
    print(json.dumps(merge(a.out, a.dirs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
