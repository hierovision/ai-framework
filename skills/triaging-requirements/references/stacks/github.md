# GitHub Source (references/stacks/github.md)

Read this only when a live GitHub fetch is required (Step 2 of the triage
pass identified GitHub as the tracker). Prefer `gh` over raw REST so auth
flows through the user's existing `gh auth login`.

## Prereq

Verify `gh` is installed and authed before fetching:

```
gh auth status
```

If unauthed or `gh` missing, surface the gap and mark the repo's issues
**unfetched** rather than guessing. Do not write a token to disk.

## Fetching open issues

```
gh issue list --repo owner/repo --state open --limit 200 --json number,title,labels,state,createdAt,updatedAt
```

Pull recently-closed issues to detect newly-done work since the last pass:

```
gh issue list --repo owner/repo --state closed --limit 50 --json number,title,closedAt
```

Filter `closedAt` against `last_triaged` in ROADMAP.md frontmatter when one
exists — that date is the whole point of recording it.

## Issue → item mapping

| GitHub field | Roadmap field |
|---|---|
| `number` (e.g. #123) | add to Sources as `owner/repo#123` |
| `title` | Title |
| `labels` | infer category but verify from content — `bug`→bug, `tech-debt`/`refactor`→debt, `chore`/`ci`→chore, else feature |
| `state` | Status |
| draft PRs / PRs | PRs are not roadmap items; only link if they're the implementation of one |

PRs are implementation, not requirements. A PR that closes #42 should map
to the #42 row, not a separate row.

## Unfetched handling

If `gh` returns an error (rate limit, repo not found, auth), record in the
pass summary:

```
Unresolved: ≥1 source (owner/repo unreachable — gh auth or repo access)
```

Use `≥1 source`, not a number — the count is unknowable when the fetch
never returned. Then proceed with whatever sources resolved: finish those,
write ROADMAP.md, surface the change summary, but leave Step 9 open. A
failed fetch is a finding, not a silent empty list.