# Merged PRs since v1.4.2

Pre-fetched change list (stands in for `gh pr list` when `gh` is unavailable).
The last release was tagged `v1.4.2`.

- feat(api)!: drop the legacy /v1/session endpoint (#311)

BREAKING CHANGE: clients pinned to /v1/session must migrate to /v2/session.

- feat(reports): add CSV export (#315)
- fix(auth): expire stale refresh tokens (#317)
