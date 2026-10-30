# ADR-0014 — OpenCode V2 cutover (native config, one adapter, drained switch)

## Status

accepted 2026-10-27

## Context

The library's OpenCode-facing surfaces were built on `opencode-ai@1.19.4`:
V1 `--dir`/`--attach`/`--log-level` flags, `session`/`message`/`part` tables,
`permission` maps with `bash`/`write`/`task` keys, and V1 plugin exports. V2
`@opencode/cli@2.1.4` removes those surfaces (except `--log-level`, see the
dated note below): the working directory is
`cwd`, wakes are typed API calls, the store is `session_v2` +
`session_message`, permissions are ordered `{action, resource, effect}` rules,
and plugins are `Plugin.define` + `setup(ctx)`.

**2026-10-30 correction — log flags.** V2 accepts the global `--log-level` and
`--print-logs` flags; they are not among the removed surfaces, and the
post-smoke loader probe uses both to capture the plugin startup line on
stderr. The repository still bans them in `.github/workflows/eval-*`, where
evals pass `OPENCODE_LOG_LEVEL=ERROR`, so the ban is repo policy, not a V2
constraint. The Context paragraph above, which lists `--log-level` as
removed, is superseded to that extent.

V1 and V2 cannot coexist under one `opencode` command, so this is a cutover,
not a compatibility layer. The session DB auto-migration is one-way; the
backup is the rollback.

## Decision

1. **One shared adapter** — `scripts/opencode_v2.py` owns every
   version-specific fact: binary/version probe, service discovery, typed API
   calls, `OPENCODE_DB` resolution, V2 DB readers, permission-rule builder,
   stream normalizer, and denial classifier. Dispatcher, observer, watchdog,
   guard, eval runner, and the operational scripts import it; none re-derive
   V1 facts.
2. **Native V2 config and agents** — 17 agent files carry path-derived IDs
   (no `name:`), ordered `permissions` with `shell`/`subagent`/`edit`/
   `execute`, and `execute: deny`. The V1 `bash` allowlists convert 1:1; the
   linter compares against `main` and fails on any added allow.
3. **Dispatcher model binding** — every dispatch passes `--model` resolved in
   V2 discovery order (`.opencode/agents/`, repo `agents/`, global layout); a
   missing binding exits 2 before launch. The child runs with `cwd`/`PWD`, no
   `--dir`, no `--attach`, and `OPENCODE_LOG_LEVEL=ERROR`.
4. **Shared service + interrupt** — local dispatch defaults to the shared
   service (`--standalone`/`--server` opt-outs). On timeout the dispatcher
   calls `session.interrupt` and records `interrupt=ok|failed|no-session`;
   `--standalone` records `not-needed` and kills only the process group.
5. **External-directory posture** — `external_directory` defaults to allow in
   V2, so the dispatcher emits a catch-all `deny` first and explicit
   `<abs>/**` `allow` rules after it (last match wins, proved live). Persona
   files never carry `external_directory`; `execute: deny` closes the Code
   Mode policy-bypass class.
6. **Wake through the service API** — `session.get` preflight (404 defers
   `unknown-session`, no ghost session), `session.agent` switch, then
   `session.prompt` on the same session. The V1 attach vehicle is gone.
7. **Watchdog/guard read V2** — `session_v2` + `session_message`, API-first
   liveness with a read-only DB fallback; `time_idle`/`idle_outcome` is the
   completion signal when present, with the assistant terminal marker as the
   fallback for migrated rows. Both shares one adapter.
8. **Version policy** — pin exactly `2.1.4` in CI, the reference, and this
   ADR. No `latest`, no caret range, no auto-update. A failed canary allows
   only the highest `2.x` that passes C1–C6; `2.0.32` is not presumed safe.
   If none passes, stay on V1 `1.19.4` and report.
9. **Drained atomic switch** — the owner runs
   `scripts/opencode_v2_cutover.py --execute --drain-acknowledged` from a
   normal terminal after both PRs are merge-ready and every session is
   closed. It takes a final verified V1 backup, stages
   `$HOME/.local/lib/opencode/2.1.4/` (runtime + versioned config root +
   wrapper), and atomically renames `$HOME/.yarn/bin/opencode` onto the
   wrapper. The wrapper sets `XDG_CONFIG_HOME` to the versioned root, so one
   link selects binary and config. V1 config/agents/plugin are untouched.
10. **Consumer readiness is commit-bound** — Paragon's isolated worktree is
    validated by `scripts/opencode_v2_consumer.py ready`, which records exact
    framework/consumer SHAs and both PR URLs. The cutover refuses stale,
    missing, dirty, or mismatched evidence.
11. **Post-smoke gates the merges** — `scripts/opencode_v2_post_smoke.py`
    proves the default command is V2, loads the agent/wrapper corpora, checks
    config/credentials/plugin/`session_v2`, and runs the live drills before
    either PR merges. `--post-merge` verifies the merged SHAs and corpus.
12. **Rollback restores data and personas** — `--rollback` stops V2 writers,
    preserves the failed V2 DB, restores the final V1 DB through Python
    `sqlite3`, atomically restores the original link, repairs any mismatched
    V1 agent from the C5 snapshot, and proves V1 `1.19.4` reads the data.
13. **Auto-compaction is a functional V2 plugin** — `plugins/
    auto-compact-at-threshold/` implements the V1 threshold semantics through
    `Plugin.define`/`setup`, a `ctx.event.subscribe` loop, and
    `ctx.session.compact({sessionID})`, with a startup marker and tests. The
    dated static-disable fallback is permitted only with explicit owner
    approval and is not used.
14. **Migration fidelity is reported, never assumed** — the migration gate
    checks source-ID membership and records the residual. The observed
    119-session residual is a truncated, resumable backfill
    (`kv.migration.v1-v2` cursor), not data loss; cutover requires its
    classification or a dated owner acceptance.

## Consequences

- Every framework script has one version seam; upgrading again touches the
  adapter, not each caller.
- The default command changes only in one drained, reversible step; a failed
  gate restores V1 without rewriting either consumer checkout.
- Two unmerged PRs (framework + Paragon) must land together after post-smoke.
- V2-only capabilities (Code Mode, todos, LSP, websearch) are not adopted;
  `execute: deny` blocks Code Mode deliberately.
- The V1 plugin/config/package tree stays as rollback state until the owner's
  retention window ends.

## References

- `.opencode/plans/opencode-v2-upgrade.md` (implementation plan; retired on
  merge — the essence lives here, in `reference/opencode-integration.md`, and
  in `docs/roadmap-detail/RM-067.md`).
- `reference/opencode-integration.md` — volatile V2 facts.
- `scripts/opencode_v2.py`, `scripts/opencode_v2_canary.py`,
  `scripts/opencode_v2_consumer.py`, `scripts/opencode_v2_cutover.py`,
  `scripts/opencode_v2_post_smoke.py`.
