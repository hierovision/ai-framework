#!/usr/bin/env python3
"""Structural checks for the delegated-result contract (RM-023).

Asserts the contract doc exists with the rule text, and that every delegating
surface cites it and states the rule. Run:
python3 scripts/test_delegated_result_contract.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
CONTRACT = "reference/delegated-result-contract.md"

SURFACES = [
    "agents/council.md",
    "docs/COUNCIL.md",
    "skills/designing-architecture/SKILL.md",
    "skills/validating-ui/SKILL.md",
    "skills/reviewing-code/SKILL.md",
    "skills/implementing-features/SKILL.md",
]

# (a) empty/malformed = failed run, never clean; (b) transient vs deterministic
# recovery; (c) the outcome is recorded.
PHRASES = [
    "delegated-result-contract",
    "empty or malformed",
    "failed run",
    "transient",
    "deterministic",
    "record",
]


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        # Normalize whitespace: the rule text wraps across markdown line
        # breaks and the assertions are phrase-level, not line-level.
        return re.sub(r"\s+", " ", fh.read())


def test_contract_doc_exists_and_has_rule_text():
    text = _read(CONTRACT)
    for phrase in PHRASES:
        assert phrase in text, f"{CONTRACT}: missing {phrase!r}"


def test_every_surface_cites_and_states_the_rule():
    for rel in SURFACES:
        text = _read(rel)
        for phrase in PHRASES:
            assert phrase in text, f"{rel}: missing {phrase!r}"


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
