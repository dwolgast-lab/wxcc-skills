---
name: wxcc-skill-profiles
description: Use when asked about Webex Contact Center routing skills or skill profiles - "what skills exist in the tenant", "find skill X", "is skill X text or proficiency type", "what skill profiles do we have", "which skills are in profile X", "what profile does team X use". Read-only. Provides confirmed paths for both the skill and skill-profile entities and their query syntax.
---

# wxcc-skill-profiles — routing skills and skill profiles (read-only)

CC routing skills (competencies like "Development" with a type and service level) and skill
profiles (named bundles of skill values assigned to teams/agents) work as a pair: profiles
carry `activeSkills`/`activeEnumSkills`, and teams reference a `skillProfileId`
(see **wxcc-teams**). Uses the shared helper `wxcc.py` (repo root); requires a working
connection (**wxcc-connect**). Every path and parameter was run against a live tenant
(127 skills, 51 profiles) on 2026-07-11.

## Use when / Do NOT use when

**Use when:**
- Listing/counting/finding routing skills or skill profiles.
- Inspecting a skill's type, service level threshold, or active flag.
- Inspecting which skills a profile contains, or resolving a team's `skillProfileId`.

**Do NOT use when:**
- Auth errors (401 / "not authenticated") → **wxcc-connect**.
- Which team uses a given profile → **wxcc-teams** (teams carry `skillProfileId`).
- Queue skill requirements → **wxcc-queues** (`queueSkillRequirements` on the queue).
- Creating or editing skills/profiles → no write skill exists yet; needs `cjp:config`
  scope (wxcc-connect "Adding write access"). Do not improvise writes.

## Ground rules

- Paths go to `wxcc.py get` **without a leading slash** (see wxcc-connect).
- Lists paginate (`meta` + `data[]`); `get --all` combines pages; trim with `attributes=`.
- Filter values are **unquoted** (quotes → HTTP 400). Item paths have **no v2** (v2 → 404).

## Recipes — skills

### List / count / find

```bash
python wxcc.py get --all "organization/{orgId}/v2/skill?attributes=id,name,skillType,active"
python wxcc.py get "organization/{orgId}/v2/skill?pageSize=1&attributes=id"   # meta.totalRecords = count
python wxcc.py get "organization/{orgId}/v2/skill?filter=name==SKILL-NAME&attributes=id,name,skillType"
python wxcc.py get "organization/{orgId}/v2/skill?search=KEYWORD&attributes=id,name"
```

### Get one skill by id (full object)

```bash
python wxcc.py get "organization/{orgId}/skill/SKILL-ID-HERE"
```
→ fields observed live 2026-07-11: `name`, `active`, `skillType`, `dynamicSkill`,
`serviceLevelThreshold`, `systemDefault`, `description`. Tenant-observed, not contract.

## Recipes — skill profiles

### List / count / find

```bash
python wxcc.py get --all "organization/{orgId}/v2/skill-profile?attributes=id,name"
python wxcc.py get "organization/{orgId}/v2/skill-profile?pageSize=1&attributes=id"
python wxcc.py get "organization/{orgId}/v2/skill-profile?filter=name==PROFILE-NAME&attributes=id,name"
python wxcc.py get "organization/{orgId}/v2/skill-profile?search=KEYWORD&attributes=id,name"
```

### What's inside profile X?

```bash
python wxcc.py get "organization/{orgId}/skill-profile/PROFILE-ID-HERE"
```
→ `activeSkills` and `activeEnumSkills` hold the skill values; resolve each skill id with
the get-one-skill recipe. Exact sub-structure of the skill-value entries is tenant-observed
— read what comes back rather than assuming a shape.

### Which profile does team X use?

Get the team (**wxcc-teams**) and read `skillProfileId`, then fetch that profile here.

## Traps (each reproduced live, 2026-07-11)

| Wrong | Result | Right |
|---|---|---|
| `v2/skill/{id}` or `v2/skill-profile/{id}` | HTTP 404 | Item paths have no v2 |
| `filter=name=="X"` (quoted) | HTTP 400 | Unquoted: `filter=name==X` |
| Non-v2 list paths (`.../skill`) | 200 but a **bare unpaginated array** (legacy) | Prefer the `v2` list |

## Provenance and maintenance

All claims run against a live us1 tenant on 2026-07-11 via `wxcc.py`; re-verify any row by
running its recipe. Filterable fields confirmed: `id`, `name` on both entities; others are
candidates. Sibling facts (OAuth, pagination, leading-slash) live in **wxcc-connect**.
