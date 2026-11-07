#!/usr/bin/env python3
"""Agent permission tests (RM-073 P1-4).

Run: python3 scripts/test_agent_permissions.py

Two controls, both cheap and structural:

1. The auth/session store (`$HOME/.local/share/opencode`) is not a read root
   for ANY dispatch profile. It holds the OpenCode credentials and the session
   DB; granting it to an agent class made every dispatched run able to read
   them.
2. Every leaf persona denies the `subagent` tool. V2 evaluates ordered
   permission rules LAST-match-wins, so the test reads the final `subagent`
   rule, not merely that a deny exists somewhere.

Hermetic: parses tracked JSON/frontmatter, no model, no network.
"""
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROFILES = os.path.join(HERE, "dispatch-profiles.json")
AGENTS_DIR = os.path.join(REPO, "agents")
AUTH_STORE = os.path.expanduser("~/.local/share/opencode")

# Leaf personas (the plan names these explicitly). `council.md` is the
# orchestrator and may delegate; the `council-*` lenses may not.
LEAF_AGENTS = ["planner", "reviewer", "skill-reviewer",
               "vision-critic-fast", "vision-critic-final"] + [
    stem[:-3] for stem in sorted(os.listdir(AGENTS_DIR))
    if stem.startswith("council-") and stem.endswith(".md")
]


def _profile_dirs(profile):
    return [os.path.expanduser(os.path.expandvars(d))
            for d in profile.get("allow_dirs") or []]


def test_auth_store_is_not_an_allow_root():
    with open(PROFILES, encoding="utf-8") as fh:
        data = json.load(fh)
    for name, profile in data.items():
        if name.startswith("_") or not isinstance(profile, dict):
            continue
        dirs = _profile_dirs(profile)
        assert AUTH_STORE not in dirs, f"profile {name} still grants the auth store"
        for path in ("$HOME/.local/share/opencode", "~/.local/share/opencode",
                     os.path.join(os.path.expanduser("~"), ".local", "share", "opencode")):
            assert path not in (profile.get("allow_dirs") or []), \
                f"profile {name} still lists {path}"


def test_profiles_keep_repo_roots():
    """The fix must be narrow: repo/config roots stay."""
    with open(PROFILES, encoding="utf-8") as fh:
        data = json.load(fh)
    for name in ("architect", "reviewer", "council", "planner"):
        dirs = (data[name].get("allow_dirs") or [])
        assert "$HOME/repos" in dirs, (name, dirs)
        assert "$HOME/.config/opencode" in dirs, (name, dirs)


def _frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    parts = text.split("---")
    assert len(parts) >= 3, f"{path}: no YAML frontmatter"
    return yaml.safe_load(parts[1]) or {}


def _last_subagent_effect(permissions):
    effect = None
    for rule in permissions or []:
        if isinstance(rule, dict) and rule.get("action") == "subagent":
            effect = rule.get("effect")
    return effect


def test_leaf_agents_deny_subagent():
    assert "council-security" in LEAF_AGENTS, LEAF_AGENTS
    for name in LEAF_AGENTS:
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        assert os.path.isfile(path), f"missing agent file: {path}"
        meta = _frontmatter(path)
        effect = _last_subagent_effect(meta.get("permissions"))
        assert effect == "deny", f"{name}: last subagent rule is {effect!r}"


def main():
    tests = [
        test_auth_store_is_not_an_allow_root,
        test_profiles_keep_repo_roots,
        test_leaf_agents_deny_subagent,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"{'FAIL' if failed else 'OK'}: {len(tests) - failed}/{len(tests)} agent-permission tests")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
