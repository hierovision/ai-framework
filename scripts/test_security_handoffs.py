#!/usr/bin/env python3
"""Hermetic tests for the handoff-brief checker (RM-076 P3-5).

Run: python3 scripts/test_security_handoffs.py

Builds five valid synthetic briefs, then fails focused cases for a missing
brief, each missing content class, an executable `--force`, and an undated
suppression. The prose prohibition of `audit fix --force` must stay allowed.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_security_handoffs as handoffs  # noqa: E402
import consumer_security_sweep as sweep  # noqa: E402

SCRATCH = os.path.join(REPO, ".scratch", "test-tmp")
SLUGS = {
    "handoff-paragon-learning-network.md":
        ("paragon-learning-network",
         "Stonegate-Software/paragon-learning-network"),
    "handoff-pt.md": ("pt", "hierovision/phasetimer"),
    "handoff-marvin-slack.md": ("marvin-slack", "hierovision/marvin-slack"),
    "handoff-excel-daily-monitor.md":
        ("excel-daily-monitor", "hierovision/excel-daily-monitor"),
    "handoff-pln.md": ("pln", "hierovision/pln"),
}
TEMPLATE = """# Handoff — {slug}

Repo: `{slug}` (`{repository}`)

## P0/P1 findings

| Finding ID | Priority | Installed | Fixed |
|---|---|---|---|
| GHSA-example | P1 | 1.2.3 | 1.2.4 |
| consumer-local/example-control | P0 | {control_installed} | {control_fixed} |

## Verification

```bash
npm ci
npm test
```

## Owner actions

- Apply the referenced upgrade and re-run the verification commands.

## Suppressions

{suppressions}

## Guardrails

Never run `npm audit fix --force`. No undated suppression: every acceptance
carries an owner, an ISO date, a review date, and a rationale.
"""
DATED_SUPPRESSIONS = """| ID | Owner | Date | Review on | Rationale |
|---|---|---|---|---|
| GHSA-example | hierovision | 2026-11-07 | 2027-02-05 | No fixed version upstream yet. |"""


def tempdir():
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(dir=SCRATCH)


def body(slug, repository, **overrides):
    values = {
        "slug": slug,
        "repository": repository,
        "control_installed": "N/A — control-only",
        "control_fixed": "N/A — control-only",
        "suppressions": "None.",
    }
    if slug == "pln":
        values["control_installed"] = "N/A — decommissioned"
        values["control_fixed"] = "N/A — decommissioned"
    values.update(overrides)
    return TEMPLATE.format(**values)


def write_briefs(root, overrides=None):
    overrides = overrides or {}
    for filename, (slug, repository) in SLUGS.items():
        text = overrides.get(filename)
        if text is None:
            text = body(slug, repository)
        with open(os.path.join(root, filename), "w", encoding="utf-8") as fh:
            fh.write(text)


def run_over(overrides, remove=None):
    root = tempdir()
    try:
        write_briefs(root, overrides)
        if remove:
            os.unlink(os.path.join(root, remove))
        return handoffs.run(root, sweep.load_inventory())
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_five_valid_briefs_pass():
    assert run_over({}) == []


def test_valid_dated_suppression_passes():
    override = {
        "handoff-pt.md": body("pt", "hierovision/phasetimer",
                              suppressions=DATED_SUPPRESSIONS),
    }
    assert run_over(override) == []


def test_missing_brief_fails():
    failures = run_over({}, remove="handoff-pln.md")
    assert any("handoff-pln.md: missing" in failure for failure in failures)


def test_missing_repo_line_fails():
    text = body("pt", "hierovision/phasetimer").replace(
        "Repo: `pt` (`hierovision/phasetimer`)", "Repo: pt")
    failures = run_over({"handoff-pt.md": text})
    assert any("Repo line" in failure for failure in failures)


def test_wrong_repository_fails():
    text = body("pt", "hierovision/not-phasetimer")
    failures = run_over({"handoff-pt.md": text})
    assert any("does not match inventory" in failure for failure in failures)


def test_missing_findings_class_fails():
    text = body("pt", "hierovision/phasetimer").replace(
        "| Finding ID | Priority | Installed | Fixed |\n"
        "|---|---|---|---|\n"
        "| GHSA-example | P1 | 1.2.3 | 1.2.4 |\n"
        "| consumer-local/example-control | P0 | N/A — control-only | "
        "N/A — control-only |\n",
        "No findings recorded.\n")
    failures = run_over({"handoff-pt.md": text})
    assert any("findings table" in failure for failure in failures)


def test_missing_version_reason_fails():
    text = body("pt", "hierovision/phasetimer").replace(
        "| GHSA-example | P1 | 1.2.3 | 1.2.4 |",
        "| GHSA-example | P1 |  | 1.2.4 |")
    failures = run_over({"handoff-pt.md": text})
    assert any("Installed must be a version" in failure for failure in failures)


def test_missing_verification_and_owner_actions_fail():
    text = body("pt", "hierovision/phasetimer").replace(
        "```bash\nnpm ci\nnpm test\n```", "").replace(
        "- Apply the referenced upgrade and re-run the verification commands.",
        "")
    failures = run_over({"handoff-pt.md": text})
    assert any("Verification needs" in failure for failure in failures)
    assert any("Owner actions needs" in failure for failure in failures)


def test_missing_suppressions_and_guardrails_fail():
    text = body("pt", "hierovision/phasetimer").replace(
        "## Suppressions\n\nNone.\n\n", "")
    text = text.replace("## Guardrails", "## Other")
    failures = run_over({"handoff-pt.md": text})
    assert any("missing section: ## Suppressions" in failure for failure in failures)
    assert any("missing section: ## Guardrails" in failure for failure in failures)


def test_executable_force_in_fence_fails():
    text = body("pt", "hierovision/phasetimer").replace(
        "npm ci\nnpm test", "npm audit fix --force")
    failures = run_over({"handoff-pt.md": text})
    assert any("executable --force" in failure for failure in failures)


def test_wrapped_executable_force_fails():
    cases = {
        "cd": "cd app && npm audit fix --force",
        "env-assignment": "FOO=1 npm install --force",
        "semicolon": "npm ci; npm audit fix --force",
        "pipe": "npm run build | npm audit fix --force",
        "or": "npm ci || yarn upgrade --force",
        "sudo": "sudo env FOO=1 npm install --force",
        "continuation": "npm audit fix \\\n  --force",
    }
    for label, command in cases.items():
        text = body("pt", "hierovision/phasetimer").replace(
            "npm ci\nnpm test", command)
        failures = run_over({"handoff-pt.md": text})
        assert any("executable --force" in failure for failure in failures), \
            f"{label}: {command!r} was not flagged"


def test_prose_force_inside_fence_is_allowed():
    text = body("pt", "hierovision/phasetimer").replace(
        "npm ci\nnpm test",
        "npm ci\nnpm test\nNever use --force here; it is forbidden.")
    assert run_over({"handoff-pt.md": text}) == []


def test_executable_inline_force_fails():
    text = body("pt", "hierovision/phasetimer").replace(
        "- Apply the referenced upgrade and re-run the verification commands.",
        "- Run `npm audit fix --force` and ship it.")
    failures = run_over({"handoff-pt.md": text})
    assert any("executable --force" in failure for failure in failures)


def test_undated_suppression_fails():
    text = body("pt", "hierovision/phasetimer", suppressions="""| ID | Owner | Date | Review on | Rationale |
|---|---|---|---|---|
| GHSA-example | hierovision | 2026-11-07 |  | No fixed version upstream yet. |""")
    failures = run_over({"handoff-pt.md": text})
    assert any("undated suppression" in failure for failure in failures)


def test_cli_exit_codes():
    root = tempdir()
    try:
        write_briefs(root)
        assert handoffs.main(["--handoff-dir", root]) == 0
        assert handoffs.main(["--handoff-dir",
                              os.path.join(root, "absent")]) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    tests = [
        test_five_valid_briefs_pass,
        test_valid_dated_suppression_passes,
        test_missing_brief_fails,
        test_missing_repo_line_fails,
        test_wrong_repository_fails,
        test_missing_findings_class_fails,
        test_missing_version_reason_fails,
        test_missing_verification_and_owner_actions_fail,
        test_missing_suppressions_and_guardrails_fail,
        test_executable_force_in_fence_fails,
        test_wrapped_executable_force_fails,
        test_prose_force_inside_fence_is_allowed,
        test_executable_inline_force_fails,
        test_undated_suppression_fails,
        test_cli_exit_codes,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
