---
name: wxcc-contact-numbers
description: Use when asked about Webex Contact Center contact numbers - the short caller-ID value shown on INTERNAL calls - "list our contact numbers", "add a contact number", "change/delete contact number X". NOT the DID/dial-number inventory and not outdial ANI. Full CRUD, but its reference scan is broken API-side so deletes cannot be pre-checked.
---

# wxcc-contact-numbers — the internal caller-ID value

Call `wxcc_list` / `wxcc_get` / `wxcc_create` / `wxcc_update` / `wxcc_delete` with
`entity="contact-number"` on the server for the tenant the user named. **If no tenant was
named, ask — do not guess.**

## What this is — and what it is not

A contact number is the caller-ID value shown on **internal** calls (per the tenant admin;
stated, **not** API-verified). **Despite the name it is not a phone-number inventory.**

| If the user means… | Use |
|---|---|
| A real DID/DN that routes calls in | **wxcc-entry-points** / **wxcc-entry-points-write** (`dial-number`) |
| The number agents present on **outbound** calls | **wxcc-outdial-ani** |
| A speed-dial directory entry | **wxcc-address-books** |
| The short internal caller-ID value | here |

Nothing links `contact-number` to `dial-number` — they are unrelated entities that happen
to both contain digits. Say so if the user conflates them.

## The 9-character cap

`number` is the **only** required field and is capped at **9 characters**. An E.164 value
fails:

```
wxcc_create(entity="contact-number", fields={"number": "+13125550143"})
  -> 400 "should not be more than 9 characters"
```

So this cannot hold a full North American number in E.164. Use the short internal form.

## Read

```
wxcc_list(entity="contact-number")
wxcc_get(entity="contact-number", id="<id>")
```

Records carry only `id`, `number`, `createdTime`, `lastUpdatedTime` — **there is no `name`
and no `description` field**, so the usual "mark it in the description" convention does not
apply to this entity.

**Do not use `contact-number/all-numbers` as the list path.** It is a real route, but it
returns a **bare list of strings** (`["5551234"]`) rather than objects — a convenience
projection with no ids, so nothing can be updated or deleted from it. `v2/contact-number`
is the list path. (This is the endpoint the portal calls *"List all contact numbers
(property - number)"*.)

## Writes

Dry-run first as always: call without `confirm`, show the preview, get an explicit yes,
re-call with `confirm=true`.

```
wxcc_create(entity="contact-number", fields={"number": "5550199"}, confirm=True)
wxcc_update(entity="contact-number", id="<id>", changes={"number": "5550200"}, confirm=True)
wxcc_delete(entity="contact-number", id="<id>", confirm=True)
```

`PUT` requires the `id` **in the payload** matching the URL (400 `"Invalid id: id in payload
and URL should be same"`). `wxcc_update` read-modify-writes, so it already sends it.

Bulk is **create + delete** on `contact-number/bulk`; there is no bulk update (id-wall 400,
`PATCH` 405). Bulk-export is out of scope for these tools.

## The reference scan does not work — deletes are unchecked

`contact-number/{id}/incoming-references` answers **400 "specify a valid external entity
type"** for a valid id, a bogus id, and every `?type=` value tried. This is an API defect,
not a configuration problem, and it has two consequences:

- **`wxcc_references` cannot answer for this entity.** It returns `SCAN_IMPOSSIBLE` with
  `total: null` — deliberately **not** an empty list, because "nobody can tell you" must
  never render as "nothing references it."
- **`wxcc_delete` does not pre-flight it.** The delete proceeds and the result carries
  `REFERENCES_NOT_CHECKED`. **Relay that to the user before they approve** — the only
  remaining guard is the API's own 412-on-referenced-delete, which is confirmed for other
  entities but **unconfirmed for this one**.

Until 2026-07-22 the failed scan was counted as a conflicting reference, so `wxcc_delete`
reported *"1 object(s) still reference this"* and could never succeed. If you see that
symptom on another entity, it is the same bug class — report it rather than working around
it with raw API calls.

## Traps

| Trap | What actually happens |
|---|---|
| Treating it as the DID inventory | It is not, and nothing links the two. Route to `dial-number`. |
| E.164 value | 400 — 9 characters max. |
| `contact-number/all-numbers` | Bare strings, no ids. Never the list path. |
| Expecting `name`/`description` | Neither exists on this entity. |
| `PUT` without `id` in the body | 400 naming the mismatch. |
| Trusting a clean reference result | There is no clean result — the scan cannot run at all. |
| Import/export | `contact-number/import|export` exist on **PUT** (GET 404s); payload shape is **UNPROBED** and not exposed. |

Reads, the reference-scan defect, and a full create → dry-run → delete round trip through
the tools were verified live on the sandbox 2026-07-22 (baseline 1 record, restored). The
9-character cap and the `PUT`-id rule were verified 2026-07-21.
