---
name: wxcc-aux-codes
description: Use when asked about Webex Contact Center auxiliary codes - idle codes or wrap-up codes - "list our wrap-up/idle codes", "create a wrap-up code called X", "rename or deactivate code X", "delete code X", "which codes are system defaults". Covers reads and verified create/update/delete. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-aux-codes — idle and wrap-up codes (read + write)

One entity, `auxiliary-code`, covers both **idle codes** and **wrap-up codes**,
discriminated by `workTypeCode` (`IDLE_CODE` | `WRAP_UP_CODE`). Full CRUD verified live
on a sandbox tenant 2026-07-11 (201/200/204, baseline restored).

## Use when / Do NOT use when

**Use when:** listing, inspecting, creating, updating, or deleting idle/wrap-up codes.

**Do NOT use when:**
- Auth errors → **wxcc-connect**. Writes without `cjp:config_write` → 403.
- Which codes a Desktop Profile exposes to agents → **wxcc-desktop-profiles**
  (`idleCodes`/`wrapUpCodes`/`accessIdleCode`/`accessWrapUpCode` live there).

## Reads

```bash
python wxcc.py get --all "organization/{orgId}/v2/auxiliary-code?attributes=id,name,workTypeCode,active,isSystemCode"
python wxcc.py get "organization/{orgId}/v2/auxiliary-code?filter=name==CODE-NAME"
python wxcc.py get "organization/{orgId}/auxiliary-code/CODE-ID"    # item path: no v2
```

Object fields (observed live): `name`, `active`, `workTypeCode`, `workTypeId`,
`defaultCode`, `isSystemCode`, `systemDefault`, `description`, `burnoutInclusion`.

## Writes — safety rules of **wxcc-teams-write** apply (confirm first, name rollback, verify after)

### Create

**Prerequisite:** a `workTypeId` — copy it from any existing code of the same
`workTypeCode` (all IDLE_CODEs share one, all WRAP_UP_CODEs another; read them with the
list recipe above).

```bash
python wxcc.py post "organization/{orgId}/auxiliary-code" --body '{"active":true,"name":"CODE-NAME","workTypeCode":"WRAP_UP_CODE","defaultCode":false,"isSystemCode":false,"description":"...","workTypeId":"WORK-TYPE-ID"}'
```

→ verify: 201 with `id`. Rollback = DELETE that id.

### Update

```bash
python wxcc.py put "organization/{orgId}/auxiliary-code/CODE-ID" --body '{"id":"CODE-ID","active":true,"name":"CODE-NAME","workTypeCode":"WRAP_UP_CODE","defaultCode":false,"description":"new text","workTypeId":"WORK-TYPE-ID"}'
```

→ verify: 200 echoes changes (verified live with a description change). Capture the
prior object first — it is the rollback.

### Delete

```bash
python wxcc.py delete "organization/{orgId}/auxiliary-code/CODE-ID"
```

→ verify: 204, then filter-by-name returns 0. Do not delete `isSystemCode: true` codes
(RONA etc.) — behavior untested and they are platform-owned (candidate/danger).

## Provenance and maintenance

All recipes run live on a us1 sandbox 2026-07-11 via `wxcc.py` (create 201 / update 200 /
delete 204, baseline count restored). Create body from Cisco's Postman collection (v3,
Aug 2023), confirmed by the live 201. Re-verify with a `zz-` named CRUD cycle.
