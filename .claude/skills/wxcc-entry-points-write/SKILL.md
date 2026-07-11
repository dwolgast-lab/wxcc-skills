---
name: wxcc-entry-points-write
description: Use when asked to create, update, or delete a Webex Contact Center entry point, or to change a dial number's entry-point mapping - "create an entry point for X", "change entry point X's service level", "repoint +1555... to entry point Y", "delete entry point X". Mutating - requires cjp:config_write scope and explicit user confirmation before each write. Provides verified EP POST/PUT/DELETE recipes and the dial-number write rules, including why new numbers cannot be invented here.
---

# wxcc-entry-points-write — create, update, delete EPs; repoint dial numbers

Mutating counterpart to **wxcc-entry-points** (reads). EP lifecycle verified end-to-end
against a live sandbox tenant on 2026-07-11 (create 201, update 200, delete 204, baseline
restored). Dial-number writes have a hard constraint — see below.

## Use when / Do NOT use when

**Use when:** creating/updating/deleting entry points; changing a dial number's mapping.

**Do NOT use when:**
- Listing/finding EPs or DNs → **wxcc-entry-points**.
- Auth errors or missing write scope → **wxcc-connect**.
- "Add a brand-new phone number" → **not possible here**: numbers must already exist in
  the Webex Calling location inventory (Control Hub / Calling admin owns provisioning).

## Safety rules

Same non-negotiables as **wxcc-teams-write**: confirm before every write, name the
rollback first (delete is effectively irreversible), verify after with a read, expect 403
without `cjp:config_write`. EPs are routing infrastructure — a mistaken delete or repoint
breaks live call delivery immediately.

## Recipes — entry points

### Create an entry point

Required fields discovered by validation (400 names them if missing): `serviceLevelThreshold`
(> 0), `active`, `maximumActiveContacts` (>= 0), plus name/type/channel:

```bash
python wxcc.py post "organization/{orgId}/entry-point" --body '{"name":"EP-NAME","entryPointType":"INBOUND","channelType":"TELEPHONY","serviceLevelThreshold":20,"active":true,"maximumActiveContacts":0}'
```

→ verify: HTTP 201 with the object; **capture `id`**. Server defaults observed: `timezone`
(tenant default), `callbackEnabled: false`. `entryPointType` is `INBOUND` or `OUTBOUND`
(both observed live). A new EP has no flow attached (`flowId` absent) — attach flows in
the admin portal; flow assignment via this API is untested (candidate).

### Update an entry point

Capture current state first (rollback), then PUT the full object with `id` in the body:

```bash
python wxcc.py get "organization/{orgId}/entry-point/EP-ID"    # capture prior state
python wxcc.py put "organization/{orgId}/entry-point/EP-ID" --body '{"id":"EP-ID","name":"EP-NAME","description":"...","entryPointType":"INBOUND","channelType":"TELEPHONY","serviceLevelThreshold":25,"active":true,"maximumActiveContacts":0,"timezone":"America/New_York"}'
```

→ verify: HTTP 200, then re-read to confirm (verified live: SLT + description change
persisted). Rollback = PUT the captured prior object back.

### Delete an entry point

```bash
python wxcc.py delete "organization/{orgId}/entry-point/EP-ID"
```

→ verify: HTTP 204, then `filter=name==...` on the v2 list returns 0. **No true rollback.**
Deleting an EP that still has dial numbers or flows attached is untested (candidate —
expect a 412-style refusal as seen on referenced skills); check `wxcc-entry-points`'s
DN→EP lookup and repoint/remove first.

## Recipes — dial numbers

### Repoint a number to a different entry point

DN update is a full-object PUT (shape verified live via an idempotent PUT, 200):

```bash
python wxcc.py get "organization/{orgId}/dial-number/DN-ID"    # capture prior state
python wxcc.py put "organization/{orgId}/dial-number/DN-ID" --body '{"id":"DN-ID","dialledNumber":"+15551234567","entryPointId":"NEW-EP-ID","defaultAni":false,"location":"LOCATION-ID","regionId":"REGION-ID"}'
```

Copy `location`/`regionId`/`defaultAni` unchanged from the GET. Changing `entryPointId` to
a different EP is the one field you'd edit — that specific change is untested (candidate);
the PUT contract itself is verified. Verify with a re-read; rollback = PUT the prior body.

### Map a number to an EP (create a DN record)

```bash
python wxcc.py post "organization/{orgId}/dial-number" --body '{"dialledNumber":"+15551234567","entryPointId":"EP-ID","location":"LOCATION-ID","regionId":"REGION-ID"}'
```

Field requirements verified by the live validation chain (missing `location` → 400,
then missing `regionId` → 400). The final gate: the number **must already exist in the
Calling location's inventory**, else HTTP **404 "Dialed number does not exist"**
(reproduced live). Copy `location`/`regionId` from a sibling DN at the same site.
Full 201 not yet observed — no free provisioned number in the sandbox (candidate).

### Delete a DN mapping — **candidate, destructive**

`DELETE organization/{orgId}/dial-number/DN-ID` is documented in Cisco's collection but
deliberately unprobed here (it would unmap a real number). Confirm emphatically first.

## Traps (observed live, 2026-07-11)

| Item | Detail |
|---|---|
| Fictional/unprovisioned number on DN create | HTTP **404** (not 400) "Dialed number does not exist" |
| Missing EP required fields | 400 names each one — read `reason` before retrying |
| Write paths have no `v2` | POST/PUT/DELETE on `organization/{orgId}/entry-point[/{id}]`, `.../dial-number[/{id}]` |
| DN PUT is full-replace | Send every field from the GET, not just the change |

## Provenance and maintenance

EP create/update/delete run live on a us1 sandbox 2026-07-11 (201/200/204, probe object
removed). DN: required-field chain + inventory 404 reproduced live; idempotent PUT 200
verified; create-201/delete unprobed (candidates). Re-verify with a `zz-` named EP cycle.
