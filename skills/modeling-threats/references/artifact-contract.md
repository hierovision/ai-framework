# Artifact contract — the prose model and its companions

The deliverable is three files written beside each other at the modeled root
(or the path the user names):

| Artifact | Role | Authority |
|---|---|---|
| `threat-model.md` | Canonical prose plus embedded tables | 1 — the source of truth |
| `threat-model.yaml` | Structured index for triage pipelines | 2 — derived; wrong when it disagrees with the prose |
| `threat-model.json` | Flat export for external consumers | 3 — lossy; never a triage input |

**Regenerate the derived artifacts whenever the prose changes**, and record in
the YAML the prose version (path plus hash) it derives from. Never introduce a
fact in YAML that the prose does not carry. The JSON's limits are part of its
contract: it does not carry the triage policy, the disposition precedence, or
disclaimer tiers, so a consumer holding only the JSON cannot route a report
against the model.

## Contents

- Provenance tags
- Status, triage policy, confidence
- Canonical prose structure (§1–§19)
- Marking a section Not applicable
- Self-check gates

## Provenance tags

Every non-trivial claim carries exactly one inline tag:

| Tag | Meaning |
|---|---|
| *(documented, source)* | Stated in a maintainer-authored public source: docs, headers, FAQ/manpage, `SECURITY.md`, release rationale, or an issue ruling. **Cite a locator, not a bare filename** — file plus function/macro/struct, a named doc section, or a quote of twelve words or fewer. A bare filename is not a citation. |
| *(maintainer, YYYY-MM)* | Stated by a maintainer in response to a question from this process. Always dated. |
| *(assumption, QN)* | A conservative default the author is willing to act on now, chosen where docs are silent and no answer exists. Still unratified; the QN resolves in §18. |
| *(inferred, QN)* | Reasoned from code, absence of a feature, or domain knowledge, **without** a committed default. Genuinely open; the QN resolves in §18. |

Rules:

- **No hedge-tags** ("implicit", "documented in purpose", "generally known").
  If a claim is not clearly documented or maintainer-sourced, it is an
  assumption or an inference.
- **A parenthesized kind is always a claim tag.** Name a tag kind as
  vocabulary in **bold** (`an **inferred** claim may only escalate`), never in
  tag syntax without its source/date/QN.
- **Retain tags in the published model.** A disposition that closes a report
  cites the tagged claim; bare prose is not defensible.
- **Never launder authority.** An inference relabelled documented is the
  cardinal-rule violation — it manufactures a project promise the project
  never made.
- **Every inferred/assumption tag maps to a §18 question** that states a
  proposed answer. Extra edge-case or meta questions are allowed.
- **A citation you cannot fill is fixed by opening the file, never by
  deleting the column.** Tag the row inferred with a question if the locator
  cannot be found.

**Absence claims.** An absent *guarantee* verifiable in the public API is a
*(documented)* §12 disclaimer. An absent *behaviour* found by scanning the
sources is a §5 assumption (exhaustive scan) or inferred (incomplete scan,
naming the hole: generated code, dynamic dispatch, unread `#ifdef`, or a
dependency acting on the project's behalf). An absence claim reaches only as
far as the component, family, or dimension its cited source names.

## Status, triage policy, confidence

The §1 header declares:

- **Status** — `draft` (work in progress, not triage-ready),
  `unratified` (published without maintainer sign-off; open questions
  remain), or `accepted` (every claim documented/maintainer; zero
  inferred/assumption tags). Use `unratified` rather than `accepted` while
  any open question remains.
- **Triage policy** — `strict` (default) or `relaxed`. It controls only what
  an **assumption** may close; inferred claims never close and the
  security-critical floor always holds (see [triage.md](triage.md)).
- **Confidence count** — documented / maintainer / assumption / inferred
  counts, kept current. A draft with none is fully reviewed or overclaiming.
- **Provenance legend** — the one-line key for the four tags.
- **Triager quick-start** — the boxed routing algorithm ending in the
  provenance gate. A model that routes to a disposition without gating the
  close is not triage-ready.
- **Backtest note** — corpus and cluster counts, real-versus-synthesized
  split, disposition histogram, and the fail-safe figure (historically-fixed
  items routed to a closing disposition; target zero). If no history was
  reachable, say exactly: *"no historical corpus was available; the backtest
  routed N synthesized cases only."* Never present synthesized cases as
  history.

## Canonical prose structure (§1–§19)

Use this order. Rename sections to fit a project's house style if needed, but
cover the same ground. Each section is substantive or exactly `Not applicable
— <reason>`.

### §1 Header

Project, version/commit, date, author(s) of the model; status; triage policy;
confidence count; provenance legend; one-paragraph plain description;
generation note (what produced the draft, human or agent); triager quick-start;
backtest note; sibling models if any.

### §2 Scope and intended use

Concrete intended use cases ("in-process decoding of caller-held files" beats
"a library"); deployment context (library / CLI / daemon / service /
distributed system); caller expectations and trust level. For a network
service, split roles into *client* (untrusted), *operator/admin* (trusted for
the instance), and *peer* (authenticated but adversarial). Lead with the
**component-family table**: family, representative entry point, whether it
touches anything outside the process, and in/out of this model.

### §3 Out of scope (explicit non-goals)

Use cases the project does not support; threats not defended against, each
with a reason; shipped-but-unsupported code (`contrib/`, examples, vendored
trees, demos) with an explicit policy. **Check each exclusion against the
build, not the directory name**: a file the supported build compiles is in
scope wherever it lives; name the exact path and the platform or flag that
pulls it in. An unqualified exclusion fails open.

### §4 Trust boundaries and data flow

Where the boundary sits; the path data takes as trust transitions (skip with a
reason if purely computational); a simple diagram when three or more roles
exist. State the **reachability precondition** per component — the condition a
finding must meet to matter.

### §5 Environment assumptions

OS/runtime/hardware, concurrency and memory model, time and filesystem
assumptions. Include the **no-surprise side-effects inventory**: what the
project does *not* do to its host (sockets, subprocesses, signal handlers, env
reads, stdout, global state). Tag negatives by scan quality, not by default.

### §6 Build-time and configuration variants

Flags and knobs that **change which security properties hold**, with their
defaults and the maintainer's support posture. **Support posture, not
defaultness, controls routing**: a defect in a supported configuration is
in-model even when that configuration is non-default; a configuration is
out-of-model only when this section marks it dev-only, discouraged for the
modeled exposure, or unsupported. For an insecure default, record the
maintainer's ruling (supported production posture vs dev-only).

### §7 Assumptions about inputs

- **Per-input-operand trust table** — `Entry point | Input operand |
  Attacker-controllable? | Control kind | Caller must enforce | Provenance`.
  Cover direct parameters and security-relevant indirect inputs; for services,
  cover headers and connection metadata as well as bodies. Do not collapse
  control into a boolean: use control kinds (data, size/rate, type/class,
  callback/code, object-graph topology, collaborator implementation,
  resource-name, serialized state; project-specific kinds use an `x-`
  prefix).
- **Contract-dimension matrix** — one row per applicable dimension for every
  in-scope family: `Component | Dimension | Status | Conditions / boundary |
  Routes to | Provenance`. Required dimensions: numeric domain and
  representational limits; failure/exception atomicity; recursive/cyclic
  topology; callback/collaborator execution; serialization/reconstruction;
  reference/object lifecycle; concurrency/reentrancy; resource complexity.
  Status is `claimed`, `disclaimed`, `N/A — reason`, or `unresolved`; no
  blank cells. Add domain-specific dimensions where they matter.
- State coverage of the table as a count when it is partial, and mark the
  remainder inferred; never claim completeness you have not counted. An
  honest partial table beats a false complete one.
- For stateful APIs, state the postcondition after validation, allocation,
  callback, or collaborator failure: unchanged, partially committed,
  best-effort cleanup, or unspecified.

### §8 Assumptions and guarantees about outputs

The mirror of §7 — the project's output is somebody else's input. One row per
output channel: `Output channel | Component | Taint | Downstream must not
assume | Provenance`. State the taint of every channel; for
parsers/decoders, state: *"Output is exactly as untrusted as the input it
derives from; no sanitization, normalization, or encoding is performed."*
Promote structural invariants that are guaranteed to §11 as properties.

### §9 Assumptions about dependencies

One trust statement per direct runtime dependency: the property relied on,
and whether a violation is triaged here or upstream. Vendored copies: covered
here or deferred upstream? The routing rule: a dependency failing its own
documented contract, with conformant usage here, routes
`OUT-OF-MODEL: dependency-contract` and is forwarded upstream; project misuse
of a dependency contract is in-model. State an explicit zero-dependency claim
if true.

### §10 Adversary model

One row per actor: `Actor | In scope? | Capabilities held | Capabilities
excluded | Goals | Provenance`. Every in-scope actor needs a non-empty
capabilities-excluded cell — that is what `adversary-not-in-scope` cites.
Name the deployment context the actor list assumes; a context whose adversary
differs gets its own row or is marked unsupported in §3. For distributed
systems, include the authenticated-but-Byzantine participant and the honest
fraction threshold.

### §11 Security properties the project provides

For each property state: (1) the property and its conditions; (2) the
**violation symptom**; (3) the **severity tier** (`security-critical` or
`correctness-only`); (4) the provenance tag; (5) **what voids it** — the
off-switches a caller can flip, cited `file:line` at the statement that
implements the switch. A property published without its off-switches is read
as absolute and causes a wrong `VALID` verdict. "Nothing voids it" must come
with the search, written as the command plus its result over the whole
supported build.

Violation symptom vocabulary: `crash`, `oob-read`, `oob-write`,
`buffer-overflow`, `use-after-free`, `uninitialized-read`, `info-leak`,
`hang`, `unbounded-allocation`, `wrong-output`, `bad-data-accepted`,
`integrity-bypass`, `data-race`, or an `x-` value. A memory-safety symptom
needs a `file:line` citation, not a doc quote: docs promise return codes, only
code shows memory outcomes.

Resource properties state a threshold ("super-linear in input is a bug;
constant-factor blowup is not"). A property counts only if the project
committed to it (normative docs, maintainer rulings, or a maintainer answer).
An unratified property never carries a `security-critical` tier — leave the
matrix row `unresolved` and put the choice to the maintainer.

Close §11 with **2–4 de-identified worked routing examples** as a table:
reported, sink, attacker needs, symptom, disposition, licensing claim. At
least one must route `VALID`. No CVE IDs, reporter names, or dates.

### §12 Security properties the project does *not* provide

The highest-value section for an integrator. Table:
`ID | The project does not provide | Conditions / boundary | Tier | False
friend? | Provenance`.

- **Tier is required on every row** and is the worst impact of a report the
  disclaimer would close, not how the project feels about the property.
  Triage fails closed on a missing tier: it escalates every matching report.
- Every disclaimer states its boundary: the components and operations it
  covers, and which neighbouring behaviour it does not.
- Call out **false friends** separately (features that look like a security
  property but are not) and name the well-known attack classes the project
  leaves to the caller (compression bombs, XXE, ReDoS, billion-laughs).
- Disclaim demonstrably-absent guarantees here rather than leaving them
  `unresolved`.

### §13 Downstream responsibilities

The action-oriented contract: what the caller or operator must do for §5–§10
to hold. Every dev-only knob reappears as "set X before exposing the service";
every risky "must not assume" becomes a positive obligation.

### §14 Known misuse patterns

Common misuses the API permits. Before publishing, expand each to *what it
looks like / why unsafe / what to do instead*.

### §15 Known non-findings (recurring false positives)

Table: `ID | Components | Symptom / attack class | What gets reported |
Conditions for an exact match | Discharged by | Provenance`. Each entry cites
the stable claim ID (§7/§11/§12/§3) that discharges it. Four rules, because
`KNOWN-NON-FINDING` fires first in the precedence:

1. **Discharge only by a claim in this document.** A process statement ("send
   us a reproducer", "we fix warnings") never discharges a finding.
2. **Match on the behaviour of the code, never on the quality of the
   report.** `no reproducer`, `no proof-of-concept`, and `scanner could not
   prove exploitability` are forbidden as match conditions. An unreproduced
   report stays open pending a reproducer.
3. **Name a symptom or attack class, not just a location.** An entry that
   reduces to "out of scope", "unsupported build", or "dependency root cause"
   is not a non-finding — it keeps its `OUT-OF-MODEL` label.
4. **The discharging claim must cover the component.** A disclaimer written
   for one component does not discharge a report against another.

A section with no established non-findings is `Not applicable — reason`, not
an empty table.

### §16 Conditions that would change this model

New public API, new input format, new network surface, new deployment
context, a changed configuration default, a new or changed dependency, a
component promoted from unsupported to core — and any report that does not
route cleanly to a disposition. That last one triggers a revision, not an
ad-hoc call.

### §17 Triage dispositions

The closed set, the precedence order, and the all-status closure constraint,
exactly as specified in [triage.md](triage.md) (single source of truth). Every
row cites its licensing section. State the deterministic precedence so
multiple failed preconditions still produce one disposition.

### §18 Open questions for the maintainers

Required while any inferred or assumption tag remains. Per question: the
proposed answer and the section it lands in. Group into waves of 3–7. **Write
it as a list, not a table** — the QN labels parse from list items; a tabled
§18 yields zero Q-IDs and dangles every body reference at once:

```markdown
- **Q1** — Is `contrib/` supported for production use?
  - Proposed answer: no; it is example code, unsupported and unreviewed.
  - Lands in: §3, licensing `OUT-OF-MODEL: unsupported-component`.
```

### §19 Machine-readable companions

Declare the two companions, their authority order (prose > yaml > json), and
the prose version the YAML derives from. Schemas live in
[artifact-schemas.md](artifact-schemas.md).

### Appendix — prior security-policy back-map

When the project already had authoritative model content (`SECURITY.md` or
equivalent), append a one-row-per-claim back-map from the prior statement to
its destination section. Keep it until maintainers approve removal; it proves
the new model is a strict superset.

## Marking a section Not applicable

A section counts as N/A only when its *entire* body is the single line `Not
applicable — <reason>`. Inside a substantive section, say what is absent in
plain words rather than writing "not applicable" mid-section: a stray phrase
can make tooling skip a section that actually carries content.

## Self-check gates

Run all four before publishing. A failed gate means loop back to the owning
step — do not publish around it.

**Gate 1 — Provenance and authority**

- [ ] Every non-trivial claim has exactly one tag with a resolving
      source/date/QN; every documented tag cites a locator; no hedge-tags.
- [ ] Every inferred/assumption tag has a §18 question with a proposed
      answer; the confidence count matches the tags.
- [ ] No unratified claim carries a `security-critical` tier.
- [ ] No closing disposition is licensed by an inferred claim; assumption
      closes only where the declared policy permits and never a
      security-critical disclaimer, a known non-finding, or a
      dependency-contract route.
- [ ] An `accepted` model has zero inferred and zero assumption claims;
      otherwise the status is `unratified`.
- [ ] Any prior `SECURITY.md` content is absorbed as a strict superset with
      a back-map.

**Gate 2 — Coverage**

- [ ] Every section is substantive or N/A with a reason.
- [ ] Every in-scope family is modeled at its own trust level or explicitly
      out of scope; sibling models are cross-linked if split.
- [ ] §7 has the trust table (with a coverage count if partial) and a
      complete matrix; no cell is blank; every claimed row is promoted to
      §11, every disclaimed row to §12 or §3, every unresolved row to §18.
- [ ] §12 and §13 are at least as substantive as §11.
- [ ] §8 states output taint for every channel; structural invariants are
      promoted to §11.

**Gate 3 — Triage readiness**

- [ ] §17 contains the closed set, each disposition's licensing section, the
      precedence, and the closure constraint.
- [ ] §1 has the triager quick-start referencing sections that exist, ending
      in the provenance gate, with the `closed` / `provisional` / `escalated`
      vocabulary.
- [ ] Every §11 property carries a violation symptom, a tier, and its
      off-switches; resource properties state a threshold.
- [ ] Every §12 disclaimer carries a boundary and a tier.
- [ ] §15 entries obey all four known-non-finding rules, or the section is
      N/A with a reason.
- [ ] The backtest was performed and its real figures are in the header; no
      historically fixed item routes to a closing disposition.
- [ ] A triager with an arbitrary finding can route it to exactly one
      disposition citing a section, without asking the maintainer.

**Gate 4 — Style and scope**

- [ ] No bullet belongs in a code review or audit report.
- [ ] No bullet restates the README/API docs as a feature list.
- [ ] A reader who has never seen the project can answer: what has the
      project taken responsibility for, and what is left to the reader?
- [ ] The document fits in one sitting (typically 3–8 pages); sentences are
      plain, active, and one-idea each; no sentence needs its cross-reference
      to be understood.
