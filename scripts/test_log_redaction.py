#!/usr/bin/env python3
"""Pattern-redaction tests (RM-073 P1-2).

Run: python3 scripts/test_log_redaction.py

Proves the two persistence paths — `log_run.py`'s free-text `detail` and the
eval runner's event-stream/stderr persistence — mask synthetic credentials of
every shape the sweep found (`sk-`, `xoxb-`, `ghp_`, `github_pat_`,
`sb_secret_`, `AKIA…`, PEM blocks) plus a value-match key held in the parent
environment. The raw values must appear nowhere in the output directory.

Hermetic: temp dirs live under `.scratch/test-tmp`, no model, no network.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OBSERVE_SCRIPTS = os.path.join(REPO, "skills", "observing-runs", "scripts")
RUNNER_SCRIPTS = os.path.join(REPO, "skills", "authoring-skills", "scripts")
for path in (HERE, OBSERVE_SCRIPTS, RUNNER_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import log_run  # noqa: E402
import redact  # noqa: E402
import run_behavioral_eval as runner  # noqa: E402

# Synthetic, non-functional credentials. Every value is unique so a raw hit is
# unambiguous.
SECRETS = {
    "provider": "sk-proj-SYNTHETIC0123456789ABCDEF",
    "anthropic": "sk-ant-SYNTHETIC0123456789",
    "slack": "xoxb-000000000000-000000000000-SYNTHETIC",
    "ghp": "ghp_SYNTHETIC0123456789ABCDEFGHIJ",
    "github_pat": "github_pat_11SYNTHETIC0123456789_abcdefghijklmnop",
    "supabase": "sb_secret_SYNTHETIC0123456789",
    "aws": "AKIAIOSFODNN7EXAMPLE",
    "pem": (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0SYNTHETIC0ONLY0NOT0A0REAL0KEY\n"
        "-----END RSA PRIVATE KEY-----"
    ),
}
PEM_MARKER = "MIIEowIBAAKCAQEA0SYNTHETIC0ONLY0NOT0A0REAL0KEY"
ENV_VALUE = "synthetic-env-provider-value-9f3a2b"


def _scratch():
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="redaction-", dir=base)


def _assert_absent(root, values, label):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for key, raw in values.items():
                assert raw not in text, f"{label}: {key} raw value in {path}"


def test_pattern_set_masks_every_shape():
    blob = "\n".join(SECRETS.values())
    out = redact.redact(blob)
    for key, raw in SECRETS.items():
        assert raw not in out, f"pattern redaction missed {key}"
    assert PEM_MARKER not in out
    assert out.count(redact.MASK) >= len(SECRETS)
    # Non-secret text survives unchanged.
    assert redact.redact("eval designing-architecture#1 passed") == \
        "eval designing-architecture#1 passed"
    assert set(redact.redaction_patterns()) >= {
        "pem", "sk-", "xoxb-", "github_pat_", "sb_secret_", "AKIA"}


def test_log_run_redacts_detail_before_append():
    work = _scratch()
    try:
        detail = "tool output: " + " | ".join(SECRETS.values())
        log_run.log_record(
            {"kind": "skill", "outcome": "failure", "detail": detail},
            logs_dir=work,
        )
        _assert_absent(work, SECRETS, "log_run")
        files = [os.path.join(work, f) for f in os.listdir(work)]
        assert files, "no run-log file written"
        with open(files[0], encoding="utf-8") as fh:
            rec = json.loads(fh.readline())
        assert rec["detail"].count(redact.MASK) >= len(SECRETS), rec["detail"]
        # Schema unchanged: only the detail value differs.
        assert rec["kind"] == "skill" and rec["outcome"] == "failure"
        # The 512-char cap is still enforced on the caller's input.
        try:
            log_run.log_record({"kind": "skill", "outcome": "success",
                                "detail": "x" * (log_run.DETAIL_MAX + 1)},
                               logs_dir=work)
        except ValueError as exc:
            assert "detail exceeds" in str(exc)
        else:
            raise AssertionError("detail cap no longer enforced")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_eval_persistence_redacts_streams_and_stderr():
    work = _scratch()
    try:
        res = runner.EvalResult(
            raw="event stream: " + " | ".join(SECRETS.values()),
            stderr="server log: " + " | ".join(SECRETS.values()),
        )
        runner._persist_event_streams(work, {"skill": "designing-architecture",
                                             "eval_id": "1"}, [("final", res)])
        _assert_absent(work, SECRETS, "eval persistence")
        stream_dir = os.path.join(work, "eval-streams")
        assert os.path.isdir(stream_dir) and os.listdir(stream_dir), \
            "eval persistence wrote no stream"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_runner_masks_owned_env_values():
    work = _scratch()
    previous = os.environ.get("OPENCODE_API_KEY")
    os.environ["OPENCODE_API_KEY"] = ENV_VALUE
    try:
        assert ENV_VALUE not in runner._redact(f"key={ENV_VALUE} end")
        log_run.log_record({"kind": "eval", "outcome": "success",
                            "detail": f"key={ENV_VALUE}"}, logs_dir=work)
        _assert_absent(work, {"env": ENV_VALUE}, "runner env value")
    finally:
        if previous is None:
            os.environ.pop("OPENCODE_API_KEY", None)
        else:
            os.environ["OPENCODE_API_KEY"] = previous
        shutil.rmtree(work, ignore_errors=True)


def main():
    tests = [
        test_pattern_set_masks_every_shape,
        test_log_run_redacts_detail_before_append,
        test_eval_persistence_redacts_streams_and_stderr,
        test_runner_masks_owned_env_values,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"{'FAIL' if failed else 'OK'}: {len(tests) - failed}/{len(tests)} redaction tests")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
