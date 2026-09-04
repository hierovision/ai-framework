#!/usr/bin/env python3
"""Model-liveness drift canary ("model doctor").

Automates the check that caught the 2026-09-02 `deepseek-v4-flash-free`
failure: verifies every model ID this repo binds or documents is actually
routable where it claims to be, using live catalog + docs evidence.

  1. Fetch the Zen catalog, the Go catalog, and the docs endpoints page
     (authoritative for free-tier availability).
  2. Collect bound IDs from `agents/*.md` frontmatter `model:` lines and
     from the Core routing table cells of `reference/model-routing.md`
     (routing-table scope only — dated history sections may name retired
     IDs and are intentionally excluded).
  3. Collect documented IDs (`` `opencode/<id>` `` tokens) from
     `agents/council.md` and `docs/FREE-TIER-COUNCIL.md` and verify each
     is bound somewhere (closes the "docs claim, no binding" failure).

Failure classes (exit 1, each printed):
  - a bound free (`*-free`) ID missing from the docs free list or the
    Zen catalog (the deepseek-v4-flash-free signature);
  - a Go/Zen escalation ID missing from its tier's catalog
    (the deepseek-v4-flash Go signature);
  - a documented ID bound nowhere.

Usage:
  python3 scripts/model-liveness-check.py [--repo <repo-root>]
"""

import argparse
import glob
import os
import re
import sys
import urllib.request

ZEN_CATALOG = "https://opencode.ai/zen/v1/models"
GO_CATALOG = "https://opencode.ai/zen/go/v1/models"
DOCS_ENDPOINTS = "https://opencode.ai/docs/zen/#endpoints"

UA = {"User-Agent": "ai-framework-model-liveness-check"}


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
    """Yield (role, free_cell, go_cell, zen_cell) from the Core routing table."""
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


def doc_tokens(repo: str, rel: str) -> set:
    with open(os.path.join(repo, rel), encoding="utf-8") as fh:
        return set(re.findall(r"`opencode(?:-go)?/([a-z0-9][a-z0-9.\-]*)`", fh.read()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
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

    # 1. agent bindings
    for rel, model in sorted(agent_bindings(repo).items()):
        prefix, _, model_id = model.partition("/")
        if model_id.endswith("-free"):
            if model_id not in docs:
                errors.append(f"{rel}: {model} not docs-listed (free tier)")
            if model_id not in zen:
                errors.append(f"{rel}: {model} not in Zen catalog")
        elif prefix == "opencode-go":
            if model_id not in go:
                errors.append(f"{rel}: {model} not in Go catalog")
        else:
            if model_id not in zen:
                errors.append(f"{rel}: {model} not in Zen catalog")

    # 2. routing table cells (free col: docs+Zen; Go col: Go catalog; Zen col: Zen catalog)
    for role, free, go_cell, zen_cell in routing_table_rows(repo):
        for token in id_tokens(free):
            if token.endswith("-free"):
                if token not in docs:
                    errors.append(f"routing row `{role}`: free {token} not docs-listed")
                if token not in zen:
                    errors.append(f"routing row `{role}`: free {token} not in Zen catalog")
        for token in id_tokens(go_cell):
            if token not in go:
                errors.append(f"routing row `{role}`: Go {token} not in Go catalog")
        for token in id_tokens(zen_cell):
            if token not in zen:
                errors.append(f"routing row `{role}`: Zen {token} not in Zen catalog")

    # 3. documented IDs must be bound somewhere (agents or routing table)
    bound = set(agent_bindings(repo).values())
    table_ids = set()
    for _, free, go_cell, zen_cell in routing_table_rows(repo):
        table_ids |= id_tokens(free) | id_tokens(go_cell) | id_tokens(zen_cell)
    bound_unprefixed = {b.split("/", 1)[-1] for b in bound} | table_ids
    for rel in ("agents/council.md", "docs/FREE-TIER-COUNCIL.md"):
        for token in sorted(doc_tokens(repo, rel)):
            if token not in bound_unprefixed:
                errors.append(f"{rel}: documents `{token}` which is bound nowhere")

    if errors:
        print(f"FAIL: {len(errors)} liveness/drift problem(s)")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OK: all bound and documented model IDs are catalog/docs-verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
