---
name: wxcc-resource-collections
description: Use when asked about Webex Contact Center resource collections - the named groupings of queues, teams, sites and other config that scope what a user profile can reach - "what resource collections exist", "what is in collection X", "which queues/teams does collection X allow", "create a resource collection", "add a queue to collection X", "delete collection X". Covers reads and verified create/update/delete. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-resource-collections — scoped groupings that user profiles point at

Call the `wxcc_*` MCP tools with `entity="resource-collection"` on the server for the tenant
the user named (`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not
guess.**

A resource collection is a named scope: for each of 20 resource types it says whether the
holder gets `ALL` of them, `NONE`, or a `SPECIFIC` list of ids. A user profile references
collections via `resourceCollections[]` — that is how "this supervisor sees only these
queues" is expressed.

## Use when / Do NOT use when

**Use when:**
- Listing collections; inspecting what a collection scopes.
- Creating, updating, or deleting a collection.
- Resolving an id found in a user profile's `resourceCollections`.

**Do NOT use when:**
- The profile that *holds* the collection → **wxcc-user-profiles**.
- Editing the underlying queues/teams/sites themselves → that entity's own skill.
- Auth errors or the wrong org → **wxcc-connect**.

## The shape

```json
{ "name": "NewCo Only", "description": "",
  "resources": [ {"name": "queue", "accessLevel": "ALL", "ids": []},
                 {"name": "working-hour", "accessLevel": "SPECIFIC",
                  "ids": ["781da294-..."]}, ... ] }
```

The 20 resource type names: `audio-prompt`, `working-hour`, `queue`, `idle-wrapup-code`,
`holiday-list`, `function`, `sub-flow`, `team`, `desktop-profile`, `desktop-layout`,
`cad-variable`, `address-book`, `site`, `flow`, `multimedia-profile`, `skill-profile`,
`channel`, `skill-definition`, `override`, `outdial-ani`.

## Reads

| Goal | Call |
|---|---|
| Every collection | `wxcc_list(entity="resource-collection", attributes="id,name", all_pages=true)` |
| Find by exact name | `wxcc_list(entity="resource-collection", filter="name==COLLECTION-NAME")` |
| One collection, full object | `wxcc_get(entity="resource-collection", id="COLLECTION-ID")` |

**The list omits `resources` entirely** — it returns only `id`, `name`, `description` and
timestamps. Every question about *what is in* a collection needs `wxcc_get`.

## Writes

Dry-run first (no `confirm`), show the user, then `confirm=true`.

```
wxcc_create(entity="resource-collection", fields={
  "name": "COLLECTION-NAME", "description": "...",
  "resources": [ {"name": "queue",  "accessLevel": "ALL", "ids": []},
                 {"name": "team",   "accessLevel": "ALL", "ids": []},
                 {"name": "site",   "accessLevel": "ALL", "ids": []},
                 {"name": "channel","accessLevel": "ALL", "ids": []},
                 ... all 20 types ... ]
})

wxcc_update(entity="resource-collection", id="COLLECTION-ID", changes={"description": "..."})
wxcc_delete(entity="resource-collection", id="COLLECTION-ID")
```

Two rules the API enforces, both reproduced live:

- **All 20 resource types must be present.** A partial list is a 400 that names exactly
  which are missing — useful, so read it. **Omitting `resources` altogether is a bare
  `500 "Processing failed"`** with no hint; that is the API reporting a missing required
  field badly, not a server fault to retry.
- **`site`, `channel`, `team` and `queue` must not be `NONE`** — use `ALL` or `SPECIFIC`
  (400 names the four).

To change membership, `wxcc_get` the collection, edit the entry for that resource type, and
pass the whole `resources` array back.

## Bulk

**Update only**, and on `PATCH resource-collection/bulk` — see **wxcc-bulk**. There is no
bulk create (per-item `500 "no mapping for id"`) and no bulk delete (`400 "requestAction
should be empty or specified as 'SAVE' for PATCH"`); the tools refuse both. Despite being a
PATCH route it is **not** partial — an item without the full `resources` array returns a
leaked Java NPE (`Cannot invoke "java.util.Set.iterator()" … getResources() is null`), so
`wxcc_bulk_update` read-modify-writes.

## Traps

| Item | Detail |
|---|---|
| List omits `resources` | The list is a summary only — `wxcc_get` for contents |
| Missing `resources` key | Bare 500, no field named. A partial list gives the helpful 400 instead |
| Four types can't be NONE | `site`, `channel`, `team`, `queue` |
| PATCH bulk is not partial | Send the full object or get a raw Java NPE (a leaked internal error) |
| No bulk create/delete | Refused by the tool; use `wxcc_create` / `wxcc_delete` per object |

## Provenance and maintenance

Verified live on a us1 sandbox 2026-07-21 (org `174…`, baseline of 2 collections restored)
end-to-end **through the MCP tools**: create → 201; update → 200 confirmed by re-read; bulk
update → per-item 207 `UPDATE` confirmed by re-read; delete → 204 with the item then 404.
The all-20-types 400, the missing-key 500, the four-must-not-be-NONE 400, the bulk-create
500 and the bulk-delete 400 were each reproduced. Re-verify with a `zzz-` named cycle.
