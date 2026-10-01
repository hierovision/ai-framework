# Glossary

One plain meaning per term. Our own words are defined here once and used
exactly as written. Industry terms (`PR`, `CI`, `API`, `schema`,
`migration`, `token`) are not listed, because no explanation is needed.

| Term | Plain meaning |
|---|---|
| agent | an AI program that can use tools and take actions, not just answer |
| subagent | an agent started by another agent to do one bounded piece of work |
| skill | a written procedure an agent follows (`SKILL.md` in a folder) |
| plan | the written design an agent follows to build something |
| handoff | the short summary passed from one stage to the next |
| artifact | a file an agent produces as its visible result |
| eval | one test of a skill: run an agent on a prompt, then check the result |
| expect | the result an eval requires; the eval fails when it is missing |
| verdict | the review outcome: `approve`, `approve-with-nits`, `request-changes`, or `blocked-on-design` |
| passed / failed | a test outcome. Never "green" or "red" |
| service failure | a failure caused by a service problem (for example the model API), not by wrong work. Never "infra" |
| batch | one group of test runs executed on its own machine. Never "shard" |
| runner | the model and account used to run a task. Never "lane" |
| stall | a run that stopped producing output before finishing |
| quarantine | an eval set aside as known-unreliable, with a dated record |

**Do not rotate these.** Write the right-hand word only.

| Do not write | Write |
|---|---|
| lane | runner |
| shard | batch |
| green / red | passed / failed |
| infra | service failure |
| probe | small sample run |
| harvest | collect |
| canary | early check |
