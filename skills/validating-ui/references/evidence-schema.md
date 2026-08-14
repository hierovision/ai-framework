# Evidence Artifact Schema + Journey-Module Contract

## Contents

- evidence.json schema (validating-ui)
- Allowlist format and discipline
- Journey-module contract (the `run(page)` function)
- Harness CLI surface (local-override points)

## evidence.json schema

`schema_version: "1.0"`. Written by `scripts/smoke.mjs` to
`--out/evidence.json` on every run — including failing runs (the artifact
is the review evidence; a blocked run's artifact carries the violations).

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string `"1.0"` | schema marker |
| `generated_at` | string (ISO) | run timestamp |
| `target` | string | dev-server base URL |
| `journey` | string | journey module basename |
| `allowlist_path` | string \| null | allowlist file used (null = none, strictest mode) |
| `console_errors[]` | string[] | console `error` messages, in order |
| `console_warnings[]` | string[] | console `warning` messages, in order |
| `page_errors[]` | {message, stack}[] | pageerror captures (stack: first 4 lines) |
| `screenshots.full` | string \| null | full-page screenshot filename (relative to `--out`) |
| `screenshots.clip` | string \| null | element-clip screenshot filename (relative to `--out`) |
| `aria_snapshot` | string \| null | page accessibility-tree dump (text) |
| `journey_error` | string \| null | journey assertion/exception message (null = clean) |
| `net_clean` | boolean | true iff no violations and no journey error |
| `allowlisted[]` | {message, pattern, date, reason}[] | messages the allowlist matched |

`net_clean` is the exit-code source: `0` iff `net_clean`, else `1`.
Screenshots are archived for the human manual-validation handoff; the
review subagent reads the text fields (console, page_errors,
aria_snapshot) — never the images.

## Allowlist format and discipline

Project-owned override point: `--allowlist <path>`, else auto-discovered
`.opencode/smoke-allowlist.json` in the working directory, else no
allowlist (strictest). The skill ships no default entries.

```json
{
  "_discipline": "Entries must be dated + justified. Substring match on the message. No blanket console.error suppression.",
  "entries": [
    {
      "pattern": "substring of the message",
      "date": "YYYY-MM-DD",
      "reason": "why this message is acceptable; the defect/source that produces it"
    }
  ]
}
```

Rules: an entry is a substring match on the message text; `date` must be
the entry's creation date; `reason` must name the producing source or
accepted behavior — a blank or `"noise"` reason is a review finding.
Never allowlist a pattern that would also match a runtime defect class
(e.g. a bare `error` or `warn` prefix).

## Journey-module contract

A journey module is project-authored (or adapted from the project's e2e
spec selectors), defaulting to the `writing-e2e-tests` doctrine: role /
accessible-name / testid selectors in that order, condition waits
(`await expect(locator).toBeVisible()` — never `waitForTimeout`), auth
via fixture, `await` on every action.

```js
// <project>/.opencode/smoke/<plan-slug>.journey.mjs
export async function run(page) {
  // navigate + act + assert the user-observable outcome
  await page.goto("/route-that-exercises-the-change");
  await page.getByRole("button", { name: "..." }).click();
  await page.getByRole("dialog").waitFor();
  // close what you open (journey-completeness rule) — assert AFTER the
  // close transition completes
  await page.getByRole("button", { name: "Close" }).click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
}
```

Rules:

1. **Selectors by role / accessible-name / testid** — never bare CSS
   (flag it fragile if forced).
2. **Condition waits only** — never `waitForTimeout`.
3. **Close what you open** (journey-completeness rule, R2): a journey
   that opens a dialog/form must exercise its close path — including
   closing with the form in an open/edited state — or explicitly justify
   why the close path is out of scope (recorded in the run summary).
   Assert console-clean AFTER close transitions complete, not mid-
   journey.
4. **No-visible-UI skip**: if the change has no visible UI, the skill
   skips the step with an explicit "no visible UI" note (it does not run
   the harness).

## Harness CLI surface (local-override points)

```
node smoke.mjs --target <baseURL> --journey <path> --out <dir>
  [--allowlist <path>] [--auth-fixture <path>]
  [--clip-role <role> --clip-name <name> | --clip-testid <id>]
  [--viewport WxH] [--chromium <executable>] [--no-screenshot]
```

| Flag | Purpose | Override surface |
|---|---|---|
| `--target` | dev-server base URL | per-project dev-server config |
| `--journey` | journey module path | project-authored |
| `--out` | evidence dir | e.g. `.opencode/evidence/<plan-slug>/` |
| `--allowlist` | allowlist file | project-owned (auto-discovers `.opencode/smoke-allowlist.json`) |
| `--auth-fixture` | Playwright storageState JSON | project auth fixture |
| `--clip-role` / `--clip-name` | element-clip target (role + name) | optional |
| `--clip-testid` | element-clip target (testid) | optional |
| `--viewport` | viewport, `WxH` | optional, default `1280x720` |
| `--chromium` | chromium executable | `CAPTURE_CHROMIUM_EXECUTABLE` env also honored |
| `--no-screenshot` | skip screenshots | optional |

Env: `VALIDATING_UI_VISION=1` enables the optional advisory vision pass
(`vision-critic-fast` = minimax-m3 over the archived screenshot;
advisory-only, never a gate — see SKILL.md).