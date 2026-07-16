---
name: wxcc-desktop-profiles
description: Use when asked about Webex Contact Center Desktop Profiles (historically "Agent Profiles" - the API path is still agent-profile) - "list desktop profiles", "what does desktop profile X allow", "which wrap-up/idle codes or queues does profile X expose", "create/copy a desktop profile", "change profile X's auto-wrap or outdial settings", "what ANI does profile X use", "delete profile X". Full CRUD, all verified live.
---

# wxcc-desktop-profiles — agent desktop behavior profiles (full CRUD)

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
wxcc_update(entity="agent-profile", id="PROFILE-ID", changes={"autoAnswer": true})
```

Verified live 2026-07-16: `autoAnswer` and `description` each changed → re-read → reverted.
The tool does the read-modify-write and re-reads afterward; check `SILENTLY_IGNORED`.

**Some fields are paired and must move together.** Reproduced live:

```
wxcc_update(..., changes={"autoWrapAfterSeconds": 7})                      # 400
#  -> "autoWrapAfterSeconds should be specified when autoWrapUp is true"
wxcc_update(..., changes={"autoWrapUp": true, "autoWrapAfterSeconds": 7})  # 200
```

The `access*` switches (`accessQueue`/`queues`, `accessIdleCode`/`idleCodes`, …) are the
same shape: ALL/SPECIFIC paired with an id list. Expect flipping one without the other to
fail the same way — **candidate**, not yet run.

**Blast radius is real:** profiles are referenced by users, so a bad change hits **every
agent on the profile at next login**. Probe on an unreferenced profile
(`wxcc_delete` dry-run tells you if anything points at one) or a throwaway clone.

## Create — clone an existing profile

There is no sensible minimal body: a profile is ~46 fields. **Read one, rename it, create.**

```
tpl = wxcc_get(entity="agent-profile", id="SOURCE-ID")
wxcc_create(entity="agent-profile", fields={**tpl["data"], "name": "NEW-NAME"})
```

The tool drops `id`/`links`/timestamps **and every nested `id`** for you. That last part
matters: `viewableStatistics` is a dict carrying its own `id`, and re-sending a borrowed one
returns **409 "Internal error. Please contact Cisco Support Team"** — which names nothing and
sends you hunting. Reproduced live 2026-07-16, then isolated to that field.

Rollback: `wxcc_delete` the returned id.

## Delete

```
wxcc_delete(entity="agent-profile", id="PROFILE-ID")               # preview
wxcc_delete(entity="agent-profile", id="PROFILE-ID", confirm=true)
```

The tool pre-flights `incoming-references`, so a profile with users on it comes back
**blocked**, listing every one by name. **No rollback** — recreate yields a new id and every
user pointing at the old one breaks.

## Traps

| Item | Detail |
|---|---|
| 409 "Internal error. Contact Cisco Support" on create | You reused a nested `id` (usually `viewableStatistics`). Not a Cisco outage — a borrowed sub-entity id. |
| `access*` switches | ALL/SPECIFIC paired with an id list. Reading the list alone misleads when the switch says ALL. |
| `dialPlanEnabled`/`dialPlans` | Still in responses; **Dial Plan is deprecated in WxCC**. Ignore. |
| Paired fields | `autoWrapAfterSeconds` alone → 400; send `autoWrapUp` with it. The `access*` switch/list pairs are likely the same (candidate). |
| Blast radius | Users reference profiles — a bad change hits every agent on it at next login. |
| Bulk / purge endpoints | `POST agent-profile/bulk` and `POST agent-profile/purge-inactive-entities` exist. **Neither is probed or exposed** — purge especially is mass-destructive. Do not improvise. |

## Provenance and maintenance

Reads and a no-op PUT (200) run live 2026-07-11; re-confirmed on the gold tenant 2026-07-14
(20 profiles). **Create (201) and delete (204) probed and verified 2026-07-16**, including
the 409-on-nested-id, which was reproduced twice and isolated to `viewableStatistics`;
reference-blocking confirmed against a profile with 12 users; baseline of 5 restored. Dial
Plan deprecation and the Desktop-Profile naming directive confirmed by the tenant owner
2026-07-11. **Field-level update verified 2026-07-16** on an unreferenced profile:
`autoAnswer` and `description` each changed → re-read → reverted; the paired-field 400 on
`autoWrapAfterSeconds` was reproduced and isolated (setting it with `autoWrapUp` → 200,
then reverted). The `access*` switch/list pairing is inferred from the same shape, not run.

Cisco's published API reference for this endpoint could not be read (the page is a JS SPA
that exceeds fetch limits and whose reference body does not render headless). Everything
here is from the live tenant, which has twice contradicted Cisco's own Postman collection
for this entity — the collection listed DELETE but no create, and missed the entry
sub-resource on sibling entities entirely.
