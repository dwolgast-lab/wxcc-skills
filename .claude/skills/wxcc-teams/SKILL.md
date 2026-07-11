---
name: wxcc-teams
description: Use when asked to list, count, look up, or inspect Webex Contact Center teams - "what teams exist", "find team X", "which site is team X at", "what skill profile or desktop layout does team X use", "is team X active", "show team X's queue rankings". Read-only. Provides the confirmed Teams API paths, filter/search/attributes syntax, and the v2-on-item-path 404 trap.
---

# wxcc-teams — list, search, and inspect WxCC teams (read-only)

Uses the shared helper `wxcc.py` (repo root); requires a working connection
(**wxcc-connect**). Every path and parameter below was run against a live tenant
(245 teams) on 2026-07-10.

## Use when / Do NOT use when

**Use when:**
- Listing or counting teams; finding a team by name, id, or keyword.
- Inspecting a team's site, skill profile, desktop layout, type, status, or queue rankings.

**Do NOT use when:**
- Auth errors (401 / "not authenticated") → **wxcc-connect**.
- Resolving a team's site id to site details → **wxcc-sites**.
- Creating/renaming/deactivating teams → no write skill exists yet; needs `cjp:config`
  scope (wxcc-connect "Adding write access"). Do not improvise writes.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (see wxcc-connect).
- List responses paginate (`meta` + `data[]`, pageSize default 100); `get --all` combines
  all pages. Trim with `attributes=` — full team objects are sizeable.

## Recipes

### List every team (id + name)

```bash
python wxcc.py get --all "organization/{orgId}/v2/team?attributes=id,name"
```

### Count teams without transferring them

```bash
python wxcc.py get "organization/{orgId}/v2/team?pageSize=1&attributes=id"
```
→ read `meta.totalRecords`.

### Find a team by exact name

```bash
python wxcc.py get "organization/{orgId}/v2/team?filter=name==TEAM-NAME&attributes=id,name,siteName,active"
```
→ `meta.totalRecords` should be 1. **Unquoted** value; quotes cause HTTP 400.
Names containing spaces are untested as filter values — candidate: URL-encode as `%20`.

### Keyword search

```bash
python wxcc.py get "organization/{orgId}/v2/team?search=KEYWORD&attributes=id,name"
```

### Get one team by id (full object)

```bash
python wxcc.py get "organization/{orgId}/team/TEAM-ID-HERE"
```
→ fields observed live 2026-07-10: `name`, `active`, `teamType`, `teamStatus`, `siteId`,
`siteName`, `skillProfileId`, `desktopLayoutId`, `rankQueuesForTeam`, `queueRankings`,
`createdTime`, `lastUpdatedTime`. Tenant-observed, not contract.

## Traps (reproduced live, 2026-07-10)

| Wrong | Result | Right |
|---|---|---|
| `organization/{orgId}/v2/team/TEAM-ID` | HTTP 404 | Item path has **no v2**: `organization/{orgId}/team/TEAM-ID` |
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted: `filter=name==X` |
| Non-v2 list `organization/{orgId}/team` | 200 but a **bare unpaginated array** (legacy) | Prefer the `v2` list for `meta`/paging/filtering |

## Provenance and maintenance

All claims run against a live us1 tenant on 2026-07-10 via `wxcc.py`. Re-verify any row by
running its recipe. Filterable fields confirmed: `id`, `name`; others are candidates.
Sibling facts (OAuth, pagination shape, leading-slash rule) live in **wxcc-connect**.
