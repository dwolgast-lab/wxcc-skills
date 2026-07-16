---
name: wxcc-users-write
description: Use when asked to update a Webex Contact Center user's CC configuration - "move agent X to team Y", "add agent X to a team", "change user X's desktop/multimedia/user profile", "enable/disable contact center for user X", "change user X's site". Update-only - users are created in Control Hub, not this API, and identity fields (name, email) are immutable here. Requires cjp:config_write and explicit confirmation.
---

# wxcc-users-write — update a user's contact-center configuration

Mutating counterpart to **wxcc-users**. Call `wxcc_update(entity="user", ...)` on the server
for the tenant the user named. **If no tenant was named, ask — do not guess.**

**Update-only by design.** This API cannot create or delete users — provisioning lives in
Control Hub / Common Identity — and identity fields are read-only mirrors here. The tool's
registry refuses `wxcc_create`/`wxcc_delete` on `user` for that reason. What it CAN change:
team assignments, site, desktop/multimedia/user profiles, `contactCenterEnabled`.

## Use when / Do NOT use when

**Use when:** moving or adding an agent to a team, changing profiles, toggling CC enablement.

**Do NOT use when:**
- Finding/inspecting users → **wxcc-users**.
- Creating or deleting users, changing names/emails/passwords → **Control Hub**, not here.
- Auth errors or 403 on write → **wxcc-connect**.
- Creating the team you are assigning to → **wxcc-teams-write**.
- **Never experiment on the org's admin account.**

## Team membership lives HERE, not on the team

This is the skill for "add X to team Y" — membership is the user's `teamIds`. The team
object's `userIds` is read-only. A user can hold **several teams at once** (confirmed live
2026-07-14).

```
wxcc_update(entity="user", id="USER-ID",
            changes={"teamIds": ["EXISTING-TEAM-ID", "NEW-TEAM-ID"]})
```

Send the **whole** list — this replaces, it does not append. Get the current value from
**wxcc-users** first; the dry run shows it under `diff.from`, which is your rollback.

Validation, both reproduced live: the target team must be on the **same site** as the user
(`400 not found for given site`) and must be **`teamType: AGENT`**
(`400 Capacity based teams are not allowed`).

## Field writability map (each probed live 2026-07-11)

| Field | Writable? | Evidence |
|---|---|---|
| `teamIds` | YES, validated | 200 on valid change; 400s named above |
| `firstName` / `lastName` / `email` | **NO** | 400 `This configuration cannot be changed` — identity-owned |
| `userLevelSummariesInclusion` | **Silently ignored** | HTTP 200 but unchanged — likely entitlement-gated |
| `siteId`, `agentProfileId`, `multimediaProfileId`, `userProfileId`, `contactCenterEnabled` | Accepted in a no-op PUT | Individual changes untested — **candidates** |

## The trap this API taught us

**200 ≠ changed.** A PUT can return 200 while silently dropping a field. This is why
`wxcc_update` re-reads after every confirmed write and returns **`SILENTLY_IGNORED`**. If
that field is non-null, **the write did not fully apply — say so; do not report success.**
`userLevelSummariesInclusion` is the known case, but treat any candidate field the same way.

Also: the API **reorders** `teamIds` (sent `[old, new]`, got `[new, old]`). Never depend on
order.

## Provenance and maintenance

All rows probed 2026-07-11 on a live us1 sandbox against a disposable test user, every
mutation reverted and verified identical to the captured original. Multi-team membership and
the reorder confirmed 2026-07-14 through the MCP tools. Re-verify a candidate row with a
change → re-read → revert cycle on a test user.
