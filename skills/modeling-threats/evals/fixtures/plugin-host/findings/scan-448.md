# scan-448

- Scanner: numeric-precision ruleset, 2026-09-03
- Location: `src/config-loader.js:24` (`parseConfig`)
- Finding: parsing the decimal `1.005` yields `1.00`; precision is lost on
  floating-point config values.
- Reporter severity: low
