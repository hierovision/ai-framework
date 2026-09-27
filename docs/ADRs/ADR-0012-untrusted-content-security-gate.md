# ADR-0012: Untrusted-content security gate

## Status: accepted 2026-09-27

## Context

The skill-gap analysis plan (`.opencode/plans/skill-gap-analysis.md`) introduces
a workflow that sweeps external sources for candidate skills. All such content
is wild and untrusted. It must never be possible for ingested content to be
interpreted as instructions by the framework or its agents.

## Decision

### Untrusted by default

- All wild content (skills, snippets, docs, scripts, configs) is **untrusted
  pure data**. It must not be possible to interpret it as instructions.

### Formal injection / vulnerability pre-scan

Every candidate undergoes a mandatory pre-scan before any evaluation or
adjudication. The scan checks for:

- Hidden Unicode (directional overrides, zero-width joiners, bidi controls)
- Prompt-injection patterns (instruction override, role hijack, context
  stuffing, delimiter confusion)
- Exfiltration URLs (telemetry beacons, data-stealing endpoints)
- Destructive commands (filesystem writes, process spawns, network egress)
- Credential access (env var reads, secret managers, keychain access)
- Covert network calls (DNS tunnels, HTTP callbacks, websocket upgrades)
- Dependency risk (supply-chain markers, known-malicious packages, version
  confusion)

### Script evaluation

- Every script (shell, Python, JS, etc.) is **fully security-reviewed** by a
  human before execution.
- Execution occurs **only after explicit user sign-off**.
- Candidates that cannot be evaluated safely are **rejected** (status `reject`
  in the candidate register with reason `security-gate`).

## Consequences

- The pre-scan is a hard gate in Phase B; no candidate advances to Phase C
  without a clean scan record.
- The `sourcing-external-skills` skill (Phase 0.5) implements the scan as an
  executable step with a documented checklist and recorded output.
- No exceptions; "looks safe" is not a verdict — the scan artifact is the
  evidence.

## Sources

- `.opencode/plans/skill-gap-analysis.md` — Phase 0 policy decisions, user-approved 2026-09-27