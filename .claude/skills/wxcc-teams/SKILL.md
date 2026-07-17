---
name: wxcc-teams
description: Use when asked to list, count, look up, or inspect Webex Contact Center teams - "what teams exist", "find team X", "which site is team X at", "what skill profile or desktop layout does team X use", "is team X active", "show team X's queue rankings". Read-only. Covers the team entity's fields, filter/search syntax, and the traps that survive into the tool layer.
---

# wxcc-teams — list, search, and inspect WxCC teams (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.** See the
repo's CLAUDE.md for the nickname → server map.

Every result carries a `tenant` field naming the org it came from. Read it: that is the
ground truth, not the server's name.

## Use when / Do NOT use when

**Use when:**
- Listing or counting teams; finding a team by name, id, or keyword.
- Inspecting a team's site, skill profile, desktop layout, type, status, or queue rankings.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Resolving a team's site id to site details → **wxcc-sites**.
- Creating/renaming/updating/deleting teams → **wxcc-teams-write**.
- Assigning a USER to a team → **wxcc-users-write** (membership lives on the user's
  `teamIds`, not on the team).

## Recipes

| Goal | Call |
|---|---|
| Every team (id + name) | `wxcc_list(entity="team", attributes="id,name", all_pages=true)` |
| Count only | `wxcc_list(entity="team", page_size=1, attributes="id")` → read `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="team", filter="name==TEAM-NAME")` |
| Keyword search | `wxcc_list(entity="team", search="KEYWORD")` |
| One team, full object | `wxcc_get(entity="team", id="TEAM-ID")` |

Full team objects are sizeable — pass `attributes` to trim unless you need everything.

Fields observed live (2026-07-10): `name`, `active`, `teamType`, `teamStatus`, `siteId`,
`siteName`, `skillProfileId`, `desktopLayoutId`, `rankQueuesForTeam`, `queueRankings`,
`userIds`, `createdTime`, `lastUpdatedTime`. Tenant-observed, not contract.

`teamType` is `AGENT` or `CAPACITY`. A CAPACITY team models external/non-Webex agents and
has no desktop seats behind it — say so rather than treating it like an agent team.

## Traps

| Trap | Why | Do this |
|---|---|---|
| `filter=name=="X"` quoted, **via the CLI** | HTTP 400 — raw quotes die in transport | Via `wxcc_list` either quote style works; plain values need no quotes |
| Filter values containing spaces | Bare space is an RSQL syntax error | Quote the value: `filter="name=='Team Name Here'"` (verified live on a team 2026-07-17; pass raw characters — the tool encodes) |
| Filterable fields | Only `id` and `name` are confirmed | Others are candidates — verify before relying |

Path shape, the v2-on-item-path 404, and pagination are handled by the tool's entity
registry (`mcp_server.py`); you no longer pass paths by hand.

## Provenance and maintenance

Field list and filter syntax run against live us1 tenants (2026-07-10; re-confirmed on
three tenants 2026-07-14). Re-verify a row by running its call. The `wxcc.py` CLI still
works and takes raw paths — use it only to debug the server itself, not for routine work.
