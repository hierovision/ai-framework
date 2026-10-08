# Delegated-result contract

When an agent delegates work to a Task subagent — a council lens, an implement
workstream, a design consult — the parent must never read a dead or malformed
result as a clean one. A provider death can return `state=completed` with an
empty or malformed result (issue #52); in a review loop, silence reads as "the
lens found nothing" — a false-green hole. This contract closes it.

## The rule

A delegated result is **valid** only when it is non-empty **and** carries every
marker of its declared contract. Anything else — an **empty or malformed**
result — is a **failed run**, never a clean result. The parent never
synthesizes a verdict, a review, or a "found nothing" from a failed run.

## Named contracts

| Contract | Used by | Required markers |
|---|---|---|
| `council-lens` | `council-*` lens results, `designing-architecture` Step 5b, `validating-ui` Step 5, `reviewing-code` council path | `Findings`, `Recommendation` |
| `implement-handoff` | a delegated implement workstream's return | `Verification`, `Handoff` |
| `design-consult` | a design-pass consult outcome record | `Consult outcome` |

Markers are matched case-insensitively as substrings after whitespace
normalization. Run the validator:

```
python3 scripts/validate_delegated_result.py --contract council-lens --file <result>
python3 scripts/validate_delegated_result.py --contract implement-handoff --stdin
python3 scripts/validate_delegated_result.py --list-contracts
```

Exit 0 = valid; non-zero = invalid (empty, or a missing marker named on stdout).

## Failure classification (before any retry)

A failed run is classified, not blindly retried:

| Class | Signal (host log) | Recovery |
|---|---|---|
| **transient** | `[server_error]`, upstream timeout, connection reset | retry the delegation |
| **deterministic** | `invalid_request_error`, model-resolution / provider-gate error, a malformed-result repeat | retry once, then switch vehicle (a different agent host/model) or take the work over inline |

The rule: a **transient** failure is retried; a **deterministic** failure is
retried once, then switched or taken over inline. Never loop on an identical
retry, and never read the failed run as a result.

## Recording the outcome

The parent **records** the delegation outcome in the artifact it owns — the
plan `## History` for a design consult, the review report for a review lens, the
handoff for an implement workstream. One line: `clean` / `retried` / `fallback`
/ `inline`. The explicit record is the closure signal; a silent loss is the
defect this contract prevents.

## Consumers

`agents/council.md`, `docs/COUNCIL.md`, and the skills that delegate —
`designing-architecture`, `validating-ui`, `reviewing-code`,
`implementing-features` — cite `reference/delegated-result-contract.md`. Related: RM-017/RM-019 (the empty-result
guard) and RM-022 (run-time supervision while a delegation is in flight).
"Never loop on an identical retry" is mechanically enforced by the
session-tree guard (`scripts/session_guard.py`, `reference/subagent-supervision.md`
§5): its `identical-retry-loop` pattern aborts the session once the bounded
retry sequence is exceeded (RM-024's cap), and its `empty-result` pattern
applies the marker table above via `scripts/validate_delegated_result.py`
(with `--contract`).
