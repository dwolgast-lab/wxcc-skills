---
name: wxcc-entry-points
description: Use when asked about Webex Contact Center entry points or dial numbers (DNs/DIDs) - "what entry points exist", "find entry point X", "what number reaches entry point X", "which entry point does +1719... route to", "list our dial numbers/DIDs", "is entry point X active", "entry point X's channel". Read-only. Covers the entryPointId linkage and the raw-plus-sign silent-zero-results trap.
---

# wxcc-entry-points — entry points and their dial numbers (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

Entry points (EPs) and dial numbers (DNs) work together for inbound voice: each DN maps a
dialed E.164 number to an EP via its `entryPointId`.

## Use when / Do NOT use when

**Use when:**
- Listing/counting/finding entry points or dial numbers.
- Mapping a phone number to its entry point, or an entry point to its numbers.
- Inspecting an EP's channel type, entry point type, flow tag, timezone, or status.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- The queue a contact lands in after the EP → **wxcc-queues**.
- Creating/updating/deleting EPs or repointing DNs → **wxcc-entry-points-write**.
- The FLOW an entry point runs → Cisco's **flow-store** MCP server. This skill sees only
  the `flowTagId` reference, not the flow itself.

## Recipes — entry points

| Goal | Call |
|---|---|
| Every EP | `wxcc_list(entity="entry-point", attributes="id,name,channelType,active", all_pages=true)` |
| Count only | `wxcc_list(entity="entry-point", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="entry-point", filter="name==EP-NAME")` |
| Keyword search | `wxcc_list(entity="entry-point", search="KEYWORD")` |
| One EP, full object | `wxcc_get(entity="entry-point", id="EP-ID")` |

Fields observed live (2026-07-11): `name`, `active`, `channelType`, `entryPointType`,
`socialChannelType`, `flowTagId`, `maximumActiveContacts`, `timezone`, `description`,
`systemInternal`. Tenant-observed, not contract.

## Recipes — dial numbers

| Goal | Call |
|---|---|
| All DNs | `wxcc_list(entity="dial-number", attributes="id,dialledNumber,entryPointId", all_pages=true)` |
| Numbers reaching EP X | `wxcc_list(entity="dial-number", filter="entryPointId==EP-ID")` |
| **Which EP does a number route to** | `wxcc_list(entity="dial-number", filter="dialledNumberDigits==15551234567")` → resolve the returned `entryPointId` with `wxcc_get(entity="entry-point", ...)` |
| One DN | `wxcc_get(entity="dial-number", id="DN-ID")` |

**DN objects have no `name` field.** Key fields: `dialledNumber` (E.164 with `+`, note the
double-L), `dialledNumberDigits` (digits only), `entryPointId`, `defaultAni`, `location`,
`regionId`.

## Traps

| Trap | Result | Do this |
|---|---|---|
| `filter=dialledNumber==+1719...` (raw `+`) | **HTTP 200 with 0 records — a silent wrong answer.** The `+` decodes to a space. | Use `dialledNumberDigits==1719...`, or encode `%2B1719...` |
| `filter=name==...` on a dial-number | Meaningless — DNs have no name | Filter by `entryPointId`, `dialledNumber`, or `dialledNumberDigits` |
| Quoted filter values | HTTP 400 | Unquoted |
| Filterable fields | EP: `id`, `name`. DN: `entryPointId`, `dialledNumber`, `dialledNumberDigits` | Others are candidates |
| `search=` on dial-number | **Untested — candidate** | Confirmed on EP only |

The raw-`+` trap is the worst kind: it does not error, it answers "no numbers found" and
looks correct. If a number lookup comes back empty, retry with `dialledNumberDigits`
before telling the user the number is not mapped.

## Provenance and maintenance

Run against a live us1 tenant 2026-07-11 (118 EPs, 31 DNs); re-confirmed 2026-07-14.
Entity naming (`dial-number` path vs `dialledNumber` field) and the `+` trap reproduced
live. Path shape is handled by the tool's registry.
