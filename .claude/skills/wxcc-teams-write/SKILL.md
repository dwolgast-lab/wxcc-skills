---
name: wxcc-teams-write
description: Use when asked to create, rename, update, activate/deactivate, move, or delete a Webex Contact Center team - "create a team called X on site Y", "rename team X", "deactivate team X", "delete team X", "change team X's site/status/type". Mutating - requires cjp:config_write and explicit user confirmation before each write. Covers the create fields, the reference-blocked delete, and how membership actually works.
---

# wxcc-teams-write — create, update, and delete WxCC teams

Mutating counterpart to **wxcc-teams**. Call `wxcc_create` / `wxcc_update` / `wxcc_delete`
on the server for the tenant the user named. **If no tenant was named, ask — do not guess.**

## Use when / Do NOT use when

**Use when:** creating, renaming, updating, re-siting, deactivating, or deleting a team.

**Do NOT use when:**
- Listing/finding/inspecting teams → **wxcc-teams**.
- Auth errors or 403 on write → **wxcc-connect**.
- **Adding or removing a team's MEMBERS** → **wxcc-users-write**. Membership lives on the
  user's `teamIds`, not on the team. The team object shows `userIds` read-only.
- Changing which queues route to a team → the queue's `callDistributionGroups`,
  **wxcc-queues-write**.

## How the write tools protect you

Every write is a two-step, enforced by the server — you do not have to remember it:

1. Call without `confirm` → **nothing is written.** You get back the tenant, a field-level
   diff (or the object that would be destroyed), and the rollback.
2. Show that to the user, get an explicit yes, then re-call with `confirm=true`.

After a confirmed write the tool **re-reads and diffs**. Watch for:

- **`TENANT`** — first field in every write result. Confirm it is the tenant the user meant
  *before* passing `confirm=true`. `[PRODUCTION]` means a real customer tenant.
- **`SILENTLY_IGNORED`** — the API returns 200 while dropping fields. If this is non-null,
  the write did **not** fully apply. Tell the user; do not report success.
- **`blocked` + `conflicting_references`** — a delete refused because other objects still
  point at this team. Resolve those first; do not retry.

## Create

```
wxcc_create(entity="team", fields={
  "name": "TEAM-NAME", "active": true, "siteId": "SITE-ID",
  "teamStatus": "IN_SERVICE", "teamType": "AGENT"
})
```

All five fields are required — the tool checks before calling, and the API would otherwise
400 naming them. `siteId` comes from **wxcc-sites**. `teamType` is `AGENT`, or `CAPACITY`
for a team of external/non-Webex agents (no desktop seats).

Optional, from Cisco's Postman collection, **candidates — never run here**:
`desktopLayoutId`, `multimediaProfileId`. Omitting them means "tenant default", which is how
you get the Global desktop layout — there is no "set to Global" value.

Rollback: `wxcc_delete` the returned id.

## Update

```
wxcc_update(entity="team", id="TEAM-ID", changes={"name": "NEW-NAME"})
```

Read-modify-write: the tool GETs the current object, merges `changes`, and PUTs the whole
thing (this API replaces, it does not patch). Pass only the fields you want changed.
Rollback is in the dry run's `diff` under `from`.

## Delete

```
wxcc_delete(entity="team", id="TEAM-ID")           # preview: shows userIds + any blockers
wxcc_delete(entity="team", id="TEAM-ID", confirm=true)
```

**Reference-blocked (confirmed live 2026-07-14):** a team with users on it returns
**HTTP 412** `referencedEntities: ["user"]`. The tool pre-flights this and returns
`conflicting_references` naming each user, so clear the team from their `teamIds`
(**wxcc-users-write**) first.

**No rollback.** Recreating yields a new id; queue distribution groups and anything else
holding the old id stay broken. Confirm emphatically.

## Traps and notes

| Item | Detail |
|---|---|
| Membership is on the USER | `teamIds` on the user, not on the team. A user can hold several teams at once (confirmed 2026-07-14). |
| The API reorders `teamIds` | Sent `[old, new]`, got `[new, old]`. Never depend on order. |
| Legacy write form | A `?teamDTO=<urlencoded-json>` query-param POST exists in portal samples. Works, but the JSON body is what is verified here. |
| DELETE absent from Cisco's Postman collection | It works anyway (204, verified). Absence from samples ≠ absence from API. |
| `version` field | Created objects carry `version: 0`. Optimistic locking under concurrent edits is untested (candidate). |

## Provenance and maintenance

Full create→update→delete lifecycle run against a live us1 sandbox (2026-07-11: 201/200/204,
baseline restored) and re-verified through the MCP tools 2026-07-14, including the 412
reference block and the confirmed-delete path. Optional create fields come from Cisco's
Postman collection (v3, Aug 2023) and are candidates until run. Re-verify with a `zz-`
prefixed throwaway.
