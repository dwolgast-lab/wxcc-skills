---
name: wxcc-desktop-profiles
description: Use when asked about Webex Contact Center Desktop Profiles (historically "Agent Profiles" - the API path is still agent-profile) - "list desktop profiles", "what does desktop profile X allow", "which wrap-up/idle codes or queues does profile X expose", "change profile X's auto-wrap or outdial settings", "what ANI does profile X use". Covers reads and the verified update shape; create/delete are labeled candidates.
---

# wxcc-desktop-profiles — agent desktop behavior profiles (read + update)

Call the `wxcc_*` MCP tools with `entity="agent-profile"` on the server for the tenant the
user named. **If no tenant was named, ask — do not guess.**

**Terminology: these are Desktop Profiles.** The API entity is still named `agent-profile`
purely for backwards compatibility — use "Desktop Profile" in every user-facing sentence,
and `agent-profile` in every tool call.

A Desktop Profile governs an agent's desktop experience: auto-answer/auto-wrap, which
idle/wrap-up codes, queues, entry points, and buddy teams are visible, outdial permission
and ANI, screen-pop, and timeouts. Users reference one via `agentProfileId`
(**wxcc-users**).

## Use when / Do NOT use when

**Use when:** listing/inspecting Desktop Profiles or updating one's settings.

**Do NOT use when:**
- Auth errors or 403 on write → **wxcc-connect**.
- Assigning a profile TO a user → **wxcc-users-write** (`agentProfileId`).
- The aux codes / ANIs / queues themselves → **wxcc-aux-codes**, **wxcc-outdial-ani**,
  **wxcc-queues**.
- Desktop **Layout** (the screen arrangement JSON) → **wxcc-desktop-layouts**. Layouts are
  screens; profiles are behavior.

## Reads

| Goal | Call |
|---|---|
| All profiles | `wxcc_list(entity="agent-profile", attributes="id,name,active", all_pages=true)` |
| One profile, full | `wxcc_get(entity="agent-profile", id="PROFILE-ID")` |

Key fields (~46 total, observed live 2026-07-11): `autoAnswer`, `autoWrapUp`,
`autoWrapAfterSeconds`, `accessIdleCode`/`idleCodes`, `accessWrapUpCode`/`wrapUpCodes`,
`accessQueue`/`queues`, `accessEntryPoint`/`entryPoints`, `accessBuddyTeam`/`buddyTeams`,
`outdialEnabled`/`outdialANIId`/`outdialEntryPointId`, `screenPopup`,
`viewableStatistics`, `loginVoiceOptions`, `parentType`, `systemDefault`.

The `access*` fields are **ALL/SPECIFIC switches paired with id-list fields** — reading the
id list alone will mislead you if the switch says ALL.

`dialPlanEnabled`/`dialPlans` still appear in responses but **Dial Plan is DEPRECATED in
WxCC** — ignore them; do not build on them.

## Update

```
wxcc_update(entity="agent-profile", id="PROFILE-ID", changes={"autoWrapAfterSeconds": 30})
```

Verified by a live no-op PUT (200, 2026-07-11). The tool does the read-modify-write and
re-reads afterward.

**Field-level changes are candidates until you run one.** And the blast radius is real:
profiles are referenced by users, so a bad change hits **every agent on the profile at next
login**. Check the `SILENTLY_IGNORED` map on the result — this API family is known to return
200 while dropping fields (**wxcc-users-write**).

## Create / delete — refused by the registry

`wxcc_create` and `wxcc_delete` on `agent-profile` are **not offered**: neither has been run
here. Cisco's Postman collection lists DELETE but no create. A profile delete while users
reference it is high-blast — check user references (**wxcc-users**, `agentProfileId`) and do
it deliberately in the portal rather than improvising through the CLI.

## Provenance and maintenance

Reads and a no-op PUT (200) run live on a us1 sandbox 2026-07-11; re-confirmed on the gold
tenant 2026-07-14 (20 profiles). Dial Plan deprecation and the Desktop-Profile naming
directive confirmed by the tenant owner 2026-07-11. Field-level update, create, and delete
remain candidates — re-verify with one change→re-read→revert cycle on a sandbox profile.
