---
name: wxcc-outdial-ani
description: Use when asked about Webex Contact Center outdial ANIs (the caller-ID numbers agents present on outbound calls) - "list our outdial ANIs", "what number shows when agents dial out", "create an outdial ANI", "add a number to ANI list X", "delete outdial ANI X". Covers reads and verified create/delete; update is a labeled candidate.
---

# wxcc-outdial-ani — outbound caller-ID number lists (read + write)

Call the `wxcc_*` MCP tools with `entity="outdial-ani"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

An outdial ANI is a **named list** of E.164 numbers an agent can present as caller ID on
outbound calls. Desktop Profiles reference one via `outdialANIId`. Entries are **embedded**
in the ANI object (`outdialANIEntries`), not a sub-resource — so adding a number is an
update to the whole list.

## Use when / Do NOT use when

**Use when:** listing/inspecting/creating/deleting outdial ANI lists or reading their numbers.

**Do NOT use when:**
- Auth errors or 403 on write → **wxcc-connect**.
- Which ANI a Desktop Profile uses → **wxcc-desktop-profiles** (`outdialANIId`).
- **Inbound** numbers → **wxcc-entry-points**. Dial numbers ≠ outdial ANIs.

## Reads

| Goal | Call |
|---|---|
| All ANI lists | `wxcc_list(entity="outdial-ani", attributes="id,name", all_pages=true)` |
| One list + its numbers | `wxcc_get(entity="outdial-ani", id="ANI-ID")` |

Object (observed live): `name`, `description`, `outdialANIEntries[]` with per-entry
`{id, name, number (+E.164), defaultANIEntry}`.

## Writes

```
wxcc_create(entity="outdial-ani", fields={
  "name": "ANI-NAME", "description": "...",
  "outdialANIEntries": [{"name": "Main", "number": "+15551234567", "defaultANIEntry": true}]
})

wxcc_delete(entity="outdial-ani", id="ANI-ID")     # preview first
```

Dry-run first, show the user, then `confirm=true`. Watch **`TENANT`**,
**`SILENTLY_IGNORED`**, **`blocked`**.

**Update is refused by the registry** — `wxcc_update` on `outdial-ani` is unproven. PUT with
the full object is the shape every other entity in this API uses, but it has never been run
here. That means **"add a number to an existing ANI list" has no verified path yet**: say so
rather than improvising. Creating a new list works.

## Traps

| Item | Detail |
|---|---|
| **Number ownership is not validated at create** | The API accepted a fictional number (observed live). Presenting an ANI the tenant does not own is a **compliance problem, not an API error** — it will fail or misbehave on real calls. Confirm the number is entitled before creating. |
| Endpoints absent from Cisco's Postman collection | The collection has GET only; create/delete were found by probing and verified live (201/204). Absence from samples ≠ absence from API. |
| Deleting a referenced ANI | Untested (**candidate/danger**). Check no Desktop Profile points at it (`outdialANIId`) first. |
| Entries are embedded | Not a sub-resource — the list is the unit |

## Provenance and maintenance

Reads, create (201), and delete (204) run live on a us1 sandbox 2026-07-11; baseline
restored. Update remains untested and is therefore refused by the tools rather than guessed
at. Re-verify with a `zz-` named create→delete cycle. **Follow-up:** probe the PUT so
adding a number to an existing list gets a verified path.
