# Attribution & Provenance

Governed by **ADR-0011** (license and ingest policy) and **ADR-0012** (untrusted-content security gate). Every row below represents an ingested or adapted item with verified provenance. Verbatim portions retain upstream notices and license text appended after the table.

## Provenance Table

| Source URL | Author / Holder | SPDX ID | Pinned Commit | Retrieved Date | Changes | Where Used |
|---|---|---|---|---|---|---|
| https://github.com/agamm/claude-code-owasp | agamm | MIT | 8ac7965caa212b4a850aff8d3df0081ab3fa9eed | 2026-09-28 | Adapted into `skills/reviewing-security/` house conventions: workflow re-expressed as the eight-step review pass; severity scale converted to the house backbone; deep-dive reference trimmed; language/config tables re-derived; no endorsement claims | `skills/reviewing-security/` |
| https://github.com/alpha-omega-security/threat-model | Alpha-Omega | MIT | 192fd60cd0afe8851128ce4c68ed68c174c11948 | 2026-09-28 | Adapted into `skills/modeling-threats/` house conventions: the orchestrator's seven-phase workflow and standalone triage specialist folded into one nine-step modeling pass plus a five-step triage pass; specialist roster, full v2 sidecar field set, JSON label mapping, glossary, worked sketch, and batch/CI scripts cut; prose spec compressed to the artifact-contract reference; house additions (untrusted-data/read-only posture, cardinal-rule closure safety, sibling handoffs, use-case inventory, `THREAT-TRIAGE.md` record, `accepted` status requires zero unratified claims); no endorsement claims | `skills/modeling-threats/` |

---

## Upstream Notices & License Text

### Adapted source — `skills/reviewing-security/` (from `agamm/claude-code-owasp`, MIT)

```
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Adapted source — `skills/modeling-threats/` (from `alpha-omega-security/threat-model`, MIT)

```
MIT License

Copyright (c) 2026 Alpha-Omega

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

*Further notices append below as items are adopted through the Phase B–D gate.*