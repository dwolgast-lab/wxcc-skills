---
name: wxcc-outdial-ani
description: Use when asked about Webex Contact Center outdial ANIs (the caller-ID numbers agents present on outbound calls) - "list our outdial ANIs", "what number shows when agents dial out", "create an outdial ANI", "add a number to ANI list X", "delete outdial ANI X". Covers reads and verified create/update/delete - including adding or removing a number, which is a full replace of the entries array.
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

### Adding or removing a number (update)

Renaming is easy — pass only what changes and the entries carry through untouched:

```
wxcc_update(entity="outdial-ani", id="ANI-ID", changes={"name": "NEW-NAME"})
```

**Changing the numbers is a FULL REPLACE of `outdialANIEntries`, and it is easy to destroy
data.** Two rules, both reproduced live 2026-07-16:

1. **An entry you omit is DELETED.** To add one number, send the existing entries *plus* the
   new one — not just the new one.
2. **Every kept entry must carry its existing sub-entity `id`**, or you get
   **409 `Duplicate entry`** (the same trap as `skill-profile.activeSkills`). New entries
   omit `id`. The 409 is a clean failure — the list is left unchanged.

```
# 1. read the current entries
cur = wxcc_get(entity="outdial-ani", id="ANI-ID")

# 2. keep them WITH their ids, append the new one WITHOUT an id
wxcc_update(entity="outdial-ani", id="ANI-ID", changes={"outdialANIEntries": [
  {"id": "<existing entry id>", "name": "Main", "number": "+15551234567",
   "defaultANIEntry": true},
  {"name": "Second", "number": "+15557654321", "defaultANIEntry": false}
]})
```

To **remove** a number, send the array without it.

The result reports `needs_your_eyes` rather than `confirmed_changed` for the array: the
server adds ids/timestamps and **reorders the entries**, so it cannot be auto-verified.
**Read the `actual` list back and confirm it is what the user asked for.**

## Traps

| Item | Detail |
|---|---|
| **Number ownership is not validated at create** | The API accepted a fictional number (observed live). Presenting an ANI the tenant does not own is a **compliance problem, not an API error** — it will fail or misbehave on real calls. Confirm the number is entitled before creating. |
| Endpoints absent from Cisco's Postman collection | The collection has GET only; create/update/delete were found by probing and verified live (201/200/204). Absence from samples ≠ absence from API. |
| Omitting an entry on update | **Deletes it.** Full replace, not merge. |
| Kept entry without its `id` | **409 duplicate-entry** (clean failure, list unchanged) |
| The API reorders entries | Sent `[A, B]`, got `[B, A]`. Never depend on order. |
| Deleting a referenced ANI | Untested (**candidate/danger**). Check no Desktop Profile points at it (`outdialANIId`) first. |
| Entries are embedded | Not a sub-resource — the list is the unit |

## Provenance and maintenance

Reads, create (201), and delete (204) run live on a us1 sandbox 2026-07-11. **Update probed
and verified 2026-07-16** (200): rename, add-an-entry, and remove-an-entry all confirmed by
re-read; the 409-without-id and the entry reordering were each reproduced; probe object
deleted and the baseline of 2 lists restored. Re-verify with a `zz-` named
create→update→delete cycle.
