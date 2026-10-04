#!/usr/bin/env python3
"""Verify a consumer repo's reachable model bindings against the Go-first policy.

Reachable bindings, in precedence order:

  1. project agent wrappers — `<repo>/.opencode/agents/*.md` (then
     `<repo>/agents/*.md`): markdown frontmatter wins over config agent.model;
  2. project config `<repo>/opencode.json` — top-level `model` / `small_model`
     are always reachable; `agent.<name>.model` only when no project wrapper
     shadows that name;
  3. the delegation registry `<repo>/config/model-candidates.json`, when
     present — the `default: true` candidate is the else-branch of the
     consumer's own resolution order (persisted preference → env → default);
  4. global agents `~/.config/opencode/agents/*.md` for any persona without a
     project wrapper of the same stem (project wrappers win over global).

Flags (exit 1): a reachable `*-free` binding (free is an explicit opt-in, not
a default), a hard-excluded ID (kimi-k3 and the framework's Hard exclusions —
exclusions sit above all scores), and a catalog-covered ID absent from its
tier's live catalog. `deepseek/` direct-key IDs are the user's explicit
opt-in lane and are not catalog-checked.

Usage:
  python3 scripts/check-consumer-bindings.py <repo-dir> [--global-agents DIR]
"""

import argparse
import glob
import importlib.util
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
FRAMEWORK_REPO = os.path.dirname(HERE)

GO_CATALOG = "https://opencode.ai/zen/go/v1/models"
ZEN_CATALOG = "https://opencode.ai/zen/v1/models"
UA = {"User-Agent": "ai-framework-consumer-bindings-check"}


def _load_framework_checker():
    path = os.path.join(HERE, "model-liveness-check.py")
    spec = importlib.util.spec_from_file_location("model_liveness_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CHECKER = _load_framework_checker()


def fetch_catalogs():
    def fetch(url):
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    return {"go": CHECKER.catalog_ids(fetch(GO_CATALOG)),
            "zen": CHECKER.catalog_ids(fetch(ZEN_CATALOG))}


def model_from_frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if not raw.startswith("---"):
        return None
    match = re.search(r"^model:\s*(\S+)\s*$", raw.split("---", 2)[1], re.MULTILINE)
    return match.group(1) if match else None


def collect_bindings(repo, global_agents_dir):
    """Return [{"surface", "model", "shadowed"}] of reachable bindings."""
    bindings = []
    project_wrappers = {}
    for sub in (".opencode/agents", "agents"):
        for path in sorted(glob.glob(os.path.join(repo, sub, "*.md"))):
            name = os.path.basename(path)[:-3]
            model = model_from_frontmatter(path)
            if not model:
                continue
            project_wrappers[name] = model
            bindings.append({"surface": os.path.relpath(path, repo),
                             "model": model, "shadowed": False})

    config = os.path.join(repo, "opencode.json")
    if os.path.isfile(config):
        with open(config, encoding="utf-8") as fh:
            data = json.load(fh)
        for key in ("model", "small_model"):
            if data.get(key):
                bindings.append({"surface": f"opencode.json:{key}",
                                 "model": data[key], "shadowed": False})
        for name, entry in (data.get("agent") or {}).items():
            model = entry.get("model") if isinstance(entry, dict) else None
            if model:
                bindings.append({"surface": f"opencode.json:agent.{name}.model",
                                 "model": model,
                                 "shadowed": name in project_wrappers})

    registry = os.path.join(repo, "config", "model-candidates.json")
    if os.path.isfile(registry):
        with open(registry, encoding="utf-8") as fh:
            candidates = json.load(fh).get("candidates") or []
        default = next((c for c in candidates if c.get("default")),
                       candidates[0] if candidates else None)
        if default and default.get("model"):
            bindings.append({"surface": "config/model-candidates.json (default)",
                             "model": default["model"], "shadowed": False})

    if os.path.isdir(global_agents_dir):
        for path in sorted(glob.glob(os.path.join(global_agents_dir, "*.md"))):
            name = os.path.basename(path)[:-3]
            if name in project_wrappers:
                continue  # the project wrapper wins
            model = model_from_frontmatter(path)
            if model:
                bindings.append({"surface": f"global agents/{name}.md",
                                 "model": model, "shadowed": False})
    return bindings


def check_bindings(bindings, catalogs, exclusions):
    errors = []
    for binding in bindings:
        model = binding["model"]
        surface = binding["surface"]
        bare = model.split("/", 1)[-1]
        reason = CHECKER.is_excluded(model, exclusions)
        if bare.endswith("-free"):
            errors.append(f"{surface}: {model} — free binding (explicit opt-in only)")
        if reason:
            errors.append(f"{surface}: {model} — hard-excluded ({reason})")
        if catalogs and "/" in model:
            prefix = model.split("/", 1)[0]
            if prefix == "opencode-go" and bare not in catalogs["go"]:
                errors.append(f"{surface}: {model} — not in the live Go catalog")
            elif prefix not in ("opencode-go", "deepseek") and bare not in catalogs["zen"]:
                errors.append(f"{surface}: {model} — not in the live Zen catalog")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", help="consumer repo directory")
    parser.add_argument("--global-agents",
                        default=os.path.expanduser("~/.config/opencode/agents"),
                        help="global opencode agents dir (default: ~/.config/opencode/agents)")
    args = parser.parse_args(argv)
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print(f"FAIL: {repo} is not a directory")
        return 2

    exclusions = CHECKER.hard_exclusions(FRAMEWORK_REPO)
    try:
        catalogs = fetch_catalogs()
    except Exception as exc:  # noqa: BLE001 — live catalog check; report and fail
        print(f"FAIL: could not fetch live catalogs: {exc}")
        return 1

    bindings = collect_bindings(repo, args.global_agents)
    if not bindings:
        print(f"FAIL: {repo}: no reachable bindings found (no project wrappers, "
              f"config, registry default, or global agents)")
        return 1

    errors = check_bindings(bindings, catalogs, exclusions)
    tier = lambda m: "direct-key" if m.startswith("deepseek/") else \
        ("go" if m.startswith("opencode-go/") else "zen")
    for binding in bindings:
        flag = "" if not binding["shadowed"] else " (shadowed by project wrapper)"
        print(f"  {binding['model']:<38} {tier(binding['model']):<10} {binding['surface']}{flag}")
    if errors:
        print(f"FAIL: {repo}: {len(errors)} binding violation(s)")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"OK: {repo}: {len(bindings)} reachable binding(s) — Go default, "
          f"no free default, no excluded ID, all catalog-live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
