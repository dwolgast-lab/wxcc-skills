---
name: wxcc-outdial-ani
description: Use when asked about Webex Contact Center outdial ANIs (the caller-ID numbers agents present on outbound calls) - "list our outdial ANIs", "what number shows when agents dial out", "create an outdial ANI", "add a number to ANI list X", "delete outdial ANI X". Full CRUD on both the ANI list and its individual numbers - add or remove one number at a time via the entry sub-resource.
---

# wxcc-outdial-ani — outbound caller-ID number lists (read + write)

Call the `wxcc_*` MCP tools with `entity="outdial-ani"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

An outdial ANI is a **named list** of E.164 numbers an agent can present as caller ID on
outbound calls. Desktop Profiles reference one via `outdialANIId`. The numbers are a
**sub-resource** (`outdial-ani/{id}/entry`) with their own tools — though they also appear
embedded in the parent's `outdialANIEntries` array when you read it.

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

### Adding, changing, or removing ONE number — use the entry tools

Numbers live in a **sub-resource** (`outdial-ani/{id}/entry`). Touch one at a time:

```
wxcc_list_entries(entity="outdial-ani", parent_id="ANI-ID")
wxcc_add_entry(entity="outdial-ani", parent_id="ANI-ID",
               fields={"name": "Second", "number": "+15557654321"})
wxcc_update_entry(entity="outdial-ani", parent_id="ANI-ID", entry_id="ENTRY-ID",
                  changes={"number": "+15557654322"})
wxcc_remove_entry(entity="outdial-ani", parent_id="ANI-ID", entry_id="ENTRY-ID")
```

All verified live 2026-07-16 (201/200/204), each confirmed by re-reading the parent.

**Renaming the list itself** is a normal update — entries carry through untouched:

```
wxcc_update(entity="outdial-ani", id="ANI-ID", changes={"name": "NEW-NAME"})
```

### Do NOT edit `outdialANIEntries` on the parent

It works, but it is a **full replace** and it is easy to destroy data: an entry you omit is
**deleted**, and every kept entry must resend its own `id` or you get **409 duplicate-entry**.
The entry tools have neither hazard. Use them.

(If you ever do replace the array, the result reports `needs_your_eyes` rather than
`confirmed_changed` — the server adds ids/timestamps and reorders the entries, so it cannot
be auto-verified. Read the `actual` list back.)

## Traps

| Item | Detail |
|---|---|
| **Number ownership is not validated at create** | The API accepted a fictional number (observed live). Presenting an ANI the tenant does not own is a **compliance problem, not an API error** — it will fail or misbehave on real calls. Confirm the number is entitled before creating. |
| Endpoints absent from Cisco's Postman collection | The collection has GET only; create/update/delete and the whole entry sub-resource were found by probing and verified live. Absence from samples ≠ absence from API. |
| `GET .../entry` | **405** — the child collection has no list endpoint. Read entries from the parent (`wxcc_list_entries` does this). |
| Replacing `outdialANIEntries` wholesale | Omitting an entry **deletes** it; a kept entry without its `id` gives **409**. Use the entry tools instead. |
| The API reorders entries | Sent `[A, B]`, got `[B, A]`. Never depend on order. |
| Deleting a referenced ANI | Untested (**candidate/danger**). Check no Desktop Profile points at it (`outdialANIId`) first. |
| Entries appear in two places | They are a real sub-resource AND echoed in the parent's array. Read from the parent; write via the entry tools. |

## Provenance and maintenance

Reads, create (201), and delete (204) run live on a us1 sandbox 2026-07-11. Parent update
(200) and the entry sub-resource (POST 201 / PUT 200 / DELETE 204, `GET .../entry` → 405)
probed and verified 2026-07-16, each confirmed by re-reading the parent; the
full-replace hazards on the parent array (omission deletes, kept entry without its `id` →
409) were each reproduced. Probe objects deleted, baseline of 2 lists restored.

The entry sub-resource was **missed on the first pass** — the create body shows entries
embedded, so they were assumed embedded-only. The tenant owner pointed at
`POST .../outdial-ani/{id}/entry` and it was there. Absence from Cisco's collection is not
absence from the API; the same two-level shape holds for **wxcc-address-books**.
