# Delegation sentinel (V2 TUI companion)

A deliberately tiny, always-loadable TUI plugin that renders the **fallback
banner** when the delegation observer is unavailable. The observer cannot draw
its own absence banner; this companion can.

It shows one line in the sidebar/footer when:

- `delegation-observer` is not in the plugin list (absent);
- its record is `failed`;
- `DELEGATION_OBSERVER_ENABLED` disables it;
- its shared health record says `disconnected`/`unavailable`/degraded;
- its TUI presence marker (`<location>/.scratch/delegation-observer/tui.json`)
  is missing or older than 45 s (TUI part failed to load).

It never renders delegate detail — that would claim visibility it does not
have. The watchdog and the terminal wake remain the authoritative fallback.

## Configuration (env — the TUI host does not forward plugin options)

| Variable | Default | Meaning |
|---|---|---|
| `DELEGATION_SENTINEL_ENABLED` | `1` | set `0` to hide the sentinel |
| `DELEGATION_OBSERVER_ENABLED` | — | mirrors the observer's disabled state |
| `DELEGATION_OBSERVER_HEALTH_FILE` | `<location>/.scratch/delegation-observer/health.json` | observer health record |

## Loading

A plugin directory must resolve a `server` entrypoint (2.1.4 skips a TUI-only
directory), so `server.ts` is a no-op definition; the work is in `tui.tsx`.
Add `./plugins/delegation-sentinel` to the versioned config's `plugins` list
(or keep the directory in the config root — the loader also scans `plugins/*`).

Tests: `node --test sentinel.test.ts`; typecheck: `tsc -p . --noEmit`.
