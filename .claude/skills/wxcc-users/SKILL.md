---
name: wxcc-users
description: Use when asked to list, count, look up, search, or inspect Webex Contact Center users or agents - "who is in the tenant", "find the user with email X", "how many agents", "is user X active", "show user X's profile/team assignments", "who is on team X". Read-only.
---

# wxcc-users — list, search, and inspect WxCC users (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

## Use when / Do NOT use when

**Use when:**
- Listing or counting the tenant's users/agents.
- Finding a user by email, id, or a name/keyword search.
- Inspecting one user's attributes (active, contactCenterEnabled, profile/team ids).

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Updating a user's CC config (teams, profiles, enablement) → **wxcc-users-write**.
- Creating/deleting users or changing names/emails → **Control Hub**, not this API.

## Recipes

| Goal | Call |
|---|---|
| Every user (id + email) | `wxcc_list(entity="user", attributes="id,email", all_pages=true)` |
| Count only | `wxcc_list(entity="user", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by email (exact) | `wxcc_list(entity="user", filter="email==alice@example.com")` |
| Keyword / name search | `wxcc_list(entity="user", search="alice")` |
| One user, full object | `wxcc_get(entity="user", id="USER-ID")` |

**User objects are large and lists default to 100/page — pass `attributes`** unless you need
everything. `all_pages=true` follows pagination and returns a combined result.

Fields observed live (2026-07-10): `firstName`, `lastName`, `email`, `active`,
`contactCenterEnabled`, `ciUserId`, `siteId`, `teamIds`, `agentProfileId`,
`multimediaProfileId`, `userProfileId`, `userLevelSummariesInclusion`. Tenant-observed,
not contract.

## Lookups `wxcc_list` cannot express — `wxcc_find_users`

Seven purpose-built routes, all read-only, all verified live 2026-07-22. Call
`wxcc_find_users(by="")` to have the tool list them.

| Goal | Call |
|---|---|
| Every user **joined to its user profile**, one call | `wxcc_find_users(by="with_profile")` |
| One user joined to its profile | `wxcc_find_users(by="with_profile_by_id", value="USER-ID")` |
| CC user from a **Control Hub (CI) id** | `wxcc_find_users(by="ci_user_id", value="CI-USER-ID")` |
| Who carries a **dynamic skill** | `wxcc_find_users(by="dynamic_skill", value="SKILL-ID")` |
| Details for many users at once | `wxcc_find_users(by="ids", values=["id1","id2"])` |
| Agents matching skill criteria | `wxcc_find_users(by="skill_requirements", values=[{"skillId":"..."}])` |
| By call-monitoring id | `wxcc_find_users(by="call_monitoring_id", value="...")` |

Two things to watch:

- **`with_profile` returns a BARE LIST** — no `meta`, no `totalRecords`, no pagination. The
  tool sets `UNPAGINATED` on the result. There is no way to tell whether the server
  truncated it, so for a large tenant prefer `wxcc_list` + `wxcc_get` when completeness
  matters.
- **`ci_user_id` wants the `ciUserId` field, not the CC `id`.** They are different values on
  the same record, and passing the wrong one returns a confusing 404.
- **Dynamic skills are invisible on the user record.** `dynamic_skill` is the only way to
  see them — a user's assignments will not appear in `wxcc_get`.

### "Who is on team X?"

There is no server-side filter for this. Two routes:

- `wxcc_get(entity="team", id=...)` returns a read-only `userIds` list (**wxcc-teams**).
- Or list users with `attributes="id,firstName,lastName,teamIds"` and match `teamIds`
  client-side. A user can be on **several teams at once**.

## Traps

| Trap | Why | Do this |
|---|---|---|
| `filter=email=="x@y.com"` (quoted) | HTTP 400 | Unquoted: `filter=email==x@y.com` |
| Filterable fields | Only `id` and `email` confirmed | Anything else is a candidate — verify first |
| Duplicate-ish names | Tenants really do contain e.g. "Dave WWW" and "Dave WWWW WWWWW" | When a name search returns near-duplicates, show the user the emails and ask which — do not pick |

## Provenance and maintenance

Run against live us1 tenants (2026-07-10, 164 users; re-confirmed 2026-07-14). Filter and
search syntax verified live. Path shape and pagination are handled by the tool's registry.
