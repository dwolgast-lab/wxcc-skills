---
name: wxcc-tasks-search
description: Use when asked about Webex Contact Center calls/contacts/tasks or agent activity data - "how many calls did we take yesterday", "show recent calls to +1555...", "what tasks are queued right now", "when did this customer last call", "agent login sessions this week". Read-only reporting over interaction data via the GraphQL Search API. Not for tenant configuration.
---

# wxcc-tasks-search — calls, tasks, and agent sessions (read-only reporting)

Call **`wxcc_search_tasks`** on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

**This is interaction data, not configuration.** Queue *settings* → **wxcc-queues**.
Call *volume through* a queue → here.

## Use when / Do NOT use when

**Use when:** counting or listing calls/tasks, looking up a contact's history, checking
what is queued now, or reading agent session/state activity.

**Do NOT use when:**
- Any tenant configuration → the entity skills (**wxcc-queues**, **wxcc-teams**, …).
- Auth errors → **wxcc-connect**.
- Recording media or transcripts → not covered here.

## How to call it

`wxcc_search_tasks(query="<a GraphQL document>")`. The tool posts it to the Search API and
returns the result.

```
wxcc_search_tasks(query="""
{ task(from: 1720000000000, to: 1720600000000, first: 50) {
    tasks { id status channelType queue { name } createdTime }
    pageInfo { hasNextPage }
} }
""")
```

Three roots: **`task`** (contacts/interactions), **`agentSession`** (login sessions and
state), **`taskDetails`** (per-task detail).

## The rule that will bite you first

**`from` and `to` are REQUIRED on every root, in epoch MILLISECONDS.**

- Omit them → `400 Missing field argument`.
- Pass **seconds** → the query succeeds and **silently returns nothing.** No error. A
  10-digit timestamp means 1970, so the window is empty and it looks like "no calls."

If a query returns zero rows, check the timestamp width before telling the user there were
no calls. This is the single most likely way to give a confidently wrong answer here.

Compute the window from the user's intent ("yesterday", "this week") and **state the window
you used** in your answer so they can catch a mistake.

## Aggregations

Cisco's Postman collection shows aggregation syntax (counts, group-bys) for wallboard-style
numbers. **Untested here — candidate.** If you use it, say the shape is unverified and
sanity-check the result against a plain `task` count over the same window.

## The REST alternative

`GET v1/tasks?from=<ms>&channelTypes=telephony` exists and is verified, with hard limits:

| Limit | Detail |
|---|---|
| Window | **≤ 184 days** between `from` and `to` |
| Lookback | `from` **≤ 12 months** ago |
| Item path | **There is no `/v1/tasks/{id}`** — 404 |

It is not exposed as an MCP tool (the GraphQL root covers the same ground with more
control). Reach for the CLI only if you need it — and note the CLI uses whatever tenant
`WXCC_PROFILE` resolves to, **not** the MCP server you were just using.

## Traps

| Item | Detail |
|---|---|
| Seconds instead of milliseconds | Silent empty result — no error |
| Missing `from`/`to` | 400 "Missing field argument" |
| Host-root API | `POST search?orgId={orgId}`, not under `organization/{orgId}` — the tool handles this |
| Aggregations | Collection-sourced, unrun — candidate |

## Provenance and maintenance

GraphQL `task` and `agentSession` roots run live on a us1 sandbox 2026-07-11 (65 real tasks
returned). The millis requirement, the 400 on missing args, the REST 184-day/12-month
limits, and the absent item path were each reproduced. Aggregation syntax is from Cisco's
Postman collection (v3, Aug 2023) and remains a candidate.
