---
name: wxcc-sites
description: Use when asked to list, count, look up, or inspect Webex Contact Center sites - "what sites exist", "find site X", "is site X active", "site X's multimedia profile", or resolving a siteId found on a team to its details. Read-only - site writes are not supported by these tools.
---

# wxcc-sites — list, search, and inspect WxCC sites (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

## Use when / Do NOT use when

**Use when:**
- Listing or counting sites; finding a site by name, id, or keyword.
- Resolving a `siteId` (e.g. from a team or user object) to the site's details.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Working with the teams at a site → **wxcc-teams** (filter by `siteId`).
- **Creating or modifying sites** → not supported. `wxcc_create`/`wxcc_update`/`wxcc_delete`
  will refuse `site`: writes have never been probed against a live tenant, so the registry
  does not claim them. Do not improvise via the CLI.

## Recipes

| Goal | Call |
|---|---|
| Every site (id + name) | `wxcc_list(entity="site", attributes="id,name", all_pages=true)` |
| Count only | `wxcc_list(entity="site", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="site", filter="name==SITE-NAME")` |
| Keyword search | `wxcc_list(entity="site", search="KEYWORD")` |
| One site, full object | `wxcc_get(entity="site", id="SITE-ID")` |

Site objects are small — `attributes` is optional here.

Fields observed live (2026-07-10): `id`, `name`, `active`, `multimediaProfileId`,
`createdTime`, `lastUpdatedTime`. Tenant-observed, not contract.

## Traps

| Trap | Why | Do this |
|---|---|---|
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted: `filter=name==X` |
| Filter values with spaces | Untested | Candidate: `%20`. Prefer `search=`. |
| Filterable fields | Only `id`, `name` confirmed | Others are candidates |

## Provenance and maintenance

Run against live us1 tenants (2026-07-10; re-confirmed 2026-07-14). Site writes remain
unprobed — that is why the tools refuse them, and it is a deliberate gap, not an oversight.
