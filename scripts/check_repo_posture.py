#!/usr/bin/env python3
"""Framework repo-posture verifier (RM-073 P1-8) — OWNER-RUN.

    python3 scripts/check_repo_posture.py --repo hierovision/ai-framework

Reads the live GitHub settings through `gh api` and asserts the Phase 0
containment is still in place:

  - `main` requires a PR and the `quality-gates`, `pre-commit-check`, and
    `dependency-audit` checks, with strict up-to-date, admins enforced, and no
    force-push/deletion;
  - the required approval count is 0 under the dated solo-owner exception
    recorded in SECURITY.md (the owner is the only engineer; a real reviewer
    requirement would lock every merge);
  - Dependabot alerts + security updates are enabled;
  - secret scanning + push protection are enabled;
  - CodeQL default setup is configured;
  - `.github/dependabot.yml` covers every tracked npm surface and GitHub
    Actions.

Not a CI gate: reading these settings needs admin-scoped credentials, and CI
must not hold them (plan Open Question 15). Run it at phase close and after
any repository-settings change. Exit 0 = posture holds; 1 = drift; 2 = the
checker could not run (missing `gh`, auth, or admin scope).
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SECURITY = os.path.join(REPO_ROOT, "SECURITY.md")
DEPENDABOT = os.path.join(REPO_ROOT, ".github", "dependabot.yml")

REQUIRED_CHECKS = {"quality-gates", "pre-commit-check", "dependency-audit"}
REQUIRED_NPM_DIRS = {
    "/.opencode",
    "/plugins/auto-compact-at-threshold",
    "/plugins/delegation-observer",
    "/plugins/delegation-sentinel",
    "/skills/capturing-ui-evidence",
    "/skills/auditing-accessibility",
    "/skills/validating-ui",
}


class CheckError(RuntimeError):
    """The checker itself could not run (auth/scope/missing gh)."""


def api(repo, path):
    """GET a repo-scoped API path; returns parsed JSON or None for 204."""
    target = f"repos/{repo}" + (f"/{path}" if path else "")
    proc = subprocess.run(["gh", "api", target],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise CheckError(
            f"gh api {target} failed: {proc.stderr.strip() or proc.returncode}")
    body = proc.stdout.strip()
    return json.loads(body) if body else None


def check(condition, message, failures):
    if condition:
        print(f"PASS  {message}")
    else:
        failures.append(message)
        print(f"FAIL  {message}")


def parse_dependabot_dirs():
    """Return (npm_dirs, actions_present) from the tracked config."""
    with open(DEPENDABOT, encoding="utf-8") as fh:
        text = fh.read()
    blocks = re.split(r"\n\s*- package-ecosystem:", text)
    npm_dirs, actions = set(), False
    for block in blocks[1:]:
        ecosystem = block.split("\n", 1)[0].strip()
        directory = re.search(r"^\s*directory:\s*(\S+)\s*$", block, re.M)
        if ecosystem == "npm" and directory:
            npm_dirs.add(directory.group(1))
        elif ecosystem == "github-actions":
            actions = True
    return npm_dirs, actions


def solo_owner_exception_recorded():
    if not os.path.isfile(SECURITY):
        return False
    with open(SECURITY, encoding="utf-8") as fh:
        text = fh.read()
    return bool(re.search(r"Solo-owner approval exception \(\d{4}-\d{2}-\d{2}\)",
                          text))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    args = parser.parse_args(argv)

    failures = []
    try:
        protection = api(args.repo, "branches/main/protection")

        checks = protection.get("required_status_checks") or {}
        contexts = set(checks.get("contexts") or [])
        check(REQUIRED_CHECKS <= contexts,
              f"main requires {sorted(REQUIRED_CHECKS)}", failures)
        check(checks.get("strict") is True,
              "main requires branches to be up to date", failures)
        check(protection.get("enforce_admins", {}).get("enabled") is True,
              "branch protection applies to admins", failures)
        check(protection.get("allow_force_pushes", {}).get("enabled") is False,
              "force-push to main is denied", failures)
        check(protection.get("allow_deletions", {}).get("enabled") is False,
              "deletion of main is denied", failures)
        check(protection.get("required_conversation_resolution", {}).get("enabled") is True,
              "conversation resolution is required", failures)
        reviews = protection.get("required_pull_request_reviews")
        check(reviews is not None, "main requires a pull request", failures)
        approvals = (reviews or {}).get("required_approving_review_count")
        check(approvals == 0,
              "required approvals is 0 (solo-owner policy)", failures)
        check(solo_owner_exception_recorded(),
              "SECURITY.md records the dated solo-owner approval exception", failures)

        alerts = api(args.repo, "vulnerability-alerts")
        check(alerts is None, "Dependabot alerts are enabled", failures)
        fixes = api(args.repo, "automated-security-fixes") or {}
        check(fixes.get("enabled") is True,
              "Dependabot security updates are enabled", failures)

        repo = api(args.repo, "")
        analysis = (repo or {}).get("security_and_analysis") or {}
        check((analysis.get("secret_scanning") or {}).get("status") == "enabled",
              "secret scanning is enabled", failures)
        check((analysis.get("secret_scanning_push_protection") or {}).get("status") == "enabled",
              "secret scanning push protection is enabled", failures)

        codeql = api(args.repo, "code-scanning/default-setup") or {}
        check(codeql.get("state") == "configured",
              "CodeQL default setup is configured", failures)

        npm_dirs, actions = parse_dependabot_dirs()
        missing = REQUIRED_NPM_DIRS - npm_dirs
        check(not missing, f"dependabot covers npm surfaces (missing: {sorted(missing)})",
              failures)
        check(actions, "dependabot covers GitHub Actions", failures)
    except CheckError as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR  could not read local config: {exc}", file=sys.stderr)
        return 2

    if failures:
        print(f"\nPOSTURE DRIFT: {len(failures)} check(s) failed")
        return 1
    print("\nOK: repository posture holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
