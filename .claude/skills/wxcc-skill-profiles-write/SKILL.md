---
name: wxcc-skill-profiles-write
description: Use when asked to create, update, or delete a Webex Contact Center routing skill or skill profile - "create a skill called X", "add an enum skill with values gold/silver", "create a skill profile with X at proficiency 5", "add skill X to profile Y", "delete skill/profile X". Mutating - requires cjp:config_write and explicit user confirmation. Covers the enum-skill value rules and the sub-entity id traps.
---

# wxcc-skill-profiles-write — create, update, delete skills and skill profiles

Mutating counterpart to **wxcc-skill-profiles**. Call `wxcc_create` / `wxcc_update` /
`wxcc_delete` with `entity="skill"` or `entity="skill-profile"` on the server for the tenant
the user named. **If no tenant was named, ask — do not guess.**

## Use when / Do NOT use when

**Use when:** creating/updating/deleting routing skills or skill profiles.

**Do NOT use when:**
- Listing/inspecting skills or profiles → **wxcc-skill-profiles**.
- Auth errors or 403 on write → **wxcc-connect**.
- Assigning a profile TO a team → **wxcc-teams-write** (`skillProfileId` on the team).
- Queue skill *requirements* → **wxcc-queues-write** (`queueSkillRequirements`).

## How the write tools protect you

Call without `confirm` → nothing is written; you get the tenant, a diff, and the rollback.
Get an explicit yes, then re-call with `confirm=true`. Watch **`TENANT`** (first field),
**`SILENTLY_IGNORED`**, and **`blocked`**.

## Skills

```
wxcc_create(entity="skill", fields={
  "name": "SKILL-NAME", "active": true,
  "skillType": "BOOLEAN", "serviceLevelThreshold": 20
})
```

`skillType`: `BOOLEAN`, `PROFICIENCY`, `TEXT`, or `ENUM`.

**An ENUM skill MUST ship its values at create** — otherwise
`400 "Enum skill should have atleast one value"`:

```
wxcc_create(entity="skill", fields={
  "name": "TIER", "active": true, "skillType": "ENUM", "serviceLevelThreshold": 20,
  "enumSkillValues": [{"name": "gold"}, {"name": "silver"}]
})
```

Each value comes back with **its own id** — those ids, not the skill id, are what profiles
reference. Capture them.

**Deleting a skill that a profile still uses returns HTTP 412** with
`referencedEntities: ["skill-profile"]` (confirmed live). The tool pre-flights this and
returns `conflicting_references` — remove the skill from those profiles first.

## Skill profiles

```
wxcc_create(entity="skill-profile", fields={
  "name": "PROFILE-NAME",
  "activeSkills": [
    {"skillId": "SKILL-ID", "booleanValue": true},
    {"skillId": "OTHER-ID", "proficiencyValue": 5}
  ],
  "activeEnumSkills": [{"enumSkillValueId": "ENUM-VALUE-ID"}]
})
```

**The two arrays follow different rules, and getting them wrong fails in two different
ways.** Both reproduced live:

| Mistake | Result |
|---|---|
| `skillId` inside an `activeEnumSkills` entry | **HTTP 500**, no message. Enum entries carry `enumSkillValueId` **only**. |
| Re-sending a kept `activeSkills` entry without its own sub-entity `id` | **HTTP 409** `Duplicate entry ... key 'active_skill.UK...'` |

That second one is the update trap. A profile update is a **full replace**: every entry you
intend to keep must come back carrying the `id` it already has (get it from
`wxcc_get(entity="skill-profile", ...)`). New entries have no `id` yet — omit it for those.

```
wxcc_update(entity="skill-profile", id="PROFILE-ID", changes={
  "activeSkills": [
    {"id": "EXISTING-ENTRY-ID", "skillId": "SKILL-ID", "booleanValue": true},
    {"skillId": "NEW-SKILL-ID", "proficiencyValue": 3}
  ]
})
```

The 500 case is worth knowing precisely: it returns no message, and a re-read showed the
profile **unchanged** — a clean failure, not a partial write. But do not rely on that;
re-read and check.

## Traps

| Item | Detail |
|---|---|
| ENUM skill with no values | 400 "Enum skill should have atleast one value" |
| `skillId` in `activeEnumSkills` | HTTP 500 (silent, no message) |
| Kept entry missing its sub-entity `id` | HTTP 409 duplicate-entry |
| Deleting a referenced skill | HTTP 412 naming `skill-profile` |
| Enum values have their own ids | Profiles reference the **value** id, never the skill id |

## Provenance and maintenance

Skill and profile lifecycles run live on a us1 sandbox 2026-07-11 (create/update/delete,
baseline restored: 11 skills, 1 profile). The 500, 409, and 412 were each reproduced, and
the correct enum body shape was recovered from Cisco's official Postman collection (v3)
after the 500. Re-verify with a `zz-` named skill + profile cycle, deleting the profile
before the skill.
