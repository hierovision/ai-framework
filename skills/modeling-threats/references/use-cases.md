# Use cases — the inventory this skill serves

Resolved against this skill's own directory — not the project's. The library
rule: evals must cover ≥80% of this inventory, so every use case listed here
carries its eval mapping. Read this file when a request does not obviously fit
a listed case — if the pass serves a need not listed here, extend this
inventory and the eval set in the same change.

## Contents

- The inventory (with eval mappings)
- Coverage math
- Known gaps (dated)
- Boundary notes

## The inventory

| # | Use case | Eval |
|---|---|---|
| 1 | Produce a model for a service/library from its repo and docs: three artifacts, provenance-tagged claims, a trust table, an adversary model, explicit non-guarantees, a triager quick-start | eval 1 |
| 2 | Hold the boundary: a request mixing modeling with a bug hunt, a fix, and CI hardening — model what is in scope and route the rest to its siblings | eval 2 |
| 3 | Triage inbound findings against a finished model: one disposition + status + licensing section per finding, including a `MODEL-GAP` that triggers a revision | eval 3 |
| 4 | Enforce artifact authority: fix a triage call made from the lossy JSON export and regenerate the derived artifacts from the canonical prose | eval 4 |
| 5 | Apply known-non-finding precedence without dressing a scope/configuration/dependency close as a non-finding | eval 5 |
| 6 | Draft-first without a maintainer: tag every claim, collect open questions with proposed answers, fabricate no maintainer position, publish under an honest status | eval 6 |
| 7 | Refresh an existing model when a change trigger fires (new surface, new context, new dependency, changed default) and re-run the affected backtest | *(none — dated deferral below)* |

## Coverage math

6 evals mapped / 7 use cases = 86% inventory coverage by mapping, above the
≥80% library bar.

## Known gaps (dated)

- 2026-09-28 — use case 7 (model refresh after a change trigger) has no eval.
  The closest coverage is eval 4's regenerate-derived-artifacts behavior, which
  is a different discipline. Deferred to the orchestrator's independent eval
  round: add a refresh fixture (an accepted model plus a changed design doc)
  and assert that the model is revised rather than copied. If not added, the
  mapping above stays honest at 86%.

## Boundary notes

- **Vulnerability review** (`reviewing-security`), **diff/plan review**
  (`reviewing-code`), **CI hardening** (`securing-ci`), and **fixing findings**
  (`implementing-features`) are sibling disciplines; eval 2 checks the
  boundary is held, it does not add their work here.
- **Supply-chain audit and incident response** are a separate discipline (in
  flight in the library's security wave). Dependency trust assumptions are
  model content; running scanners and incident playbooks is not.
- **Exploit execution, pentest, and CVE enumeration** are never a use case:
  the model is a static contract description.
- **Designing the system** is `designing-architecture`; when a model's open
  questions need a design decision, that decision is a separate pass.
