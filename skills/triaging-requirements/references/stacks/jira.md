# Jira Source (references/stacks/jira.md)

Read this when Step 2 of the triage pass identifies Jira as the tracker —
either for a live fetch, or for the issue → item mapping when the user
supplies an export file (in that case skip the Auth and Fetching sections).
This is *reference*, not a script to execute — adapt the queries to the
project. `PROJ` below is a placeholder for the project key.

## Auth

Prefer an API token over password auth. Jira Cloud expects:

- `JIRA_HOST` — e.g. `https://yourorg.atlassian.net`
- `JIRA_EMAIL` — the account email
- `JIRA_API_TOKEN` — API token from
  https://support.atlassian.com/atlassian-account/

Fetch via REST with HTTP Basic auth (`email:api_token`). Do not print the
token or write it into ROADMAP.md. If no credentials are found, surface
the gap and list the project's issues as **unfetched** rather than guessing.

## Fetching open issues for a project key

JQL query — adapt the status set to the project's workflow:

```
project = PROJ AND statusCategory != Done ORDER BY priority DESC, updated DESC
```

REST endpoint:

```
GET {JIRA_HOST}/rest/api/3/search?jql={url-encoded-query}&fields=summary,status,priority,issuetype,labels,updated&maxResults=200
```

Handle pagination (`startAt` + `maxResults`) — backlogs >200 exist.

Also fetch recently-resolved issues to detect newly-done work since the
last pass:

```
project = PROJ AND statusCategory = Done AND statuschanged DURING ("-14d", now)
```

Adjust the `-14d` window to the time since `last_triaged` in ROADMAP.md
frontmatter when one exists — that is the whole point of recording it.

## Issue → item mapping

| Jira field | Roadmap field |
|---|---|
| `key` (e.g. PROJ-123) | add to Sources |
| `summary` | Title (trim; keep ID in Sources) |
| `issuetype` (Bug/Story/Task/Epic) | maps to category but verify from content — Epics split into their children |
| `priority` | informs Impact but does not override the rubric |
| `status` | Status (open/in-progress/done) |
| `labels` | notes; can suggest category |

Epics are not work items themselves — split an Epic into its child issues
unless the Epic is tracked standalone in this project. Two roadmap rows
for an Epic and its child Story is a duplicate.

## Unfetched handling

If the fetch fails (auth, network, project key wrong), record in the pass
summary:

```
Unresolved: ≥1 source (Jira PROJ unreachable — auth missing)
```

Use `≥1 source`, not a number — the count is unknowable when the fetch
never returned, and writing `0` would claim success over a gap you
couldn't see. Then proceed with the sources that did resolve: finish
those, write ROADMAP.md, surface the change summary, but leave Step 9
open. A failed fetch is a finding, not a silent empty list.