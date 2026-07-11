---
name: wxcc-sites
description: Use when asked to list, count, look up, or inspect Webex Contact Center sites - "what sites exist", "find site X", "is site X active", "site X's multimedia profile", or resolving a siteId found on a team to its details. Read-only. Provides the confirmed Sites API paths, filter/search/attributes syntax, and the v2-on-item-path 404 trap.
---

# wxcc-sites — list, search, and inspect WxCC sites (read-only)

Uses the shared helper `wxcc.py` (repo root); requires a working connection
(**wxcc-connect**). Every path and parameter below was run against a live tenant
(68 sites) on 2026-07-10.

## Use when / Do NOT use when

**Use when:**
- Listing or counting sites; finding a site by name, id, or keyword.
- Resolving a `siteId` (e.g. from a team object) to the site's details.

**Do NOT use when:**
- Auth errors (401 / "not authenticated") → **wxcc-connect**.
- Working with the teams at a site → **wxcc-teams** (filter teams client-side by `siteId`).
- Creating or modifying sites → no write skill exists yet; needs `cjp:config` scope
  (wxcc-connect "Adding write access"). Do not improvise writes.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (see wxcc-connect).
- List responses paginate (`meta` + `data[]`, pageSize default 100); `get --all` combines
  all pages. Site objects are small — trimming with `attributes=` is optional here.

## Recipes

### List every site (id + name)

```bash
python wxcc.py get --all "organization/{orgId}/v2/site?attributes=id,name"
```

### Count sites

```bash
python wxcc.py get "organization/{orgId}/v2/site?pageSize=1&attributes=id"
```
→ read `meta.totalRecords`.

### Find a site by exact name

```bash
python wxcc.py get "organization/{orgId}/v2/site?filter=name==SITE-NAME&attributes=id,name,active"
```
→ **unquoted** value; quotes cause HTTP 400. Names with spaces untested — candidate:
URL-encode as `%20`.

### Keyword search

```bash
python wxcc.py get "organization/{orgId}/v2/site?search=KEYWORD&attributes=id,name"
```

### Get one site by id (full object)

```bash
python wxcc.py get "organization/{orgId}/site/SITE-ID-HERE"
```
→ fields observed live 2026-07-10: `id`, `name`, `active`, `multimediaProfileId`,
`createdTime`, `lastUpdatedTime`. Tenant-observed, not contract.

## Traps (reproduced live, 2026-07-10)

| Wrong | Result | Right |
|---|---|---|
| `organization/{orgId}/v2/site/SITE-ID` | HTTP 404 | Item path has **no v2**: `organization/{orgId}/site/SITE-ID` |
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted: `filter=name==X` |
| Non-v2 list `organization/{orgId}/site` | 200 but a **bare unpaginated array** (legacy) | Prefer the `v2` list for `meta`/paging/filtering |

## Provenance and maintenance

All claims run against a live us1 tenant on 2026-07-10 via `wxcc.py`. Re-verify any row by
running its recipe. Filterable fields confirmed: `id`, `name`; others are candidates.
Sibling facts (OAuth, pagination shape, leading-slash rule) live in **wxcc-connect**.
