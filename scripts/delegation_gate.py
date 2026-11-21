#!/usr/bin/env python3
"""Decide and record the delegation vehicle (fail-closed audit gate).

An orchestrator must choose the vehicle mechanically, not by habit: the
in-session subagent tool is only for a short read-only consult in the same
working directory, and everything else runs through the run-vehicle
(`scripts/dispatch_agent.py`). This CLI is that decision, and its JSON record
is the audit trail.

Rules (fail closed — a missing classification is mutating):

  run-vehicle is forced by
    * a role that always runs detached: implementer, reviewer, test-writer,
      debugger, skill-author, skill-reviewer, vision-critic-fast,
      vision-critic-final;
    * any mutating task;
    * an expected duration above 2 minutes;
    * any external directory;
    * live observation;
    * an explicit `--request run-vehicle`.

  subagent is allowed only when the request is `auto` or `subagent`, the role
  is not forced, the task is read-only, there are no external dirs, there is
  no live observation, and the duration is at most 2 minutes.

A refused `--request subagent` exits 2 with every reason and prints the
run-vehicle command; it never prints a usable subagent instruction.

The run-vehicle command carries the full detached, observable form:
`--detach --heartbeat --stream-out --stream-err --delegation-to --wake-to
--wake-agent --task-label --timeout`, plus `--agent` and `--prompt-file`.
Default artifact paths are stable under `.scratch/delegation/`.

Exit 0 on an allowed decision, 2 on refusal or usage error.
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

RUN_VEHICLE_AGENTS = (
    "implementer",
    "reviewer",
    "test-writer",
    "debugger",
    "skill-author",
    "skill-reviewer",
    "vision-critic-fast",
    "vision-critic-final",
)
MAX_SUBAGENT_MINUTES = 2.0
DEFAULT_DIR = os.path.join(".scratch", "delegation")
PARENT_PLACEHOLDER = "<parent-session>"
ORCHESTRATOR_PLACEHOLDER = "<orchestrator-agent>"
PROMPT_PLACEHOLDER = "<prompt-file>"


def _stamp(now=None):
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def _quote(value):
    text = str(value)
    if any(ch.isspace() for ch in text):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def default_paths(agent, stamp=None):
    """Stable artifact paths for one decision (progress, events, stderr, json)."""
    base = os.path.join(DEFAULT_DIR, f"{agent}-{stamp or _stamp()}")
    return {
        "progress": base + ".progress",
        "events": base + ".events",
        "stderr": base + ".stderr",
        "record": base + ".json",
    }


def run_vehicle_reasons(agent, minutes, mutating, external_dirs,
                        live_observation):
    """Every condition that forces the run-vehicle, in a stable order."""
    reasons = []
    if agent in RUN_VEHICLE_AGENTS:
        reasons.append(f"agent role requires the run-vehicle: {agent}")
    if mutating:
        reasons.append("task is mutating (default classification, fail closed)")
    if minutes > MAX_SUBAGENT_MINUTES:
        reasons.append(
            f"expected duration {minutes:g} min > {MAX_SUBAGENT_MINUTES:g} min")
    if external_dirs:
        reasons.append("external directory access: " + ", ".join(external_dirs))
    if live_observation:
        reasons.append("live observation requested")
    return reasons


def build_run_vehicle_command(agent, minutes, paths, prompt_file, parent,
                              orchestrator, label):
    """The exact pre-dispatch run-vehicle command."""
    timeout = max(60, int(math.ceil(minutes * 60)))
    parts = [
        "python3", "scripts/dispatch_agent.py",
        "--agent", _quote(agent),
        "--prompt-file", _quote(prompt_file),
        "--detach",
        "--heartbeat", _quote(paths["progress"]),
        "--stream-out", _quote(paths["events"]),
        "--stream-err", _quote(paths["stderr"]),
        "--delegation-to", _quote(parent),
        "--wake-to", _quote(parent),
        "--wake-agent", _quote(orchestrator),
        "--task-label", _quote(label),
        "--timeout", str(timeout),
    ]
    return " ".join(parts)


def build_subagent_instruction(agent, label):
    """The only permitted in-session form: background, same cwd, read-only."""
    return (f'subagent(agent="{agent}", description="{label}", '
            "background=true) — same cwd, read-only, <= 2 minutes")


def decide(args):
    """Resolve the decision dict and whether the request was refused."""
    mutating = not args.read_only
    external_dirs = list(args.external_dirs or [])
    live_observation = bool(args.live_observation)

    paths = default_paths(args.agent)
    record_path = args.record or paths["record"]
    parent = args.parent_session or PARENT_PLACEHOLDER
    orchestrator = args.orchestrator_agent or ORCHESTRATOR_PLACEHOLDER
    prompt_file = args.prompt_file or PROMPT_PLACEHOLDER
    label = args.task_label or f"{args.agent} delegation"

    run_command = build_run_vehicle_command(
        args.agent, args.minutes, paths, prompt_file, parent, orchestrator,
        label)
    subagent_instruction = build_subagent_instruction(args.agent, label)
    forces = run_vehicle_reasons(
        args.agent, args.minutes, mutating, external_dirs, live_observation)

    refused = False
    if args.request == "run-vehicle":
        vehicle = "run-vehicle"
        command = run_command
        reasons = forces + ["explicitly requested run-vehicle"]
    elif args.request == "subagent":
        if forces:
            refused = True
            vehicle = "run-vehicle"
            command = run_command
            reasons = [f"requested subagent refused: {reason}"
                       for reason in forces]
        else:
            vehicle = "subagent"
            command = subagent_instruction
            reasons = ["requested subagent: short read-only same-cwd consult"]
    else:  # auto
        if forces:
            vehicle = "run-vehicle"
            command = run_command
            reasons = forces
        else:
            vehicle = "subagent"
            command = subagent_instruction
            reasons = ["auto: short read-only same-cwd consult"]

    decision = {
        "agent": args.agent,
        "vehicle": vehicle,
        "reasons": reasons,
        "command": command,
        "record": record_path,
        "minutes": args.minutes,
        "mutating": mutating,
        "external_dirs": external_dirs,
        "live_observation": live_observation,
    }
    return decision, refused


def write_record(record_path, decision):
    directory = os.path.dirname(record_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as fh:
        json.dump(decision, fh, indent=2)
        fh.write("\n")


def render_text(decision, refused):
    lines = [f"vehicle={decision['vehicle']}"]
    if refused:
        lines.append("refused: requested subagent does not meet the gate")
    lines.append("reasons:")
    lines.extend(f"  - {reason}" for reason in decision["reasons"])
    if decision["vehicle"] == "subagent":
        lines.append(
            "constraints: background=true (required), same cwd, read-only, "
            "<= 2 minutes")
    lines.append("command:")
    lines.append(decision["command"])
    lines.append(f"record: {decision['record']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Decide and record the delegation vehicle.")
    ap.add_argument("--agent", required=True, help="Agent name to delegate to.")
    ap.add_argument("--minutes", type=float, required=True,
                    help="Expected wall-clock duration in minutes.")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--mutating", action="store_true",
                       help="Task writes or executes (the default).")
    group.add_argument("--read-only", action="store_true",
                       help="Task only reads; required for a subagent.")
    ap.add_argument("--external-dir", dest="external_dirs", action="append",
                    default=None, metavar="PATH",
                    help="Path outside the working directory (repeatable).")
    live = ap.add_mutually_exclusive_group()
    live.add_argument("--live-observation", dest="live_observation",
                      action="store_true", default=False,
                      help="Needs live event/heartbeat visibility.")
    live.add_argument("--no-live-observation", dest="live_observation",
                      action="store_false",
                      help="No live observation (the default).")
    ap.add_argument("--prompt-file", default=None,
                    help="Prompt file for the run-vehicle command.")
    ap.add_argument("--parent-session", default=None, metavar="ses_...",
                    help="Orchestrator session id (wake/delegation target).")
    ap.add_argument("--orchestrator-agent", default=None,
                    help="Agent the orchestrator session runs as.")
    ap.add_argument("--task-label", default=None,
                    help="Short task label for the delegation title.")
    ap.add_argument("--request", choices=("auto", "subagent", "run-vehicle"),
                    default="auto",
                    help="Explicit vehicle request (default: auto).")
    ap.add_argument("--json", action="store_true",
                    help="Emit the decision object as JSON.")
    ap.add_argument("--record", default=None,
                    help="Write the decision JSON here (default: "
                         ".scratch/delegation/<agent>-<UTC>.json).")
    args = ap.parse_args(argv)

    decision, refused = decide(args)
    write_record(decision["record"], decision)

    if args.json:
        print(json.dumps(decision, indent=2))
    else:
        print(render_text(decision, refused))
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
