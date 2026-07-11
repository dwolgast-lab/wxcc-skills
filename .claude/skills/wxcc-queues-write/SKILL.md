---
name: wxcc-queues-write
description: Use when asked to create, update, or delete a Webex Contact Center queue / contact service queue (CSQ) - "create a queue for X", "change queue X's service level or max time", "add/remove a team from queue X's routing", "deactivate or delete queue X". Mutating - requires cjp:config_write scope and explicit user confirmation before each write. Provides the verified POST/PUT/DELETE recipes, the required-field list, and rollback steps.
---

# wxcc-queues-write — create, update, and delete WxCC queues

Mutating counterpart to **wxcc-queues** (reads). Entity is `contact-service-queue` (never
`queue`). Every recipe run end-to-end against a live sandbox tenant on 2026-07-11
(create 201, update 200, delete 204, baseline restored).

## Use when / Do NOT use when

**Use when:** creating/updating/deleting queues, changing routing teams, SLT, or limits.

**Do NOT use when:**
- Listing/finding/inspecting queues → **wxcc-queues**.
- Auth errors or missing write scope → **wxcc-connect**.
- Creating the teams referenced in distribution groups → **wxcc-teams-write**.

## Safety rules

Same non-negotiables as **wxcc-teams-write**: confirm before every write, name the
rollback first (delete is effectively irreversible), verify after with a read, and expect
403 when `cjp:config_write` is missing (`auth status` → `granted :` line).

## Recipes

### Create a queue

Required fields discovered by validation (400 names them if missing): the five permission
booleans `monitoringPermitted`, `parkingPermitted`, `recordingPermitted`,
`recordingAllCallsPermitted`, `pauseRecordingPermitted` — plus the core fields below.
Verified minimal create (use `--body @queue.json` for bodies this size):

```bash
python wxcc.py post "organization/{orgId}/contact-service-queue" --body '{"name":"QUEUE-NAME","queueType":"INBOUND","channelType":"TELEPHONY","serviceLevelThreshold":20,"maxActiveContacts":0,"maxTimeInQueue":3600,"defaultMusicInQueueMediaFileId":"AUDIO-FILE-ID","active":true,"routingType":"LONGEST_AVAILABLE_AGENT","monitoringPermitted":true,"parkingPermitted":false,"recordingPermitted":false,"recordingAllCallsPermitted":false,"pauseRecordingPermitted":false,"callDistributionGroups":[{"agentGroups":[{"teamId":"TEAM-ID"}],"order":1,"duration":0}]}'
```

→ verify: HTTP 201 with the created object; **capture `id`**. Prerequisites: a `teamId`
(**wxcc-teams**) and an audio file id for `defaultMusicInQueueMediaFileId` — copy one from
an existing queue (`wxcc-queues` get-by-id) or list `v2/audio-file` (candidate: untested
as a standalone list here; observed working when reused from an existing queue).

Note: skill-based queues (`queueRoutingType: AGENT_BASED` with `agents[]` instead of
`callDistributionGroups`) exist in the wild — creating that variant is untested (candidate).

### Update a queue

Capture current state first (rollback), then PUT the full object with `id`:

```bash
python wxcc.py get "organization/{orgId}/contact-service-queue/QUEUE-ID"   # capture prior state
python wxcc.py put "organization/{orgId}/contact-service-queue/QUEUE-ID" --body @updated-queue.json
```

→ verify: HTTP 200 echoes new values; re-read to confirm (verified live with a
serviceLevelThreshold change). Rollback = PUT the captured prior object back.

### Delete a queue

```bash
python wxcc.py delete "organization/{orgId}/contact-service-queue/QUEUE-ID"
```

→ verify: HTTP 204, then `filter=name==...` on the v2 list returns 0. **No true rollback**
(recreate = new id; flows and reports referencing the old id break). Check nothing routes
to it first (entry-point flows) and confirm emphatically.

## Traps (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| Missing permission booleans | 400 listing each one — they are required on create, not defaulted. |
| Error bodies are precise | 400 `reason` names the exact offending fields — read it before retrying. |
| Write paths have no `v2` | POST/PUT/DELETE on `organization/{orgId}/contact-service-queue[/{id}]`. |
| `version` | Returned on create (`version: 1`); PUT without it succeeded. Concurrent-edit behavior untested (candidate). |

## Provenance and maintenance

Create/update/delete run live on a us1 sandbox 2026-07-11 (201/200/204, baseline 8 queues
restored; required-boolean rule reproduced from an actual 400). Body shape corroborated by
Cisco's WxCC Postman collection (v3, Aug 2023). Re-verify with a full `zz-` named
create→update→delete cycle.
