#!/usr/bin/env python3
"""Validate a Task-delegated agent result against a declared report contract.

RM-023. An empty or malformed delegated result is a failed run, never a clean
one; this script makes that mechanical. A result is VALID only when it carries
non-whitespace content AND every marker in its contract (whitespace-normalized,
case-insensitive).

Usage:
  validate_delegated_result.py --contract council-lens --file result.md
  validate_delegated_result.py --contract implement-handoff --stdin
  validate_delegated_result.py --markers Findings,Recommendation --file r.md
  validate_delegated_result.py --list-contracts

Exit 0 = valid; 1 = invalid (empty / malformed / unknown contract); 2 = usage.
"""
import argparse
import re
import sys

# Named report contracts. Markers are matched case-insensitively as substrings
# after whitespace normalization. See reference/delegated-result-contract.md.
CONTRACTS = {
    "council-lens": ["Findings", "Recommendation"],
    "implement-handoff": ["Verification", "Handoff"],
    "design-consult": ["Consult outcome"],
}


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def validate(text, markers):
    """Return (ok, missing). `missing` is None when the result is empty."""
    norm = _norm(text)
    if not norm:
        return False, None
    missing = [m for m in markers if _norm(m) not in norm]
    return (not missing), missing


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", help="Named contract (see --list-contracts).")
    ap.add_argument("--markers", help="Comma-separated markers (overrides --contract).")
    ap.add_argument("--file", dest="path", help="Path to the delegated result.")
    ap.add_argument("--stdin", action="store_true", help="Read the result from stdin.")
    ap.add_argument("--list-contracts", action="store_true",
                    help="Print the named contracts and exit.")
    args = ap.parse_args(argv)

    if args.list_contracts:
        print("\n".join(sorted(CONTRACTS)))
        return 0

    if args.markers:
        markers = [m.strip() for m in args.markers.split(",") if m.strip()]
    elif args.contract:
        if args.contract not in CONTRACTS:
            print(f"unknown contract: {args.contract}")
            return 1
        markers = CONTRACTS[args.contract]
    else:
        print("error: pass --contract or --markers")
        return 2

    if args.stdin:
        text = sys.stdin.read()
    elif args.path:
        try:
            with open(args.path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"cannot read result: {exc}")
            return 1
    else:
        print("error: pass --file or --stdin")
        return 2

    ok, missing = validate(text, markers)
    if ok:
        print(f"valid: {len(markers)} marker(s) present")
        return 0
    if missing is None:
        print("invalid: empty result")
        return 1
    print(f"invalid: missing marker(s): {', '.join(missing)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
