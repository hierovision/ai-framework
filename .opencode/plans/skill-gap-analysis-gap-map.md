# Skill-pool gap map — Phase A companion

Status: **awaiting user approval** (plan AC2)
Created: 2026-09-28
Related plan: `.opencode/plans/skill-gap-analysis.md` (approved 2026-09-27)
Sources audited: 24 registered skills (`registry.json`); sample repos
`/home/hierovision/repos/{pt,pln,choredomino,clcnext}` (read-only); the plan's
work-type inventory.

## How to read this

- **Verdict scale.** `covered` — a skill owns the phase with usable guidance
  (skill + file cited). `weak` — partial or conditional coverage: a skill
  touches it, or repo practice exists without a skill, or a stack/domain gap
  blocks it. `absent` — no skill and no practice evidence; the work would be
  improvised.
- **Evidence rule.** Every cell cites a skill/file (repo-relative) or a
  sample-repo path. Cells without a sample repo resting on pool analysis say
  so — no invented practice evidence.
- **Sample-repo coverage.** `pt` = education/therapy PWA (Vue 3, Supabase,
  Playwright, LighthouseCI, REQUIREMENTS + triaged ROADMAP). `pln` = education
  monorepo (Next.js/TypeORM/GraphQL legacy; 10 CI workflows; ADR-0001;
  design plan + council review). `choredomino` = household PWA (Vue 3,
  Supabase migrations in CI, Azure SWA; **no test files found**). `clcnext` =
  greenfield (README only). No sample repo exists for medical / SaaS-specific /
  turnkey / location-aware; those cells rest on pool evidence and say so.

## The matrix (7 work types × 7 phases = 49 cells)

Legend per cell: verdict + evidence. Phase order:
discover | design | build | verify | secure | deploy | operate.

| Work type | discover | design | build | verify | secure | deploy | operate |
|---|---|---|---|---|---|---|---|
| **Small-business web presence** | covered (generic) — `triaging-requirements`; no content-strategy step | weak — `designing-architecture` generic; no SEO/CMS/design-system guidance | covered — `implementing-features` | covered — test trio; content-site perf budgets only project-local (`pt/.lighthouseci`) | weak — `securing-ci` (pipeline only) | covered — `deploying-to-azure-swa`; DNS practice `pt/.github/workflows/azure-dns-config.yml` | absent — analytics/privacy/uptime/email deliverability unguided |
| **Non-profit** | covered (generic) — as above | weak — as above; a11y depth matters more | covered — `implementing-features` | covered — test trio + `auditing-accessibility` (axe ceiling) | weak — `securing-ci` only | covered — as above | absent — as above |
| **Education (security-certification focus)** | covered — `pt/docs/REQUIREMENTS.md`; `pln/ROADMAP.md` (triaged 2026-09-27) | covered — `pln/.opencode/plans/identity-tenancy-foundation.md`, `pln/docs/ADRs/ADR-0001-platform-architecture.md` | covered — `implementing-features`; pln onboarding recorded in its ROADMAP sources | covered — `pln` 30 test files + 10 workflows; `pt/e2e/*.spec.ts` | weak — privacy practice exists (`pln-privacy-terms` repo); no security skill | covered — `pln` preview/deploy workflows; `pt`/`choredomino` Azure SWA | weak — quality/deploy workflows exist; no monitoring/incident guidance |
| **Medical** | weak — generic backlog skills; no compliance-requirements step (no sample repo) | weak — `designing-architecture` generic; compliance-informed architecture unguided | covered — `implementing-features` | covered — test trio | **absent** — no threat-modeling / authz / secrets / OWASP skill; `securing-ci` is pipeline-only | covered — `deploying-with-supabase` / `deploying-to-azure-swa` (target assumption) | **absent** — uptime/backups/runbooks/incident unguided |
| **SaaS** | covered (generic) — backlog skills | weak — tenancy/RBAC/billing design patterns absent; manual precedent (`pln` identity-tenancy plan, issue #29) | covered — `implementing-features` | covered — test trio | weak — as medical, plus multi-tenant authz patterns absent | covered — Supabase/SWA skills | absent — quotas/monitoring/onboarding/lifecycle email unguided |
| **Turnkey** | weak — generic backlog skills; packaging/distribution requirements step absent | weak — no distribution/update-channel guidance | covered — `implementing-features` | covered — test trio | weak — `securing-ci` only | weak — deploy skills assume Supabase/SWA | absent — as above |
| **Location-aware** | weak — generic backlog skills | absent — geolocation/maps/offline-map design absent | covered (generic) — `implementing-features` | weak — location-dependent journeys unguided; e2e waits only | weak — location-data privacy unguided | covered — Supabase/SWA targets | absent — as above |

**Cell count: 49 populated, zero blank verdict cells.**

## Cross-cutting findings

1. **Use-case inventories missing pool-wide.** Only `sourcing-external-skills`
   carries `references/use-cases.md` (7 rows, 100% eval-mapped). The plan's
   Q5 ≥80% rule needs an inventory per skill before its landing/amendment
   gate — 23 skills need one authored during their amendment pass (AC6).
2. **Legacy eval debt:** 93 evals total, 19 typed / **74 legacy**
   (no `expect`). Already tracked under RM-003 (migrate-on-touch); relevant
   because amended skills must bring their amended surface to the typed bar
   (AC6).
3. **Stack references are two:** `vue-supabase` (10 role-tailored copies) and
   `nextjs-supabase` (design-time; RM-020 covers the nine siblings). Any other
   stack runs generic.
4. **The `secure` and `operate` columns are the pool-wide weakness**; work
   types differ mainly in which security/ops capabilities they need first
   (medical: compliance+availability; SaaS: tenancy+billing; small
   sites: privacy+deliverability).

## Ranked candidate-search briefs (Phase B input)

Rank = impact × urgency on the program's finish line (types × sizes, security
and correctness first). Source tiers per ADR-0011/0012: (1) Agent Skills
format, (2) adjacent frameworks (port, never copy), (3) authoritative
references (authoring input only), (4) out of bounds.

**1. Application security engineering (beyond CI).**
Gap: threat modeling, authn/authz patterns, secrets management, OWASP-class
review, CSP/security headers, dependency audit beyond CI pins, incident
response. Evidence: `secure` column absent/weak for medical/SaaS; ADR-0012
covers ingest, not app code. Search: tier-1/2 candidates from security-focused
skill collections; tier-3 OWASP ASVS/Cheat Sheets, OWASP Top 10, CSP docs as
authoring input. Must-have: runnable review workflow with observable outputs
(checklist + evidence), framework-neutral, no exploit execution without
sign-off. Notes: pair with `reviewing-code` (review lens) rather than
duplicating it.

**2. SaaS tenancy & authorization patterns.**
Gap: orgs/memberships/invites, RBAC, multi-tenant RLS patterns, seat/role
design. Evidence: `pln` identity-tenancy design hand-translated (issue #29);
`weak` design cell for SaaS/education. Search: tier-1 skill candidates;
tier-3 Supabase multi-tenant/RLS guidance + OWASP authorization material.
Must-have: design-time checklist + testable acceptance shapes (isolation
queries), stack refs for Supabase.

**3. Application observability & operations.**
Gap: error monitoring/tracing, structured logging, analytics, uptime,
backups/DR, runbooks, on-call/incident basics. Evidence: `operate` column
absent across types. Search: tier-1/2 candidates; tier-3 SRE/observability
reference material; provider docs for the chosen tools. Must-have: plan-time
design checklist + acceptance criteria shapes (alert conditions, retention,
restore drill). Notes: `observing-runs` is agent-run telemetry — adjacent,
not overlapping.

**4. PWA / offline engineering depth.**
Gap: service-worker lifecycle, caching strategies, manifest/installability,
background sync, push, update flows, performance budgets. Evidence: practice
in `pt` (offline-first) and `choredomino` (vite-plugin-pwa, RxDB); no skill;
`designing-architecture` vue-supabase reference has only planning checks.
Search: tier-1 PWA skill candidates; tier-3 web.dev/PWA + Workbox docs.
Must-have: build/verify workflow with observable checks (SW update flow,
offline journey), stack-aware (Vite/Vue, Next.js).

**5. Accessibility beyond automation.**
Gap: manual WCAG technique depth, screen-reader/AT testing, ARIA authoring
patterns, SPA focus management, form semantics. Evidence:
`auditing-accessibility` states its axe ceiling (~30–40%) and manual
checklist; `pt` targets WCAG AA. Search: tier-1/2 candidates; tier-3 WCAG
2.2 techniques, APG patterns. Must-have: manual-technique workflow with
observable artifacts, complements (does not replace) the axe audit.

**6. Billing, metering, quota & rate limiting.**
Gap: subscription lifecycle, usage metering, quotas, rate limiting, dunning.
Evidence: SaaS design/operate cells; no pool coverage. Search: tier-1/2
candidates; tier-3 Stripe/Billing docs as authoring input. Must-have:
plan-time patterns + verifiable ACs (webhook idempotency, quota enforcement).

**7. Background jobs, queues & email lifecycle.**
Gap: job queues, scheduled/background processing, retries/idempotency;
transactional email deliverability (SPF/DKIM/DMARC, bounce handling). Evidence:
SaaS/small-business cells; `choredomino`'s migrate job is CI, not app
processing. Search: tier-1/2 candidates; tier-3 queue/provider docs.
Must-have: design + verify shapes (retry/idempotency assertions).

**8. SEO, metadata & content-site performance.**
Gap: SEO/metadata/OG, Core Web Vitals budgets for content sites, CMS
choice/migration. Evidence: small-business/non-profit design+operate cells;
`pt/.lighthouseci` shows the practice local to one repo. Search: tier-1/2
candidates; tier-3 CWV/SEO guidance. Must-have: measurable budget checks
(Lighthouse CI-style) + metadata checklists.

**9. Privacy & compliance reference workflow.**
Gap: privacy policy/consent/tracking inventory; medical/education compliance
posture as authoritative-reference consumption (not legal advice). Evidence:
`pln-privacy-terms` repo practice; medical cells. Search: tier-3 compliance
material (HIPAA/GDPR-facing references) + tier-1 candidates for
consent/tracking workflows. Must-have: checklist workflow with explicit
"not legal advice" boundary; cite sources, never assert compliance.

**10. API design, versioning & scale data patterns.**
Gap: API design/versioning, data modeling at scale, caching, search,
realtime, file uploads. Evidence: `pln` GraphQL/TypeORM practice with no
skill; SaaS/education cells. Search: tier-1/2 candidates; tier-3
API-style references. Must-have: design-time review checklist with verifiable
shapes; framework-neutral where possible.

**11. Design-system construction & visual quality.**
Gap: building/evolving a design system (tokens, components, docs) beyond
fixing single defects. Evidence: `correcting-ui` fixes defects; no
construction skill; every web type needs one. Search: tier-1/2 candidates;
tier-3 design-token/WCAG-contrast references. Must-have: observable outputs
(token files, component gallery), pairs with `capturing-ui-evidence`.

**12. Location-aware engineering.**
Gap: geolocation, maps, offline maps, tour/route UX, location-data privacy.
Evidence: location-aware row; no skill, no sample repo. Search: tier-1
candidates; tier-3 mapping SDK docs as authoring input. Must-have:
design + verify shapes for location permissions and offline behavior.

**13. Internationalization / localization.**
Gap: i18n architecture, string extraction, locale routing, RTL, locale-aware
formats. Evidence: education/medical reach assumptions; no pool coverage.
Search: tier-1/2 candidates; tier-3 i18n references. Must-have:
framework-appropriate design checklist + verifiable locale behavior.

## Pool audit — trigger boundary, closure, coverage baseline (24 skills)

Coverage baseline: evals typed/legacy; `use-cases` present or `—`.

| Skill | Trigger boundary (abridged) | Closure (abridged) | Baseline |
|---|---|---|---|
| auditing-accessibility | "audit a11y", WCAG checks; not fixing/capturing/e2e | axe targets + schema-valid report + manual checklist; read-only | 0/4; — |
| authoring-skills | create/edit/optimize skills, write evals; no explicit not-for clause | evals pass + validator + install verified | 2/1; — |
| capturing-ui-evidence | "capture current state", CSS evidence; not diagnosing/fixing | schema-valid evidence artifact; STOP | 0/3; — |
| correcting-ui | fix CSS defects from evidence; broad restyle → design | measurable delta + regression guard + adherence | 0/6; — |
| debugging-test-failures | non-converging verification; not writing tests/converging plans | root cause + fix + full suite green, or honest terminal | 0/5; — |
| deploying-to-azure-swa | SWA workflows; not CI topology/token hardening | workflow drafted + trigger split + approved; never deploys | 0/3; — |
| deploying-with-supabase | Supabase migrations in CI; not topology/hardening | migration config + invariants + approved; never db push | 0/3; — |
| designing-architecture | plan one item; not trivial edits/research/backlog/CI | plan artifact + verifiable ACs + approved; STOP | 1/3; — |
| designing-cicd | CI/CD topology design; not app code/review/deploy specifics | topology plan + observable gates + approved | 0/3; — |
| implementing-features | execute one approved plan; not planning/debugging | plan Verification green + History + manual handoff | 1/9; — |
| managing-github-issues | roadmap → issues (+Project ranking) | idempotent re-run 0-to-create; cleanup gated | 0/2; — |
| observing-runs | run-log schema/emission/query; not prompt-feeding | append-only per-run record + out-of-band query | 2/0; — |
| optimizing-model-routing | rebind models from evidence; not one-off config | approval-gated apply + verify_rebind; PR | 0/3; deferred |
| refining-issue-acceptance | rough issue → spec+ACs; not creating/triage/impl | issue edited only on validation PASS | 0/4; — |
| releasing-a-version | cut release/bump/changelog; not CI topology/issues | tag + draft release verified; publish gated | 3/0; — |
| reviewing-code | review diff/branch vs plan; not fixing/re-running design | every hunk + verdict + REVIEW.md; read-only | 1/4; — |
| securing-ci | harden CI tokens/supply chain; not topology/deploy | least-privilege + pinned + protected; approved | 0/3; — |
| sourcing-external-skills | screen external skills; not authoring/adjudication | every candidate terminal + gates recorded | 7/0; 7 rows |
| triaging-requirements | backlog → ROADMAP; not single specs/estimates | every resolvable source item resolved | 1/2; — |
| validating-against-official-docs | validate vs vendor docs; not writing artifacts | cited ADHERENCE.md + gaps with fixes; STOP | 0/3; deferred |
| validating-ui | runtime UI validation in-loop; not e2e authoring | net verdict + council findings + evidence paths | 0/2; — |
| writing-e2e-tests | Playwright journeys; not unit/integration/debugging | spec + AC map + discipline + suite green | 0/4; — |
| writing-integration-tests | seam tests (store/client, DB/policy); not unit/e2e | suite green + red-on-broken + additive | 0/4; — |
| writing-unit-tests | isolated logic tests; not seams/journeys | suite green + red-on-broken + no weakened net | 1/3; — |

## History

- 2026-09-28 — Gap map produced by the Phase A read-only audit (24-skill pool
  inventory; `pt`/`pln`/`choredomino`/`clcnext` inspected read-only; 49-cell
  matrix; 13 ranked candidate-search briefs). **User approval pending (AC2).**
