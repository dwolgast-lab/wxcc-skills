---
name: wxcc-address-books
description: Use when asked about Webex Contact Center address books or their entries (speed-dial directories agents see) - "list address books", "create an address book", "add/update/remove an entry in address book X", "what numbers are in address book X", "delete address book X". Covers reads and verified create/update/delete for both books and entries. Writes require cjp:config_write and explicit confirmation.
---

# wxcc-address-books — address books and their entries (read + write)

Two-level entity: the **address book** (`address-book`) and its **entries**
(`address-book/{id}/entry`), each entry a `{name, number}` pair. Full CRUD on both levels
verified live on a sandbox tenant 2026-07-11.

## Use when / Do NOT use when

**Use when:** listing/creating/updating/deleting address books or the entries in them.

**Do NOT use when:**
- Auth errors → **wxcc-connect**. Writes without `cjp:config_write` → 403.
- Which address book a Desktop Profile exposes → **wxcc-desktop-profiles**.
- Dial numbers that route INTO the tenant → **wxcc-entry-points** (different thing).

## Reads

```bash
python wxcc.py get --all "organization/{orgId}/v2/address-book?attributes=id,name"
python wxcc.py get "organization/{orgId}/address-book/BOOK-ID"          # book + embedded entries
python wxcc.py get "organization/{orgId}/v2/address-book/BOOK-ID/entry" # paginated entry list
```

The v2 entry list supports the standard `page`/`pageSize` (and per Cisco's collection,
`search` and `sort=name,ASC` — candidates, untested here).

## Writes — safety rules of **wxcc-teams-write** apply (confirm first, name rollback, verify after)

### Create a book (entries can be embedded at creation)

```bash
python wxcc.py post "organization/{orgId}/address-book" --body '{"name":"BOOK-NAME","parentType":"ORGANIZATION","description":"...","addressBookEntries":[{"name":"Alice","number":"+15551234567"}]}'
```

→ verify: 201 with the book `id`. `parentType: SITE` + `siteId` exists per Cisco's
collection (candidate, untested). Rollback = DELETE the book.

### Add / update / delete an entry

```bash
python wxcc.py post "organization/{orgId}/address-book/BOOK-ID/entry" --body '{"name":"Bob","number":"+15557654321"}'
python wxcc.py put "organization/{orgId}/address-book/BOOK-ID/entry/ENTRY-ID" --body '{"id":"ENTRY-ID","name":"Bob Renamed","number":"+15557654321"}'
python wxcc.py delete "organization/{orgId}/address-book/BOOK-ID/entry/ENTRY-ID"
```

→ each verified live (201/200/204). Get entry ids from the v2 entry list. Entry update
rollback = PUT the prior values back.

### Delete a book

```bash
python wxcc.py delete "organization/{orgId}/address-book/BOOK-ID"
```

→ verify: 204; the v2 book list count drops. Deletes the entries with it — no rollback.

## Provenance and maintenance

Full two-level CRUD run live on a us1 sandbox 2026-07-11 via `wxcc.py` (book 201/204,
entry 201/200/204, tenant returned to zero books). Body shapes from Cisco's Postman
collection (v3, Aug 2023), each confirmed live. Re-verify with a `zz-` named cycle.
