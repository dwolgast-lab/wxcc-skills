---
name: wxcc-multimedia-profiles-write
description: Use when asked to create, update, or delete a Webex Contact Center multimedia profile - "create a multimedia profile", "change profile X's concurrent chat limit", "set profile X to blended", "rename multimedia profile X", "delete multimedia profile X". Mutating - requires cjp:config_write and explicit user confirmation before each write. Covers the required create fields and the workItem PUT trap.
---

# wxcc-multimedia-profiles-write — create, update, and delete WxCC multimedia profiles

Mutating counterpart to **wxcc-multimedia-profiles**. Call `wxcc_create` / `wxcc_update` /
`wxcc_delete` with `entity="multimedia-profile"` on the server for the tenant the user named.
**If no tenant was named, ask — do not guess.**

A multimedia profile sets how many contacts of each channel an agent on it can handle at
once. It is referenced by **sites** (`site.multimediaProfileId`), so a bad change reaches
every agent at those sites — treat it like the shared config it is.

## Use when / Do NOT use when

**Use when:** creating, updating, or deleting a multimedia profile; changing its per-channel
concurrency caps, blending mode, or active flag.

**Do NOT use when:**
- Listing/finding/inspecting profiles → **wxcc-multimedia-profiles**.
- Auth errors or 403 on write → **wxcc-connect**.
- Assigning a profile to a site → **wxcc-sites** (set the site's `multimediaProfileId`).

## How the write tools protect you

Call without `confirm` → nothing is written; you get the tenant, a diff (or what would be
destroyed), and the rollback. Show it, get an explicit yes, re-call with `confirm=true`.
The tool then re-reads and diffs. Watch **`TENANT`** (first field — `[PRODUCTION]` means a
real customer), **`SILENTLY_IGNORED`** (200 but the field did not apply), and **`blocked`**
(a delete refused because a site still references it).

## Create

```
wxcc_create(entity="multimedia-profile", fields={
  "name": "PROFILE-NAME", "active": true,
  "telephony": 1, "chat": 0, "email": 0, "social": 0,
  "blendingMode": "BLENDED", "blendingModeEnabled": false,
  "manuallyAssignable": {"telephony": 0, "chat": 0, "email": 0, "social": 0}
})
```

**All nine fields above are REQUIRED on create** — reproduced from a real 400 that named
each. The per-channel integers are **concurrent-contact caps**, not on/off flags:
`telephony: 1` = one call at a time. `blendingMode` is one of **`BLENDED` |
`BLENDED_REALTIME` | `EXCLUSIVE`** (a bad value is a clean 400 naming the enum).
`manuallyAssignable` is a required nested `{channel: int}` object.

Rollback: `wxcc_delete` the returned id.

## Update

```
wxcc_update(entity="multimedia-profile", id="PROFILE-ID", changes={"chat": 3})
```

Read-modify-write full-object PUT, handled by the tool. Pass only what changes; rollback is
in the dry run's `diff` under `from`.

**The `workItem` trap is handled for you, but know it exists.** The API returns a `workItem`
field (top-level *and* inside `manuallyAssignable`) on a read, but **rejects it on a PUT when
the tenant's workItem feature flag is off** (HTTP 400, "workItem is not allowed when feature
flag is disabled"). Because the update is read-modify-write, that field would otherwise ride
along and fail every update. `wxcc_update` strips exactly the field the API names and retries,
then reports it under **`stripped_for_feature_flag`** — harmless unless you were trying to
change `workItem` itself, in which case it also shows up as not applied. On a tenant where the
flag is *on*, nothing is stripped.

## Delete

```
wxcc_delete(entity="multimedia-profile", id="PROFILE-ID")            # preview
wxcc_delete(entity="multimedia-profile", id="PROFILE-ID", confirm=true)
```

**Reference-blocked:** a profile still assigned to any site (and the API's graph also surfaces
the teams/users under those sites) is refused with the blocker list, before the API's 412.
Repoint each site's `multimediaProfileId` first (**wxcc-sites**). **No rollback** — recreating
yields a new id, and every site that pointed at the old id stays broken. Do not delete a
`systemDefault: true` profile.

## Traps

| Item | Detail |
|---|---|
| Channel fields are counts | `telephony: 1` = one concurrent call, not "telephony enabled" |
| `workItem` on PUT | Rejected when the feature flag is off; the tool strips + retries and reports it |
| `blendingMode` values | `BLENDED` \| `BLENDED_REALTIME` \| `EXCLUSIVE` — others are a clean 400 |
| `manuallyAssignable` | Required nested object on create; also carries a `workItem` the PUT rejects |
| Deleting a referenced profile | Blocked with the site/team/user list; repoint sites first |

## Provenance and maintenance

Create/update/delete verified live on a us1 sandbox 2026-07-17 (201 / 200 / 204, baseline 3
profiles restored) through the MCP tools, including the reference-block pre-flight and the
`workItem` adaptive strip on update. The required-field set and the `workItem` PUT rejection
were each reproduced from real 400s. Re-verify with a `zzz-` named full cycle.
