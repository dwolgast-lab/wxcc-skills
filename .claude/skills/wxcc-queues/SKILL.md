---
name: wxcc-queues
description: Use when asked to list, count, look up, or inspect Webex Contact Center queues / contact service queues (CSQs) - "what queues exist", "find queue X", "queue X's routing type or service level threshold", "which teams serve queue X", "is queue X active", "queue skill requirements". Read-only. Provides the confirmed API entity name (contact-service-queue, NOT queue), paths, filter/search syntax, and traps.
---

# wxcc-queues — list, search, and inspect WxCC queues (read-only)

**The API entity is `contact-service-queue` — the path `queue` does not exist (404).**
Uses the shared helper `wxcc.py` (repo root); requires a working connection
(**wxcc-connect**). Every path and parameter below was run against a live tenant
(149 queues) on 2026-07-10.

## Use when / Do NOT use when

**Use when:**
- Listing or counting queues; finding a queue by name, id, or keyword.
- Inspecting routing type, channel type, service level threshold, max time in queue,
  call distribution groups (which teams serve it), or skill requirements.

**Do NOT use when:**
- Auth errors (401 / "not authenticated") → **wxcc-connect**.
- Resolving the teams referenced by a queue's distribution groups → **wxcc-teams**.
- Creating/updating/deleting queues → **wxcc-queues-write**.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (see wxcc-connect).
- List responses paginate (`meta` + `data[]`, pageSize default 100); `get --all` combines
  all pages. Queue objects are the largest of the config entities — always trim list
  calls with `attributes=`.

## Recipes

### List every queue (id + name)

```bash
python wxcc.py get --all "organization/{orgId}/v2/contact-service-queue?attributes=id,name"
```

### Count queues

```bash
python wxcc.py get "organization/{orgId}/v2/contact-service-queue?pageSize=1&attributes=id"
```
→ read `meta.totalRecords`.

### Find a queue by exact name

```bash
python wxcc.py get "organization/{orgId}/v2/contact-service-queue?filter=name==QUEUE-NAME&attributes=id,name,active,channelType"
```
→ **unquoted** value; quotes cause HTTP 400. Names with spaces untested — candidate:
URL-encode as `%20`.

### Keyword search

```bash
python wxcc.py get "organization/{orgId}/v2/contact-service-queue?search=KEYWORD&attributes=id,name"
```

### Get one queue by id (full object)

```bash
python wxcc.py get "organization/{orgId}/contact-service-queue/QUEUE-ID-HERE"
```
→ fields observed live 2026-07-10 include: `name`, `active`, `channelType`, `queueType`,
`routingType`, `queueRoutingType`, `serviceLevelThreshold`, `maxTimeInQueue`,
`maxActiveContacts`, `callDistributionGroups` (team ids serving the queue),
`queueSkillRequirements`, recording/monitoring permissions, `timezone`. Tenant-observed,
not contract.

## Traps (reproduced live, 2026-07-10)

| Wrong | Result | Right |
|---|---|---|
| `organization/{orgId}/v2/queue` or `.../queue` | HTTP 404 | Entity is `contact-service-queue` |
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted: `filter=name==X` |
| Non-v2 list `organization/{orgId}/contact-service-queue` | 200 but a **bare unpaginated array** (legacy) | Prefer the `v2` list for `meta`/paging/filtering |

Note an inconsistency vs teams/sites/users: the **v2 item path works for queues**
(`v2/contact-service-queue/{id}` → 200, verified 2026-07-10). Both forms are valid; these
recipes use the non-v2 item form for consistency with the other entities.

## Provenance and maintenance

All claims run against a live us1 tenant on 2026-07-10 via `wxcc.py`. Re-verify any row by
running its recipe. Filterable fields confirmed: `id`, `name`; others are candidates.
Sibling facts (OAuth, pagination shape, leading-slash rule) live in **wxcc-connect**.
