# Principles — what a threat model is, and is not

Shared context for the modeling and triage passes. Read this before writing a
fresh model or classifying a finding against one.

## Contents

- The contract
- What a threat model is not
- The four questions
- Provenance over assertion
- Write so a human can read it
- One model or several
- What to leave out

## The contract

A threat model describes the **implicit contract** between a project and its
users: the assumptions it makes about its environment, inputs, and callers;
the security properties it upholds; the properties it explicitly does *not*
uphold; and the misuses that are syntactically possible but fall outside
intended use.

It serves two consumers, and every section must be usable by both without
re-deriving the reasoning:

- the **downstream integrator** — "which threats do I now own, and which does
  the project own?"
- the **triager** — "is the violated property one the project claims, is the
  attacker in scope, is the affected code in scope?" — citing the section that
  justifies the call.

The model describes the project as it **is**, not as it should be. The moment
a sentence starts "the project should" or "we recommend", it is audit output
and does not belong here.

## What a threat model is not

- **Not a vulnerability assessment, audit, pentest, or bug hunt.** Do not
  hunt for defects. Do not enumerate CVE-style findings. Past bugs are not the
  model; a *pattern* across past bugs can be ("historically, integer overflow
  on 32-bit systems, so the assumption that size does not wrap is
  load-bearing"), but the CVE list stays out.
- **Not supply-chain, build, or release hygiene** (action pinning, signing,
  dependency freshness, whether `SECURITY.md` exists). Dependency *trust*
  assumptions are model content; dependency *update* hygiene is not.
- **Not a restatement of the API docs.** The model captures the **unwritten**
  assumptions: what the docs leave implicit, and what their silence means.
- **Not a secure-coding guide** or a list of every theoretical attack. Cover
  the threats the design has an opinion about — by addressing them or by
  declining to.
- **Not a description of private working state.** Model the published,
  committed revision that a downstream reader can see. Uncommitted edits,
  unmerged branches, stashes, and draft PRs are invisible to that reader; if
  in-flight work matters, model it once it lands, or list it under the
  conditions that would change the model.

**Conservative defaults, not silent gaps.** Where the docs are silent, prefer
a **documented disclaimer** of the safe (no-guarantee) direction over an open
question — "no thread-safety is guaranteed" is a verifiable statement about
the project as it is. Three bounds keep that lever honest:

- **An absent guarantee is a disclaimer; an absent behaviour is a scan
  result.** "The docs never promise thread safety" is a §12 disclaimer.
  "I scanned and found no socket" is a §5 assumption (exhaustive scan) or
  inferred (incomplete scan, naming the hole) — the project never promised to
  keep it absent.
- **An absence claim reaches only as far as the source you cite.** A FAQ
  answer about one component says nothing about another; each needs its own
  check.
- **Silence never closes the serious cases.** A disclaimer resting on the
  *absence* of a statement never closes a security-critical report, a known
  non-finding, or a dependency-contract route. "Nobody promised otherwise" is
  a reason to ask the maintainer, not a reason to close a memory-safety
  report.

## The four questions

Every section answers one of:

1. **What does the project assume?** Environment, callers, inputs,
   dependencies, and which threat actors are in or out of scope.
2. **What does it guarantee, given those assumptions?** Memory safety on
   valid input, deterministic output, bounded resource use, structural output
   invariants.
3. **What does it explicitly leave to the user?** Input validation at the
   boundary, output sanitization, transport security, key management, rate
   limiting.
4. **What known misuses look reasonable but violate (1)?** Anti-patterns the
   API permits, and false friends (a CRC is not a MAC; a hash is not
   collision-resistant; a PRNG is not a CSPRNG; a resource sandbox is not
   isolation).

Use the contract-dimension matrix to make these answers complete, not to turn
the model into an audit: it asks whether the project claims, disclaims, or has
not decided edge semantics (overflow, callback failure, cycles,
serialization, lifecycle, resource bounds); it does not test the
implementation for defects.

## Provenance over assertion

Every non-trivial claim carries exactly one tag — *(documented, source)*,
*(maintainer, YYYY-MM)*, *(assumption, QN)*, or *(inferred, QN)*. The full
definition and citation rules live in
[artifact-contract.md](artifact-contract.md).

**Mine before you infer.** Facts attributable to maintainer-authored sources
(README, API reference, header comments, manpage, FAQ, changelog rationale,
issue rulings) are documented and need no escalation. A draft that is mostly
inferred usually means the mining pass was thin — not that the project is
undocumented.

## Write so a human can read it

The model is read by a tired on-call engineer and an integrator under
deadline, not a thesis committee. Accuracy comes first, but plain prose is a
requirement:

- One idea per sentence. Split three-"and" chains and semicolon-joined
  clauses.
- Short, common words; verbs over nominalizations; active voice with a real
  subject.
- Define a term once, in plain words, the first time it appears.
- Break piled-up noun stacks and long inline lists into short bullets or
  table rows.
- Keep provenance tags and section cross-references, but never let a citation
  stand in for the sentence: the reader should get the point without
  following it.
- Say the same precise thing in fewer, plainer words.

## One model or several

A repo with multiple component families is usually one model — that is what
the component-family table is for. **Split** into separate documents when
families do not share a release cadence, a maintainer set, or an adversary
model (a core library plus an independently versioned GUI or hosted service,
for example). A model that must constantly say "except for component X" is a
sign to split. When splitting, name the sibling models in each header.

## What to leave out

Recurring temptations, and why:

- **CVE history.** Past bugs are not the model. A pattern across past bugs
  can be; the individual reports seed the producer-side backtest corpus only
  and never appear in the published artifact.
- **Code-level findings.** "Function X ignores the return of Y" is a code
  review result, not a contract statement.
- **Build/release/SDLC hygiene.** Dependency trust per dependency is model
  content; dependency freshness is not.
- **What the README already says** as a plain feature list. The model adds
  the contract the docs leave implicit.
- **Generic platitudes** ("use defense in depth", "keep dependencies up to
  date"). Cut on sight.
- **Speculation about future features.** Model what exists; put a change
  under the conditions that would change the model.
