---
name: wxcc-bulk
description: Use when asked to create, update, or delete MANY Webex Contact Center objects of one type in a single operation - "bulk update these queues", "create 20 entry points from this list", "bulk-create these global variables", "delete all these teams", "change the service level on every X queue at once". Mutating - requires cjp:config_write and explicit confirmation. Verified for contact-service-queue, entry-point, auxiliary-code, dial-number, outdial-ani, cad-variable (global variables), team, skill, skill-profile, user-profile, resource-collection, site, multimedia-profile, agent-profile (Desktop Profile), desktop-layout, business-hours, holiday-list, overrides, and contact-number - and which of create/update/delete each supports differs sharply. Other entities are refused until probed.
---

# wxcc-bulk — create / update / delete many objects in one call

Bulk counterparts to `wxcc_create` / `wxcc_update` / `wxcc_delete`. Use them when the user
wants to act on **a set** of objects of one entity at once, on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

The tools: `wxcc_bulk_update`, `wxcc_bulk_create`, `wxcc_bulk_delete`. Each takes an
`entity` and a list, is **dry-run until `confirm=true`**, and reports a per-item outcome.

## Use when / Do NOT use when

**Use when:** the same operation applies to many objects — patch a field across many queues,
create a batch of queues, delete a list of queues.

**Do NOT use when:**
- A single object → the plain `wxcc_create` / `wxcc_update` / `wxcc_delete` (**wxcc-queues-write** etc.).
- Listing/finding → the read skill for that entity.
- Auth errors or 403 on write → **wxcc-connect**.
- The entity — or the specific operation on it — is not yet bulk-verified. The tool refuses
  and names what is supported. Do not improvise a bulk path or op; they are not uniform (see
  the capability matrix).

## The one model to understand: a per-item 207

Every bulk call returns **HTTP 207 Multi-Status** — a *mixed* result. One item can succeed
while the next fails, and the call as a whole still "succeeds." The tools collate the
response for you into:

- **`succeeded`** — each item's `operation` (CREATE/UPDATE/DELETE) and resulting `id`.
- **`failed`** — each item's `status` and the API's own per-item `reason` (e.g. a 412).
- **`NOT_PROCESSED`** — items the API returned **no result for**. A 207 with an empty result
  list means *nothing matched* — a silent no-op. **Never read a 207 as proof; read these three lists.**

Always check **`TENANT`** (first field; `[PRODUCTION]` = a real customer) before confirming.

## Which entities support which op (verified live)

Bulk support is **per operation, per entity** — the API is not uniform, and the tool refuses
an op an entity hasn't been proven to support. As of 2026-07-21:

| Entity | create | update | delete | Notes |
|---|---|---|---|---|
| `contact-service-queue` | ✅ | ✅ partial | ✅ | update is a native partial patch |
| `auxiliary-code` | ✅ | ✅ partial | ✅ | update is a native partial patch |
| `entry-point` | ✅ | ✅ RMW | ✅ | no partial route; update read-modify-writes |
| `cad-variable` (global variables) | ✅ | ✅ RMW | ✅ | no partial route; `agentViewable=true` needs `desktopLabel` |
| `user-profile` | ✅ | ✅ RMW | ✅ | route is **`v3/user-profile/bulk`** — the v2 route answers but 400s per item |
| `dial-number` | ✅ | ✅ RMW | ❌ | delete would unmap a live number — refused; create needs a number already in the Calling inventory |
| `outdial-ani` | ✅ | ❌ | ✅ | no bulk update (id-bearing item → 400 "cannot have an id"); use `wxcc_update` or the entry tools |
| `team` | ✅ | ❌ | ✅ | no bulk update, same 400 as outdial-ani |
| `skill` | ✅ | ❌ | ✅ | no bulk update, same 400; `skill/v2/bulk` 404s — the route is `skill/bulk` |
| `skill-profile` | ✅ | ❌ | ✅ | no bulk update, same 400; create needs at least one skill |
| `site` | ✅ | ❌ | ✅ | no bulk update, same 400; `PATCH site/bulk` is 405 |
| `multimedia-profile` | ✅ | ❌ | ✅ | no bulk update, same 400; strip `workItem` when cloning (see the entity note) |
| `agent-profile` (Desktop Profile) | ✅ | ❌ | ✅ | no bulk update, same 400; a clone MUST set `systemDefault=false` or every item 403s — the stock profiles are all systemDefault |
| `desktop-layout` | ✅ | ❌ | ✅ | no bulk update, same 400; MUST send `global=false` and `teamIds=[]` — cloning a global layout gives a misleading 400 naming "Teams assigned" on a payload with no teams key |
| `business-hours` | ✅ | ❌ | ✅ | no bulk update, same 400; `workingHours` must be non-empty |
| `holiday-list` | ✅ | ❌ | ✅ | no bulk update, same 400; `holidays` must be non-empty; does NOT need `timezone` |
| `overrides` | ✅ | ❌ | ✅ | no bulk update, same 400; `overrides` must be non-empty; DOES need `timezone` |
| `contact-number` | ✅ | ❌ | ✅ | no bulk update, same 400; `number` only, max 9 chars |
| `resource-collection` | ❌ | ✅ RMW | ❌ | **update only, and on PATCH**; create → 500 "no mapping for id", delete → 400 "SAVE only" |
| `audio-file` | ❌ | ❌ | ❌ | **no bulk route published** (2026-07-22). Each file is a multipart upload — see **wxcc-audio-files**. Bulk-export is out of scope for these tools. |
| `user` | ❌ | ✅ partial | ❌ | **update only**, on `PATCH user/bulk` (207 + items, verified 2026-07-22). No bulk create/delete because **Control Hub owns the user lifecycle**. Identity fields stay immutable in bulk too. |

## Purge endpoints: real, and 403 for everyone (canonical note)

Several entities publish `POST <entity>/purge-inactive-entities`. **None of them is
exposed as a tool, and none can be called.** Probed 2026-07-22 on `auxiliary-code`,
`desktop-layout` and `agent-profile`: all three return **403 "Access denied - Client is
forbidden access to the resource"** for a **full-rights tenant admin** holding
`cjp:config_write`. Cisco does not document the scope required.

The routes are real, not missing — they answer with the app's `trackingId` error shape,
while a nonexistent sub-path on the same entity answers **405** with the framework's
`timestamp` shape. Three entities behaving identically means the gate is **tenant-wide**,
not per-entity, so assume any other `purge-inactive-entities` behaves the same.

**When a user asks to "purge" or "delete all the inactive X":**

1. `wxcc_list(entity="<entity>", all_pages=true)`
2. Filter the inactive ones **in code** — the flag is `active` on most entities but
   **`status`** on `desktop-layout`. Show the user the names.
3. `wxcc_bulk_delete(entity="<entity>", ids=[...], confirm=True)`

That is aimable at exactly the objects the user chose, which a tenant-wide sweep is not.
Do not present the purge endpoint as something they could reach another way.

### Correction (2026-07-22): "address-book and user have no bulk route at all" was WRONG

That claim shipped here as "confirmed, not merely unprobed." It was false on **both**
entities. The evidence behind it was sound but probed the wrong path level:

- `address-book/bulk` really does parse `bulk` as an `{id}` (POST 405 / PUT 400 "name: should
  not be null or blank") — but bulk lives on the **child** collection.
  `POST address-book/{id}/entry/bulk` → **207 + `items`**. So does
  `POST outdial-ani/{id}/entry/bulk`.
- `POST user/bulk` → **207 + `items`** directly. (`v2/user/bulk` and `v3/user/bulk` 404.)

All three re-probed live 2026-07-22. **The routes exist; which ops they accept is still
unprobed**, so the tools continue to refuse them — extend via the procedure at the bottom of
this file, don't assume create/update/delete from the route's existence.

The method was right even though the conclusion wasn't: a *real* bulk route answers `POST`
with a `207` and an `items` envelope; that is the only reliable test — status code alone
cannot distinguish them, and neither can the error-body shape. **Probe every path level
(parent, child, `v2`/`v3` variants) before concluding a route is absent.**

## wxcc_bulk_update — update many objects

```
wxcc_bulk_update(entity="contact-service-queue", items=[
  {"id": "QUEUE-ID-1", "serviceLevelThreshold": 30},
  {"id": "QUEUE-ID-2", "maxTimeInQueue": 1800}
])                                                   # dry run
# ...show the preview, get a yes...
wxcc_bulk_update(entity="contact-service-queue", items=[...], confirm=true)
```

Each item is `id` (required) plus **only the fields that change** — you never send what you
don't intend to change. How that reaches the API depends on the entity, and the dry run tells
you which under `update_style`:

- **queues** and **auxiliary-code** have a native partial-patch endpoint — only your fields
  are sent.
- **entry-point**, **cad-variable**, **dial-number**, **user-profile** and
  **resource-collection** have no partial endpoint, so the tool **read-modify-writes**: it
  fetches each object and merges your fields into a full-object save. Same call for you
  either way. (`resource-collection` is a PATCH route that is nonetheless *not* partial —
  a partial item returns a leaked Java NPE.)
- **outdial-ani**, **team**, **skill** and **skill-profile** have **no** bulk update at all
  — the tool refuses it (use `wxcc_update` per object).

Rollback: re-run with the prior values (read them first if you need them).

## wxcc_bulk_create — many new objects

```
wxcc_bulk_create(entity="contact-service-queue", items=[ {<full create body>}, ... ])
```

Each item is a **full create body** — the same required fields the single create enforces
(for queues, see **wxcc-queues-write**; the five `*Permitted` booleans are required). The
tool checks each item's required fields before calling and reports `missing_by_index`. An
item must **not** carry an `id` (that would be an update). Rollback: `wxcc_bulk_delete` the
returned ids. Note `dial-number` create still needs a number already in the Calling inventory
(a fictional number 404s per item), same as the single create.

## wxcc_bulk_delete — many deletes

```
wxcc_bulk_delete(entity="contact-service-queue", ids=["QUEUE-ID-1", "QUEUE-ID-2"])   # dry run
wxcc_bulk_delete(entity="contact-service-queue", ids=[...], confirm=true)
```

Pass **ids** — the tool fetches each full object itself (the endpoint rejects an id-only
delete with a misleading "system generated" error; see Traps). **No rollback** — recreating
yields new ids. The API self-guards references: a still-referenced object comes back in
`failed` with a **412** and is left intact, while the rest of the batch is deleted. Ids that
don't exist are reported under `not_found` and never sent.

## Traps (all reproduced live, 2026-07-20 sandbox)

| Item | Detail |
|---|---|
| Delete needs the FULL object | An id-only delete returns a misleading `400 "Cannot Update/Delete system generated Entities"`. The tool fetches the object for you — pass ids. |
| A 207 is not proof | An empty per-item result = nothing matched = silent no-op. Read `NOT_PROCESSED`. |
| References are API-guarded | A referenced delete → per-item `412`, not deleted; the rest of the batch still applies. No client pre-flight needed. |
| System-generated entities | Cannot be updated or deleted in bulk (per-item error). |
| Routes/ops are NOT uniform | Queues use `contact-service-queue/v2/bulk` (create/delete) + `contact-service-queue/bulk` (PATCH update); `user-profile` is on `v3/user-profile/bulk`; every other verified entity is on `{entity}/bulk`. Some have a PATCH partial route (queues, aux-code), some don't, and `resource-collection` is PATCH-only yet *not* partial. Some lack an op entirely (no update on outdial-ani/team/skill/skill-profile; no delete on dial-number; `resource-collection` is update-only). `skill/v2/bulk` 404s. Only verified (entity, op) pairs are accepted — see the capability matrix. |
| "New configuration cannot have an id" | The signature of **no bulk update on this entity** — `team`, `skill`, `skill-profile`, `outdial-ani` all return it for an id-bearing SAVE. It is not a body you can fix; the op does not exist. |
| Flow references | Counted by the API's reference check (a flow reference blocked a queue delete with 412), but flow *authoring* is out of scope — Cisco's **flow-store** MCP server. |

## Provenance and maintenance

Verified live on a us1 sandbox 2026-07-20/21 through the actual tools (org `174…`; every
entity's baseline restored). Each verified op was exercised end-to-end — create → per-item
`207 CREATE`, update → `207 UPDATE` (a real field change re-read where safe), delete → `207
DELETE`; referenced deletes came back as per-item `412` (proven on a queue's flow reference
and an entry-point's dial-number reference); and every unsupported op is refused by the
tool, not attempted. `team`, `skill`, `skill-profile`, `user-profile` and
`resource-collection` were added 2026-07-21 by the same loop. Request envelope is
`{"items":[{"itemIdentifier":<int>,"item":{...},"requestAction":"SAVE"|"DELETE"}]}` — the
array key is `items` but each element wraps the object under `item`; the response reuses
`items` with a different per-item shape.

To extend bulk to another entity, **probe its bulk route(s) and each op live** — they are not
uniform — then add a `bulk` block to that entity in `mcp_server.py`'s registry listing only
the proven ops (`create`/`update`/`delete`), each with its method, path tail, and (for update)
whether it is a native partial patch. An empty-`items` POST is a safe existence probe (`207`
if the route exists, `404` if not).
