#!/usr/bin/env python3
"""Policy tests for the Go-first model policy (plan go-first-model-bindings).

Two halves, both hermetic (no network, no model calls):

  - repo assertions: every `agents/*.md` binding is the planned Go default,
    the core routing table is Go-default / free-opt-in, the hard-exclusion
    list is present and applied, CONCEPTS/routing carry no free-first
    phrasing, and `ci-lane-overrides.py` yields an empty agent map;
  - fixture-driven failure classes: synthetic repos fed to the same policy
    checker (`model-liveness-check.py`) prove it fails on (a) a bound
    `-free` ID, (b) a bound hard-excluded ID, (c) a routing-table Go cell
    absent from the Go catalog; plus the AC3(d) probe contract: a >20s
    responder is classified not-live, the probe shape carries the documented
    endpoint + `x-opencode-session` + a bare catalog ID, protocol-unsupported
    is not death, and the timeout can never be extended past 20s.

Run: python3 scripts/test_model_policy.py
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)

# --- the policy: planned bindings per plan go-first-model-bindings ---------

EXPECTED_AGENT_BINDINGS = {
    "architect": "opencode-go/glm-5.3-flash",
    "planner": "opencode-go/glm-5.3-flash",
    "curator": "opencode-go/glm-5.3-flash",
    "implementer": "opencode-go/deepseek-v4.1-flash",
    "test-writer": "opencode-go/deepseek-v4.1-flash",
    "debugger": "opencode-go/mimo-v2.6-pro",
    "reviewer": "opencode-go/mimo-v2.6-pro",
    "skill-reviewer": "opencode-go/mimo-v2.6-pro",
    "skill-author": "opencode-go/minimax-m3",
    "vision-critic-fast": "opencode-go/minimax-m3",
    "vision-critic-final": "opencode-go/deepseek-v4.1-flash",
    "council": "opencode-go/qwen3.8-flash",
    "council-performance": "opencode-go/gpt-5.6-luna",
    "council-architecture": "opencode-go/glm-5.3-flash",
    "council-security": "opencode-go/deepseek-v4.1-flash",
    "council-ux": "opencode-go/minimax-m3",
    "council-product": "opencode-go/mimo-v2.6-flash",
}

EXCLUDED_IDS = ("kimi-k3", "glm-5.3", "glm-5.2", "gpt-6-luna", "grok-4.5",
                "claude-fable-5", "gpt-6-astra", "claude-sonnet-5")

# A minimal routing fixture for the failure-class tests. `ghost-2` is the
# absent-Go-cell case (digit-bearing so the token heuristic sees it).
FIXTURE_ROUTING = """# Model Routing (fixture)

Retrieval: 2026-10-03. Free use is an explicit opt-in
(`AI_FRAMEWORK_FREE_TIER=1` or a per-session model switch).

## Core routing table

| Role | Default — Go flat-rate | Free opt-in | Zen PAYG | Bench basis |
|---|---|---|---|---|
| `planner` | glm-5.3-flash | nemotron-3-ultra-free | claude-opus-5-5 | fixture |

## Hard exclusions

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `kimi-k3` | Go, Zen | fixture cost directive (2026-10-03) |
| `gpt-6-luna` | Go, Zen | fixture CI canary directive (2026-10-03) |
| `glm-5.3` | Go, Zen | fixture cost directive (2026-10-01) |
| `glm-5.2` | Go, Zen | fixture cost directive (2026-10-01) |
"""

# The fixture routing table's Zen cell references claude-opus-5-5 and its
# free cell nemotron-3-ultra-free; every fixture catalog carries both.
FIXTURE_ZEN = {"nemotron-3-ultra-free", "claude-opus-5-5"}


def _load_checker():
    """Import scripts/model-liveness-check.py by path (dash in the filename)."""
    path = os.path.join(HERE, "model-liveness-check.py")
    spec = importlib.util.spec_from_file_location("model_liveness_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CHECKER = _load_checker()


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def _fixture_repo(agents, routing=FIXTURE_ROUTING):
    root = tempfile.mkdtemp(prefix="model-policy-")
    os.makedirs(os.path.join(root, "agents"))
    for name, model in agents.items():
        with open(os.path.join(root, "agents", name + ".md"), "w",
                  encoding="utf-8") as fh:
            fh.write(f"---\nname: {name}\nmodel: {model}\n---\nbody\n")
    os.makedirs(os.path.join(root, "reference"))
    with open(os.path.join(root, "reference", "model-routing.md"), "w",
              encoding="utf-8") as fh:
        fh.write(routing)
    return root


# --- repo assertions (AC1, AC2, AC4, AC5(ish), AC7) ------------------------


def test_all_agents_bind_the_planned_go_defaults():
    """AC1: every persona binds the planned Go default — no `-free`, no
    excluded ID."""
    bound = CHECKER.agent_bindings(REPO)
    assert set(bound) == {f"agents/{n}.md" for n in EXPECTED_AGENT_BINDINGS}, bound
    for name, model in EXPECTED_AGENT_BINDINGS.items():
        got = bound[f"agents/{name}.md"]
        assert got == model, (name, got, model)


def test_check_policy_clean_on_this_repo():
    """AC1/AC2: the shipped policy checker finds zero violations on the real
    repo (catalog membership is the live canary's half)."""
    errors = CHECKER.check_policy(REPO, None)
    assert errors == [], errors


def test_routing_table_is_go_default_free_optin():
    """AC2: the core table's first data column is the Go default, the second
    is the free opt-in; no `-free` token sits in a default cell."""
    text = _read(os.path.join("reference", "model-routing.md"))
    section = text.split("## Core routing table", 1)[1].split("\n## ", 1)[0]
    header = next(l for l in section.splitlines() if l.startswith("| Role"))
    cells = [c.strip() for c in header.strip().strip("|").split("|")]
    assert "Go" in cells[1], header
    assert "Free" in cells[2] and "opt-in" in cells[2].lower(), header
    rows = CHECKER.routing_table_rows(REPO)
    assert rows, "routing table rows missing"
    for role, default_cell, free_cell, _zen in rows:
        for token in CHECKER.id_tokens(default_cell):
            assert not token.endswith("-free"), (role, default_cell)
        for token in CHECKER.id_tokens(free_cell):
            assert token.endswith("-free"), (role, free_cell)


def test_exclusions_are_explicit_and_above_scores():
    """AC2: kimi-k3 / glm-5.3 / glm-5.2 / gpt-6-luna are hard-excluded with
    the peak-tier note and the exclusions-above-all-scores clause."""
    text = _read(os.path.join("reference", "model-routing.md"))
    section = text.split("## Hard exclusions", 1)[1]
    for excluded in ("kimi-k3", "glm-5.3", "glm-5.2", "gpt-6-luna"):
        assert f"`{excluded}`" in section, f"missing exclusion: {excluded}"
    lowered = section.lower()
    assert "peak" in lowered, "peak-tier note missing"
    assert "above all scores" in lowered, "above-all-scores clause missing"
    assert "gpt-5.5" in section, "peak-tier class member gpt-5.5 missing"


def test_free_is_optin_in_docs():
    """AC4: CONCEPTS §7c and routing document the opt-in; the old free-first
    phrasing is absent."""
    concepts = _read(os.path.join("docs", "CONCEPTS.md"))
    routing = _read(os.path.join("reference", "model-routing.md"))
    for rel, text in (("docs/CONCEPTS.md", concepts),
                      ("reference/model-routing.md", routing)):
        assert "free-first" not in text.lower(), f"{rel}: free-first phrasing"
        assert "AI_FRAMEWORK_FREE_TIER=1" in text, f"{rel}: opt-in toggle missing"
    lowered = concepts.lower()
    assert "go by default" in lowered, "CONCEPTS §7c not retitled"
    assert "free by default" not in lowered, "CONCEPTS still says free-by-default"


def test_council_six_distinct_go_seats():
    """AC5: six seats, six distinct Go bindings, no excluded ID."""
    seats = ["council", "council-performance", "council-architecture",
             "council-security", "council-ux", "council-product"]
    bound = CHECKER.agent_bindings(REPO)
    models = [bound[f"agents/{s}.md"] for s in seats]
    assert len(set(models)) == 6, models
    for model in models:
        assert model.startswith("opencode-go/"), model
        assert CHECKER.is_excluded(model, {}) is None, model
    for rel in ("agents/council.md", "docs/COUNCIL.md"):
        text = _read(rel)
        assert "kimi-k3" not in text, f"{rel}: kimi-k3 still referenced"
        for aliases in ("council-performance", "council-product"):
            assert aliases in text, f"{rel}: seat {aliases} missing"


def test_ci_lane_overrides_yields_empty_agent_map():
    """AC7: no persona is free-bound, so the CI override is an empty agent
    map with the /tmp permission block kept."""
    out = subprocess.run(
        [sys.executable, os.path.join(HERE, "ci-lane-overrides.py"),
         "--model", "opencode-go/deepseek-v4.1-flash", "--repo", REPO],
        capture_output=True, text=True, check=True).stdout
    cfg = json.loads(out)
    assert cfg["agent"] == {}, cfg
    assert cfg["permission"]["external_directory"]["/tmp/**"] == "allow", cfg


# --- fixture-driven failure classes (AC3) ----------------------------------


def test_free_binding_fails_check():
    """AC3(a): a bound `-free` ID is a policy failure."""
    repo = _fixture_repo({"bad": "opencode/nemotron-3-ultra-free"})
    errors = CHECKER.check_policy(
        repo, {"go": {"glm-5.3-flash"}, "zen": FIXTURE_ZEN,
               "docs": "nemotron-3-ultra-free"})
    assert any("free" in e for e in errors), errors


def test_excluded_binding_fails_check():
    """AC3(b): a bound hard-excluded ID (kimi-k3) is a policy failure even
    though the live catalog lists it."""
    repo = _fixture_repo({"bad": "opencode-go/kimi-k3"})
    errors = CHECKER.check_policy(repo, {"go": {"kimi-k3"}, "zen": FIXTURE_ZEN,
                                         "docs": ""})
    assert any("kimi-k3" in e and "excluded" in e for e in errors), errors
    # gpt-6-luna too (3/3 CI canary failures, 2026-10-03)
    repo2 = _fixture_repo({"bad": "opencode-go/gpt-6-luna"})
    errors2 = CHECKER.check_policy(repo2, {"go": {"gpt-6-luna"},
                                           "zen": FIXTURE_ZEN, "docs": ""})
    assert any("gpt-6-luna" in e for e in errors2), errors2


def test_free_token_in_default_column_fails_check():
    """AC2: a free opt-in ID in the routing default column is a violation."""
    routing = FIXTURE_ROUTING.replace("| glm-5.3-flash |",
                                      "| nemotron-3-ultra-free |")
    repo = _fixture_repo({"good": "opencode-go/glm-5.3-flash"}, routing=routing)
    errors = CHECKER.check_policy(
        repo, {"go": {"glm-5.3-flash"}, "zen": FIXTURE_ZEN,
               "docs": "nemotron-3-ultra-free"})
    assert any("default column" in e for e in errors), errors


def test_missing_go_cell_fails_check():
    """AC3(c): a routing-table Go cell absent from the live Go catalog is a
    policy failure."""
    routing = FIXTURE_ROUTING.replace("| glm-5.3-flash |", "| ghost-2 |")
    repo = _fixture_repo({"good": "opencode-go/ghost-2"}, routing=routing)
    errors = CHECKER.check_policy(
        repo, {"go": {"glm-5.3-flash"}, "zen": FIXTURE_ZEN, "docs": ""})
    assert any("ghost-2" in e and "Go catalog" in e for e in errors), errors


def test_clean_fixture_passes():
    """The policy checker passes a clean Go-first fixture (failability
    control — the failure cases above fail for their stated reason)."""
    repo = _fixture_repo({"good": "opencode-go/glm-5.3-flash"})
    errors = CHECKER.check_policy(
        repo, {"go": {"glm-5.3-flash"}, "zen": FIXTURE_ZEN,
               "docs": "nemotron-3-ultra-free"})
    assert errors == [], errors


def test_hard_exclusions_cover_families():
    """The exclusion evaluator covers the family/peak classes, without
    false-positives on allowed near-neighbours."""
    exclusions = CHECKER.hard_exclusions(REPO)
    for excluded in EXCLUDED_IDS:
        assert CHECKER.is_excluded(excluded, exclusions), excluded
    assert CHECKER.is_excluded("grok-4.7", exclusions)  # family, not table row
    assert CHECKER.is_excluded("gpt-5.5", exclusions)   # peak class
    for allowed in ("glm-5.3-flash", "kimi-k2.7-code", "gpt-5.6-luna",
                    "mimo-v2.6-pro", "deepseek-v4.1-flash"):
        assert CHECKER.is_excluded(allowed, exclusions) is None, allowed


# --- probe contract (AC3(d)) ------------------------------------------------


class _FakeResponse:
    def __init__(self, body=b'{"choices":[{"message":{"content":"OK"}}]}'):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _recording_opener(capture, response=None):
    def opener(req, timeout=None):
        capture["url"] = req.full_url
        capture["headers"] = {k.lower(): v for k, v in req.header_items()}
        capture["body"] = json.loads(req.data.decode("utf-8"))
        capture["timeout"] = timeout
        return response or _FakeResponse()
    return opener


def test_probe_shape_endpoint_session_bare_id():
    """AC3(d): the probe POSTs the trivial prompt to /zen/go/v1 with the
    x-opencode-session header and a BARE catalog ID (no lane prefix)."""
    capture = {}
    result = CHECKER.probe("opencode-go/deepseek-v4.1-flash", tier="go",
                           api_key="test-key", session_id="ses_test",
                           opener=_recording_opener(capture))
    assert result["live"] is True, result
    assert capture["url"] == "https://opencode.ai/zen/go/v1/chat/completions", \
        capture["url"]
    assert capture["headers"].get("x-opencode-session") == "ses_test", capture
    assert capture["headers"].get("authorization") == "Bearer test-key", capture
    assert capture["body"]["model"] == "deepseek-v4.1-flash", capture["body"]
    assert capture["body"]["messages"][0]["content"] == "Reply with exactly: OK", \
        capture["body"]
    assert capture["timeout"] == 20, capture
    # Zen tier targets the Zen endpoint
    capture2 = {}
    CHECKER.probe("opencode/glm-5.3-flash", tier="zen", api_key="k",
                  session_id="s", opener=_recording_opener(capture2))
    assert capture2["url"] == "https://opencode.ai/zen/v1/chat/completions", \
        capture2["url"]
    assert capture2["body"]["model"] == "glm-5.3-flash", capture2["body"]


def test_probe_timeout_is_not_live_and_never_extended():
    """AC3(d): a >20s responder is 'not live for that check' and the timeout
    is never extended to rescue it."""
    capture = {}

    def timeout_opener(req, timeout=None):
        capture["timeout"] = timeout
        raise TimeoutError("timed out")

    result = CHECKER.probe("opencode-go/mimo-v2.6-pro", tier="go",
                           api_key="k", session_id="s",
                           opener=timeout_opener)
    assert result["live"] is False, result
    assert "20s" in result["reason"], result
    assert capture["timeout"] == 20, capture
    try:
        CHECKER.probe("opencode-go/mimo-v2.6-pro", tier="go", api_key="k",
                      session_id="s", timeout=90, opener=timeout_opener)
        raise AssertionError("probe accepted a >20s timeout")
    except ValueError:
        pass


def test_probe_http_error_is_not_live():
    """AC3(d): a non-protocol HTTP error (e.g. 401) is a dead probe, not a
    protocol statement."""
    def unauthorized_opener(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"invalid key"}}'))

    result = CHECKER.probe("opencode-go/glm-5.3-flash", tier="go",
                           api_key="bad", session_id="s",
                           opener=unauthorized_opener)
    assert result["live"] is False, result
    assert result["protocol_unsupported"] is False, result
    assert "401" in result["reason"], result


def test_probe_protocol_unsupported_is_not_death():
    """AC3(d)/OQ9: a chat-completions 400 ModelProtocolUnsupported is
    classified as protocol-unsupported, not as a dead candidate."""
    def unsupported_opener(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {},
            io.BytesIO(b'{"error":{"code":"ModelProtocolUnsupported"}}'))

    result = CHECKER.probe("opencode-go/gpt-5.6-luna", tier="go",
                           api_key="k", session_id="s",
                           opener=unsupported_opener)
    assert result["live"] is False, result
    assert result["protocol_unsupported"] is True, result
    assert "/responses" in result["reason"], result


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001 — every red is reported
            failed += 1
            print(f"FAIL  {test.__name__}: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
