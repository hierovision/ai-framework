# Audit Report Schema

The single source of truth for the `report.json` artifact
`auditing-accessibility` writes. The auditor LINKS this file; consumers (a
developer, a sibling fixing skill, a CI gate) LINK it — the format is never
duplicated across skills. The artifact is VERSIONED (`schema_version`); a
consumer that reads a version it does not understand must stop and surface the
drift, not guess.

`auditing-accessibility` produces the report and STOPS — it never fixes. A
violation entry's `route` field names the sibling that owns the fix
(`correcting-ui` for contrast/spacing, `implementing-features` for
markup/role/keyboard/label, `designing-architecture` for a structural
redesign). The report is the auditor's whole deliverable.

## Contents

- Top-level shape
- `audit_meta` (run metadata)
- `verdict` + `severity_rollup`
- `violations[]` (per axe violation × node × viewport)
- Severity backbone (blocker/major/minor/nit — axe impact mapping)
- `needs_manual_verification[]` (axe `incomplete` resurfaced)
- `manual_checklist[]` (the beyond-axe list — always emitted)
- `accepted_risks[]` (dated explicit risk acceptance)
- WCAG scoping + the success-criterion mapping
- `source_location` (contrast -> the color rule)
- Determinism guarantees
- Versioning + drift

## Top-level shape

```jsonc
{
  "schema_version": "1.0",           // string; the consumer gates on this
  "audit_meta": { ... },            // run metadata (see below)
  "verdict": "pass" | "violations-found",
  "severity_rollup": { "blocker": N, "major": N, "minor": N, "nit": N },
  "violations": [ /* per axe violation × node × viewport */ ],
  "needs_manual_verification": [ /* axe incomplete × node × viewport */ ],
  "manual_checklist": [ /* the beyond-axe list — always present */ ],
  "accepted_risks": [ /* dated explicit risk acceptances */ ],
  "automation_ceiling_note": "..."  // one-line honesty about automation's reach
}
```

A run with `V` viewports expands each axe violation node into `V` entries
(one per viewport). The verdict follows the severity rollup MECHANICALLY
(reviewing-code posture) — never a separate judgement. "Looks accessible" is
not a verdict; the axe result + the schema-valid report are the closure.

## `audit_meta` (run metadata)

| field | type | note |
|---|---|---|
| `mode` | `"app" \| "component"` | which capture mode produced the run |
| `target` | string | app: dev-server URL; component: harness HTML path |
| `route` | string \| null | app mode only; appended to `target` |
| `viewports` | `string[]` | the `WxH` specs, in run order |
| `level` | `"AA" \| "AAA"` | the WCAG conformance level audited |
| `wcag_version` | string | the WCAG version (`2.2` default) |
| `axe_run` | boolean | `true` for a real axe run; `false` for a canned self-check fixture |
| `axe_engine` | string | `axe-core` |
| `name` | string | run name |
| `auth_fixture_used` | boolean | app mode: was the e2e auth-fixture applied |
| `device_scale_factor` | number | pinned (1) — scale perturbs layout/contrast |
| `animations_disabled` | boolean | the freeze/reduce-motion injection was applied |
| `rules_run_total` | number | violations+passes+incomplete+inapplicable rules, summed over viewports |
| `audit_clock` | string \| number | metadata only — a CONSUMER MUST EXCLUDE it from comparison |

`audit_meta` is for traceability + determinism knobs; the DIFFABLE substance is
the `violations[]` + `needs_manual_verification[]` arrays. `audit_clock` is
explicitly excluded from any before/after comparison.

## `verdict` + `severity_rollup`

- `verdict: "violations-found"` iff `violations.length > 0`; else `"pass"`.
- `severity_rollup` counts violations by severity. The verdict is **derived**
  from the rollup — issuing `pass` while the rollup has a blocker is a defect.

A `pass` verdict is honest about automation's ceiling: it means axe found no
automated violations, NOT "verified accessible." The `manual_checklist` is
always present and OUTSTANDING; the `automation_ceiling_note` states this. An
audit that returns `pass` without flagging manual verification is lying about
what automation can decide.

## `violations[]` (per axe violation × node × viewport)

```jsonc
{
  "rule_id": "color-contrast",          // axe rule id
  "rule_help": "Elements must have ...",
  "help_url": "https://... ",            // axe helpUrl or the WCAG SC URL
  "wcag_sc": ["1.4.3"],                 // success-criterion codes parsed from axe tags
  "wcag_level": "AA",
  "wcag_version": "2.2",
  "impact": "serious",                   // axe impact as returned
  "severity": "major",                   // mapped to the library backbone (see below)
  "node": {
    "target": "css:.btn",               // axe node target chain joined with spaces
    "html": "<button class=\"btn\">..",  // axe node html snippet
    "accessible_name": "Submit",         // axe accessibleName where supplied
    "selector_spec": "label:Submit"      // role/label spec when derivable; null otherwise
  },
  "reason": "Elements must have ... — Fix any of the following: ..", // concrete + failureSummary
  "fix_pointer": "Increase the text color contrast ... See <helpUrl>",  // the rule + routing-friendly hint
  "route": "correcting-ui",             // the sibling that owns the fix
  "source_location": { "selector": "..", "source_url": "..", "computed": { "color": "..", "background-color": ".." } } | null,
  "viewport": { "width": 375, "height": 667 },
  "route_path": "/dashboard",            // app mode only; null in component mode
  "accepted": false,                    // true iff an accepted_risks record covers this rule+node
  "accepted_record": { "date": "2026-07-10", "justification": "demo risk, owner sig" } | null
}
```

`reason` is concrete (axe `help` + the node `failureSummary`), not "feels
inaccessible." `fix_pointer` names the rule to satisfy and points at the axe
help URL — it never instructs suppressing the rule (the cardinal rule). The
`route` is MECHANICAL from the rule id (color/spacing → `correcting-ui`;
markup/role/keyboard/label → `implementing-features`; redesign-needed →
`designing-architecture`); default `implementing-features`.

## Severity backbone (blocker/major/minor/nit — axe impact mapping)

Reuses `reviewing-code`'s severity backbone so a report rollup is comparable to
a review. axe impact maps MECHANICALLY — no vibe:

| axe impact | library severity |
|---|---|
| `critical` | `blocker` |
| `serious` | `major` |
| `moderate` | `minor` |
| `minor` | `nit` |

Discipline (from `reviewing-code` false-positive discipline): a genuinely
accessible page gets a clean report — never manufacture a violation to seem
thorough, never inflate a `nit` into a `blocker`, never deflate a `critical`
into a `minor`. A page that IS accessible must read `pass` with an empty rollup
(and the manual checklist still flagged); a page with a real `critical` is a
blocker even if the rest is clean. Severity follows axe impact + WCAG level,
mechanically, for the same reason reviewing-code severities do.

## `needs_manual_verification[]` (axe `incomplete` resurfaced)

axe returns `incomplete` when it ran a rule but could not fully determine a
pass/fail — e.g. contrast at non-default states, focus-visible perceptibility,
name-role-value for custom widgets, reduced-motion. Each such item is
resurfaced here (NOT silently dropped) as:

```jsonc
{
  "rule_id": "color-contrast",
  "wcag_sc": ["1.4.3"],
  "impact": "serious",
  "severity": "major",
  "node": { "target": "..", "html": "..", "selector_spec": null },
  "reason": ".. — failureSummary",
  "what_to_verify": "axe could not fully determine this; verify manually against the WCAG criterion. Failure detail: ..",
  "viewport": { "width": 375, "height": 667 },
  "route_path": "/dashboard"
}
```

Honest, not faked: an `incomplete` is surfaced as "needs a human," never quietly
flattened to `pass` nor inflated to a `violation`.

## `manual_checklist[]` (the beyond-axe list — always emitted)

axe automates ~30-40% of WCAG. The high-value checks it cannot automate are a
documented, ALWAYS-present list (flagged, not faked) regardless of verdict — a
`pass` verdict does not discharge them:

- **Keyboard trap** (SC 2.1.2) — Tab leaves every container; no scripted trap.
- **Focus order** (SC 2.4.3) — DOM focus order preserves meaning across dynamic states.
- **Meaningful focus-visible** (SC 2.4.7, 2.4.13) — every focusable shows a perceptible indicator on every viewport; no `outline: none` without a replacement.
- **Reduced-motion honored** (SC 2.3.3) — `prefers-reduced-motion` stops/reduces animation.
- **Live-region semantics** (SC 4.1.3) — dynamic inserts/updates announced via `aria-live`/`role=status|alert`.
- **Form-error association** (SC 3.3.1, 3.3.3) — errors programmatically associated + focus moved on submit error.

Each entry carries `check`, `how_to_verify`, `why_not_automated`, `wcag_sc`. The
list lives in `scripts/audit.mjs` (`MANUAL_CHECKLIST`) AND here — they agree.

## `accepted_risks[]` (dated explicit risk acceptance)

The cardinal rule (from `debugging-test-failures`): never green an audit by
suppressing a rule / excluding a node / narrowing scope to dodge a violation.
A suppressed check WITH a record is a decision; WITHOUT a record it is a lie.

Where the user explicitly accepts a violation's risk, the auditor records it
dated — and the violation STAYS in `violations[]` marked `accepted: true`,
pointing at this record (it is not removed):

```jsonc
{
  "rule_id": "color-contrast",
  "target": "css:.btn",
  "justification": "demo blocker, owner-signed, fixed in next sprint",
  "date": "2026-07-10"
}
```

The grader treats a covered rule+node as `accepted` but NEVER as resolved: the
severity rollup still counts it, and the verdict stays `violations-found`. A
report with an empty `accepted_risks` and a real violation present is the
**refusal** path (the auditor refused to suppress and routed the fix) — that is
the default and the legitimate default.

## WCAG scoping + the success-criterion mapping

The audit targets a stated conformance level (default **WCAG 2.2 AA**; **AAA**
on request). axe `runOnly` tags:

- AA: `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa`
- AAA: the AA set plus `wcag2aaa, wcag21aaa, wcag22aaa`

Every rule runs for the chosen level — NO rule is disabled by default. The
success-criterion codes in each violation are parsed from axe tags of the form
`wcag<digit><digit><digit>` (e.g. `wcag143` → `1.4.3`) into canonical `X.Y.Z`
strings + the W3C Understanding URL (e.g. `https://www.w3.org/WAI/WCAG22/Understanding/1.4.3`).
A violation with no parseable SC tag keeps an empty `wcag_sc` array but is still
reported (best-practice axe rules surface honestly rather than being silently
dropped).

## `source_location` (contrast -> the color rule)

Reuses the `capturing-ui-evidence` matched-styles idea: for color/contrast
rules a real-browser run opens a CDP session and records the offending node's
computed `color` + `background-color` so the fix pointer names the rule to
change, not "increase contrast" alone:

```jsonc
{
  "selector": "css:.btn",
  "source_url": "http://localhost:5173/dashboard",
  "computed": { "color": "#9e9e9e", "background-color": "#f5f5f5" }
}
```

This is OPTIONAL — where CDP is unavailable the entry's `source_location` is
`null` (honest), and the `fix_pointer`'s axe help URL still carries the
guidance. A canned self-check fixture may supply a `sourceLocation` per node
directly so the contrast->rule path is unit-checked without a browser.

## Determinism guarantees

The same canned axe input yields the same report (the objective self-check
asserts byte-equal classification). In a real browser, axe is the
deterministic engine; the harness mirrors the `capturing-ui-evidence`
determinism posture:

- animations + transitions reduced (`emulateMedia({ reducedMotion: 'reduce' })
  + the freeze injection) so transient motion never perturbs axe's DOM read;
- load + fonts awaited as **conditions** (`networkidle`, `document.fonts.ready`,
  `readyState === 'complete'`), never a fixed `waitForTimeout` (the
  `debugging-test-failures` class-4 flake, forbidden);
- `deviceScaleFactor: 1` + an explicit viewport pinned per viewport iteration.

## Versioning + drift

`schema_version` is a string `"MAJOR.MINOR"`. A breaking change to the shape
(`violations[]` fields, the severity mapping, the `manual_checklist` contract)
bumps MAJOR. An additive change (a new optional field) bumps MINOR. A consumer
that reads a version outside its supported range must STOP and surface the drift
rather than silently misparse — the report is a contract.