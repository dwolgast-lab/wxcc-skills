---
name: wxcc-user-profiles
description: Use when asked about Webex Contact Center User Profiles - the admin access-rights profiles referenced by user.userProfileId - "what user profiles exist", "what can profile X do", "which permissions does profile X grant", "create a user profile", "change profile X's permissions or resource collections", "delete user profile X". NOT the Desktop Profile (agent desktop behaviour) - that is wxcc-desktop-profiles. Covers reads and verified create/update/delete. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-user-profiles — the admin access-rights profile (v3)

Call the `wxcc_*` MCP tools with `entity="user-profile"` on the server for the tenant the
user named (`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

A user profile governs **what an administrator or supervisor may see and do** — which
permissions they hold and which resources they may reach. It is what `user.userProfileId`
points at. It is **not** the Desktop Profile that controls agent desktop behaviour.

## Use when / Do NOT use when

**Use when:**
- Listing user profiles; inspecting what a profile grants.
- Creating, updating, or deleting a user profile.
- Resolving a `userProfileId` found on a user.

**Do NOT use when:**
- Agent desktop behaviour (wrap-up, outdial, auto-answer) → **wxcc-desktop-profiles**
  (the API path there is `agent-profile`).
- Assigning a profile to a person → **wxcc-users-write** (`user.userProfileId`).
- Scoping *which* resources a profile can reach → **wxcc-resource-collections**
  (this entity references them by id).
- Auth errors or the wrong org → **wxcc-connect**.

## The v2/v3 trap — read this before anything else

**This is the only entity in the registry whose item path keeps its version prefix.**
Everywhere else `v2/<entity>/{id}` 404s and the item path drops it. Here, **both answer,
with different schemas**:

| Path | Returns |
|---|---|
| `v3/user-profile/{id}` | the **current** shape — `permissionAccessLevel`, `resourceAccessLevel`, `permissions[]`, `resourceCollections[]` |
| `user-profile/{id}` | the **old v2** shape — `accessAll*`, `userProfileAppModules[]` |

The tools are pinned to **v3**. Reading the v2 path yourself gives a stale-looking object
that is not what a write will accept.

**v2 writes are decommissioned per-org**: a v2 create returns
`400 "v2 user profile is decommissioned for this organization … Please use the new version
of API"`. Reads still work, which is what makes it confusing.

## Reads

| Goal | Call |
|---|---|
| Every profile | `wxcc_list(entity="user-profile", attributes="id,name", all_pages=true)` |
| Find by exact name | `wxcc_list(entity="user-profile", filter="name==PROFILE-NAME")` |
| One profile, full object | `wxcc_get(entity="user-profile", id="PROFILE-ID")` |

**The list omits `permissions`** — it comes back empty there even on a profile that has 32
of them. Read the item to see them. (Same shape of trap as `resource-collection.resources`.)

## Writes

Dry-run first (no `confirm`), show the user, then `confirm=true`.

```
wxcc_create(entity="user-profile", fields={
  "name": "PROFILE-NAME", "profileType": "ADMINISTRATOR_ONLY",
  "permissionAccessLevel": "SPECIFIC", "resourceAccessLevel": "ALL",
  "active": true,
  "permissions": [{"name": "resource-collection", "access": "EDIT"}, ...]
})

wxcc_update(entity="user-profile", id="PROFILE-ID", changes={"description": "..."})
wxcc_delete(entity="user-profile", id="PROFILE-ID")
```

Five fields are required (`name`, `profileType`, `permissionAccessLevel`,
`resourceAccessLevel`, `active`) — each named by a 400 when missing. Beyond that:

- **`permissionAccessLevel` must be `SPECIFIC`** for `ADMINISTRATOR_ONLY` and
  `STANDARD_AGENT` (a 400 says so), and `SPECIFIC` then **requires the permission list**.
- **The permission list's key on write is `permissions`**, entries `{name, access}`. The
  API's own 400 calls it **`userProfilePermissions`** — sending *that* key is treated as
  absent and you get the same 400 forever. Documented API defect, not a convention.
- **Building a profile from a copy of another must strip the sub-entity ids** — a full copy
  returns `409 "Internal error. Please contact Cisco Support Team"`. `wxcc_create` does this
  for you (`clone_safe: False`).
- `systemDefault: true` profiles (6 of the 8 on the sample tenant) cannot be modified.

## Bulk

`user-profile` supports **all three** bulk ops on `POST v3/user-profile/bulk` — see
**wxcc-bulk**. Update is read-modify-write (no partial route). The v2 `user-profile/bulk`
route also answers but returns a per-item 400; the tools use v3.

## Traps

| Item | Detail |
|---|---|
| Item path keeps `v3` | The one exception to "item paths drop the version". `user-profile/{id}` silently returns the OLD schema |
| v2 writes decommissioned | 400 naming the org; reads still succeed, so it looks like a permissions problem |
| List omits `permissions` | Read the item, not the list, before cloning or auditing |
| `userProfilePermissions` | The key the error message names is **not** the key the API accepts — use `permissions` |
| Cloning a profile | Strip nested ids or get a 409 "Internal error" that names nothing |
| Not the Desktop Profile | `agent-profile` is a different entity → **wxcc-desktop-profiles** |

## Provenance and maintenance

Verified live on a us1 sandbox 2026-07-21 (org `174…`, 8 profiles, baseline restored)
end-to-end **through the MCP tools**: create → 201 (and each required field's 400 reproduced
by omitting it); update → 200 confirmed by re-read; bulk update → per-item 207 `UPDATE`
confirmed by re-read; bulk delete → 207 `DELETE` with the item then 404; single delete →
204. The v2-decommissioned 400, the `userProfilePermissions`-vs-`permissions` mismatch, and
the 409 on an unstripped clone were each reproduced. Re-verify with a `zzz-` named cycle.
