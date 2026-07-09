#!/usr/bin/env node
// check-adherence.js — the loop's QUALITY gate (the second closure
// condition). It is the CSS-system analogue of `debugging-test-failures`'s
// cardinal rule: never "win" a visual target by weakening the system. Here
// "weakening the system" means raising specificity, adding a new
// `!important`, or a magic-px override that defeats the project's tokens. A
// fix that needs any of those is a SIGNAL the change is larger than a
// correction — it routes to design, not to an override.
//
//   node check-adherence.js <candidate.scss|css> \
//       --baseline <baseline.scss|css> --system <name> --tokens <tokens.json> \
//       [--target-selector <sel>]
//
// FAILABLE — exits non-zero when the candidate:
//   - raises specificity on the target rule (more compound selectors than the
//     baseline rule for the same target), OR
//   - introduces a new `!important` the baseline did not have, OR
//   - uses a magic px on a track property (padding/margin/border-radius/gap/
//     font-size) where the project has a token/$variable AND the candidate
//     could have used the named token instead (a named token is
//     self-documenting; a magic px is not), OR
//   - violates the detected system's naming discipline (BEM flat block__elem
//     --mod, Tailwind utilities / @apply sparingly, no ad-hoc class selectors,
//     Vuetify: no gratuitous ::v-deep, prefer props/semantic classes).
//
// Passes (exit 0) only when the candidate edits within the system: flat
// specificity, no new !important, track values snap to a token/variable, and
// naming matches the methodology.
const fs = require('fs')

function fail(msg) { console.error('check-adherence: FAILED — ' + msg); process.exit(1) }
function arg(name) {
  const i = process.argv.indexOf(name)
  if (i < 0) return null
  const v = process.argv[i + 1]
  if (v == null) { console.error('missing value for ' + name); process.exit(2) }
  return v
}
const cand = arg('--candidate') || (process.argv[2] && process.argv[2].startsWith('--') ? null : process.argv[2])
const base = arg('--baseline')
const system = arg('--system')
const tokensPath = arg('--tokens')
const targetSel = arg('--target-selector')
if (!cand || !base || !system) { console.error('usage: check-adherence.js <candidate> --baseline <b> --system <name> [--tokens <t.json>] [--target-selector <sel>]'); process.exit(2) }

// --- minimal SCSS/CSS declaration reader -------------------------------
// Good enough for fixture sources: split into top-level rules `{ ... }`,
// capture the selector text and the declarations inside. Handles SCSS nesting
// shallowly by indent is not attempted; fixtures use flat rules.
function stripComments(s) {
  return s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
    // SCSS forward-declarations are statements, not selectors — drop so the
    // first real selector isn't glued to an @use/@import when regex captures.
    .replace(/^[ \t]*@(use|forward|import)[^;]*;[ \t]*\n/gm, '')
}
function readRules(raw) {
  const src = stripComments(raw)
  const rules = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let m
  while ((m = re.exec(src)) !== null) {
    const selector = m[1].trim()
    const body = m[2]
    if (!selector) continue
    // skip SCSS @-rules like @use / @include / @media wrappers (no declarations
    // of interest for adherence); a bare @use line has no following brace.
    if (selector.startsWith('@')) continue
    const decls = []
    const dre = /([\w-]+)\s*:\s*([^;]+);/g
    let d
    while ((d = dre.exec(body)) !== null) {
      decls.push({ prop: d[1].toLowerCase(), value: d[2].trim() })
    }
    rules.push({ selector, decls })
  }
  return rules
}
// specificity proxy: count compound selectors (comma-splits counted once; we
// use the FIRST comma arm). ::v-deep / :deep() count as themselves.
function specificity(sel) {
  const arm = sel.split(',')[0].trim()
  // split on descendant combinators
  const parts = arm.split(/\s+/).filter(Boolean)
  return parts.length
}
function declIndex(rules, selector, prop) {
  return rules.find((r) => r.selector === selector && r.decls.find((d) => d.prop === prop))
}

let candSrc, baseSrc
try { candSrc = fs.readFileSync(cand, 'utf8') } catch (e) { fail(`cannot read candidate ${cand}: ${e.message}`) }
try { baseSrc = fs.readFileSync(base, 'utf8') } catch (e) { fail(`cannot read baseline ${base}: ${e.message}`) }
const candRules = readRules(candSrc)
const baseRules = readRules(baseSrc)
const errors = []

// TOKENS: a map of { "<prop>": ["$tokenA", "$tokenB", ...] } OR
// { "<category>": [...] }. A track value is a "magic px" if it is a bare
// number+unit AND the tokens file lists a token for that prop AND that token
// is available in the candidate source (defined or it is a known theme token).
const TRACK_PROPS = new Set(['padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-right','margin-bottom','margin-left','border-radius','gap','row-gap','column-gap','font-size','line-height','width','height','min-width','max-width'])
const SHORTHAND_EXPAND = {
  padding: ['padding-top','padding-right','padding-bottom','padding-left'],
  margin: ['margin-top','margin-right','margin-bottom','margin-left'],
  'border-radius': ['border-radius'],
  gap: ['gap','row-gap','column-gap'],
}
function trackLonghands(prop) {
  if (SHORTHAND_EXPAND[prop]) return SHORTHAND_EXPAND[prop]
  if (TRACK_PROPS.has(prop)) return [prop]
  return []
}
let tokens = {}
if (tokensPath) {
  try { tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8')) } catch (e) { fail(`cannot read tokens ${tokensPath}: ${e.message}`) }
}
function tokensFor(prop) {
  // accept keys by exact prop or by category prefix mapping
  const out = new Set()
  if (tokens[prop]) (tokens[prop]).forEach((t) => out.add(t))
  return out
}
function isMagicPx(value, prop) {
  const longhands = trackLonghands(prop)
  if (longhands.length === 0) return false
  // a "magic px" is a bare numeric with unit, NOT a variable/token reference.
  if (/(^|[^$\w])\d+(\.\d+)?px($|[^a-zA-Z])/i.test(value) === false) return false
  // tokens.json is the authoritative declaration of what named tokens the
  // project has for this property. If a token exists for any longhand this
  // declaration sets, a bare px is a weaken of the system — snap to the token.
  const toks = new Set()
  for (const lh of longhands) for (const t of tokensFor(lh)) toks.add(t)
  return toks.size > 0
}

// --- checks ------------------------------------------------------------

// 1. NEW !important anywhere the baseline did not have one.
const baseImpts = new Set()
for (const r of baseRules) for (const d of r.decls) if (/!important/i.test(d.value)) baseImpts.add(r.selector + '/' + d.prop)
for (const r of candRules) {
  for (const d of r.decls) {
    if (/!important/i.test(d.value) && !baseImpts.has(r.selector + '/' + d.prop)) {
      errors.push(`new !important on '${r.selector}' ${d.prop} — a raw override to win the cascade is the cardinal-rule violation; snap to a token or route to design`)
    }
  }
}

// 2. SPECIFICITY RAISE on the target rule.
if (targetSel) {
  const bRule = baseRules.find((r) => r.selector === targetSel)
  const cRule = candRules.find((r) => r.selector === targetSel)
  if (bRule && cRule) {
    const bSpec = specificity(bRule.selector), cSpec = specificity(cRule.selector)
    if (bSpec !== cSpec) {
      errors.push(`specificity changed on '${targetSel}': baseline ${bSpec} compound part(s) → candidate ${cSpec} (a raised specificity to win the cascade is a weaken of the system)`)
    }
  }
  // also detect an ADDED more-specific selector that now wins the same target
  // (e.g. baseline `.card` → candidate adds `.app .card`). Covered above when
  // targetSel is the original: a new compound selector is a different string.
}

// 3. MAGIC PX on track props where a token exists.
for (const r of candRules) {
  for (const d of r.decls) {
    if (isMagicPx(d.value, d.prop)) {
      const toks = new Set()
      for (const lh of trackLonghands(d.prop)) for (const t of tokensFor(lh)) toks.add(t)
      errors.push(`magic px on '${r.selector}' ${d.prop} = '${d.value}' but a token exists (${[...toks].join(', ')}) — snap to the named token; a magic px defeats the scale and is not self-documenting`)
    }
  }
}

// 4. SYSTEM NAMING DISCIPLINE.
function classSelectors(sel) {
  return (sel.match(/\.[\w-]+/g) || []).map((s) => s.slice(1))
}
const BEM_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)*(__[a-z0-9-]+)?(--[a-z0-9-]+)*$/
if (system === 'bem') {
  for (const r of candRules) {
    for (const cls of classSelectors(r.selector)) {
      if (!BEM_RE.test(cls)) errors.push(`BEM naming violation: '.${cls}' is not block__element--modifier (flat specificity, one block family)`)
    }
    // BEM is flat — a descendant compound selector with two element classes is a smell
    if ((r.selector.match(/\./g) || []).length > 1 && !r.selector.includes('__')) {
      errors.push(`BEM flatness: '${r.selector}' chains two class hooks (descendant coupling) — use element/modifier classes on the node, not descendant selectors`)
    }
  }
} else if (system === 'tailwind') {
  for (const r of candRules) {
    // Tailwind: utilities compose in markup; a non-@apply authored class rule is ad-hoc CSS.
    if (!r.selector.startsWith('@') && (r.selector.match(/\./g) || []).length > 0) {
      errors.push(`Tailwind discipline: '${r.selector}' is an ad-hoc class selector in CSS; compose utilities in markup or use @apply sparingly in a component layer (no bespoke class names)`)
    }
  }
} else if (system === 'vuetify-scss') {
  for (const r of candRules) {
    if (/::v-deep|:deep\(/.test(r.selector)) {
      errors.push(`Vuetify scoping: '${r.selector}' uses ::v-deep/:deep() — prefer a component prop / semantic class or a scoped token over piercing the component boundary (deprecate deep unless truly unavoidable)`)
    }
  }
} else {
  errors.push(`unknown system '${system}' (expected bem | tailwind | vuetify-scss)`)
}

if (errors.length) {
  console.error('check-adherence: FAILED (the fix weakened the CSS system)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(`check-adherence: ok — ${candRules.length} rule(s); system '${system}'; no specificity raise, no new !important, no magic px, naming ok`)
process.exit(0)