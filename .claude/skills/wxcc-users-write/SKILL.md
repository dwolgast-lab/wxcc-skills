---
name: wxcc-users-write
description: Use when asked to update a Webex Contact Center user's CC configuration - "move agent X to team Y", "change user X's agent/multimedia/user profile", "enable/disable contact center for user X", "change user X's site". Update-only - users are created in Control Hub, not this API, and identity fields (name, email) are immutable here. Requires cjp:config_write and explicit confirmation before each write.
---

# wxcc-users-write — update a user's contact-center configuration

Mutating counterpart to **wxcc-users** (reads). **Update-only**: this API cannot create or
delete users (provisioning lives in Control Hub / Common Identity), and identity fields are
read-only mirrors here. What it CAN change: the CC-owned attributes — team assignments,
site, agent/multimedia/user profiles, `contactCenterEnabled`. All findings below were
probed live on a sandbox tenant, 2026-07-11, with every change reverted.

## Use when / Do NOT use when

**Use when:** moving an agent between teams, changing profiles, toggling CC enablement.

**Do NOT use when:**
- Finding/inspecting users → **wxcc-users**.
- Creating or deleting users, changing names/emails/passwords → **Control Hub**, not this
  API (identity-owned; see traps).
- Auth errors or missing write scope → **wxcc-connect**.
- Creating the team you're assigning to → **wxcc-teams-write**.

## Safety rules

Same non-negotiables as **wxcc-teams-write**: confirm before every write; capture the
user's current object FIRST (it is the rollback); verify after with a read. Never
experiment on the org's admin account.

## The one write shape

There is no PATCH — GET the full object, modify CC-owned fields, PUT it back:

```bash
python wxcc.py get "organization/{orgId}/user/USER-ID" > user.json   # capture = rollback
# edit user.json: strip "links"/"_links", change ONLY CC-owned fields
python wxcc.py put "organization/{orgId}/user/USER-ID" --body @user.json
```

→ verify: HTTP 200 echoes the changed object; re-read to confirm the field actually
changed (see silent-no-op trap). Rollback = PUT the captured original back (no-op PUT of
an unchanged object is safe — verified 200).

### Example: move an agent to another team

1. Get the user; note `teamIds` and `siteId`.
2. Check the target team in **wxcc-teams**: it must be on the **same site** and
   `teamType: AGENT` — both enforced (see traps).
3. PUT with the edited `teamIds` array. Verified live: add → 200 with both teams,
   revert → 200 back to the original.

## Field writability map (each probed live, 2026-07-11)

| Field | Writable? | Evidence |
|---|---|---|
| `teamIds` | YES, validated | 200 on valid change; 400 `not found for given site` (cross-site) and 400 `Capacity based teams are not allowed` (CAPACITY team). |
| `firstName` / `lastName` | NO | 400 `This configuration cannot be changed` — identity-owned; edit in Control Hub. |
| `userLevelSummariesInclusion` | **Silently ignored** | HTTP 200 but the value did not change — likely entitlement-gated. Always re-read after PUT. |
| `siteId`, `agentProfileId`, `multimediaProfileId`, `userProfileId`, `contactCenterEnabled` | Present in the PUT body; accepted in no-op PUT | Individual changes untested (candidates) — apply the same change→re-read→revert-on-surprise discipline. |

## Traps (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| **200 ≠ changed** | A PUT can return 200 while silently ignoring a field. The post-write READ is the only proof a change took. |
| No create/delete | POST/DELETE on users deliberately unprobed (an accidental create has no API rollback). Cisco's Postman collection ships read-only user endpoints; provisioning is Control Hub's job. |
| Team assignment rules | Same-site + AGENT-type only; validation errors name the offending id. |
| PUT needs the full object | Send everything GET returned (minus `links`/`_links`) with your edits — this API replaces, not merges. |

## Provenance and maintenance

All rows probed 2026-07-11 against a live us1 sandbox via `wxcc.py` on a disposable test
user; every mutation reverted and the final state verified identical to the captured
original. Re-verify any row with the GET→PUT→re-read→revert cycle on a test user.
