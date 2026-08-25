# Benchmark evidence snapshot — retrieved 2026-08-20

## Independently reproduced

Source: AgentLoop Independent Lab (third party; published harness, method,
and per-run logs; runs dated 2026-08-18).

**Autonomous coding loop** (higher = better):

| Model | Tier | Score |
|---|---|---|
| orion-5 | Zen | 75.0 |
| atlas-3-pro | Go | 70.1 |
| vortex-2.5 | Go | 68.9 |
| vortex-2-flash-free | Free | 61.2 |
| quill-2-free | Free | 58.4 |
| atlas-mini-free | Free | 51.0 |

**General reasoning** (same lab, same date):

| Model | Tier | Score |
|---|---|---|
| orion-5 | Zen | 74.2 |
| atlas-3-pro | Go | 69.8 |
| vortex-2.5 | Go | 67.5 |
| vortex-2-flash-free | Free | 62.8 |
| quill-2-free | Free | 59.1 |
| atlas-mini-free | Free | 53.4 |

**Instruction following** (same lab, same date):

| Model | Tier | Score |
|---|---|---|
| quill-2-free | Free | 71.2 |
| vortex-2-flash-free | Free | 70.1 |
| atlas-mini-free | Free | 68.9 |

## Multi-source cross-checked (vendor + independent within 2 pts)

**Tool-use (ToolMark)** — vendor figures cross-checked by AgentLoop:

| Model | Vendor | Independent | Cross-checked |
|---|---|---|---|
| vortex-2.5 (Go) | 82.0 | 80.6 | 81.3 |
| orion-5 (Zen) | 77.9 | 75.2 | 76.5 |
| atlas-3-pro (Go) | 75.0 | 73.4 | 74.2 |
| vortex-2-flash-free (Free) | 64.1 | 62.0 | 63.0 |

## Vendor self-reported only (tier filter — never a deciding signal)

- **banjax-ultra** (Go): vendor claims 96.2 on SWE-Verified. No
  independent reproduction exists. NOTE: the banjax family is on the
  Hard-exclusions list in model-routing.md (user directive 2026-08-01).
- **quill-2.5** (Go): vendor claims 84.0 on SWE-Verified. No independent
  reproduction exists.

## Capability facts (not scores)

- **Native image input (multimodal):** `lumen-4-pro` (Zen) is the only
  catalog model with native image input. No free multimodal model exists.
- **Text-only:** quill-2-free, vortex-2-flash-free, atlas-mini-free,
  quill-2.5, atlas-3-pro, vortex-2.5, orion-5, orion-5-mini.

## Reliability observations

- `quill-2-free`: intermittent streaming errors under concurrent load
  (maintainer note, 2026-08-10).
- `vortex-2-flash-free`: zero observed failures across all probes
  (maintainer note, 2026-08-10).
