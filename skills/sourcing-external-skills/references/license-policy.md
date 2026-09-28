# License policy — operational restatement (ADR-0011)

Resolved against this skill's own directory — not the project's.
Binding source: `docs/ADRs/ADR-0011-license-and-ingest-policy.md`
(accepted 2026-09-27). This restatement exists so the license gate is
executable in any runtime — including isolated workdirs where the ADR
itself is not reachable. ADR-0011 remains the authority: when it is
amended, re-sync this file in the same change.

## Allow-list — copy/adapt permitted

- `MIT`
- `BSD-2-Clause`, `BSD-3-Clause`
- `ISC`
- `Apache-2.0` — preserve the `NOTICE` file and state modifications
- `0BSD`
- `Unlicense`
- `CC0-1.0` (code)
- `CC-BY-4.0` (prose only)

Any license not listed is `inspire` at best.

## Never-list — no copy/adapt

- `GPL-*`, `AGPL-*`, `LGPL-*` (any version)
- `CC-BY-SA-*`, `CC-BY-ND-*` (any version)
- Proprietary / paywalled content
- Anything without an explicit license at the pinned commit

## Missing or unclear license

`inspire` only — clean-room rewrite, no close paraphrase. Pin the
commit; verify the license at that commit. Record `unlicensed` in the
License cell.

## Verdict order

The security gate (Step 3) runs first and is dispositive: a critical
ADR-0012 finding forces `reject`/`security-gate` regardless of license.
An allow-list license never launders a critical finding.
