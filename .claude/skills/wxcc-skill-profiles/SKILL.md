---
name: wxcc-skill-profiles
description: Use when asked about Webex Contact Center routing skills or skill profiles - "what skills exist in the tenant", "find skill X", "is skill X text or proficiency type", "what skill profiles do we have", "which skills are in profile X", "what profile does team X use". Read-only.
---

# wxcc-skill-profiles — routing skills and skill profiles (read-only)

Call the **`wxcc_list` / `wxcc_get`** MCP tools on the server for the tenant the user named
(`mcp__wxcc-<tenant>__wxcc_list`). **If no tenant was named, ask — do not guess.**

Two entities working as a pair: **`skill`** is a competency (a name, a type, a service
level); **`skill-profile`** is a named bundle of skill *values* that teams and agents
reference via `skillProfileId`.

## Use when / Do NOT use when

**Use when:**
- Listing/counting/finding routing skills or skill profiles.
- Inspecting a skill's type, service level threshold, or active flag.
- Inspecting which skills a profile contains, or resolving a team's `skillProfileId`.

**Do NOT use when:**
- Auth errors, or `wxcc_whoami` reports the wrong org → **wxcc-connect**.
- Which team uses a given profile → **wxcc-teams** (teams carry `skillProfileId`).
- Queue skill requirements → **wxcc-queues** (`queueSkillRequirements`).
- Creating or editing skills/profiles → **wxcc-skill-profiles-write**.

## Recipes — skills

| Goal | Call |
|---|---|
| Every skill | `wxcc_list(entity="skill", attributes="id,name,skillType,active", all_pages=true)` |
| Count only | `wxcc_list(entity="skill", page_size=1, attributes="id")` → `meta.totalRecords` |
| Find by exact name | `wxcc_list(entity="skill", filter="name==SKILL-NAME")` |
| Keyword search | `wxcc_list(entity="skill", search="KEYWORD")` |
| One skill, full | `wxcc_get(entity="skill", id="SKILL-ID")` |

Fields observed live (2026-07-11): `name`, `active`, `skillType`, `dynamicSkill`,
`serviceLevelThreshold`, `systemDefault`, `description`. `skillType` is `BOOLEAN`,
`PROFICIENCY`, `TEXT`, or `ENUM` — an ENUM skill also carries `enumSkillValues`, each with
its own id.

## Recipes — skill profiles

| Goal | Call |
|---|---|
| Every profile | `wxcc_list(entity="skill-profile", attributes="id,name", all_pages=true)` |
| Find by exact name | `wxcc_list(entity="skill-profile", filter="name==PROFILE-NAME")` |
| **What is inside profile X** | `wxcc_get(entity="skill-profile", id="PROFILE-ID")` |
| Which profile does team X use | `wxcc_get(entity="team", id=...)` → `skillProfileId`, then fetch here |

A profile's contents live in two separate arrays, and the distinction matters:

- **`activeSkills`** — non-enum skills: `{id, skillId, booleanValue | proficiencyValue |
  textValue}`. The `id` is the *entry's* own sub-entity id, not the skill's.
- **`activeEnumSkills`** — enum skills, keyed by `enumSkillValueId` only.

Read what comes back rather than assuming a shape; sub-entity ids are what make writes work
(**wxcc-skill-profiles-write**).

## Traps

| Trap | Why | Do this |
|---|---|---|
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted |
| Filterable fields | Only `id`, `name` confirmed on both | Others are candidates |
| Assuming one skills array | Enum and non-enum skills live in **different** arrays | Check both |

## Provenance and maintenance

Run against a live us1 tenant 2026-07-11 (127 skills, 51 profiles); re-confirmed
2026-07-14. Path shape and pagination are handled by the tool's registry.
