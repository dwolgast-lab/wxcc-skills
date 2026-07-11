---
name: wxcc-entry-points
description: Use when asked about Webex Contact Center entry points or dial numbers (DNs/DIDs) - "what entry points exist", "find entry point X", "what number reaches entry point X", "which entry point does +1719... route to", "list our dial numbers/DIDs", "is entry point X active", "entry point X's channel or flow". Read-only. Provides confirmed paths for both entities, the entryPointId linkage between them, and the raw-plus-sign silent-zero-results trap.
---

# wxcc-entry-points — entry points and their dial numbers (read-only)

Entry points (EPs) and dial numbers (DNs) work hand-in-hand for inbound voice: each DN maps
a dialed E.164 number to an EP via its `entryPointId`. This skill covers both entities and
the lookups between them. Uses the shared helper `wxcc.py` (repo root); requires a working
connection (**wxcc-connect**). Every path and parameter was run against a live tenant
(118 EPs, 31 DNs) on 2026-07-11.

## Use when / Do NOT use when

**Use when:**
- Listing/counting/finding entry points or dial numbers.
- Mapping a phone number to its entry point, or an entry point to its numbers.
- Inspecting an EP's channel type, entry point type, flow tag, timezone, or status.

**Do NOT use when:**
- Auth errors (401 / "not authenticated") → **wxcc-connect**.
- The queue a contact lands in after the EP/flow → **wxcc-queues**.
- Creating or repointing EPs/DNs → no write skill exists yet; needs `cjp:config` scope
  (wxcc-connect "Adding write access"). Do not improvise writes.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (see wxcc-connect).
- Lists paginate (`meta` + `data[]`); `get --all` combines pages; trim with `attributes=`.
- DN objects have **no `name` field**. Their key fields: `dialledNumber` (E.164 with `+`,
  note the double-L spelling), `dialledNumberDigits` (digits only), `entryPointId`,
  `defaultAni`, `location`, `regionId`.

## Recipes — entry points

### List / count / find

```bash
python wxcc.py get --all "organization/{orgId}/v2/entry-point?attributes=id,name,channelType,active"
python wxcc.py get "organization/{orgId}/v2/entry-point?pageSize=1&attributes=id"   # meta.totalRecords = count
python wxcc.py get "organization/{orgId}/v2/entry-point?filter=name==EP-NAME&attributes=id,name"
python wxcc.py get "organization/{orgId}/v2/entry-point?search=KEYWORD&attributes=id,name"
```
Filter values are **unquoted** (quotes → HTTP 400).

### Get one entry point by id (full object)

```bash
python wxcc.py get "organization/{orgId}/entry-point/EP-ID-HERE"
```
→ fields observed live 2026-07-11: `name`, `active`, `channelType`, `entryPointType`,
`socialChannelType`, `flowTagId`, `maximumActiveContacts`, `timezone`, `description`,
`systemInternal`. Tenant-observed, not contract. Item path has **no v2** (v2 → 404).

## Recipes — dial numbers

### List all dial numbers

```bash
python wxcc.py get --all "organization/{orgId}/v2/dial-number?attributes=id,dialledNumber,entryPointId"
```

### Which numbers reach entry point X?

```bash
python wxcc.py get "organization/{orgId}/v2/dial-number?filter=entryPointId==EP-ID-HERE"
```

### Which entry point does a number route to?

Prefer the digits-only field — no URL-encoding pitfalls:

```bash
python wxcc.py get "organization/{orgId}/v2/dial-number?filter=dialledNumberDigits==15551234567"
```

then resolve the returned `entryPointId` with the get-one-EP recipe. Filtering on
`dialledNumber` requires encoding the plus as `%2B` (`filter=dialledNumber==%2B15551234567`).

### Get one dial number by id

```bash
python wxcc.py get "organization/{orgId}/dial-number/DN-ID-HERE"
```

## Traps (each reproduced live, 2026-07-11)

| Wrong | Result | Right |
|---|---|---|
| `filter=dialledNumber==+1719...` (raw `+`) | **HTTP 200 with 0 records — silent wrong answer** (`+` decodes to a space) | Use `dialledNumberDigits==1719...`, or encode `%2B1719...` |
| `v2/entry-point/{id}` or `v2/dial-number/{id}` | HTTP 404 | Item paths have no v2 |
| `v2/dialed-number` (single-L spelling) | HTTP 404 | Entity is `dial-number`; fields spell it `dialledNumber` |
| `filter=name==...` quoted | HTTP 400 | Unquoted values |
| `filter=name==...` on dial-number | n/a — DNs have no `name` field | Filter DNs by `entryPointId`, `dialledNumber`, or `dialledNumberDigits` |

## Provenance and maintenance

All claims run against a live us1 tenant on 2026-07-11 via `wxcc.py`; re-verify any row by
running its recipe. Filterable fields confirmed — EP: `id`, `name`; DN: `entryPointId`,
`dialledNumber`, `dialledNumberDigits`. `search=` confirmed on EP; **untested on DN**
(candidate). Sibling facts (OAuth, pagination, leading-slash rule) live in **wxcc-connect**.
