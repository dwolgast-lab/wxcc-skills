---
name: wxcc-desktop-profiles
description: Use when asked about Webex Contact Center Desktop Profiles (historically "Agent Profiles" - the API path is still agent-profile) - "list desktop profiles", "what does desktop profile X allow", "which wrap-up/idle codes or queues does profile X expose", "change profile X's auto-wrap or outdial settings", "what ANI does profile X use". Covers reads and the verified update shape; create/delete are labeled candidates.
---

# wxcc-desktop-profiles — agent desktop behavior profiles (read + update)

**Terminology: these are Desktop Profiles.** The API entity is still named
`agent-profile` purely for backwards compatibility — use "Desktop Profile" in every
user-facing sentence, and `agent-profile` in every API path.

A Desktop Profile governs an agent's desktop experience: auto-answer/auto-wrap, which
idle/wrap-up codes, queues, entry points, and buddy teams are visible, outdial permission
and ANI, screen-pop, and timeout behavior. Users reference one via `agentProfileId`
(**wxcc-users**).

## Use when / Do NOT use when

**Use when:** listing/inspecting Desktop Profiles or updating one's settings.

**Do NOT use when:**
- Auth errors → **wxcc-connect**. Writes without `cjp:config_write` → 403.
- Assigning a profile TO a user → **wxcc-users-write** (`agentProfileId`).
- The aux codes / ANIs / queues themselves → **wxcc-aux-codes**, **wxcc-outdial-ani**,
  **wxcc-queues**.
- Desktop Layout (screen arrangement JSON) → **wxcc-desktop-layouts**.

## Reads

```bash
python wxcc.py get --all "organization/{orgId}/v2/agent-profile?attributes=id,name,active"
python wxcc.py get "organization/{orgId}/agent-profile/PROFILE-ID"    # item path: no v2
```

Key fields (observed live 2026-07-11, ~46 total): `autoAnswer`, `autoWrapUp`,
`autoWrapAfterSeconds`, `accessIdleCode`/`idleCodes`, `accessWrapUpCode`/`wrapUpCodes`,
`accessQueue`/`queues`, `accessEntryPoint`/`entryPoints`, `accessBuddyTeam`/`buddyTeams`,
`outdialEnabled`/`outdialANIId`/`outdialEntryPointId`, `screenPopup`, `viewableStatistics`,
`loginVoiceOptions`, `parentType`, `systemDefault`. The `access*` fields are ALL/SPECIFIC
switches paired with id-list fields. `dialPlanEnabled`/`dialPlans` still appear in
responses but Dial Plan is **deprecated in WxCC** — ignore them; do not build on them.

## Update — safety rules of **wxcc-teams-write** apply (confirm first, name rollback, verify after)

Full-object replace, verified by a live no-op PUT (200, 2026-07-11):

```bash
python wxcc.py get "organization/{orgId}/agent-profile/PROFILE-ID" > profile.json   # capture = rollback
# edit profile.json: strip "links"/"_links", change the target fields
python wxcc.py put "organization/{orgId}/agent-profile/PROFILE-ID" --body @profile.json
```

→ verify: 200, then **re-read to confirm the field actually changed** — this API family
can silently ignore fields on a 200 (seen on users, **wxcc-users-write**). Field-level
changes are candidates until you have run one; profiles are referenced by users, so a bad
change hits every agent on the profile at next login. Rollback = PUT the captured original.

## Create / delete (candidates — deliberately unprobed)

Cisco's Postman collection lists DELETE (and bulk-export) but no create; neither has been
run here. A profile delete while users reference it is high-blast — check user references
(**wxcc-users**, filter mentally on `agentProfileId`) and confirm emphatically before
attempting, or clone-edit an existing profile object via POST as an experiment on a
sandbox first (POST shape untested).

## Provenance and maintenance

Reads and the no-op PUT (200) run live on a us1 sandbox 2026-07-11 via `wxcc.py`.
Deprecation of Dial Plan and the Desktop-Profile naming directive confirmed by the tenant
owner, 2026-07-11. Field-level update, create, and delete remain candidates — re-verify
by running one change→re-read→revert cycle on a sandbox profile.
