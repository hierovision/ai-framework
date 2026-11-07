#!/usr/bin/env python3
"""Eval child-env allowlist tests (RM-073 P1-3).

Run: python3 scripts/test_eval_env.py

Asserts `run_behavioral_eval.sandbox_env` keeps only the allowlisted keys:
`AWS_*`, `AZURE_*`, `SLACK_*`, `SUPABASE_*`, `GH_TOKEN` and `GITHUB_TOKEN` are
absent while `PATH`, `HOME`, `OPENCODE_API_KEY` and `DEEPSEEK_API_KEY` remain,
and the runner's own `BEVAL_*` configuration never reaches the child.

Hermetic: pure function, no model, no network.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OBSERVE_SCRIPTS = os.path.join(REPO, "skills", "observing-runs", "scripts")
RUNNER_SCRIPTS = os.path.join(REPO, "skills", "authoring-skills", "scripts")
for path in (HERE, OBSERVE_SCRIPTS, RUNNER_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import run_behavioral_eval as runner  # noqa: E402

MUST_KEEP = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/home/synthetic",
    "PWD": "/tmp/beval-work",
    "TMPDIR": "/tmp/beval-tmp",
    "XDG_CONFIG_HOME": "/tmp/beval-config",
    "XDG_STATE_HOME": "/tmp/beval-state",
    "XDG_CACHE_HOME": "/tmp/beval-cache",
    "OPENCODE_API_KEY": "synthetic-opencode-key",
    "DEEPSEEK_API_KEY": "synthetic-deepseek-key",
    "OPENCODE_LOG_LEVEL": "ERROR",
    "OPENCODE_DB": "/tmp/beval.db",
    "OPENCODE_CONFIG_CONTENT": "{}",
}

MUST_DROP = {
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "synthetic-aws-secret",
    "AWS_SESSION_TOKEN": "synthetic-session",
    "AZURE_STATIC_WEB_APPS_API_TOKEN": "synthetic-azure-token",
    "AZURE_CLIENT_SECRET": "synthetic-azure-secret",
    "SLACK_BOT_TOKEN": "xoxb-synthetic",
    "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_synthetic",
    "SUPABASE_DB_URL": "postgres://synthetic",
    "GH_TOKEN": "ghp_synthetic",
    "GITHUB_TOKEN": "ghp_synthetic",
    "GITHUB_ACTIONS": "true",
    "GITHUB_WORKSPACE": "/home/runner/work/repo",
    "RUNNER_TEMP": "/home/runner/work/_temp",
    "BEVAL_FALLBACK_ENABLED": "1",
    "BEVAL_MAX_CONTINUATIONS": "2",
    "BEVAL_TIMEOUT_SECONDS": "240",
    "BEVAL_STARTUP_LOG": "1",
    "UNRELATED_SECRET": "synthetic-unrelated",
}


def _synthetic_env():
    env = dict(MUST_KEEP)
    env.update(MUST_DROP)
    return env


def test_blocked_keys_are_absent():
    child = runner.sandbox_env(_synthetic_env())
    for key in MUST_KEEP:
        assert key in child, f"allowlisted key dropped: {key}"
    for key in MUST_DROP:
        assert key not in child, f"non-allowlisted key leaked: {key}"
    for prefix in ("AWS_", "AZURE_", "SLACK_", "SUPABASE_", "GITHUB_",
                   "RUNNER_", "BEVAL_"):
        leaked = [k for k in child if k.startswith(prefix)]
        assert not leaked, f"{prefix} leaked: {leaked}"


def test_allowlist_is_not_a_denylist():
    """A novel credential-shaped key must also be dropped (allowlist proof)."""
    env = _synthetic_env()
    env["SOME_FUTURE_PROVIDER_KEY"] = "synthetic-future-key"
    child = runner.sandbox_env(env)
    assert "SOME_FUTURE_PROVIDER_KEY" not in child
    assert set(child) == set(MUST_KEEP) & set(env), sorted(set(child))


def test_no_side_effects_on_parent():
    env = _synthetic_env()
    before = dict(env)
    runner.sandbox_env(env)
    assert env == before, "sandbox_env mutated the parent environment mapping"


def test_runner_beval_config_stays_in_parent():
    """The runner reads BEVAL_* from `os.environ`; the child must not see it."""
    child = runner.sandbox_env(dict(MUST_KEEP, BEVAL_FALLBACK_ENABLED="1"))
    assert "BEVAL_FALLBACK_ENABLED" not in child
    assert runner.os.environ is os.environ  # parent process untouched


def main():
    tests = [
        test_blocked_keys_are_absent,
        test_allowlist_is_not_a_denylist,
        test_no_side_effects_on_parent,
        test_runner_beval_config_stays_in_parent,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"{'FAIL' if failed else 'OK'}: {len(tests) - failed}/{len(tests)} eval-env tests")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
