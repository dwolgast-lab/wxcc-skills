---
name: wxcc-users
description: Use when asked to list, count, look up, search, or inspect Webex Contact Center users or agents - "who is in the tenant", "find the user with email X", "how many agents", "is user X active", "show user X's profile/team assignments". Read-only. Provides the confirmed Users API paths, filter/search/attributes query syntax, pagination via the helper's --all flag, and the known 400/404 traps.
---

# wxcc-users — list, search, and inspect WxCC users (read-only)

All commands use the shared helper `wxcc.py` at the repo root and require a working
connection (see **wxcc-connect**). Every path, parameter, and trap below was run against a
live tenant on 2026-07-10.

## Use when / Do NOT use when

**Use when:**
- Listing or counting the tenant's users/agents.
- Finding a user by email, id, or a name/keyword search.
- Inspecting one user's attributes (active, contactCenterEnabled, profile/team ids).

**Do NOT use when:**
- Not yet authenticated, or calls return 401 / "not authenticated" → **wxcc-connect**.
- Updating a user's CC config (teams, profiles, enablement) → **wxcc-users-write**.
- Creating/deleting users or changing names/emails → Control Hub, not this API.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (Git Bash mangles leading `/` —
  see wxcc-connect).
- List responses are paginated: `meta` (page, pageSize [default 100], totalPages,
  totalRecords, links.next/prev/self/first/last) + `data[]`. `get --all` follows
  `meta.links.next` and emits one combined `{totalRecords, pagesFetched, data[]}`.
- Trim payloads with `attributes=` whenever you don't need full objects — full user
  objects are large and list calls default to 100 per page.

## Recipes

### List every user (id + email only)

```bash
python wxcc.py get --all "organization/{orgId}/v2/user?attributes=id,email"
```
→ verify: `totalRecords` equals the tenant's user count.

### Count users / page manually

```bash
python wxcc.py get "organization/{orgId}/v2/user?pageSize=1&attributes=id"
```
→ `meta.totalRecords` is the count without transferring the records. Page manually with
`?page=N&pageSize=M` when you only need a slice.

### Find a user by email (exact match)

```bash
python wxcc.py get "organization/{orgId}/v2/user?filter=email==alice@example.com&attributes=id,email,active"
```
→ verify: `meta.totalRecords` is 1. **Do not quote the filter value** — quotes cause
HTTP 400 (see traps).

### Find users by keyword (name search)

```bash
python wxcc.py get "organization/{orgId}/v2/user?search=alice&attributes=id,email"
```
→ substring search across users; returned `meta.totalRecords` tells you how many matched.

### Get one user by id (full object)

```bash
python wxcc.py get "organization/{orgId}/user/USER-ID-HERE"
```
→ full user object: `firstName`, `lastName`, `email`, `active`, `contactCenterEnabled`,
`ciUserId`, `userProfileId`, and `links[]` to related objects (organization, user_profile).
Fields as observed live 2026-07-10; treat exact field lists as tenant-observed, not contract.

An equivalent list-shaped alternative: `?filter=id==USER-ID-HERE` on the v2 list path.

## Traps (each reproduced live, 2026-07-10)

| Wrong | Result | Right |
|---|---|---|
| `organization/{orgId}/v2/user/USER-ID` | HTTP 404 | Get-by-id has **no `v2`**: `organization/{orgId}/user/USER-ID`. The list path has `v2`; the item path does not. |
| `filter=email=="alice@example.com"` | HTTP 400 (HTML error page) | Unquoted: `filter=email==alice@example.com` |
| `"/organization/..."` leading slash in Git Bash | `bad URL ... C:/Program Files/Git/...` | Drop the leading slash. |
| `get --all` on a get-by-id path | clean error: "--all requires a paginated list response" | Use `--all` only on list endpoints. |

## Provenance and maintenance

All claims verified 2026-07-10 by running them against a live us1 tenant (164 users) via
`wxcc.py`; filter/attributes syntax corroborated by developer.webex.com search results the
same day. Volatile items:

- List path `organization/{orgId}/v2/user`; item path `organization/{orgId}/user/{id}`
  (no v2, 404 if included) — re-verify: run the "Get one user by id" recipe.
- Query params `page`, `pageSize` (default 100), `attributes`, `filter` (FIQL `==`,
  unquoted values), `search` (substring) — re-verify: run the recipes above.
- Combined-output shape of `get --all` (`totalRecords`/`pagesFetched`/`data`) is a
  **helper construct** (wxcc.py), not an API shape — re-verify: `python wxcc.py get --help`.
- Filterable fields confirmed: `id`, `email`. Other fields untested as filter targets —
  treat additional `filter=` fields as **candidates** until run.
