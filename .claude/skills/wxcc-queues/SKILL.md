---
name: wxcc-queues
description: Use when asked to list, count, look up, or inspect Webex Contact Center queues / contact service queues (CSQs) - "what queues exist", "find queue X", "queue X's routing type or service level threshold", "which teams serve queue X", "is queue X active", "queue skill requirements". Read-only.
---

# wxcc-queues — list, search, and inspect WxCC queues (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

**The entity is `contact-service-queue`.** `queue` is not a thing — it 404s. Pass
`entity="contact-service-queue"`; the tool rejects unknown entity names rather than guessing.

## Use when / Do NOT use when

**Use when:**
- Listing or counting queues; finding a queue by name, id, or keyword.
- Inspecting routing type, channel type, service level threshold, max time in queue,
  call distribution groups (which teams serve it), or skill requirements.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Resolving the team ids inside `callDistributionGroups` → **wxcc-teams**.
- Creating/updating/deleting queues → **wxcc-queues-write**.
- Call/contact volume, handle time, or anything time-series → **wxcc-tasks-search**.
  This skill reads queue *configuration*, not activity.

## Recipes

| Goal | Call |
|---|---|
| Every queue (id + name) | `wxcc_list(entity="contact-service-queue", attributes="id,name", all_pages=true)` |
| Count only | `wxcc_list(entity="contact-service-queue", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="contact-service-queue", filter="name==QUEUE-NAME")` |
| Keyword search | `wxcc_list(entity="contact-service-queue", search="KEYWORD")` |
| One queue, full object | `wxcc_get(entity="contact-service-queue", id="QUEUE-ID")` |

**Queue objects are the largest config entity — always pass `attributes` on list calls**
unless you genuinely need every field.

Fields observed live (2026-07-10): `name`, `active`, `channelType`, `queueType`,
`routingType`, `queueRoutingType`, `serviceLevelThreshold`, `maxTimeInQueue`,
`maxActiveContacts`, `callDistributionGroups` (team ids serving the queue),
`queueSkillRequirements`, recording/monitoring permission booleans, `timezone`.
Tenant-observed, not contract.

## Traps

| Trap | Why | Do this |
|---|---|---|
| `entity="queue"` | The path 404s | Use `contact-service-queue` |
| `filter=name=="X"` quoted, **via the CLI** | HTTP 400 — raw quotes die in transport | Via `wxcc_list` either quote style works; plain values need no quotes |
| Filter values with spaces | Bare space is an RSQL syntax error | Quote the value: `filter="name=='Inside Sales'"` (verified live 2026-07-17; pass raw characters — the tool encodes) |
| Filterable fields | Only `id`, `name` confirmed | Others are candidates |

## Provenance and maintenance

Run against live us1 tenants (2026-07-10, 149 queues; re-confirmed 2026-07-14). Queues are
the one entity where the v2 item path ALSO works — an inconsistency vs teams/sites/users.
The tool's registry pins one form, so this no longer matters at call time.
