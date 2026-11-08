# Consumer-security fixtures

Synthetic, hermetic inputs for the RM-076 tooling. They contain no live
consumer data, no advisory text beyond the allowlisted fields, no manifests or
lockfiles, and no paths. Nothing here is a dependency-graph surface.

| File | Used by | Purpose |
|---|---|---|
| `snapshot.json` | `consumer_security_sweep.py`, `check_security_register.py` | Synthetic `advisory-snapshot-v1`: four active revisions, six queries (empty and non-empty results), every severity level. |
| `controls.json` | `consumer_security_sweep.py` | Synthetic open control observations, including one retired-`pln` control. |
| `expected-sweep.json` | `test_consumer_security_sweep.py` | Canonical golden report for the two inputs above. |
| `register.json` | `check_security_register.py`, `test_security_register.py` | Synthetic valid dispositions covering every golden sweep ID exactly once; never the real register. |
| `osv-response.json` | `test_fetch_advisories.py`, `fetch_advisories.py --osv-json` | Mocked OSV batch response. |

## Regeneration rules

- Fixtures are hand-authored or produced by the scripts under test; never
  copy live OSV payloads, GHSA text, lockfiles, or consumer names beyond the
  five canonical slugs.
- `expected-sweep.json` is regenerated only with:
  `python3 scripts/consumer_security_sweep.py --from-audit scripts/fixtures/consumer-security --out scripts/fixtures/consumer-security/expected-sweep.json`
  and the diff must be reviewed for determinism (two consecutive runs are
  byte-identical).
- `register.json` IDs are the `sweep_id` values in `expected-sweep.json`.
  They are opaque hashes; do not hand-edit a row's identity fields without
  recomputing its `sweep_id`.
