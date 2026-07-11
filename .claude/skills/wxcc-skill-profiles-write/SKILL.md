---
name: wxcc-skill-profiles-write
description: Use when asked to create, update, or delete a Webex Contact Center routing skill or skill profile - "create a skill called X", "add an enum skill with values gold/silver", "create a skill profile with X at proficiency 5", "add skill X to profile Y", "delete skill/profile X". Mutating - requires cjp:config_write scope and explicit user confirmation before each write. Provides verified POST/PUT/DELETE recipes for both entities, the enum-skill value rules, and the profile sub-entity id traps.
---

# wxcc-skill-profiles-write — create, update, delete skills and skill profiles

Mutating counterpart to **wxcc-skill-profiles** (reads). Both lifecycles verified
end-to-end against a live sandbox tenant on 2026-07-11 (create 201, update 200,
delete 204, baseline restored), including an ENUM skill and a profile carrying it.

## Use when / Do NOT use when

**Use when:** creating/updating/deleting routing skills or skill profiles, or changing
which skills (and values) a profile carries.

**Do NOT use when:**
- Listing/inspecting skills or profiles → **wxcc-skill-profiles**.
- Assigning a profile to a team (`skillProfileId`) → **wxcc-teams-write**.
- Auth errors or missing write scope → **wxcc-connect**.

## Safety rules

Same non-negotiables as **wxcc-teams-write**: confirm before every write, name the
rollback first (delete is effectively irreversible), verify after with a read, expect 403
without `cjp:config_write`.

## Recipes — skills

### Create a skill

```bash
python wxcc.py post "organization/{orgId}/skill" --body '{"name":"SKILL-NAME","active":true,"skillType":"BOOLEAN","serviceLevelThreshold":20}'
```

→ verify: HTTP 201; **capture `id`**. `skillType`: `BOOLEAN`, `PROFICIENCY`, `TEXT`, or
`ENUM` (all four observed live). ENUM additionally **requires at least one value**
(400 "Enum skill should have atleast one value" without it):

```bash
python wxcc.py post "organization/{orgId}/skill" --body '{"name":"SKILL-NAME","active":true,"skillType":"ENUM","serviceLevelThreshold":20,"enumSkillValues":[{"name":"gold"},{"name":"silver"}]}'
```

→ each value comes back with its own `id` — capture them; profiles reference values by
that `enumSkillValueId`, not by name.

### Update a skill

```bash
python wxcc.py get "organization/{orgId}/skill/SKILL-ID"    # capture prior state (rollback)
python wxcc.py put "organization/{orgId}/skill/SKILL-ID" --body '{"id":"SKILL-ID","name":"SKILL-NAME","description":"...","active":true,"skillType":"BOOLEAN","serviceLevelThreshold":30}'
```

→ verify: HTTP 200, re-read to confirm (verified live: SLT + description change persisted).

### Delete a skill

```bash
python wxcc.py delete "organization/{orgId}/skill/SKILL-ID"
```

→ HTTP 204 when unreferenced. If any profile still carries it → HTTP **412** with
`referencedEntities: ["skill-profile"]` (reproduced live) — remove it from those profiles
first. **No true rollback.**

## Recipes — skill profiles

### Create a profile

Skill values are typed per entry: `booleanValue`, `proficiencyValue` (number), or
`textValue` — matching the skill's type. Enum skills go in a **separate array** and
reference the value id only:

```bash
python wxcc.py post "organization/{orgId}/skill-profile" --body '{"name":"PROFILE-NAME","description":"...","activeSkills":[{"skillId":"SKILL-ID","booleanValue":true},{"skillId":"OTHER-ID","proficiencyValue":5}],"activeEnumSkills":[{"enumSkillValueId":"ENUM-VALUE-ID"}]}'
```

→ verify: HTTP 201 (both arrays verified live in one POST); **capture `id`**.

### Update a profile (add/remove/re-value skills)

PUT is full-replace, and the sub-entries are real sub-entities with their own ids:

```bash
python wxcc.py get "organization/{orgId}/skill-profile/PROFILE-ID"    # capture prior state
python wxcc.py put "organization/{orgId}/skill-profile/PROFILE-ID" --body '{"id":"PROFILE-ID","name":"PROFILE-NAME","description":"...","activeSkills":[{"id":"EXISTING-ENTRY-ID","skillId":"SKILL-ID","booleanValue":true}],"activeEnumSkills":[{"enumSkillValueId":"ENUM-VALUE-ID"}]}'
```

Rules verified by differential probing (see traps): entries you are **keeping** must
include their existing entry `id` (from the GET); entries you are **adding** have no `id`;
entries you omit are removed. Verify with a re-read; rollback = PUT the captured original.

### Delete a profile

```bash
python wxcc.py delete "organization/{orgId}/skill-profile/PROFILE-ID"
```

→ HTTP 204. Check first that no team references it (**wxcc-teams**, `skillProfileId`) —
deleting one that is referenced is untested (candidate; expect the 412 pattern).

## Traps (each reproduced live, 2026-07-11)

| Wrong | Result | Right |
|---|---|---|
| PUT keeping an existing skill entry without its entry `id` | HTTP **409** "Duplicate entry..." (raw DB error) | Copy each kept entry's `id` from the GET |
| `skillId` included inside an `activeEnumSkills` entry | HTTP **500** (no validation message) | Enum entries are `{"enumSkillValueId": "..."}` only |
| ENUM skill created without values | HTTP 400 "should have atleast one value" | Include `enumSkillValues: [{"name": "..."}]` |
| Deleting a skill a profile still uses | HTTP **412**, names `skill-profile` | Edit the profiles first |

## Provenance and maintenance

All recipes run live on a us1 sandbox 2026-07-11: skill (BOOLEAN + ENUM) and profile
lifecycles 201/200/204 each; enum-entry shape corroborated by Cisco's Postman collection
(v3) after the 500 trap. Baselines restored (probe objects deleted, verified by list).
Re-verify with a `zz-` named skill→profile→cleanup cycle.
