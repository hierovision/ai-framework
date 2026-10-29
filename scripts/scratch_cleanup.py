#!/usr/bin/env python3
"""Bounded cleanup for per-run scratch directories (F12).

Two surfaces accumulate without a lifecycle:

* `.scratch/dispatch-config/run-*` — a generated config per dispatch. A failed
  dispatch should keep its tree for diagnosis; successful runs and stale
  failures should not accumulate forever.
* `.scratch/test-tmp/*` — hermetic-test workdirs and logs, including the
  behavioral-eval fixtures. A killed/failed test leaves its directory behind.

The policy is count + age bounded: never delete the newest `keep` entries and
never delete anything younger than `max_age_seconds`. Cleanup is best-effort
and never raises into the caller's main path.
"""
import os
import shutil
import time

DEFAULT_KEEP = 5
DEFAULT_MAX_AGE = 7 * 86400
TEST_KEEP = 20
TEST_MAX_AGE = 2 * 86400


def _stat(entry):
    try:
        return entry.stat(follow_symlinks=False)
    except OSError:
        return None


def prune_run_configs(root, keep=DEFAULT_KEEP, max_age_seconds=DEFAULT_MAX_AGE,
                      prefix="run-", now=None):
    """Remove `prefix*` entries beyond `keep` or older than `max_age_seconds`.

    Newest entries survive first. Returns the removed paths (diagnostics and
    tests only; callers ignore the result on the hot path).
    """
    if not root or not os.path.isdir(root):
        return []
    current = time.time() if now is None else now
    entries = []
    try:
        for entry in os.scandir(root):
            if not entry.name.startswith(prefix):
                continue
            info = _stat(entry)
            if info is not None:
                entries.append((info.st_mtime, entry))
    except OSError:
        return []
    entries.sort(key=lambda pair: pair[0], reverse=True)
    removed = []
    for index, (mtime, entry) in enumerate(entries):
        stale = index >= keep or (current - mtime) > max_age_seconds
        if not stale:
            continue
        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path, ignore_errors=True)
            else:
                os.unlink(entry.path)
        except OSError:
            continue
        removed.append(entry.path)
    return removed


def cleanup_run_config(path, outcome):
    """Delete a generated dispatch config after a successful run.

    Failures keep the tree as evidence; the next dispatch's prune bounds it.
    """
    if not path or outcome != "success":
        return
    shutil.rmtree(path, ignore_errors=True)


def prune_test_scratch(base=None, keep=TEST_KEEP,
                       max_age_seconds=TEST_MAX_AGE):
    """Bound `.scratch/test-tmp` (or an explicit base) before a test run."""
    if base is None:
        repo = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        base = os.path.join(repo, ".scratch", "test-tmp")
    return prune_run_configs(base, keep=keep, max_age_seconds=max_age_seconds,
                             prefix="")
