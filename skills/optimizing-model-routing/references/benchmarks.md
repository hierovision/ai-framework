# Benchmark Objectivity Guide

Read at Step 4 of the routing pass, before ranking any candidate. This
file defines what counts as objective evidence and how to match evidence
to the role being routed.

## The objectivity hierarchy

1. **Independently reproduced** — a third party ran the benchmark and
   published method and results. The strongest signal; a deciding basis.
2. **Multi-source cross-checked** — a vendor claim plus at least one
   independent reproduction within a few points. Deciding basis when
   cited with both sources and their spread.
3. **Vendor self-reported** — a tier filter, never a deciding signal. Any
   candidate whose best evidence is vendor-only goes to
   Questionable/Uncertain with the reason, and a binding decided on it is
   a defect in the pass.

Reading rules that keep the ranking honest:

- **Benchmarks are a tier filter, not a ranking.** Harness choice alone
  can swing scores double-digit points; saturated, contamination-prone
  suites overstate small gaps. A few points of separation is noise —
  treat it as a tie and break it on objectivity or reliability.
- **Capability facts and liveness are hard gates, not scores.** Native image input,
  context length, catalog membership, docs-listed status (free tier),
  and live routing (actually routes in a live opencode session): a model
  lacking a required capability or failing liveness cannot hold the seat
  at any benchmark number. Non-live IDs never enter ranking or
  benchmark comparison.
- **Match the benchmark to the work.** Prefer the benchmark that measures
  the role's actual task (autonomous loop for planners, tool-use for
  implementers, instruction-following for skill authors) over a generic
  aggregate index.
- **Reliability observations count.** A model with clean scores but
  observed streaming failures under load carries that caveat into
  Questionable/Uncertain — reliability is part of the decision, not
  noise.
- **Family diversity is the objectivity mechanism for council seats** —
  mixing model families buys independent perspective; raw score does not.

## Role → dominant trait

| Role | Dominant trait | Decisive benchmark class |
|---|---|---|
| planner / design | autonomous-loop reasoning on existing code | independent agent-loop benches |
| implementer / test-writer | tool + file orchestration | tool-use benches |
| triager | generalist quality + reliability | generalist benches + reliability observations |
| debugger / reviewer | defect localization + loop reasoning | agent-loop benches |
| council-member | family diversity | capability + family mix, not raw score |
| vision-critic | native multimodality | capability fact (hard gate) |
| skill-author / skill-reviewer | instruction following | IF-style benches |

## Skills → roles

Do not memorize a mapping. Read the "Used by (loop stage)" column of the
repo's model-routing.md bindings table — it names the loop stage and
skills each role serves. Build the approval table's skill list from that
column so the table and the routing file can never disagree.
