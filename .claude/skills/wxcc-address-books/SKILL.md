---
name: wxcc-address-books
description: Use when asked about Webex Contact Center address books or their entries (speed-dial directories agents see) - "list address books", "create an address book", "add/update/remove an entry in address book X", "what numbers are in address book X", "delete address book X". Full CRUD on both the book and its individual entries.
---

# wxcc-address-books — address books and their entries (read + write)

Call the `wxcc_*` MCP tools with `entity="address-book"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

Two-level entity: the **book**, and its **entries** (`{name, number}` pairs). Entries are a
sub-resource with their own tools — touch one at a time rather than replacing the array.

## Use when / Do NOT use when

**Use when:** listing/creating/updating/deleting address books or the entries in them.

**Do NOT use when:**
- Auth errors or 403 on write → **wxcc-connect**.
- Which address book a Desktop Profile exposes → **wxcc-desktop-profiles**.
- Numbers that route **into** the tenant → **wxcc-entry-points**. An address book is an
  outbound speed-dial directory — a different thing entirely.

## Reads

| Goal | Call |
|---|---|
| All books | `wxcc_list(entity="address-book", attributes="id,name", all_pages=true)` |
| One book + its entries | `wxcc_get(entity="address-book", id="BOOK-ID")` — entries come embedded |
| Find by name | `wxcc_list(entity="address-book", filter="name==BOOK-NAME")` |

## Writes — books

```
wxcc_create(entity="address-book", fields={
  "name": "BOOK-NAME", "parentType": "ORGANIZATION",
  "description": "...",
  "addressBookEntries": [{"name": "Alice", "number": "+15551234567"}]
})

wxcc_update(entity="address-book", id="BOOK-ID", changes={"description": "..."})
wxcc_delete(entity="address-book", id="BOOK-ID")
```

Entries can be **embedded at creation** — that is the cleanest way to make a populated book
through the tools. `parentType: "SITE"` with a `siteId` exists per Cisco's collection
(**candidate, untested**).

**Deleting a book deletes its entries with it. No rollback.**

## Writes — entries

```
wxcc_list_entries(entity="address-book", parent_id="BOOK-ID")
wxcc_add_entry(entity="address-book", parent_id="BOOK-ID",
               fields={"name": "Bob", "number": "+15557654321"})
wxcc_update_entry(entity="address-book", parent_id="BOOK-ID", entry_id="ENTRY-ID",
                  changes={"name": "Bob Renamed"})
wxcc_remove_entry(entity="address-book", parent_id="BOOK-ID", entry_id="ENTRY-ID")
```

Each is dry-run by default and verified by re-reading the parent. All confirmed live
2026-07-16 (201/200/204).

Removing an entry has **no rollback**: re-adding produces a new entry id.

## Entry paths — correction (2026-07-22)

An earlier note here said "`GET .../entry` returns 405 — the child collection has no list
endpoint." **That was wrong.** Two different paths:

| Path | Verb | What it is |
|---|---|---|
| `v2/address-book/{id}/entry` | GET → **200** | the entry **LIST**, paginated (`meta.totalRecords`) |
| `address-book/{id}/entry` | GET → **405** | the POST-only **CREATE** path — the 405 means "wrong verb", not "no list" |

This is the house path rule holding, not an exception: list carries `v2`, create drops it.

`wxcc_list_entries` still reads the entries **embedded in the parent**. That agreed exactly
with the list path when re-checked 2026-07-22 (4 of 4), but it does **not** paginate — a book
larger than whatever the embedded array caps at is a live risk. Follow-up logged in the tool.

**Trap: `GET v3/address-book/{id}` omits `addressBookEntries` entirely.** The non-`v2` item
path returns the entries embedded; the `v3` item path returns only the book's own six fields
(both verified 2026-07-22). Do not "modernize" the item read to `v3` — it would silently
empty every entry list.

## Provenance and maintenance

Full two-level CRUD run live on a us1 sandbox 2026-07-11 (book 201/204, entry 201/200/204,
tenant returned to zero books). Re-verified end-to-end through the MCP tools 2026-07-16. Body
shapes from Cisco's Postman collection (v3, Aug 2023), each confirmed live. The entry-path
correction, the `v3` item-path trap, and `POST address-book/{id}/entry/bulk` → 207 were probed
live 2026-07-22 (read-only; the `bulk` probe sent an empty `items` array). Re-verify with a
`zz-` named book + entry cycle.
