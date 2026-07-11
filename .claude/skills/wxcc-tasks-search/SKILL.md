---
name: wxcc-tasks-search
description: Use when asked about Webex Contact Center calls/contacts/tasks or agent activity data - "how many calls did we take yesterday", "show recent calls to +1555...", "what tasks are queued right now", "when did this customer last call", "agent login sessions this week". Read-only reporting via the GraphQL Search API (POST /search) and the REST tasks API (GET /v1/tasks). Not for tenant configuration - this is interaction data, not admin config.
---

# wxcc-tasks-search — interaction data: tasks, calls, agent sessions (read-only)

Two read APIs over the same interaction data: the **GraphQL Search API**
(`POST search?orgId={orgId}` — flexible fields, filters, aggregation) and the simpler
**REST tasks API** (`GET v1/tasks`). Both verified against a live tenant on 2026-07-11
(65 historical tasks + agent sessions returned). These paths sit at the **API host root**
— they are *not* under `organization/{orgId}`.

## Use when / Do NOT use when

**Use when:** counting/finding calls or tasks, real-time queued contacts, customer
interaction history, agent session/login data, wallboard-style aggregates.

**Do NOT use when:**
- Tenant config (queues, teams, EPs...) → the domain skills (wxcc-queues, wxcc-teams, ...).
- Registering for event pushes → **wxcc-webhooks**.
- Auth errors → **wxcc-connect**.

## Ground rules

- Timestamps are **epoch milliseconds**. Get them with:
  `python -c "import time; print(int(time.time()*1000) - 7*24*3600*1000)"` (7 days back).
- `{orgId}` substitution works anywhere in the path string, including query params.
- GraphQL bodies are JSON: `{"query": "{ ... }"}`. Quoting gets hairy inline — prefer
  `--body @query.json`.

## Recipes — GraphQL search

### Tasks in a time window

```bash
python wxcc.py post "search?orgId={orgId}" --body '{"query":"{ task(from: FROM_MS, to: TO_MS, pagination: { cursor: \"0\" }) { tasks { id createdTime channelType direction status isActive origin destination totalDuration lastQueue { name } lastEntryPoint { name } owner { name } } pageInfo { endCursor hasNextPage } } }"}'
```

All field names above verified live. `from`/`to` are **required** (400 names them if
missing). Never-answered tasks return `owner.name`/`lastQueue.name` as null. Paginate by
passing `pageInfo.endCursor` back as the next `cursor`.

### Filters (verified pattern)

Inside `task(...)`: `filter: { and: [ { channelType: { equals: telephony } },
{ direction: { equals: "inbound" } }, { isActive: { equals: true } } ] }` — that
combination is Cisco's real-time-queued-tasks query. Enum-ish values (`telephony`) are
bare; strings are quoted. `timeComparator: createdTime` (or `endedTime`) picks which
timestamp `from`/`to` compare against.

### Agent sessions

```bash
python wxcc.py post "search?orgId={orgId}" --body '{"query":"{ agentSession(from: FROM_MS, to: TO_MS) { agentSessions { agentId agentName startTime endTime } pageInfo { hasNextPage } } }"}'
```

→ verified live. A third root, `taskDetails`, also exists (same required `from`/`to`).

### Aggregates (candidate)

Cisco's collection shows `aggregation:`/`aggregations:` blocks (sum/count/average/max
over duration fields, e.g. calls-per-queue wallboards) — **not yet run here**; expect to
iterate on syntax against the 400s, which are precise.

## Recipes — REST tasks list

```bash
python wxcc.py get "v1/tasks?from=FROM_MS&channelTypes=telephony&pageSize=10"
```

→ `data[]` of `{id, attributes: {owner, queue, channelType, status, createdTime, origin,
destination, direction, captureRequested}}`. `from` is **required**; `channelTypes` is
optional; there is **no `v1/tasks/{id}` item path** (404, reproduced live).

## Traps (each reproduced live, 2026-07-11)

| Wrong | Result | Right |
|---|---|---|
| `v1/tasks` window > 184 days, or `from` > 12 months ago | HTTP 400 (message states both limits) | Chunk long lookbacks |
| GraphQL root without `from`/`to` | HTTP 400 "Missing field argument" | Always pass both (epoch ms) |
| Seconds instead of milliseconds | Empty results, no error | Epoch **ms** everywhere |
| `GET v1/tasks/{id}` | HTTP 404 | Filter the search APIs by `id` instead |

## Provenance and maintenance

Run live on a us1 sandbox 2026-07-11: task + agentSession queries (fields as shown),
v1/tasks constraints from real 400s. Filter/aggregation syntax beyond what is marked
verified comes from Cisco's Postman collection (v3, Aug 2023) — treat as candidate and
lean on the API's precise validation errors. Results contain real caller numbers — treat
output as sensitive.
