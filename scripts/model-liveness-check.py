#!/usr/bin/env python3
"""Model-liveness + Go-first policy canary ("model doctor").

Two jobs in one canary:

1. Drift/availability (the original check that caught the 2026-09-02
   `deepseek-v4-flash-free` failure): every model ID this repo binds or
   documents is actually routable where it claims to be, using live
   catalog + docs evidence.
2. Go-first policy (plan go-first-model-bindings, 2026-10-03): no bound
   `-free` ID, no bound hard-excluded ID (parsed from the routing file's
   Hard exclusions section — kimi-k3, glm-5.3, glm-5.2, gpt-6-luna, the
   grok/sonnet/fable/astra families, the peak $10/$50 class), and every
   routing-table Go cell present in the live Go catalog.

The liveness probe contract (AC3d, 2026-10-03): `--probe` sends the trivial
prompt `Reply with exactly: OK` with a **20s cap** against
`POST https://opencode.ai/zen/go/v1/chat/completions` (`/zen/v1/*` for Zen),
**bare catalog IDs** (no lane prefix in the gateway request), and the
required `x-opencode-session` header. A candidate that cannot answer within
20s is "not live for that check" — the timeout is never extended to rescue
it. The old `https://opencode.ai/api/*` endpoints are not used (they 404).
A chat-completions `ModelProtocolUnsupported` 400 is reported as
protocol-unsupported (verify via `/responses` through the opencode path),
never as death.

Failure classes (exit 1, each printed):
  - a bound free (`*-free`) ID (free is opt-in only);
  - a bound hard-excluded ID (the routing file's Hard exclusions);
  - a Go default/routing cell missing from the Go catalog;
  - a bound Zen/direct ID missing from its catalog;
  - a free opt-in cell that is not docs-listed / not in the Zen catalog;
  - a documented ID bound nowhere.

Usage:
  python3 scripts/model-liveness-check.py [--repo <repo-root>]
  OPENCODE_API_KEY=... python3 scripts/model-liveness-check.py --probe
"""

import argparse
import glob
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid

ZEN_CATALOG = "https://opencode.ai/zen/v1/models"
GO_CATALOG = "https://opencode.ai/zen/go/v1/models"
DOCS_ENDPOINTS = "https://opencode.ai/docs/zen/#endpoints"
GO_CHAT_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
ZEN_CHAT_ENDPOINT = "https://opencode.ai/zen/v1/chat/completions"
PROBE_TIMEOUT_SECONDS = 20
PROBE_PROMPT = "Reply with exactly: OK"

UA = {"User-Agent": "ai-framework-model-liveness-check"}

# Family / class exclusions stated in the routing file's closing paragraph.
# The table rows themselves are parsed from the document (single source of
# truth); these cover the prose rules that are not table rows.
EXCLUDED_FAMILY_PREFIXES = ("grok-",)
EXCLUDED_FAMILY_SUBSTRINGS = ("sonnet",)
EXCLUDED_PEAK_PREFIXES = ("claude-fable-",)
EXCLUDED_PEAK_SUBSTRINGS = ("astra",)
PEAK_TIER_IDS = ("gpt-5.5", "gpt-5.5-pro")
GLM_COST_CLASS = ("glm-5.3", "glm-5.2")
GLM_COST_ALLOWED = ("glm-5.3-flash",)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def catalog_ids(text: str) -> set:
    return set(re.findall(r'"id"\s*:\s*"([a-z0-9][a-z0-9.\-]*)"', text))


def agent_bindings(repo: str) -> dict:
    out = {}
    for path in sorted(glob.glob(os.path.join(repo, "agents", "*.md"))):
        with open(path, encoding="utf-8") as fh:
            match = re.search(r"^model:\s*(\S+)\s*$", fh.read(), re.MULTILINE)
        if match:
            out[os.path.relpath(path, repo)] = match.group(1)
    return out


def routing_table_rows(repo: str) -> list:
    """Yield (role, default_cell, free_cell, zen_cell) from the Core routing table.

    The Go-first table (2026-10-03) leads with the Go default column and
    documents free as the opt-in column.
    """
    with open(os.path.join(repo, "reference", "model-routing.md"), encoding="utf-8") as fh:
        text = fh.read()
    section = text.split("## Core routing table", 1)[1]
    section = section.split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] == "Role":
            continue
        rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def id_tokens(cell: str) -> set:
    """Model-ID-looking tokens: lowercase id-shaped, containing a digit
    (the digit heuristic cleanly separates IDs from prose like
    'alt', 'peak', 'native multimodal').

    Only escalation annotations (`alt ...`, `peak ...`) are bindings and
    are checked; other parentheticals are explanatory cross-references to
    another tier's row (e.g. "(qwen3.7-max is Go-only IF leader)" in a Zen
    cell) and are excluded — annotate any new escalation with alt/peak."""
    cell = re.sub(r"\((?!(?:alt|peak)\b)[^)]*\)", "", cell)
    return {t for t in re.findall(r"[a-z0-9][a-z0-9.\-]*", cell) if re.search(r"\d", t)}


def hard_exclusions(repo: str) -> dict:
    """{bare_id: reason} from the routing file's Hard exclusions table."""
    path = os.path.join(repo, "reference", "model-routing.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    exclusions = {}
    if "## Hard exclusions" in text:
        section = text.split("## Hard exclusions", 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            if not line.startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells or cells[0] == "Excluded ID":
                continue
            for excluded in re.findall(r"`([a-z0-9][a-z0-9.\-]*)`", cells[0]):
                exclusions[excluded] = cells[2] if len(cells) > 2 else "hard-excluded"
    return exclusions


def is_excluded(model_id: str, exclusions: dict):
    """Return the exclusion reason for a model ID (bare or prefixed), else None.

    Exclusions sit above all scores (routing file): a live probe or a top
    benchmark result never overrides one.
    """
    bare = model_id.split("/", 1)[-1]
    if bare in exclusions:
        return exclusions[bare]
    if bare.startswith(EXCLUDED_FAMILY_PREFIXES):
        return "grok family excluded (2026-08-14)"
    if any(s in bare for s in EXCLUDED_FAMILY_SUBSTRINGS):
        return "all sonnet IDs eliminated (2026-09-18)"
    if bare.startswith(EXCLUDED_PEAK_PREFIXES) or \
            any(s in bare for s in EXCLUDED_PEAK_SUBSTRINGS):
        return "peak-pricing class ($10/$50 tier)"
    if bare in PEAK_TIER_IDS:
        return "peak-pricing class ($10/$50 tier)"
    for prefix in GLM_COST_CLASS:
        if bare.startswith(prefix) and bare not in GLM_COST_ALLOWED:
            return "GLM cost class (2026-10-01; glm-5.3-flash is the allowed row)"
    return None


def check_policy(repo: str, catalogs=None) -> list:
    """Go-first policy violations for a repo checkout.

    `catalogs` is {"go": set, "zen": set, "docs": str} for live membership
    checks, or None for a hermetic policy-only pass.
    """
    errors = []
    exclusions = hard_exclusions(repo)

    for rel, model in sorted(agent_bindings(repo).items()):
        bare = model.split("/", 1)[-1]
        if bare.endswith("-free"):
            errors.append(f"{rel}: bound free ID {model} — free is opt-in only")
        reason = is_excluded(model, exclusions)
        if reason:
            errors.append(f"{rel}: bound hard-excluded ID {model} ({reason})")
        if catalogs:
            prefix = model.split("/", 1)[0] if "/" in model else ""
            if prefix == "opencode-go":
                if bare not in catalogs["go"]:
                    errors.append(f"{rel}: {model} not in Go catalog")
            elif prefix != "deepseek":
                if bare not in catalogs["zen"]:
                    errors.append(f"{rel}: {model} not in Zen catalog")

    for role, default_cell, free_cell, zen_cell in routing_table_rows(repo):
        for token in id_tokens(default_cell):
            if token.endswith("-free"):
                errors.append(f"routing row `{role}`: free {token} in the default column")
            reason = is_excluded(token, exclusions)
            if reason:
                errors.append(f"routing row `{role}`: hard-excluded {token} ({reason})")
            if catalogs and token not in catalogs["go"]:
                errors.append(f"routing row `{role}`: Go {token} not in Go catalog")
        for token in id_tokens(free_cell):
            if not token.endswith("-free"):
                errors.append(
                    f"routing row `{role}`: non-free {token} in the free opt-in column")
            elif catalogs:
                if token not in catalogs["zen"]:
                    errors.append(f"routing row `{role}`: free {token} not in Zen catalog")
                if token not in catalogs["docs"]:
                    errors.append(f"routing row `{role}`: free {token} not docs-listed")
        for token in id_tokens(zen_cell):
            reason = is_excluded(token, exclusions)
            if reason:
                errors.append(f"routing row `{role}`: hard-excluded {token} ({reason})")
            if catalogs and token not in catalogs["zen"]:
                errors.append(f"routing row `{role}`: Zen {token} not in Zen catalog")

    return errors


def doc_tokens(repo: str, rel: str) -> set:
    with open(os.path.join(repo, rel), encoding="utf-8") as fh:
        return set(re.findall(r"`opencode(?:-go)?/([a-z0-9][a-z0-9.\-]*)`", fh.read()))


def probe(model_id: str, tier: str = "go", api_key=None, session_id=None,
          timeout=None, opener=None) -> dict:
    """Live trivial-prompt probe (20s cap; never extended).

    Returns {"live", "protocol_unsupported", "reason", "seconds"}.
    `opener` exists for hermetic tests; production uses urlopen.
    """
    if timeout is not None and timeout > PROBE_TIMEOUT_SECONDS:
        raise ValueError(
            f"probe timeout {timeout}s exceeds the {PROBE_TIMEOUT_SECONDS}s cap — "
            "the timeout is never extended to rescue a candidate")
    bare = model_id.split("/", 1)[-1]
    endpoint = GO_CHAT_ENDPOINT if tier == "go" else ZEN_CHAT_ENDPOINT
    body = json.dumps({
        "model": bare,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": 16,
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key or ''}",
        "x-opencode-session": session_id or uuid.uuid4().hex,
        "User-Agent": UA["User-Agent"],
    })
    started = time.monotonic()

    def elapsed():
        return round(time.monotonic() - started, 2)

    try:
        with (opener or urllib.request.urlopen)(req, timeout=PROBE_TIMEOUT_SECONDS) as resp:
            resp.read()
        return {"live": True, "protocol_unsupported": False,
                "reason": "answered", "seconds": elapsed()}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — body read is best-effort
            pass
        if "ModelProtocolUnsupported" in detail:
            return {"live": False, "protocol_unsupported": True,
                    "reason": "protocol-unsupported on chat/completions — verify "
                              "via /responses through the opencode path",
                    "seconds": elapsed()}
        return {"live": False, "protocol_unsupported": False,
                "reason": f"HTTP {exc.code}: {detail[:200]}", "seconds": elapsed()}
    except (TimeoutError, socket.timeout) as exc:
        return {"live": False, "protocol_unsupported": False,
                "reason": f"not live: no answer within {PROBE_TIMEOUT_SECONDS}s "
                          f"({type(exc).__name__})",
                "seconds": elapsed()}
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            reason = f"not live: no answer within {PROBE_TIMEOUT_SECONDS}s"
        else:
            reason = f"probe error: {exc.reason}"
        return {"live": False, "protocol_unsupported": False,
                "reason": reason, "seconds": elapsed()}


def _probe_targets(repo: str, exclusions: dict) -> list:
    """Bound Go models to probe: agent bindings plus table default cells."""
    targets = set()
    for model in agent_bindings(repo).values():
        if model.startswith("opencode-go/"):
            targets.add(model)
    for _role, default_cell, _free, _zen in routing_table_rows(repo):
        for token in id_tokens(default_cell):
            if not token.endswith("-free"):
                targets.add(f"opencode-go/{token}")
    return sorted(t for t in targets if not is_excluded(t, exclusions))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--probe", action="store_true",
                        help="live trivial-prompt probe of bound Go models "
                             "(needs OPENCODE_API_KEY; 20s cap)")
    parser.add_argument("--probe-model", action="append", default=[],
                        help="probe only this model id (repeatable)")
    args = parser.parse_args()
    repo = os.path.abspath(args.repo)
    errors = []

    try:
        zen = catalog_ids(fetch(ZEN_CATALOG))
        go = catalog_ids(fetch(GO_CATALOG))
        docs = fetch(DOCS_ENDPOINTS)
    except Exception as exc:  # noqa: BLE001 — network canary; report and fail
        print(f"FAIL: could not fetch catalogs/docs: {exc}")
        return 1

    errors += check_policy(repo, {"go": go, "zen": zen, "docs": docs})

    # Documented IDs must be bound somewhere (agents or routing table).
    bound = set(agent_bindings(repo).values())
    table_ids = set()
    for _, default_cell, free_cell, zen_cell in routing_table_rows(repo):
        table_ids |= id_tokens(default_cell) | id_tokens(free_cell) | id_tokens(zen_cell)
    bound_unprefixed = {b.split("/", 1)[-1] for b in bound} | table_ids
    for rel in ("agents/council.md", "docs/COUNCIL.md"):
        for token in sorted(doc_tokens(repo, rel)):
            if token not in bound_unprefixed:
                errors.append(f"{rel}: documents `{token}` which is bound nowhere")

    if args.probe:
        api_key = os.environ.get("OPENCODE_API_KEY")
        if not api_key:
            print("FAIL: --probe needs OPENCODE_API_KEY in the environment")
            return 2
        targets = args.probe_model or _probe_targets(repo, hard_exclusions(repo))
        for model in targets:
            result = probe(model, tier="go", api_key=api_key,
                           session_id="model-doctor-canary")
            if result["protocol_unsupported"]:
                print(f"SKIP: {model}: {result['reason']}")
            elif not result["live"]:
                print(f"DEAD: {model}: {result['reason']} ({result['seconds']}s)")
                errors.append(f"probe {model}: {result['reason']}")
            else:
                print(f"LIVE: {model} ({result['seconds']}s)")

    if errors:
        print(f"FAIL: {len(errors)} liveness/policy problem(s)")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OK: all bound and documented model IDs pass the Go-first policy "
          "and catalog/docs checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
