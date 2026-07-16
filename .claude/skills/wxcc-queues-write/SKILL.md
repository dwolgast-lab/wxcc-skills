---
name: wxcc-queues-write
description: Use when asked to create, update, or delete a Webex Contact Center queue / contact service queue (CSQ) - "create a queue for X", "change queue X's service level or max time", "add/remove a team from queue X's routing", "deactivate or delete queue X". Mutating - requires cjp:config_write and explicit user confirmation before each write.
---

# wxcc-queues-write — create, update, and delete WxCC queues

Mutating counterpart to **wxcc-queues**. Call `wxcc_create` / `wxcc_update` / `wxcc_delete`
with `entity="contact-service-queue"` on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

## Use when / Do NOT use when

**Use when:** creating/updating/deleting queues, changing routing teams, SLT, or limits.

**Do NOT use when:**
- Listing/finding/inspecting queues → **wxcc-queues**.
- Auth errors or 403 on write → **wxcc-connect**.
- Creating the teams referenced in distribution groups → **wxcc-teams-write**.
- Authoring the flow that routes INTO a queue → Cisco's **flow-store** MCP server.

## How the write tools protect you

Call without `confirm` → nothing is written; you get the tenant, a diff (or what would be
destroyed), and the rollback. Show it, get an explicit yes, re-call with `confirm=true`.
The tool then re-reads and diffs. Watch **`TENANT`** (first field — `[PRODUCTION]` means a
real customer), **`SILENTLY_IGNORED`** (200 but the field did not apply — do not report
success), and **`blocked`** (a delete refused because something still references it).

## Create

```
wxcc_create(entity="contact-service-queue", fields={
  "name": "QUEUE-NAME", "queueType": "INBOUND", "channelType": "TELEPHONY",
  "serviceLevelThreshold": 20, "maxActiveContacts": 0, "maxTimeInQueue": 3600,
  "active": true, "routingType": "LONGEST_AVAILABLE_AGENT",
  "monitoringPermitted": true, "parkingPermitted": false,
  "recordingPermitted": false, "recordingAllCallsPermitted": false,
  "pauseRecordingPermitted": false,
  "defaultMusicInQueueMediaFileId": "AUDIO-FILE-ID",
  "callDistributionGroups": [{"agentGroups": [{"teamId": "TEAM-ID"}], "order": 1, "duration": 0}]
})
```

**The five `*Permitted` booleans are REQUIRED on create, not defaulted** — reproduced from
a real 400 that named each one. The tool checks them before calling.

Prerequisites: a `teamId` (**wxcc-teams**) and an audio file id for
`defaultMusicInQueueMediaFileId` — copy one from an existing queue (`wxcc_get`). Listing
`audio-file` as a standalone entity is not in the registry (unprobed).

Skill-based queues (`queueRoutingType: AGENT_BASED` with `agents[]` instead of
`callDistributionGroups`) exist in the wild — **candidate, untested.**

Rollback: `wxcc_delete` the returned id.

## Update

```
wxcc_update(entity="contact-service-queue", id="QUEUE-ID",
            changes={"serviceLevelThreshold": 30})
```

Read-modify-write full-object PUT, handled by the tool. Pass only what changes.
Rollback is in the dry run's `diff` under `from`.

## Delete

```
wxcc_delete(entity="contact-service-queue", id="QUEUE-ID")            # preview
wxcc_delete(entity="contact-service-queue", id="QUEUE-ID", confirm=true)
```

**No rollback.** Recreating yields a new id, and **flows referencing the old id break** —
flows live in flow-store and this tool cannot see them, so a queue delete can break routing
in a way nothing here will warn you about. Check what routes to it before confirming.

## Traps

| Item | Detail |
|---|---|
| Entity name | `contact-service-queue`; `queue` 404s |
| Error bodies are precise | A 400's `reason` names the exact offending fields — read it before retrying |
| `version` | Returned on create (`version: 1`); PUT without it succeeded. Concurrent-edit behavior untested (candidate) |
| Flow references | Invisible to these tools — a delete may orphan a flow |

## Provenance and maintenance

Create/update/delete run live on a us1 sandbox 2026-07-11 (201/200/204, baseline 8 queues
restored; required-boolean rule reproduced from an actual 400). Body shape corroborated by
Cisco's Postman collection (v3, Aug 2023). Re-verify with a `zz-` named full cycle.
