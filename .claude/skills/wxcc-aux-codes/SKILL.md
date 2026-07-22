---
name: wxcc-aux-codes
description: Use when asked about Webex Contact Center auxiliary codes - idle codes or wrap-up codes - "list our wrap-up/idle codes", "create a wrap-up code called X", "rename or deactivate code X", "delete code X", "which codes are system defaults". Covers reads and verified create/update/delete. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-aux-codes — idle and wrap-up codes (read + write)

Call the `wxcc_*` MCP tools with `entity="auxiliary-code"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

**One entity covers both** idle codes and wrap-up codes, discriminated by `workTypeCode`
(`IDLE_CODE` | `WRAP_UP_CODE`).

## Use when / Do NOT use when

**Use when:** listing, inspecting, creating, updating, or deleting idle/wrap-up codes.

**Do NOT use when:**
- Auth errors or 403 on write → **wxcc-connect**.
- Which codes a Desktop Profile *exposes to agents* → **wxcc-desktop-profiles**
  (`idleCodes`/`wrapUpCodes`/`accessIdleCode`/`accessWrapUpCode` live there). Creating a
  code does not make agents see it.

## Reads

| Goal | Call |
|---|---|
| All codes | `wxcc_list(entity="auxiliary-code", attributes="id,name,workTypeCode,active,isSystemCode", all_pages=true)` |
| Just wrap-up codes | list, then filter client-side on `workTypeCode` |
| Find by name | `wxcc_list(entity="auxiliary-code", filter="name==CODE-NAME")` |
| One code | `wxcc_get(entity="auxiliary-code", id="CODE-ID")` |

Fields (observed live): `name`, `active`, `workTypeCode`, `workTypeId`, `defaultCode`,
`isSystemCode`, `systemDefault`, `description`, `burnoutInclusion`.

## Writes

Dry-run first (no `confirm`), show the user, then `confirm=true`. Watch **`TENANT`**,
**`SILENTLY_IGNORED`**, **`blocked`**.

```
wxcc_create(entity="auxiliary-code", fields={
  "active": true, "name": "CODE-NAME", "workTypeCode": "WRAP_UP_CODE",
  "defaultCode": false, "workTypeId": "WORK-TYPE-ID"
})

wxcc_update(entity="auxiliary-code", id="CODE-ID", changes={"description": "new text"})
wxcc_delete(entity="auxiliary-code", id="CODE-ID")
```

**`workTypeId` is not derivable and not guessable** — copy it from an existing code with the
**same `workTypeCode`** (all IDLE_CODEs share one, all WRAP_UP_CODEs another). Get it from
the list recipe above. The tool requires it on create because the API 400s without it.

## "Delete all the inactive codes"

There **is** a purge endpoint — `POST auxiliary-code/purge-inactive-entities` — and it is
**deliberately not exposed**. It returns **403 "Access denied"** even for a full-rights
tenant admin holding `cjp:config_write`, and Cisco does not document which scope it needs
(probed 2026-07-22). The route itself is real: it answers with the app's `trackingId` error
shape, where a nonexistent sub-path answers 405 with the framework's `timestamp` shape.
The same 403 was then confirmed on `desktop-layout` and `agent-profile`, so the gate is
**tenant-wide rather than specific to aux codes** — canonical note in **wxcc-bulk**.

Do this instead — it is aimable at exactly the codes the user chose, which a tenant-wide
sweep is not:

1. `wxcc_list(entity="auxiliary-code", all_pages=true)`
2. Filter `active == false` **in code**, and show the user the resulting names.
3. `wxcc_bulk_delete(entity="auxiliary-code", ids=[...], confirm=True)` — or
   `wxcc_delete` one at a time for a short list.

Never present the purge endpoint as an option the user could reach another way.

## Traps

| Item | Detail |
|---|---|
| `isSystemCode: true` codes | Platform-owned (RONA etc.). **Do not delete** — behavior untested and they are not yours (candidate/danger). Warn the user if they ask. |
| `workTypeId` | Must match the `workTypeCode` family; copy from a sibling |
| Creating ≠ visible to agents | Desktop Profile controls exposure — **wxcc-desktop-profiles** |
| Bulk export | `GET auxiliary-code/bulk-export` is out of scope for these tools — not probed, not exposed. |

## Provenance and maintenance

Full CRUD run live on a us1 sandbox 2026-07-11 (201/200/204, baseline restored). Create body
from Cisco's Postman collection (v3, Aug 2023), confirmed by the live 201. Re-verify with a
`zz-` named cycle.
