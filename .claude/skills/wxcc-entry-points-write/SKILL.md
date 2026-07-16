---
name: wxcc-entry-points-write
description: Use when asked to create, update, or delete a Webex Contact Center entry point, or to change a dial number's entry-point mapping - "create an entry point for X", "change entry point X's service level", "repoint +1555... to entry point Y", "delete entry point X". Mutating - requires cjp:config_write and explicit user confirmation. Covers why a brand-new phone number cannot be created here.
---

# wxcc-entry-points-write — create/update/delete EPs; repoint dial numbers

Mutating counterpart to **wxcc-entry-points**. Call `wxcc_create` / `wxcc_update` /
`wxcc_delete` on the server for the tenant the user named. **If no tenant was named, ask.**

**EPs are live routing infrastructure.** A mistaken delete or repoint breaks call delivery
immediately, for real callers. Treat every write here as production-grade even in a sandbox.

## Use when / Do NOT use when

**Use when:** creating/updating/deleting entry points; changing a dial number's mapping.

**Do NOT use when:**
- Listing/finding EPs or DNs → **wxcc-entry-points**.
- Auth errors or 403 on write → **wxcc-connect**.
- **"Add a brand-new phone number"** → **not possible here.** See the DN section.
- Attaching or authoring the FLOW an EP runs → Cisco's **flow-store** MCP server.

## How the write tools protect you

Call without `confirm` → nothing is written; you get the tenant, a diff (or what would be
destroyed), and the rollback. Show it, get an explicit yes, re-call with `confirm=true`.
Watch **`TENANT`** (first field), **`SILENTLY_IGNORED`**, and **`blocked`**.

## Entry points

```
wxcc_create(entity="entry-point", fields={
  "name": "EP-NAME", "entryPointType": "INBOUND", "channelType": "TELEPHONY",
  "serviceLevelThreshold": 20, "active": true, "maximumActiveContacts": 0
})

wxcc_update(entity="entry-point", id="EP-ID", changes={"serviceLevelThreshold": 25})
wxcc_delete(entity="entry-point", id="EP-ID")            # preview first
```

Required on create (a 400 names them otherwise): `serviceLevelThreshold` (> 0), `active`,
`maximumActiveContacts` (>= 0), plus name/type/channel. `entryPointType` is `INBOUND` or
`OUTBOUND` (both observed). Server defaults: `timezone` (tenant default),
`callbackEnabled: false`.

A new EP has **no flow attached**. Flow assignment via this API is untested (**candidate**)
— flows are flow-store's job.

Delete: **no rollback.** Deleting an EP that still has dial numbers attached is untested
(**candidate** — expect a 412-style refusal like referenced skills). Check the DN→EP lookup
in **wxcc-entry-points** and repoint first.

## Dial numbers — read this before promising anything

**You cannot invent a phone number here.** A DN record *maps* a number that already exists
in the Webex Calling location inventory. Provisioning lives in Control Hub / Calling admin.

The live validation chain, reproduced in order: missing `location` → 400, then missing
`regionId` → 400, then — with a fictional number — **HTTP 404 "Dialed number does not
exist"**. Note it is a **404, not a 400**: the API is saying the number is not in inventory,
which reads like a broken endpoint if you are not expecting it.

```
wxcc_create(entity="dial-number", fields={
  "dialledNumber": "+15551234567", "entryPointId": "EP-ID",
  "location": "LOCATION-ID", "regionId": "REGION-ID"
})
```

Copy `location`/`regionId` from a sibling DN at the same site. **A full 201 has never been
observed** — no free provisioned number was available to test (**candidate**).

### Repoint a number to a different EP

```
wxcc_update(entity="dial-number", id="DN-ID", changes={"entryPointId": "NEW-EP-ID"})
```

The tool does the read-modify-write, carrying `location`/`regionId`/`defaultAni` through
unchanged. The PUT contract is verified (idempotent PUT → 200); **changing `entryPointId`
specifically is untested (candidate)** — re-read and confirm the mapping moved.

### Delete a DN mapping

`wxcc_delete(entity="dial-number", ...)` is **refused by the registry**: it is unprobed and
would unmap a live number. If genuinely needed, do it deliberately in the portal.

## Traps

| Item | Detail |
|---|---|
| Unprovisioned number on DN create | **404** (not 400) "Dialed number does not exist" |
| Field spelling | Path is `dial-number`; field is `dialledNumber` (double L) |
| DN update is full-replace | The tool handles it — do not hand-build partial bodies |
| EP required fields | A 400's `reason` names each one — read it before retrying |

## Provenance and maintenance

EP create/update/delete run live on a us1 sandbox 2026-07-11 (201/200/204, probe removed).
DN: required-field chain and the inventory 404 reproduced live; idempotent PUT 200 verified;
create-201 and delete remain candidates. Re-verify with a `zz-` named EP cycle.
