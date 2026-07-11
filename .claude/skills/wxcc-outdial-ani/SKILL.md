---
name: wxcc-outdial-ani
description: Use when asked about Webex Contact Center outdial ANIs (the caller-ID numbers agents present on outbound calls) - "list our outdial ANIs", "what number shows when agents dial out", "create an outdial ANI", "add a number to ANI list X", "delete outdial ANI X". Covers reads and verified create/delete; update is a labeled candidate. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-outdial-ani — outbound caller-ID number lists (read + write)

An outdial ANI is a named list of E.164 numbers (`outdialANIEntries`) an agent can present
as caller ID on outbound calls; Desktop Profiles reference one via `outdialANIId`.
Entries are **embedded** in the ANI object, not a sub-resource. Create/delete verified
live on a sandbox tenant 2026-07-11.

## Use when / Do NOT use when

**Use when:** listing/inspecting/creating/deleting outdial ANI lists or reading their numbers.

**Do NOT use when:**
- Auth errors → **wxcc-connect**. Writes without `cjp:config_write` → 403.
- Which ANI a Desktop Profile uses → **wxcc-desktop-profiles** (`outdialANIId`).
- Inbound numbers → **wxcc-entry-points** (dial numbers ≠ outdial ANIs).

## Reads

```bash
python wxcc.py get --all "organization/{orgId}/v2/outdial-ani?attributes=id,name"
python wxcc.py get "organization/{orgId}/outdial-ani/ANI-ID"    # item path: no v2
```

Object (observed live): `name`, `description`, `outdialANIEntries[]` with per-entry
`{id, name, number (+E.164), defaultANIEntry}`.

## Writes — safety rules of **wxcc-teams-write** apply (confirm first, name rollback, verify after)

### Create

```bash
python wxcc.py post "organization/{orgId}/outdial-ani" --body '{"name":"ANI-NAME","description":"...","outdialANIEntries":[{"name":"Main","number":"+15551234567","defaultANIEntry":true}]}'
```

→ verify: 201 with `id` (verified live — note this endpoint is absent from Cisco's
Postman collection, which has GET only; probing found it). Rollback = DELETE the id.
The number must be a real, tenant-entitled ANI to be usable on calls — the API accepted a
fictional number, so **validation of number ownership appears not to happen at create**
(observed; treat presenting an unowned ANI as a compliance problem, not an API one).

### Update (candidate — untested)

PUT `organization/{orgId}/outdial-ani/ANI-ID` with the full object is the expected shape
per every other entity in this API, but it has NOT been run. Capture the prior object
first, apply the change→re-read→revert-on-surprise discipline from **wxcc-users-write**.

### Delete

```bash
python wxcc.py delete "organization/{orgId}/outdial-ani/ANI-ID"
```

→ verify: 204 (verified live); list count drops. Check no Desktop Profile references it
first (`outdialANIId`) — deleting a referenced ANI is untested (candidate/danger).

## Provenance and maintenance

Reads, create (201), and delete (204) run live on a us1 sandbox 2026-07-11 via `wxcc.py`;
baseline count restored. PUT update untested — labeled candidate above. Re-verify with a
`zz-` named create→delete cycle.
