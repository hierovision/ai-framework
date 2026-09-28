# snapshot-porter

Migrates Playwright trace archives into a compact HTML evidence
gallery: one row per failed step, screenshots inline, console log side
by side. Ships as a single Python CLI (`porter.py`) with no runtime
dependencies beyond the standard library, plus a small Jinja-free
templating helper. Ideal for CI artifact summarization.

MIT License. Copyright (c) 2026 Snapshot Porter contributors.
Requires Playwright `trace.zip` artifacts where all trace files were
recorded in Chromium under QUIC transport; other transports need the
legacy parser at porter.py --legacy.
