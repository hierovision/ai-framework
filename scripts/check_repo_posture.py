#!/usr/bin/env python3
"""Framework and consumer repo-posture verifier (RM-073 P1-8, RM-076 P3-7).

Three mutually exclusive modes:

    python3 scripts/check_repo_posture.py --repo hierovision/ai-framework
    python3 scripts/check_repo_posture.py \
        --consumer-inventory reference/consumer-repos.md
    python3 scripts/check_repo_posture.py --local

`--repo` is the original OWNER-RUN live framework check (the default mode when
no mode is named). It reads live GitHub settings through `gh api` and asserts
the Phase 0 containment is still in place:

  - `main` requires a PR and the `quality-gates`, `pre-commit-check`, and
    `dependency-audit` checks, with strict up-to-date, admins enforced, and no
    force-push/deletion;
  - the required approval count is 0 under the dated solo-owner exception
    recorded in SECURITY.md;
  - Dependabot alerts + security updates are enabled;
  - secret scanning + push protection are enabled;
  - CodeQL default setup is configured;
  - `.github/dependabot.yml` covers every tracked npm surface and GitHub
    Actions.

`--consumer-inventory` is the OWNER-RUN live consumer check. It requires
Dependabot alerts/security updates and secret scanning/push protection for
every active consumer, requires retired `pln` to stay archived, and honors only
an unexpired dated register acceptance for a documented feature-unavailable
response. Authentication, network, permission, and unexpected API failures
exit 2 and cannot be suppressed.

`--local` is the only posture mode CI may run: tracked configuration and dated
exception syntax only, no `gh` call, no socket. Live settings print
`SKIP — owner-run` and are never reported as `PASS`.

Exit codes: 0 = posture holds (or local static checks pass); 1 = drift;
2 = the checker could not run.
"""
import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

SECURITY = os.path.join(REPO_ROOT, "SECURITY.md")
DEPENDABOT = os.path.join(REPO_ROOT, ".github", "dependabot.yml")
DEFAULT_INVENTORY = sweep.DEFAULT_INVENTORY
DEFAULT_REGISTER = os.path.join(REPO_ROOT, "docs", "security", "register.json")
FRAMEWORK_REPO = "hierovision/ai-framework"

REQUIRED_CHECKS = {"quality-gates", "pre-commit-check", "dependency-audit"}
REQUIRED_NPM_DIRS = {
    # `/.opencode` is host-local: its package.json is gitignored, so it is not
    # a tracked npm surface. Configuring it made every Dependabot run fail
    # `dependency_file_not_found` (observed 2026-11-07).
    "/plugins/auto-compact-at-threshold",
    "/plugins/delegation-observer",
    "/plugins/delegation-sentinel",
    "/skills/capturing-ui-evidence",
    "/skills/auditing-accessibility",
    "/skills/validating-ui",
}
CONSUMER_SETTINGS = (
    "dependabot-alerts",
    "dependabot-security-updates",
    "secret-scanning",
    "secret-scanning-push-protection",
)
UNAVAILABLE_MARKERS = (
    "advanced security",
    "not available",
    "not enabled for this repository",
    "upgrade your plan",
)
DISABLED = object()


class CheckError(RuntimeError):
    """The checker itself could not run (auth/scope/network/missing gh)."""


class FeatureUnavailable(RuntimeError):
    """A documented platform-gated setting; eligible for dated acceptance."""


# --------------------------------------------------------------------------
# Live transport
# --------------------------------------------------------------------------

def _gh_api(target):
    try:
        return subprocess.run(["gh", "api", target],
                              capture_output=True, text=True)
    except OSError as exc:
        raise CheckError(f"gh is not runnable: {exc}") from exc


def api(repo, path):
    """GET a repo-scoped API path; returns parsed JSON or None for 204."""
    target = f"repos/{repo}" + (f"/{path}" if path else "")
    proc = _gh_api(target)
    if proc.returncode != 0:
        raise CheckError(
            f"gh api {target} failed: {proc.stderr.strip() or proc.returncode}")
    body = proc.stdout.strip()
    return json.loads(body) if body else None


def fetch_consumer(repo, path):
    """(payload | None | DISABLED); raises FeatureUnavailable or CheckError."""
    target = f"repos/{repo}" + (f"/{path}" if path else "")
    proc = _gh_api(target)
    if proc.returncode == 0:
        body = proc.stdout.strip()
        return json.loads(body) if body else None
    error = (proc.stderr or "").lower()
    if "not found (http 404)" in error:
        return DISABLED
    if any(marker in error for marker in UNAVAILABLE_MARKERS):
        raise FeatureUnavailable(f"{target}: {proc.stderr.strip()}")
    raise CheckError(f"gh api {target} failed: {proc.stderr.strip()}")


# --------------------------------------------------------------------------
# Static helpers
# --------------------------------------------------------------------------

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


def load_exceptions(register_path):
    """Return {(repo, control_id): row} for accepted posture rows."""
    if not os.path.isfile(register_path):
        return {}
    with open(register_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = {}
    for row in doc.get("findings") or []:
        control_id = row.get("control_id") or ""
        if not control_id.startswith("consumer-local/posture/"):
            continue
        rows[(row.get("repo"), control_id)] = row
    return rows


def exception_for(repo, setting, exceptions, today):
    row = exceptions.get((repo, f"consumer-local/posture/{setting}"))
    if not row or row.get("disposition") != "accepted":
        return None
    review_on = row.get("review_on")
    if not review_on or review_on < today:
        return None
    return row


# --------------------------------------------------------------------------
# Live consumer posture
# --------------------------------------------------------------------------

def _repo_payload_state(repo, fetch):
    payload = fetch(repo, "")
    payload = payload if isinstance(payload, dict) else {}
    analysis = payload.get("security_and_analysis") or {}
    states = {}
    for setting, key in (("secret-scanning", "secret_scanning"),
                         ("secret-scanning-push-protection",
                          "secret_scanning_push_protection")):
        value = analysis.get(key)
        if not isinstance(value, dict) or "status" not in value:
            states[setting] = "unavailable"
            continue
        states[setting] = value["status"] == "enabled"
    return payload, states


def consumer_state(repo, fetch):
    """Return ({setting: bool | 'unavailable'}, archived)."""
    states = {}
    for setting, path in (("dependabot-alerts", "vulnerability-alerts"),
                          ("dependabot-security-updates",
                           "automated-security-fixes")):
        try:
            payload = fetch(repo, path)
        except FeatureUnavailable:
            states[setting] = "unavailable"
            continue
        if setting == "dependabot-alerts":
            states[setting] = payload is not DISABLED
        else:
            states[setting] = bool(
                isinstance(payload, dict) and payload.get("enabled") is True)
    payload, analysis = _repo_payload_state(repo, fetch)
    states.update(analysis)
    return states, payload.get("archived") is True


def check_consumers(inventory_path, register_path, today, fetch=None):
    failures = []
    fetch = fetch or fetch_consumer
    consumers = sweep.load_inventory(inventory_path)
    exceptions = load_exceptions(register_path)
    for record in consumers:
        repo, slug = record["repository"], record["slug"]
        if record["status"] == "retired":
            try:
                payload = fetch(repo, "")
            except FeatureUnavailable as exc:
                print(f"FAIL  {slug}: archived state unreadable ({exc})")
                failures.append(f"{slug}: archived state unreadable")
                continue
            archived = isinstance(payload, dict) and payload.get("archived") is True
            check(archived, f"{slug} remains archived/decommissioned", failures)
            continue
        try:
            states, _ = consumer_state(repo, fetch)
        except FeatureUnavailable as exc:
            print(f"FAIL  {slug}: live posture unreadable ({exc})")
            failures.append(f"{slug}: live posture unreadable")
            continue
        for setting in CONSUMER_SETTINGS:
            state = states.get(setting)
            if state == "unavailable":
                exception = exception_for(slug, setting, exceptions, today)
                if exception:
                    print(f"ACCEPTED  {slug} {setting} — feature unavailable, "
                          f"accepted until {exception['review_on']}")
                else:
                    print(f"FAIL  {slug} {setting} — feature unavailable with "
                          f"no unexpired dated acceptance")
                    failures.append(f"{slug}: {setting} unavailable")
            else:
                check(state is True, f"{slug} {setting} enabled", failures)
    return failures


# --------------------------------------------------------------------------
# Live framework posture (original behavior)
# --------------------------------------------------------------------------

def check_framework(repo):
    failures = []
    try:
        protection = api(repo, "branches/main/protection")

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
              "SECURITY.md records the dated solo-owner approval exception",
              failures)

        alerts = api(repo, "vulnerability-alerts")
        check(alerts is None, "Dependabot alerts are enabled", failures)
        fixes = api(repo, "automated-security-fixes") or {}
        check(fixes.get("enabled") is True,
              "Dependabot security updates are enabled", failures)

        repo_payload = api(repo, "")
        analysis = (repo_payload or {}).get("security_and_analysis") or {}
        check((analysis.get("secret_scanning") or {}).get("status") == "enabled",
              "secret scanning is enabled", failures)
        check((analysis.get("secret_scanning_push_protection") or {}).get("status") == "enabled",
              "secret scanning push protection is enabled", failures)

        codeql = api(repo, "code-scanning/default-setup") or {}
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


# --------------------------------------------------------------------------
# Local static mode
# --------------------------------------------------------------------------

def check_local(inventory_path, register_path):
    failures = []
    try:
        npm_dirs, actions = parse_dependabot_dirs()
        missing = REQUIRED_NPM_DIRS - npm_dirs
        check(not missing,
              f"tracked dependabot covers npm surfaces (missing: {sorted(missing)})",
              failures)
        check(actions, "tracked dependabot covers GitHub Actions", failures)
        check(solo_owner_exception_recorded(),
              "SECURITY.md records the dated solo-owner approval exception",
              failures)

        consumers = sweep.load_inventory(inventory_path)
        retired = [row["slug"] for row in consumers if row["status"] == "retired"]
        check(len(consumers) == 5 and retired == ["pln"],
              f"inventory parses: {len(consumers)} consumers, retired {retired}",
              failures)

        import check_security_register as register_checker
        with open(register_path, encoding="utf-8") as fh:
            register = json.load(fh)
        problems = register_checker.validate(register, consumers)
        check(not problems,
              f"dated exception syntax valid ({len(problems)} problem(s))",
              failures)
    except (CheckError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR  could not read local config: {exc}", file=sys.stderr)
        return 2
    except sweep.SchemaError as exc:
        print(f"FAIL  {exc}")
        failures.append(str(exc))

    for item in ("live branch protection and required checks",
                 "Dependabot alerts and security updates",
                 "secret scanning and push protection",
                 "CodeQL default setup",
                 "per-consumer Dependabot/secret-scanning posture",
                 "pln archived/decommissioned state"):
        print(f"SKIP — owner-run  {item}")
    if failures:
        print(f"\nSTATIC POSTURE DRIFT: {len(failures)} check(s) failed")
        return 1
    print("\nOK: local posture checks hold (live settings are owner-run)")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--repo", help="owner/name (live framework check)")
    mode.add_argument("--consumer-inventory", metavar="PATH",
                      help="live consumer fleet check")
    mode.add_argument("--local", action="store_true",
                      help="tracked configuration only; no gh, no network")
    parser.add_argument("--register", default=DEFAULT_REGISTER,
                        help="dated posture exceptions (owner-run modes)")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY,
                        help="inventory for --local / --consumer-inventory")
    parser.add_argument("--today", default=None, metavar="YYYY-MM-DD",
                        help="acceptance evaluation date (default: today)")
    args = parser.parse_args(argv)

    if args.local:
        return check_local(args.inventory, args.register)
    if args.consumer_inventory:
        today = args.today or _dt.date.today().isoformat()
        try:
            failures = check_consumers(
                args.consumer_inventory, args.register, today)
        except CheckError as exc:
            print(f"ERROR  {exc}", file=sys.stderr)
            return 2
        except (sweep.SchemaError, OSError, json.JSONDecodeError) as exc:
            print(f"ERROR  could not read posture input: {exc}", file=sys.stderr)
            return 2
        if failures:
            print(f"\nCONSUMER POSTURE DRIFT: {len(failures)} check(s) failed")
            return 1
        print("\nOK: consumer posture holds")
        return 0
    return check_framework(args.repo or FRAMEWORK_REPO)


if __name__ == "__main__":
    sys.exit(main())
