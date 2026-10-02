#!/usr/bin/env python3
"""RED-first tests for scripts/dispatch_agent.py (plan agent-teams-dispatch AC5/AC6/AC7).

Hermetic: a stub `opencode` on PATH emits canned `--format json` streams; no
model calls, no network. Cases per the plan: valid / empty / malformed /
timeout, plus the emitted run-log record's agent/model/outcome and the
printed session id.

Run: python3 scripts/test_dispatch_agent.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
DISPATCH = os.path.join(HERE, "dispatch_agent.py")

# The stub mimics `opencode run --agent <n> --format json <prompt>`: a
# newline-delimited JSON stream with `sessionID` on every event, `text`
# parts carrying the final output, and `step_finish` parts carrying
# tokens/cost (the shapes probed live 2026-10-02).
STUB_OPENCODE = '''#!/usr/bin/env python3
"""Stub opencode for scripts/test_dispatch_agent.py (no model calls)."""
import json
import os
import sys
import time

mode = os.environ.get("STUB_MODE", "valid")
argv = sys.argv[1:]
assert "run" in argv, argv
assert "--format" in argv, argv


def emit(obj):
    print(json.dumps(obj), flush=True)


def start(sid):
    emit({"type": "step_start", "sessionID": sid,
          "part": {"type": "step-start", "sessionID": sid}})


if mode == "timeout":
    start("ses_stub_timeout")
    time.sleep(30)  # dispatch_agent's --timeout must kill the group
    sys.exit(0)

if mode == "nonzero":
    start("ses_stub_err")
    print("provider exploded", file=sys.stderr)
    sys.exit(1)

if mode == "empty":
    sys.exit(0)

if mode == "malformed":
    start("ses_stub_malformed")
    print("this line is not json")
    sys.exit(0)

# valid
sid = "ses_stub_valid"
start(sid)
emit({"type": "text", "sessionID": sid,
      "part": {"type": "text", "sessionID": sid,
               "text": "Verification: all green\\nHandoff: ready"}})
emit({"type": "step_finish", "sessionID": sid,
      "part": {"type": "step-finish", "tokens": {"input": 100, "output": 50},
               "cost": 0.0012}})
'''


def _run(mode, extra=None, timeout="10"):
    """Invoke dispatch_agent.py against the stub -> result namespace."""
    assert os.path.isfile(DISPATCH), "scripts/dispatch_agent.py missing (red-first)"
    td = tempfile.mkdtemp(prefix="dispatch-test-")
    try:
        bin_dir = os.path.join(td, "bin")
        os.makedirs(bin_dir)
        stub = os.path.join(bin_dir, "opencode")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write(STUB_OPENCODE)
        os.chmod(stub, 0o755)

        prompt = os.path.join(td, "prompt.md")
        with open(prompt, "w", encoding="utf-8") as fh:
            fh.write("Do the thing.")

        out = os.path.join(td, "result.md")
        logs = os.path.join(td, "logs")
        cmd = [
            sys.executable, DISPATCH, "--agent", "architect",
            "--prompt-file", prompt, "--out", out, "--logs-dir", logs,
            "--timeout", timeout,
        ] + list(extra or [])
        env = dict(os.environ)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env["STUB_MODE"] = mode

        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              cwd=REPO, timeout=60)
        elapsed = time.monotonic() - started

        records = []
        if os.path.isdir(logs):
            for name in sorted(os.listdir(logs)):
                if not name.endswith(".jsonl"):
                    continue
                with open(os.path.join(logs, name), encoding="utf-8") as fh:
                    records += [json.loads(l) for l in fh if l.strip()]
        result_text = ""
        if os.path.isfile(out):
            with open(out, encoding="utf-8") as fh:
                result_text = fh.read()
        return SimpleNamespace(rc=proc.returncode, stdout=proc.stdout,
                               stderr=proc.stderr, records=records,
                               result_text=result_text, elapsed=elapsed)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_valid_dispatch_records_attribution():
    """AC5+AC6+AC7: exit 0, session id printed, result written, one
    kind=agent record carrying agent + resolved model + tokens/cost."""
    r = _run("valid", extra=["--contract", "implement-handoff"])
    assert r.rc == 0, (r.rc, r.stdout, r.stderr)
    assert "session_id=ses_stub_valid" in r.stdout, r.stdout
    assert "Verification" in r.result_text, r.result_text
    assert len(r.records) == 1, r.records
    rec = r.records[0]
    assert rec["kind"] == "agent", rec
    assert rec["agent"] == "architect", rec
    assert rec["model"] == "opencode/nemotron-3-ultra-free", rec
    assert rec["outcome"] == "success", rec
    assert rec["tokens_in"] == 100 and rec["tokens_out"] == 50, rec
    assert abs(rec["cost"] - 0.0012) < 1e-9, rec
    assert rec["detail"] is None, rec
    # a --model override wins over the frontmatter binding
    r2 = _run("valid", extra=["--model", "opencode-go/kimi-k3"])
    assert r2.rc == 0, (r2.rc, r2.stderr)
    assert r2.records[0]["model"] == "opencode-go/kimi-k3", r2.records[0]


def test_empty_result_fails_contract():
    """AC5: an empty stream exits non-zero and the record is not success."""
    r = _run("empty", extra=["--contract", "implement-handoff"])
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] in ("error", "failure"), r.records
    assert r.records[0]["detail"], r.records


def test_malformed_result_fails_contract():
    """AC5: a non-JSON stream exits non-zero and the record is not success."""
    r = _run("malformed", extra=["--contract", "implement-handoff"])
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] in ("error", "failure"), r.records
    assert r.records[0]["detail"], r.records


def test_timeout_kills_and_records_error():
    """AC5: a stalled run is killed at --timeout, exits non-zero, records
    outcome=error with a timeout detail."""
    r = _run("timeout", timeout="1")
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.elapsed < 15, r.elapsed
    assert r.records and r.records[0]["outcome"] == "error", r.records
    assert "timeout" in (r.records[0]["detail"] or "").lower(), r.records


def test_nonzero_exit_records_error():
    """Coverage gate (Step 9b): a non-zero opencode exit is outcome=error
    with the exit code in the detail — the provider/process error branch."""
    r = _run("nonzero")
    assert r.rc != 0, (r.rc, r.stdout)
    assert r.records and r.records[0]["outcome"] == "error", r.records
    assert "exited 1" in (r.records[0]["detail"] or ""), r.records


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
