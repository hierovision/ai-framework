#!/usr/bin/env python3
"""Contract tests for the shared supervision thresholds (RM-069 AC6/AC8).

The plugin must not re-guess numbers: this asserts the JSON contract matches
its owners and that the named predicates resolve. The TypeScript half (its
DEFAULTS equal this file) is asserted by
`node --test plugins/delegation-observer/state.test.ts`.

Run: python3 scripts/test_supervision_contract.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import supervision_contract as contract  # noqa: E402
import observe_completion  # noqa: E402
import watch_agent  # noqa: E402

FAILS = []


def check(name, condition, detail=""):
    if condition:
        print(f"PASS {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"FAIL {name}: {detail}")


def main():
    payload = contract.contract()
    check("stall window is the watchdog's",
          payload["stall_seconds"] == watch_agent.DEFAULT_STALL_SECONDS,
          payload["stall_seconds"])
    check("call window is the watchdog's",
          payload["call_seconds"] == watch_agent.DEFAULT_CALL_SECONDS,
          payload["call_seconds"])
    check("loop cap is the watchdog's",
          payload["loop_repeats"] == watch_agent.DEFAULT_LOOP_REPEATS,
          payload["loop_repeats"])
    check("generation budget is the watchdog's",
          payload["generation_seconds"] == watch_agent.DEFAULT_GENERATION_SECONDS,
          payload["generation_seconds"])
    check("wake deadline is the observer's",
          payload["terminal_wake_deadline_seconds"] == observe_completion.DEFAULT_DEADLINE,
          payload["terminal_wake_deadline_seconds"])
    check("milestone cap is 30s", payload["milestone_min_interval_seconds"] == 30,
          payload["milestone_min_interval_seconds"])

    on_disk = contract.load()
    check("committed JSON equals the generated contract", on_disk == payload,
          json.dumps(on_disk, sort_keys=True))
    check("no drift check", contract.check() == [], contract.check())

    for name, fn in contract.predicates().items():
        check(f"predicate {name} resolves", callable(fn), repr(fn))

    # Drift must fail loudly, not be tolerated.
    original = watch_agent.DEFAULT_STALL_SECONDS
    try:
        watch_agent.DEFAULT_STALL_SECONDS = original + 1
        errors = contract.check()
        check("drift is detected", bool(errors), errors)
        check("drift names the window", "stall_seconds" in (errors[0] if errors else ""),
              errors)
    finally:
        watch_agent.DEFAULT_STALL_SECONDS = original

    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
