---
name: wxcc-multimedia-profiles
description: Use when asked about Webex Contact Center multimedia profiles - "what multimedia profiles exist", "find multimedia profile X", "what does a site's multimediaProfileId point at", "which channels does profile X allow", "how many concurrent chats/emails does profile X permit", "is profile X the tenant default". Read-only. Resolves the multimediaProfileId carried by sites (and referenced when creating one).
---

# wxcc-multimedia-profiles — list, search, and inspect WxCC multimedia profiles (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools with `entity="multimedia-profile"` on the
server for the tenant the user named (`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was
named, ask — do not guess.**

A multimedia profile defines how many contacts of each channel an agent assigned to it can
handle at once, and its blending mode. It is what a **site's `multimediaProfileId`** points
at (`wxcc-sites` carries that id but not this detail), and the id you copy when creating a
new site.

## Use when / Do NOT use when

**Use when:**
- Listing or counting multimedia profiles; finding one by name, id, or keyword.
- Resolving a site's `multimediaProfileId` to the profile's name and channel caps.
- Reading a profile's per-channel concurrency limits, `blendingMode`, or whether it is the
  tenant default.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Working with the site that references a profile → **wxcc-sites**.
- **Creating, updating, or deleting a multimedia profile** → not supported. Writes have
  never been probed against a live tenant, so the registry does not claim them —
  `wxcc_create`/`wxcc_update`/`wxcc_delete` refuse `multimedia-profile`. Do not improvise
  via the CLI.

## Recipes

| Goal | Call |
|---|---|
| Every profile (id + name) | `wxcc_list(entity="multimedia-profile", attributes="id,name", all_pages=true)` |
| Count only | `wxcc_list(entity="multimedia-profile", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="multimedia-profile", filter="name==PROFILE-NAME")` |
| Keyword search | `wxcc_list(entity="multimedia-profile", search="KEYWORD")` |
| One profile, full object | `wxcc_get(entity="multimedia-profile", id="PROFILE-ID")` |
| The tenant default | List all, pick the one with `systemDefault: true` |

## Fields

Observed live (2026-07-17). Tenant-observed, not contract.

| Field | Meaning |
|---|---|
| `id`, `name`, `description` | Identity |
| `telephony`, `chat`, `email`, `social`, `video`, `fax`, `others`, `workItem` | **Concurrent-contact cap per channel** — an integer, not a boolean. `telephony: 1` = one voice call at a time; `chat: 5` = up to five simultaneous chats |
| `blendingModeEnabled`, `blendingMode` | Whether an agent can mix channels (e.g. `BLENDED`) |
| `active` | Profile is usable |
| `systemDefault` | `true` on the tenant's built-in default profile |
| `manuallyAssignable` | Nested object of per-channel flags — **survives an `attributes` projection**, so it appears even when you asked only for `id,name` |
| `createdTime`, `lastUpdatedTime` | Epoch millis |

## Traps

| Trap | Why | Do this |
|---|---|---|
| Reading a channel integer as on/off | They are **counts**, not booleans — `telephony: 1` means one concurrent call, not "telephony enabled" | Report the number |
| `filter=name=="X"` quoted, **via the CLI** | HTTP 400 — raw quotes die in transport | Via `wxcc_list` either quote style works; plain values need no quotes |
| Filter values with spaces | Bare space is an RSQL syntax error | Quote the value: `filter="name=='Some Profile'"` (the tool encodes; pass raw characters) |
| Filterable fields | Only `name` confirmed | Others are candidates |
| Expecting writes | The tools refuse — writes are unproven for this entity | Read-only; do not route to the CLI to force one |

## Provenance and maintenance

Read paths verified live on a us1 sandbox 2026-07-17: list `v2/multimedia-profile`, item
`multimedia-profile/{id}` (the item path **drops v2** — `v2/.../{id}` 404s, same convention
as teams/sites/users), `filter=name==` confirmed. Path shape and the v2 rule are pinned in
the tool's entity registry (`mcp_server.py`); you do not pass paths by hand. Writes deliberately
unprobed — a multimedia profile is referenced by sites, so a bad write would hit every agent
at those sites.
