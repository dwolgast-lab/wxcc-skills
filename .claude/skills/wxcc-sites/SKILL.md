---
name: wxcc-sites
description: Use when asked about Webex Contact Center sites - "what sites exist", "find site X", "is site X active", "create a site called X", "rename site X", "delete site X", or resolving a siteId found on a team or user to its details. Covers reads and verified create/update/delete. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-sites — list, inspect, create, update, delete WxCC sites

Call the `wxcc_*` MCP tools with `entity="site"` on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

A site is the physical/logical location teams and users hang off (`team.siteId`,
`user.siteId`). It is a small object: `name`, `active`, `multimediaProfileId`, `description`.

## Use when / Do NOT use when

**Use when:**
- Listing or counting sites; finding a site by name, id, or keyword.
- Resolving a `siteId` (from a team or user) to the site's details.
- Creating, renaming, updating, or deleting a site.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Working with the teams at a site → **wxcc-teams** (filter by `siteId`).
- The multimedia profile itself → not covered by any skill yet (read-only referenced id).

## Reads

| Goal | Call |
|---|---|
| Every site | `wxcc_list(entity="site", attributes="id,name", all_pages=true)` |
| Count only | `wxcc_list(entity="site", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="site", filter="name==SITE-NAME")` |
| One site, full object | `wxcc_get(entity="site", id="SITE-ID")` |

## Writes

Dry-run first (no `confirm`), show the user, then `confirm=true`. Watch **`TENANT`**,
**`SILENTLY_IGNORED`**, **`blocked`**.

```
wxcc_create(entity="site", fields={
  "name": "SITE-NAME", "active": true,
  "multimediaProfileId": "MM-PROFILE-ID"
})

wxcc_update(entity="site", id="SITE-ID", changes={"name": "NEW-NAME"})
wxcc_delete(entity="site", id="SITE-ID")
```

**All three create fields are required** — a 400 names the missing ones (reproduced live).
`multimediaProfileId` is not derivable: copy it from an existing site
(`wxcc_get` any sibling).

**Deleting a site that teams or users still reference is blocked** by the pre-flight, with
each blocker named (`incoming-references` reports `team` and `user` types on a live site).
Repoint teams first (`wxcc_update(entity="team", ...)` — verified); moving a user's
`siteId` is a **candidate** (accepted in a no-op PUT, never changed for real). A site
delete is **not reversible** — recreate yields a new id.

## Traps

| Item | Detail |
|---|---|
| Create with name only | 400 naming `active` and `multimediaProfileId` — required, not defaulted |
| `multimediaProfileId` | Copy from a sibling site; there is no skill for the entity itself |
| Deleting a referenced site | Blocked with the list of teams/users; repointing users is a candidate |
| Filter values | Unquoted (`filter=name==X`); quotes → 400. Spaces untested. |

## Provenance and maintenance

Reads run live 2026-07-10 (68 sites, gold) and re-confirmed since. **Full write lifecycle
verified 2026-07-16 on a us1 sandbox**: minimal POST → 400 naming the required fields;
POST with all three → 201; PUT rename + description → 200 confirmed by re-read; DELETE →
204 with re-read 404; baseline of 2 sites restored. `incoming-references` on a live site
returned `team` and `user` — the delete pre-flight uses that same endpoint. Re-verify with
a `zz-` named cycle.
