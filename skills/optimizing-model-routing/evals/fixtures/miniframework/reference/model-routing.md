# Model Routing

Maps workflow **roles** to recommended models. Skills reference roles only;
this file is the single place model IDs appear.

- Retrieved: 2026-07-01 (catalog + benchmark snapshot of record)
- Review cadence: monthly, or when a deprecation notice lands
- Status: bindings last reviewed 2026-07-01 — predates the 2026-08-20
  benchmark snapshot and the 2026-08-15 catalog removals.

## Roles → bindings

Tiers: **Free default** (`opencode/*-free`, $0) → **Escalation — Go
flat-rate** → **Escalation — Zen PAYG**.

| Role | Used by (loop stage) | Free default | Escalation — Go | Escalation — Zen |
|---|---|---|---|---|
| `planner` | design + architecture skills | quill-2-free | atlas-3-pro | orion-5 |
| `implementer` | build + test-writing skills | vortex-2-flash-free | vortex-2.5 | orion-5 |
| `triager` | triage + backlog skills | atlas-2.9-free | quill-2.5 | orion-5-mini |
| `council-member` | multi-perspective review | family mix: quill-2-free + atlas-mini-free + vortex-2-flash-free | — | — |
| `vision-critic-fast` | UI iteration loop | — (no free multimodal) | quill-2.5 | lumen-4-pro |

Agents bind the free default in their `model:` frontmatter; escalation
rows are applied by the harness at escalation time.

## Hard exclusions

Never bind, recommend, or escalate to these models in any tier. User
directive, dated 2026-08-01.

| Excluded ID | Tier(s) | Reason |
|---|---|---|
| `banjax-ultra` | Go | user directive (2026-08-01): banjax family excluded from everything |
| `banjax-frontier` | Zen | same |

When a new `banjax-*` ID appears in a catalog fetch, treat it as excluded
automatically.

## Deprecation watch

| Model | Status | Action |
|---|---|---|
| `atlas-2.9-free` (free tier) | removed from catalog 2026-08-15 | rebind to a catalog-valid free generalist |
| `quill-1-free` (free tier) | removed 2026-06-20 | already rebound to quill-2-free |

## Provider notes

- **Free tier** ($0): the `opencode/*-free` catalog entries. Default tier.
- **Go** ($10/mo flat): open models; escalation only.
- **Zen** (pay-as-you-go): full catalog; escalation only.

## Update procedure

1. Fetch current catalogs:
   - https://opencode.ai/zen/v1/models
   - https://opencode.ai/zen/go/v1/models
2. Update the tables above; bump the retrieved date.
3. If a bound model is deprecated or beaten on objective evidence, update
   the role row and note it in the commit message.
4. Record benchmark evidence alongside any change.
