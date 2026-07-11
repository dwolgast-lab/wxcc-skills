---
name: wxcc-teams-write
description: Use when asked to create, rename, update, activate/deactivate, move, or delete a Webex Contact Center team - "create a team called X on site Y", "rename team X", "deactivate team X", "delete team X", "change team X's site/status/type". Mutating operations - requires the cjp:config_write scope and explicit user confirmation before each write. Provides the verified POST/PUT/DELETE recipes with rollback steps.
---

# wxcc-teams-write — create, update, and delete WxCC teams

Mutating counterpart to **wxcc-teams** (reads). Uses the shared helper `wxcc.py`. Every
recipe below was run end-to-end against a live sandbox tenant on 2026-07-11 (create 201,
update 200, delete 204, tenant restored to baseline).

## Use when / Do NOT use when

**Use when:** creating, renaming, updating, re-siting, deactivating, or deleting a team.

**Do NOT use when:**
- Listing/finding/inspecting teams → **wxcc-teams**.
- Auth errors or missing write scope → **wxcc-connect** ("Adding write access").
- Changing which queues route to a team → that lives on the queue
  (`callDistributionGroups`) — **wxcc-queues** for reads; no queue write skill yet.

## Safety rules (non-negotiable)

1. **Confirm before every write.** State exactly what will change and get an explicit yes
   from the user first — a green read is authorization to read, not to write.
2. **Name the rollback before writing.** Create → rollback is DELETE the new id. Update →
   rollback is PUT the prior values (capture them with a GET first). Delete → effectively
   irreversible (recreate loses the id and any references) — treat with the most care.
3. **Verify after every write** with a read (recipes below), and report the delta.
4. Writes need `cjp:config_write` on the token — check `python wxcc.py auth status`
   (`granted :` line). 403 on write = scope missing → wxcc-connect.

## Prerequisites

- A working connection with write scopes granted (**wxcc-connect**).
- For create: a `siteId` from **wxcc-sites**.

## Recipes

### Create a team

Minimal verified body — `name`, `active`, `siteId`, `teamStatus`, `teamType`:

```bash
python wxcc.py post "organization/{orgId}/team" --body '{"name":"TEAM-NAME","active":true,"siteId":"SITE-ID-HERE","teamStatus":"IN_SERVICE","teamType":"AGENT"}'
```

→ verify: HTTP 201 and the response echoes the created object **including its `id`** —
capture it; it is the handle for update/delete/rollback. Optional fields seen in Cisco's
official Postman collection (candidates, not run here): `desktopLayoutId`,
`multimediaProfileId`. `teamType` is `AGENT` (or `CAPACITY` for capacity-based teams —
untested, candidate).

For complex bodies prefer a file: `--body @team.json` (see `wxcc.py --help`; `--body -`
reads stdin).

### Update a team (rename, deactivate, change status/site)

PUT the full object with `id` included — capture current state first for rollback:

```bash
python wxcc.py get "organization/{orgId}/team/TEAM-ID-HERE"    # capture prior state
python wxcc.py put "organization/{orgId}/team/TEAM-ID-HERE" --body '{"id":"TEAM-ID-HERE","name":"NEW-NAME","active":true,"siteId":"SITE-ID-HERE","teamStatus":"IN_SERVICE","teamType":"AGENT"}'
```

→ verify: HTTP 200 and the response shows the new values; confirm with
`filter=name==NEW-NAME` on the v2 list (**wxcc-teams**). Rollback = PUT the captured
prior values back.

### Delete a team

```bash
python wxcc.py delete "organization/{orgId}/team/TEAM-ID-HERE"
```

→ verify: HTTP 204, then `filter=name==...` returns `totalRecords: 0`. **No true
rollback** — recreating produces a new id; anything referencing the old id (queue
distribution groups, agent assignments) stays broken. Confirm emphatically before delete.

## Traps and notes (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| Legacy write form | A `?teamDTO=<urlencoded-json>` query-param POST also exists in the wild (portal-generated samples). Works, but these recipes use the plain JSON body — cleaner and verified. |
| DELETE not in Cisco's Postman collection | It works anyway (204, verified live). Absence from samples ≠ absence from API. |
| `version` field | Created objects carry `version: 0`. PUT without `version` succeeded; optimistic-locking behavior under concurrent edits is untested (candidate). |
| Write paths have no `v2` | Same convention as team reads' item path. |
| Deleting referenced teams | Untested what happens when the team is in a queue's `callDistributionGroups` — check the queue (**wxcc-queues**) before deleting (candidate). |

## Provenance and maintenance

Create/update/delete each run against a live us1 sandbox tenant on 2026-07-11 via
`wxcc.py` (201/200/204), with post-write verification reads and baseline restoration
(5 teams before and after). Optional create fields sourced from Cisco's official WxCC
Postman collection (v3, Aug 2023) — labeled candidate until run. Scope naming
(`cjp:config_write`) confirmed by consent + `auth status` granted-scopes line, 2026-07-11.
Re-verify any recipe by running the full create→verify→delete cycle with a `zz-` prefixed
throwaway name.
