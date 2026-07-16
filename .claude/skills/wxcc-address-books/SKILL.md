---
name: wxcc-address-books
description: Use when asked about Webex Contact Center address books or their entries (speed-dial directories agents see) - "list address books", "create an address book", "add/update/remove an entry in address book X", "what numbers are in address book X", "delete address book X". Books have full MCP tool coverage; entry-level writes currently need the CLI.
---

# wxcc-address-books — address books and their entries (read + write)

Call the `wxcc_*` MCP tools with `entity="address-book"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

Two-level entity: the **book**, and its **entries** (`{name, number}` pairs).

> **Coverage gap, stated plainly:** the MCP tools cover the **book**. Entries are a
> sub-resource (`address-book/{id}/entry`) and the entity registry has **no tool for them
> yet**. Create entries by embedding them at book creation (below); for entry-level
> add/update/delete on an existing book, fall back to the CLI recipes at the bottom — and
> know you lose the dry-run, the tenant stamp, and the re-read verification when you do.

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

## Entry-level writes — CLI fallback (no tool coverage yet)

Get entry ids from `wxcc_get(entity="address-book", id=...)`. These bypass the write
safety layer, so confirm with the user and re-read afterward **by hand**:

```bash
python wxcc.py post "organization/{orgId}/address-book/BOOK-ID/entry" --body '{"name":"Bob","number":"+15557654321"}'
python wxcc.py put "organization/{orgId}/address-book/BOOK-ID/entry/ENTRY-ID" --body '{"id":"ENTRY-ID","name":"Bob Renamed","number":"+15557654321"}'
python wxcc.py delete "organization/{orgId}/address-book/BOOK-ID/entry/ENTRY-ID"
```

⚠️ **The CLI uses whatever tenant `WXCC_PROFILE` resolves to in the shell — not the MCP
server you were just using.** Check `python wxcc.py auth status` before any entry write, or
set `WXCC_PROFILE` explicitly.

## Provenance and maintenance

Full two-level CRUD run live on a us1 sandbox 2026-07-11 via the CLI (book 201/204, entry
201/200/204, tenant returned to zero books). Book-level operations re-confirmed through the
MCP tools 2026-07-14. Body shapes from Cisco's Postman collection (v3, Aug 2023), each
confirmed live. **Follow-up:** add `address-book-entry` to the registry so entries get the
same dry-run/verify treatment as everything else.
