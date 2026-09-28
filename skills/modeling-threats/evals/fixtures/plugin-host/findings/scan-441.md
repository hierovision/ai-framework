# scan-441

- Scanner: memory-safety ruleset, 2026-09-02
- Location: `contrib/bundled-example/render.c:118`
- Finding: out-of-bounds read when the example renderer walks a layer table
  past its length.
- Reporter severity: high
