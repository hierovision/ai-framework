#!/usr/bin/env python3
"""Table-driven tests for the delegation-vehicle gate.

Each case runs the CLI in a subprocess and asserts the decision, the exit
code, and the emitted command. Records go to temp paths (or a temp cwd) so
nothing is written into the repo and nothing is dispatched.

Run: python3 scripts/test_delegation_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
GATE = os.path.join(HERE, "delegation_gate.py")
REQUIRED_JSON_KEYS = {
    "agent", "vehicle", "reasons", "command", "record", "minutes",
    "mutating", "external_dirs", "live_observation",
}
REQUIRED_RUN_FLAGS = (
    "--detach", "--heartbeat", "--stream-out", "--stream-err",
    "--delegation-to", "--wake-to", "--wake-agent", "--task-label",
    "--timeout", "--agent", "--prompt-file",
)

FAILS = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} {name}"
          + ("" if condition else f": {detail}"))
    if not condition:
        FAILS.append(name)


def run_gate(args, cwd=None):
    proc = subprocess.run(
        [sys.executable, GATE, *args],
        cwd=cwd or REPO, capture_output=True, text=True,
    )
    return proc


def json_case(args, record):
    proc = run_gate([*args, "--json", "--record", record])
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return proc, {"_error": str(exc), "_stdout": proc.stdout}


def main():
    with tempfile.TemporaryDirectory(prefix="delegation-gate-") as tmp:
        # --- vehicle decisions -------------------------------------------------
        cases = [
            ("reviewer 0.5 min read-only -> run-vehicle (role)",
             ["--agent", "reviewer", "--minutes", "0.5", "--read-only"],
             "run-vehicle"),
            ("implementer 1 min -> run-vehicle",
             ["--agent", "implementer", "--minutes", "1"],
             "run-vehicle"),
            ("explore 1 min read-only -> subagent",
             ["--agent", "explore", "--minutes", "1", "--read-only"],
             "subagent"),
            ("explore 5 min -> run-vehicle",
             ["--agent", "explore", "--minutes", "5", "--read-only"],
             "run-vehicle"),
            ("explore mutating -> run-vehicle",
             ["--agent", "explore", "--minutes", "1"],
             "run-vehicle"),
            ("explore external dir -> run-vehicle",
             ["--agent", "explore", "--minutes", "1", "--read-only",
              "--external-dir", os.path.join(tmp, "outside")],
             "run-vehicle"),
            ("explore live observation -> run-vehicle",
             ["--agent", "explore", "--minutes", "1", "--read-only",
              "--live-observation"],
             "run-vehicle"),
            ("request run-vehicle for a short consult -> run-vehicle",
             ["--agent", "explore", "--minutes", "0.5", "--read-only",
              "--request", "run-vehicle"],
             "run-vehicle"),
        ]
        for index, (name, args, expected) in enumerate(cases):
            record = os.path.join(tmp, f"case-{index}.json")
            proc, data = json_case(args, record)
            check(f"rc 0: {name}", proc.returncode == 0,
                  (proc.returncode, proc.stderr))
            check(f"vehicle {expected}: {name}",
                  data.get("vehicle") == expected, data)
            check(f"json keys: {name}",
                  REQUIRED_JSON_KEYS <= set(data), sorted(data))

        # --- subagent instruction shape ---------------------------------------
        sub_record = os.path.join(tmp, "subagent.json")
        proc = run_gate(["--agent", "explore", "--minutes", "1",
                         "--read-only", "--record", sub_record])
        check("subagent rc 0", proc.returncode == 0, proc.stderr)
        check("subagent output says subagent", "subagent" in proc.stdout,
              proc.stdout)
        check("subagent output requires background=true",
              "background=true" in proc.stdout, proc.stdout)
        check("subagent output states same-cwd read-only 2-minute constraints",
              all(token in proc.stdout.lower()
                  for token in ("same cwd", "read-only", "2 minutes")),
              proc.stdout)

        # --- run-vehicle command carries the required flags -------------------
        rv_record = os.path.join(tmp, "reviewer.json")
        proc, data = json_case(
            ["--agent", "reviewer", "--minutes", "0.5", "--read-only",
             "--parent-session", "ses_orchestrator",
             "--orchestrator-agent", "architect",
             "--task-label", "review pass",
             "--prompt-file", ".scratch/prompt.md"],
            rv_record)
        command = data.get("command", "")
        missing = [flag for flag in REQUIRED_RUN_FLAGS if flag not in command]
        check("run-vehicle command carries every required flag",
              not missing, missing)
        check("run-vehicle command carries the caller values",
              "ses_orchestrator" in command and "architect" in command
              and "review pass" in command
              and ".scratch/prompt.md" in command, command)
        check("run-vehicle default artifact paths are under .scratch/delegation",
              ".scratch/delegation/" in command
              and ".progress" in command
              and ".events" in command
              and ".stderr" in command, command)

        # --- refused subagent requests ---------------------------------------
        refused = [
            ("reviewer", ["--agent", "reviewer", "--minutes", "0.5",
                          "--read-only", "--request", "subagent"]),
            ("implementer", ["--agent", "implementer", "--minutes", "1",
                             "--request", "subagent"]),
        ]
        for index, (name, args) in enumerate(refused):
            record = os.path.join(tmp, f"refused-{index}.json")
            proc = run_gate([*args, "--record", record])
            check(f"refuses subagent for {name} (rc 2)",
                  proc.returncode == 2, proc.returncode)
            check(f"refusal names reasons for {name}",
                  "reasons:" in proc.stdout and "refused" in proc.stdout,
                  proc.stdout)
            check(f"refusal prints the run-vehicle command for {name}",
                  "--detach" in proc.stdout and "dispatch_agent.py" in proc.stdout,
                  proc.stdout)
            check(f"refusal prints no usable subagent instruction for {name}",
                  "background=true" not in proc.stdout, proc.stdout)
            json_proc, data = json_case(args, record)
            check(f"refusal JSON vehicle is run-vehicle for {name}",
                  json_proc.returncode == 2
                  and data.get("vehicle") == "run-vehicle", data)
            check(f"refusal JSON has no subagent command for {name}",
                  "background=true" not in data.get("command", ""), data)

        # --- usage error ------------------------------------------------------
        proc = run_gate(["--agent", "explore", "--read-only",
                         "--record", os.path.join(tmp, "no-minutes.json")])
        check("missing --minutes -> rc 2", proc.returncode == 2, proc.returncode)

        # --- JSON shape, record parity, default record path -------------------
        parity_record = os.path.join(tmp, "parity.json")
        proc, data = json_case(
            ["--agent", "explore", "--minutes", "1", "--read-only"],
            parity_record)
        check("json shape is exactly the stable object",
              set(data) == REQUIRED_JSON_KEYS, sorted(data))
        with open(parity_record, encoding="utf-8") as fh:
            stored = json.load(fh)
        check("record file matches the JSON decision", stored == data,
              (stored, data))

        default_cwd = os.path.join(tmp, "cwd")
        os.makedirs(default_cwd)
        proc = run_gate(
            ["--agent", "explore", "--minutes", "1", "--read-only", "--json"],
            cwd=default_cwd)
        data = json.loads(proc.stdout)
        rel = data["record"].replace(os.sep, "/")
        check("default record path stays under .scratch/delegation/",
              rel.startswith(".scratch/delegation/")
              and rel.endswith(".json"), rel)
        check("default record file is written",
              os.path.isfile(os.path.join(default_cwd, data["record"])),
              data["record"])

    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
