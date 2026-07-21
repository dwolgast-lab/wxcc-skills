#!/usr/bin/env python3
"""wxcc_mcp - MCP server exposing Webex Contact Center admin config as tools.

Wraps `wxcc.py` (stdlib-only core) with a small tool surface. The knowledge the
skills learned by probing a live tenant lives in ENTITIES below as enforced code
rather than prose: which item paths drop `v2`, which fields a create actually
requires, which deletes get blocked by references.

Writes are dry-run by default. `confirm=True` executes, then RE-READS and diffs,
because this API can return 200 while silently ignoring a field.

Flows are deliberately absent: Cisco's flow-store MCP server owns those.

Run locally:  claude mcp add --transport stdio wxcc -- python mcp_server.py
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

from mcp.server.fastmcp import FastMCP

import wxcc

# Which tenant is this server process bound to? WXCC_PROFILE selects the config
# and token store; the LABEL and ALIASES are how a human refers to the tenant, so
# they go into the server's own identity and reach the model at tool-selection time.
_CFG = wxcc.load_config()
_PROFILE = wxcc.profile() or "default"
_LABEL = _CFG.get("WXCC_TENANT_LABEL") or _PROFILE
_ALIASES = _CFG.get("WXCC_TENANT_ALIASES") or ""

_IDENTITY = f"This server administers exactly ONE Webex Contact Center tenant: " \
            f"{_LABEL} (profile '{_PROFILE}')."
if _ALIASES:
    _IDENTITY += f" This tenant is also called: {_ALIASES}."
_IDENTITY += (" It CANNOT reach any other tenant. If the user names a different "
              "tenant, use that tenant's own wxcc-* server instead. Call "
              "wxcc_whoami to confirm which org you are talking to.")

mcp = FastMCP(f"wxcc-{_PROFILE}", instructions=_IDENTITY)


# --------------------------------------------------------------------------- #
# Entity registry - every fact below was confirmed against a live tenant.
#   list   : collection path (v2)
#   item   : item path. NOT uniform - most entities drop `v2` here (v2 -> 404).
#   create : fields a POST requires. Absent ones come back as a 400 naming them.
#   writes : which verbs are proven. Anything absent is unproven, not forbidden.
# --------------------------------------------------------------------------- #
ENTITIES: dict[str, dict[str, Any]] = {
    "user": {
        "list": "v2/user", "item": "user/{id}",
        "writes": ["update"],
        "note": "Users are created/deleted in Control Hub, not here. Identity "
                "fields (firstName/lastName/email) are immutable via this API. "
                "`userLevelSummariesInclusion` is SILENTLY IGNORED on a 200 (confirmed "
                "again 2026-07-16 with a valid value) - likely entitlement-gated. Its "
                "accepted values are EXCLUDED | NOT_APPLICABLE | INCLUDED; anything else "
                "is a clean 400 naming the enum.",
    },
    "team": {
        "list": "v2/team", "item": "team/{id}",
        "create": ["name", "active", "siteId", "teamStatus", "teamType"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "team/bulk"},
            "delete": {"method": "POST", "tail": "team/bulk"},
        },
        "note": "Bulk has NO update: an id-bearing SAVE item returns 400 \"New "
                "configuration cannot have an id\" (same as outdial-ani). Use "
                "wxcc_update per team.",
    },
    "site": {
        "list": "v2/site", "item": "site/{id}",
        "create": ["name", "active", "multimediaProfileId"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "site/bulk"},
            "delete": {"method": "POST", "tail": "site/bulk"},
        },
        "note": "All three create fields are REQUIRED (a 400 names them). Copy "
                "multimediaProfileId from an existing site. Deleting a site that "
                "teams or users still reference is pre-flighted and blocked - repoint "
                "them first (team.siteId via wxcc_update; user.siteId is a candidate).",
    },
    "contact-service-queue": {
        "list": "v2/contact-service-queue", "item": "contact-service-queue/{id}",
        "create": ["name", "queueType", "channelType", "serviceLevelThreshold",
                   "maxActiveContacts", "maxTimeInQueue", "active", "routingType",
                   "monitoringPermitted", "parkingPermitted", "recordingPermitted",
                   "recordingAllCallsPermitted", "pauseRecordingPermitted"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "contact-service-queue/v2/bulk"},
            "update": {"method": "PATCH", "tail": "contact-service-queue/bulk", "partial": True},
            "delete": {"method": "POST", "tail": "contact-service-queue/v2/bulk"},
        },
        "note": "The queue entity is `contact-service-queue`; `/queue` 404s. The "
                "five *Permitted booleans are REQUIRED on create, not defaulted.",
    },
    "entry-point": {
        "list": "v2/entry-point", "item": "entry-point/{id}",
        "create": ["name", "entryPointType", "channelType", "serviceLevelThreshold",
                   "active", "maximumActiveContacts"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "entry-point/bulk"},
            "update": {"method": "POST", "tail": "entry-point/bulk", "partial": False},
            "delete": {"method": "POST", "tail": "entry-point/bulk"},
        },
    },
    "dial-number": {
        "list": "v2/dial-number", "item": "dial-number/{id}",
        "create": ["dialledNumber", "entryPointId", "location", "regionId"],
        "writes": ["create", "update"],
        "bulk": {
            "create": {"method": "POST", "tail": "dial-number/bulk"},
            "update": {"method": "POST", "tail": "dial-number/bulk", "partial": False},
        },
        "note": "Field is `dialledNumber` (double L). Numbers CANNOT be invented: "
                "create 404s with 'Dialed number does not exist' unless the number "
                "is already in the Webex Calling location inventory. Filter/search "
                "with a raw '+' works here (the tool URL-encodes values); only the "
                "CLI path still needs dialledNumberDigits==. DELETE is unprobed "
                "and would unmap a live number - so bulk delete is deliberately NOT "
                "exposed either (bulk is POST dial-number/bulk, create+update only; "
                "bulk update is read-modify-write, verified live via a no-op).",
    },
    "skill": {
        "list": "v2/skill", "item": "skill/{id}",
        "create": ["name", "active", "skillType", "serviceLevelThreshold"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "skill/bulk"},
            "delete": {"method": "POST", "tail": "skill/bulk"},
        },
        "note": "skillType ENUM additionally requires enumSkillValues:[{name}]. "
                "Deleting a skill still referenced by a profile returns 412 with "
                "referencedEntities - delete the profiles first. Bulk has NO "
                "update (400 \"New configuration cannot have an id\"); `skill/v2/bulk` "
                "404s - the route is `skill/bulk`.",
    },
    "skill-profile": {
        "list": "v2/skill-profile", "item": "skill-profile/{id}",
        "create": ["name"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "skill-profile/bulk"},
            "delete": {"method": "POST", "tail": "skill-profile/bulk"},
        },
        "note": "activeSkills entries are {skillId, booleanValue|proficiencyValue|"
                "textValue}. activeEnumSkills entries carry {enumSkillValueId} ONLY "
                "- adding skillId there returns HTTP 500. On update, every KEPT "
                "activeSkills entry must resend its own sub-entity `id` or you get "
                "409 duplicate-entry. At least one skill is mandatory on create "
                "(400 \"Atleast one skill is mandatory.\"). Bulk has NO update "
                "(400 \"New configuration cannot have an id\").",
    },
    "auxiliary-code": {
        "list": "v2/auxiliary-code", "item": "auxiliary-code/{id}",
        "create": ["active", "name", "workTypeCode", "defaultCode", "workTypeId"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "auxiliary-code/bulk"},
            "update": {"method": "PATCH", "tail": "auxiliary-code/bulk", "partial": True},
            "delete": {"method": "POST", "tail": "auxiliary-code/bulk"},
        },
        "note": "workTypeId is not derivable - copy it from an existing code with "
                "the same workTypeCode (WRAP_UP_CODE or IDLE_CODE). The `work-type` "
                "entity itself is DEPRECATED/obsolete in WxCC - do NOT register it "
                "here just because this id references it.",
    },
    "address-book": {
        "list": "v2/address-book", "item": "address-book/{id}",
        "create": ["name", "parentType"],
        "writes": ["create", "update", "delete"],
        "child": "entry",
        "child_create": ["name", "number"],
        "note": "Entries are a sub-resource. Use the wxcc_*_entry tools to touch one "
                "entry at a time rather than replacing the whole array - safer, and it "
                "avoids the kept-entry-needs-its-id 409. Entries can also be embedded at "
                "book creation via addressBookEntries.",
    },
    "outdial-ani": {
        "list": "v2/outdial-ani", "item": "outdial-ani/{id}",
        "create": ["name", "outdialANIEntries"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "outdial-ani/bulk"},
            "delete": {"method": "POST", "tail": "outdial-ani/bulk"},
        },
        "child": "entry",
        "child_create": ["name", "number"],
        "note": "To add/change/remove ONE number use the wxcc_*_entry tools "
                "(outdial-ani/{id}/entry) - targeted and safe. Updating the parent's "
                "outdialANIEntries array instead is a FULL REPLACE: an omitted entry is "
                "DELETED, and every kept entry must resend its own `id` or you get 409 "
                "duplicate-entry. Number ownership is NOT validated - a fictional ANI is "
                "accepted and fails on real calls.",
    },
    "agent-profile": {
        "list": "v2/agent-profile", "item": "agent-profile/{id}",
        "create": ["name"],
        "writes": ["create", "update", "delete"],
        "clone_safe": False,
        "bulk": {
            "create": {"method": "POST", "tail": "agent-profile/bulk"},
            "delete": {"method": "POST", "tail": "agent-profile/bulk"},
        },
        "note": "This is a DESKTOP PROFILE. The `agent-profile` path is backwards "
                "compatibility only - always say 'Desktop Profile' to the user. "
                "CREATE BY CLONING an existing profile, but STRIP EVERY NESTED `id` "
                "first - `viewableStatistics` is a dict carrying its own id, and "
                "reusing it returns 409 'Internal error. Please contact Cisco Support "
                "Team', which names nothing. wxcc_create strips them for you. "
                "Several fields are PAIRED and must move together: autoWrapAfterSeconds "
                "alone is a 400 ('should be specified when autoWrapUp is true') - send "
                "autoWrapUp with it. The access* fields are ALL/SPECIFIC switches paired "
                "with id lists - reading the list alone misleads when the switch says "
                "ALL, and flipping one without the other is likely the same shape. "
                "dialPlanEnabled/dialPlans still appear but Dial Plan is DEPRECATED in "
                "WxCC - ignore them. A profile is referenced by users, so a bad change "
                "hits every agent on it at next login. BULK create refuses a "
                "systemDefault clone with 403 'User not Allowed to create system default "
                "entity' - the stock profiles are ALL systemDefault, so send "
                "systemDefault=false (verified live 2026-07-21).",
    },
    "desktop-layout": {
        "list": "v2/desktop-layout", "item": "desktop-layout/{id}",
        "create": ["name", "jsonFileName", "jsonFileContent",
                   "defaultJsonModified", "status", "editedBy"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "desktop-layout/bulk"},
            "delete": {"method": "POST", "tail": "desktop-layout/bulk"},
        },
        "note": "jsonFileContent is the ENTIRE layout JSON as an embedded string "
                "(~20KB), and only appears on the item GET, not the list. It is NOT "
                "validated at POST - a malformed layout fails at agent-desktop load. "
                "Never modify the systemDefault Global Layout. The team-scoping field "
                "is `teamIds` plus a `global` boolean; cloning a global layout gives a "
                "MISLEADING 400 naming 'Teams assigned ... already assigned to another "
                "desktop layout' even though the payload has no teams key at all - a "
                "global layout implicitly claims every team. Send global=false and "
                "teamIds=[] (verified live 2026-07-21).",
    },
    "multimedia-profile": {
        "list": "v2/multimedia-profile", "item": "multimedia-profile/{id}",
        "create": ["name", "active", "telephony", "chat", "email", "social",
                   "blendingMode", "blendingModeEnabled", "manuallyAssignable"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "multimedia-profile/bulk"},
            "delete": {"method": "POST", "tail": "multimedia-profile/bulk"},
        },
        "note": "This is what a site's `multimediaProfileId` points at. The per-channel "
                "integers (telephony/chat/email/social/...) are concurrent-contact caps, "
                "not booleans. blendingMode is BLENDED | BLENDED_REALTIME | EXCLUSIVE; "
                "manuallyAssignable is a REQUIRED nested {channel:int} object. "
                "WORKITEM TRAP: the API returns `workItem` (top-level AND inside "
                "manuallyAssignable) on GET but REJECTS it on PUT when the workItem "
                "feature flag is off (400 'workItem is not allowed when feature flag is "
                "disabled'). wxcc_update strips exactly the field the API names and "
                "retries, so a read-modify-write update still works; the stripped field "
                "is reported. Delete is reference-blocked by sites (pre-flight). "
                "Item/create paths drop v2 (v2/.../{id} 404s), like team/site/user.",
    },
    "cad-variable": {
        "list": "v2/cad-variable", "item": "cad-variable/{id}",
        "create": ["name", "variableType", "defaultValue", "active",
                   "agentEditable", "agentViewable", "reportable"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "cad-variable/bulk"},
            "update": {"method": "POST", "tail": "cad-variable/bulk", "partial": False},
            "delete": {"method": "POST", "tail": "cad-variable/bulk"},
        },
        "note": "This is the WxCC 'Global Variables' entity (the API name is "
                "cad-variable). defaultValue MUST be valid for the variableType (a 400 "
                "says validDefaultValueForVariabelType; the sample tenant used "
                "variableType 'String'). The seven create fields above are each required "
                "(named by a 400); additionally agentViewable=true requires desktopLabel. "
                "Item/create paths drop v2. Bulk create/update/delete all POST "
                "cad-variable/bulk (update is read-modify-write; no partial route).",
    },
    "user-profile": {
        "list": "v3/user-profile", "item": "v3/user-profile/{id}",
        "create": ["name", "profileType", "permissionAccessLevel",
                   "resourceAccessLevel", "active"],
        "writes": ["create", "update", "delete"],
        "clone_safe": False,
        "bulk": {
            "create": {"method": "POST", "tail": "v3/user-profile/bulk"},
            "update": {"method": "POST", "tail": "v3/user-profile/bulk", "partial": False},
            "delete": {"method": "POST", "tail": "v3/user-profile/bulk"},
        },
        "note": "THE ONLY ENTITY WHOSE ITEM PATH KEEPS ITS VERSION PREFIX. v2 and v3 "
                "are DIFFERENT SCHEMAS and both answer: `user-profile/{id}` returns the "
                "OLD v2 shape (accessAll*/userProfileAppModules), `v3/user-profile/{id}` "
                "the current one (permissionAccessLevel/resourceAccessLevel/permissions/"
                "resourceCollections). v2 WRITES ARE DECOMMISSIONED per-org (400 'v2 user "
                "profile is decommissioned for this organization'), so everything here is "
                "v3. permissionAccessLevel must be SPECIFIC for ADMINISTRATOR_ONLY and "
                "STANDARD_AGENT, which then REQUIRES the permission list - and that list's "
                "key on write is `permissions` [{name, access}], NOT the "
                "`userProfilePermissions` the API's own 400 names (sending that key is "
                "silently treated as absent). Sub-entity ids must be stripped when cloning "
                "(a full copy returns 409 'Internal error'). LIST OMITS `permissions` - "
                "read the item. systemDefault=true objects cannot be modified.",
    },
    "business-hours": {
        "list": "v2/business-hours", "item": "business-hours/{id}",
        "create": ["name", "timezone", "workingHours"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "business-hours/bulk"},
            "delete": {"method": "POST", "tail": "business-hours/bulk"},
        },
        "note": "Entity name is PLURAL. `workingHours` must be NON-EMPTY (400 'Working "
                "hours cannot be empty') - entries are {name, days:[MON..SUN], startTime, "
                "endTime} with 24h 'HH:MM' times and 3-letter UPPERCASE days. `timezone` is "
                "an IANA name (e.g. America/Chicago). `holidaysId` is a REFERENCE to a "
                "holiday-list - GET holiday-list/{holidaysId} resolves it (verified). "
                "Item path drops v2; the bare `business-hours` list alias returns a BARE "
                "LIST, while v2/business-hours returns {data:[...]}. Bulk is create+delete; "
                "no bulk update (400 id-wall, PATCH 405). Verified live 2026-07-21.",
    },
    "holiday-list": {
        "list": "v2/holiday-list", "item": "holiday-list/{id}",
        "create": ["name", "holidays"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "holiday-list/bulk"},
            "delete": {"method": "POST", "tail": "holiday-list/bulk"},
        },
        "note": "`holidays` must be NON-EMPTY (400 'Holiday list cannot be empty'). Entries "
                "are {name, startDate, endDate, frequency, recurrence:{interval, daysOfWeek, "
                "specificDayOfMonth, specificMonth}} with ISO 'YYYY-MM-DD' dates. Unlike "
                "business-hours and overrides this entity does NOT require `timezone` "
                "(create with name+holidays alone returns 201 - verified). Referenced by "
                "business-hours.holidaysId. Bulk is create+delete; no bulk update (400 "
                "id-wall, PATCH 405). Verified live 2026-07-21.",
    },
    "overrides": {
        "list": "v2/overrides", "item": "overrides/{id}",
        "create": ["name", "timezone", "overrides"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "overrides/bulk"},
            "delete": {"method": "POST", "tail": "overrides/bulk"},
        },
        "note": "Entity name is PLURAL and its own payload key is also `overrides` - the "
                "array must be NON-EMPTY (400 'Overrides cannot be empty'). Entries are "
                "{name, startDateTime, endDateTime, workingHours:bool, frequency, "
                "recurrence:{interval, daysOfWeek}} with 'YYYY-MM-DDTHH:MM' datetimes (no "
                "seconds, no zone - the record's `timezone` supplies it). `timezone` IS "
                "required here even though holiday-list does not need it. Bulk is "
                "create+delete; no bulk update (400 id-wall, PATCH 405). Verified live "
                "2026-07-21.",
    },
    "contact-number": {
        "list": "v2/contact-number", "item": "contact-number/{id}",
        "create": ["number"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "create": {"method": "POST", "tail": "contact-number/bulk"},
            "delete": {"method": "POST", "tail": "contact-number/bulk"},
        },
        "note": "PURPOSE: the caller-ID value shown on INTERNAL calls (per the tenant "
                "admin 2026-07-21 - stated, not API-verified). Despite the name this is "
                "NOT the dial-number/DID inventory and nothing links the two. `number` is "
                "the ONLY required field and is capped at 9 CHARACTERS - not E.164 (a "
                "'+1...' value returns 400 'should not be more than 9 characters'). "
                "`contact-number/all-numbers` is a real route but returns a BARE LIST OF "
                "STRINGS (['5551234']), not objects - it is a convenience projection and "
                "must NOT be used as the list path; v2/contact-number returns the "
                "{data:[...]} objects. PUT requires the `id` IN THE PAYLOAD matching the "
                "URL (400 'Invalid id: id in payload and URL should be same') - "
                "wxcc_update read-modify-writes, so it already sends it. Bulk is "
                "create+delete on contact-number/bulk; no bulk update (400 'New "
                "configuration cannot have an id', PATCH 405). Import/export exist at "
                "contact-number/import|export on **PUT** (GET 404s) - payload shape is "
                "UNPROBED. All verified live 2026-07-21.",
    },
    "resource-collection": {
        "list": "v2/resource-collection", "item": "resource-collection/{id}",
        "create": ["name", "resources"],
        "writes": ["create", "update", "delete"],
        "bulk": {
            "update": {"method": "PATCH", "tail": "resource-collection/bulk",
                       "partial": False},
        },
        "note": "Scoped-access grouping referenced by user-profile.resourceCollections. "
                "`resources` must list ALL 20 resource types - a partial list is a 400 "
                "naming the missing ones, and OMITTING the key entirely is a bare 500. "
                "Each entry is {name, accessLevel: NONE|SPECIFIC|ALL, ids:[]}; site, "
                "channel, team and queue must NOT be NONE. LIST OMITS `resources` - read "
                "the item. Bulk is UPDATE-ONLY and on PATCH: bulk create returns 500 'no "
                "mapping for id' and requestAction DELETE is rejected outright (400, "
                "'should be empty or specified as SAVE for PATCH'). Despite being a PATCH "
                "route it is NOT partial - an item without the full `resources` array "
                "500s on a leaked Java NPE, so the tool read-modify-writes.",
    },
}


def _find_references(client: wxcc.WxccClient, entity: str, target: str) -> list[dict]:
    """Who points at this object, straight from the API.

    `GET <entity>/{id}/incoming-references` is authoritative and exists on every
    config entity (verified on 10). It replaced a client-side scan over a
    hand-written map of relationships - which was slow, mostly inferred, and
    provably incomplete: it knew a team was referenced by users but not by a
    queue's callDistributionGroups.

    Read it carefully. The response covers ONE entity type at a time:
      meta.referencedEntities -> every type that points here
      meta.currentEntity      -> the only type in this response's data[]
    So `?type=<each>` must be walked, or you report the first type's blockers and
    silently miss the rest. `meta.totalPages` counts pages WITHIN the current
    type, while a bare `?page=N` walks ACROSS types - do not conflate them.
    """
    root = f"organization/{{orgId}}/{entity}/{target}/incoming-references"
    try:
        status, body = client.json("GET", root)
    except Exception as exc:
        return [{"scan_failed": f"{exc}"}]        # never let a failure read as "clean"
    if status == 404:
        return []
    if status >= 400 or not isinstance(body, dict):
        return [{"scan_failed": f"HTTP {status}: {str(body)[:120]}"}]

    types = (body.get("meta") or {}).get("referencedEntities") or []
    hits: list[dict] = []
    for ref_entity in types:
        page = 0
        while True:
            status, doc = client.json("GET", f"{root}?type={ref_entity}&page={page}"
                                            "&pageSize=100")
            if status >= 400 or not isinstance(doc, dict):
                hits.append({"entity": ref_entity,
                             "scan_failed": f"HTTP {status}"})
                break
            meta = doc.get("meta") or {}
            # Guard: if the API ignores ?type= it echoes a different currentEntity.
            # Trust what it says it returned, not what we asked for.
            actual = meta.get("currentEntity") or ref_entity
            hits += [{"entity": actual, "id": r.get("id"),
                      "name": r.get("name") or r.get("id")}
                     for r in (doc.get("data") or [])]
            page += 1
            if page >= (meta.get("totalPages") or 1) or page > 50:
                break
    return hits


def _entity(name: str) -> dict[str, Any]:
    if name not in ENTITIES:
        raise ValueError(
            f"unknown entity {name!r}. Known: {', '.join(sorted(ENTITIES))}. "
            "Flows are NOT here - use the flow-store MCP server."
        )
    return ENTITIES[name]


def _client() -> wxcc.WxccClient:
    """Where the token comes from depends on how this server is being run.

    Over HTTP (Cloud Run) the CALLER authenticated to Webex themselves and their
    token is on the request - this process stores no credentials and is
    tenant-agnostic; the token decides the org. Over stdio (local) there is no
    request, so fall back to this machine's token store for WXCC_PROFILE.
    """
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
        access = get_access_token()
    except Exception:
        access = None

    if access is not None:
        return wxcc.WxccClient(
            _CFG.get("WXCC_API_BASE", "https://api.wxcc-us1.cisco.com"),
            access.token,
        )
    return wxcc.client_from_store(wxcc.load_config())


# Cache: org identity is immutable for the life of a token, and every tool call
# stamps it, so this must not cost an API round-trip each time.
_org_cache: dict[str, dict] = {}


def _org_info(client: wxcc.WxccClient) -> dict:
    """The tenant's OWN name, straight from `GET organization/{orgId}`.

    Authoritative on purpose: a configured label can drift or be copied to the
    wrong profile, and on Cloud Run there is no config at all. Asking the tenant
    who it is cannot lie. `subscriptionType` distinguishes a paying customer's
    org from a trial/sandbox without anyone having to declare it.
    """
    org_id = client.org_id
    if not org_id:
        # Without an org id there is nothing to ask and nothing to cache: the
        # request would go to `organization/None` and 404. Say so instead.
        return {"name": "(org id unresolved)", "org_id": None, "production": None}
    if org_id in _org_cache:
        return _org_cache[org_id]
    try:
        status, body = client.json("GET", f"organization/{org_id}")
    except Exception:
        status, body = 0, None
    if status != 200 or not isinstance(body, dict):
        return {"name": "(org name unavailable)", "org_id": org_id,
                "production": None}
    info = {
        "name": body.get("name"),
        "org_id": org_id,
        "subscription": body.get("subscriptionType"),
        "environment": body.get("environment"),
        # A paying subscription is a real customer tenant. Trials are sandboxes.
        "production": body.get("subscriptionType") == "SUBSCRIPTION",
    }
    _org_cache[org_id] = info
    return info


def _tenant(client: wxcc.WxccClient) -> str:
    """One line naming exactly which tenant a result came from / would change."""
    i = _org_info(client)
    if i.get("production") is None:
        return f"{i['name']} (org {i['org_id']})"
    tag = "PRODUCTION" if i["production"] else "trial/sandbox"
    return f"{i['name']} [{tag}] (org {i['org_id']})"


def _path(entity: str, item_id: str | None = None, write: bool = False) -> str:
    """List (GET) uses the v2 path; item AND create-collection paths drop v2.

    This is not cosmetic - GET v2/team lists, but POST v2/team is not the create
    endpoint. Confirmed across every entity in the skills.
    """
    spec = _entity(entity)
    if item_id:
        tail = spec["item"].replace("{id}", item_id)
    elif write:
        tail = spec["item"].replace("/{id}", "")
    else:
        tail = spec["list"]
    return f"organization/{{orgId}}/{tail}"


def _strip(obj: dict) -> dict:
    """Drop server-generated link blocks that a PUT must not echo back."""
    return {k: v for k, v in obj.items() if k not in ("links", "_links")}


def _strip_nested_ids(obj: Any) -> Any:
    """Remove every `id` below the top level.

    A sub-entity id belongs to the object it was read from. Re-sending one while
    CREATING a different object collides, and this API reports that badly: 409
    "Internal error. Please contact Cisco Support Team" (agent-profile, via the
    viewableStatistics dict), 409 duplicate-entry (outdial-ani entries), or a
    bare 500 (skill-profile activeEnumSkills). Same cause, three error shapes.
    """
    if isinstance(obj, dict):
        return {k: _strip_nested_ids(v) for k, v in obj.items() if k != "id"}
    if isinstance(obj, list):
        return [_strip_nested_ids(i) for i in obj]
    return obj


def _as_dict(body: object) -> dict:
    """A parsed response body as a dict, or {} if it is any other shape.

    `client.json` returns whatever parsed - dict, list, bare string, or None - so
    a naive `.get()` on it is an AttributeError waiting for the right response.
    That is not hypothetical: a 4xx carrying `error` as a bare string already
    crashed one call chain (see _api_reason). Use this wherever a body is read
    for a field WITHOUT an isinstance check first.
    """
    return body if isinstance(body, dict) else {}


def _read(client: wxcc.WxccClient, entity: str, item_id: str) -> dict:
    status, body = client.json("GET", _path(entity, item_id))
    if status >= 400:
        raise ValueError(f"cannot read {entity}/{item_id}: HTTP {status} {body}")
    if not isinstance(body, dict):
        raise ValueError(f"cannot read {entity}/{item_id}: expected a JSON object, "
                         f"got {type(body).__name__}: {str(body)[:120]}")
    return body


# A read-modify-write PUT re-sends every field the GET returned - including ones
# this tenant is not entitled to write, which the API returns on GET but rejects
# on PUT with "<field> is not allowed when feature flag is disabled" (seen on
# multimedia-profile.workItem, at the top level AND nested in manuallyAssignable,
# when the workItem feature flag is off). Whether a field is writable is
# tenant-state, not contract, so this is discovered per call, not hardcoded: a
# flag-ENABLED tenant's first PUT succeeds and nothing is stripped.
_FLAG_DENY = re.compile(r"(\w+) is not allowed when feature flag is disabled")


def _drop_key(obj: Any, key: str) -> Any:
    """Remove `key` at every nesting level."""
    if isinstance(obj, dict):
        return {k: _drop_key(v, key) for k, v in obj.items() if k != key}
    if isinstance(obj, list):
        return [_drop_key(i, key) for i in obj]
    return obj


def _api_reason(body: Any) -> str:
    """The API's own failure reason, whatever shape the error body arrived in.

    Usually {"error": {"reason": "..."}}, but a 4xx can carry `error` as a bare
    string - which crashed a naive .get() chain. Anything unrecognized is
    stringified rather than dropped, so the reason still reaches the caller.
    """
    if not isinstance(body, dict):
        return str(body) if body else ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("reason") or "")
    return str(err) if err else ""


def _put_adaptive(client: wxcc.WxccClient, path: str, body: dict) -> tuple[int, Any, list[str]]:
    """PUT; if the API rejects a field ONLY because its feature flag is off, drop
    exactly that field (at any depth) and retry. Returns (status, body, stripped).
    Strips nothing on any other error, and never the same field twice."""
    status, out = client.json("PUT", path, body)
    stripped: list[str] = []
    while status >= 400 and isinstance(out, dict):
        m = _FLAG_DENY.search(_api_reason(out))
        if not m or m.group(1) in stripped:
            break
        body = _drop_key(body, m.group(1))
        stripped.append(m.group(1))
        status, out = client.json("PUT", path, body)
    return status, out, stripped


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def wxcc_whoami() -> dict:
    """Check the WxCC connection: org id, API host, token validity, granted scopes.

    Run this first when anything looks like an auth problem.
    """
    tok = wxcc.load_tokens()      # None when running over HTTP - no local store
    remote = tok is None

    if remote:
        try:
            client = _client()    # token rides on the request
        except Exception as exc:
            return {"authenticated": False, "transport": "http",
                    "error": str(exc),
                    "fix": "run /mcp (or `claude mcp login <server>`) to sign in "
                           "to Webex as an admin of the tenant you want"}
    else:
        client = _client()

    status, _ = client.json("GET", _path("site") + "?pageSize=1")

    out: dict[str, Any] = {
        "authenticated": True,
        "org_id": client.org_id,
        "api_base": client.api_base,
        "live_read_check": f"HTTP {status}",
        "entities": sorted(ENTITIES),
    }

    if remote:
        # Nothing is stored here: the caller's own Webex token decides the org,
        # so there are no profiles to compare and no configured label to read.
        # The tenant's own record is the only source of truth available - and the
        # better one, since it cannot drift from what the token actually reaches.
        info = _org_info(client)
        out |= {
            "transport": "http (per-caller Webex OAuth; server stores no tokens)",
            "tenant": _tenant(client),
            "production": info.get("production"),
            "note": "This is the tenant YOUR token reaches. Confirm it is the one "
                    "you meant before writing.",
        }
        return out

    # Local: two profiles resolving to the same org means one authenticated to
    # the wrong tenant (the browser reused an existing Webex session). Surface it
    # here, not after someone has already written to the wrong place.
    others = {p: o for p, o in wxcc.all_profile_orgs().items()
              if o == client.org_id and p not in (_PROFILE, "(default)" if _PROFILE == "default" else "")}
    granted = tok.get("granted_scopes") or ""
    out |= {
        "transport": "stdio (local token store)",
        "tenant": _LABEL,
        "aliases": _ALIASES or None,
        "profile": _PROFILE,
        "granted_scopes": granted or "(not reported by Webex)",
        "write_capable": "cjp:config_write" in granted,
        "WRONG_TENANT_WARNING": (
            f"Profile '{_PROFILE}' shares org {client.org_id} with {list(others)}. "
            "One of them authenticated to the wrong tenant. Do NOT write until fixed."
        ) if others else None,
    }
    return out


@mcp.tool()
def wxcc_list(entity: str, filter: str = "", search: str = "",
              attributes: str = "", page_size: int = 100,
              all_pages: bool = False) -> dict:
    """List a WxCC config entity (team, contact-service-queue, entry-point, ...).

    entity     : one of the registry keys. Call wxcc_whoami to see them all.
    filter     : FIQL, e.g. `name==Sales`. Pass RAW characters - this tool
                 URL-encodes for transport, so `+` and spaces are safe here.
                 SINGLE-quote a value containing a space (`name=='Inside Sales'`)
                 - that is RSQL syntax, not encoding. Raw double quotes are
                 rejected before RSQL ever parses them.
    search     : substring match across fields. Raw characters; spaces and '+'
                 are fine.
    attributes : projection, e.g. `id,name,active`.
    all_pages  : follow pagination to exhaustion.
    """
    spec = _entity(entity)
    client = _client()
    q = [f"pageSize={page_size}"]
    # Encode values for transport: a raw '+' otherwise decodes server-side to a
    # space (silent 0 rows), and a raw space is refused by urllib outright.
    # FIQL syntax characters stay literal in filter; search is opaque.
    for key, val, safe in (("filter", filter, "=!<>;,()'*~"),
                           ("search", search, ""),
                           ("attributes", attributes, ",")):
        if val:
            q.append(f"{key}={urllib.parse.quote(val, safe=safe)}")
    path = _path(entity) + "?" + "&".join(q)

    if all_pages:
        records, pages = client.list_all(path)
        return {"tenant": _tenant(client), "entity": entity,
                "totalRecords": len(records), "pagesFetched": pages,
                "data": records, "note": spec.get("note")}
    status, body = client.json("GET", path)
    if status >= 400:
        return {"error": f"HTTP {status}", "body": body}
    doc = _as_dict(body)
    return {"tenant": _tenant(client), "entity": entity, "meta": doc.get("meta"),
            "data": doc.get("data"), "note": spec.get("note")}


@mcp.tool()
def wxcc_get(entity: str, id: str) -> dict:
    """Read one WxCC config object by id. Returns the full object."""
    spec = _entity(entity)
    client = _client()
    obj = _read(client, entity, id)
    return {"tenant": _tenant(client), "entity": entity, "data": obj,
            "note": spec.get("note")}


@mcp.tool()
def wxcc_references(entity: str, id: str) -> dict:
    """What points AT this object? Answers "what breaks if I change or delete it".

    The same scan wxcc_delete runs as its pre-flight, exposed on its own so the
    question can be asked about an object you intend to KEEP - no write attempted.

    The object itself is read first on purpose: a bad id makes the references
    endpoint 404, which would otherwise return an empty list and read as "nothing
    points here" - the most dangerous wrong answer this tool could give.
    """
    client = _client()
    obj = _read(client, entity, id)      # raises on a bad id, so empty means empty
    hits = _find_references(client, entity, id)

    groups: dict[str, list[dict]] = {}
    for h in hits:
        if h.get("scan_failed"):
            continue
        groups.setdefault(h["entity"], []).append({"id": h["id"], "name": h["name"]})

    return {
        "tenant": _tenant(client),
        "entity": entity, "id": id, "name": obj.get("name"),
        "referenced_by": groups,
        "total": sum(len(v) for v in groups.values()),
        "scan_failed": [h for h in hits if h.get("scan_failed")] or None,
        "note": "Empty referenced_by means nothing points here and a delete would "
                "not be reference-blocked. A non-empty scan_failed means the scan "
                "is INCOMPLETE - do not read it as clean.",
    }


# --------------------------------------------------------------------------- #
# Write tools - dry-run by default, re-read after every confirmed write.
# --------------------------------------------------------------------------- #
@mcp.tool()
def wxcc_create(entity: str, fields: dict, confirm: bool = False) -> dict:
    """Create a WxCC config object.

    With confirm=False (default) this WRITES NOTHING: it validates the required
    fields and returns a preview plus the rollback. Show that preview to the user
    and get an explicit yes before calling again with confirm=True.
    """
    spec = _entity(entity)
    if "create" not in spec.get("writes", []):
        return {"refused": f"create is not supported/proven for {entity}",
                "why": spec.get("note", "")}

    missing = [f for f in spec.get("create", []) if f not in fields]
    if missing:
        return {"error": "missing required fields (the API would return a 400 "
                         "naming these)", "missing": missing,
                "required": spec.get("create"), "note": spec.get("note")}

    # Entities whose sub-objects carry ids cannot be created from a clone that
    # still holds them. Strip rather than let the caller hit an error that names
    # nothing (agent-profile answers 409 "Internal error. Contact Cisco Support").
    if spec.get("clone_safe") is False:
        cleaned = _strip_nested_ids(fields)
        if cleaned != fields:
            fields = cleaned

    if not confirm:
        return {"TENANT": _tenant(_client()), "dry_run": True,
                "action": f"POST {_path(entity, write=True)}",
                "would_create": fields, "note": spec.get("note"),
                "rollback": f"wxcc_delete(entity='{entity}', id=<new id>, confirm=True)",
                "next": "re-call with confirm=True once the user approves"}

    client = _client()
    status, body = client.json("POST", _path(entity, write=True), fields)
    if status >= 400:
        return {"created": False, "http": status, "error": body}
    new_id = _as_dict(body).get("id")
    verified = _read(client, entity, new_id) if new_id else None
    return {"TENANT": _tenant(client), "created": True, "http": status, "id": new_id,
            "verified_by_reread": verified,
            "rollback": f"wxcc_delete(entity='{entity}', id='{new_id}', confirm=True)"}


@mcp.tool()
def wxcc_update(entity: str, id: str, changes: dict, confirm: bool = False) -> dict:
    """Update a WxCC config object (read-modify-write full-object PUT).

    Reads the current object, merges `changes`, and PUTs the whole thing back -
    this API replaces, it does not patch.

    With confirm=False (default) this WRITES NOTHING: it returns a field-by-field
    diff and the rollback. After a confirmed write it RE-READS and reports any
    field the API silently ignored - a 200 here does not mean it changed.
    """
    spec = _entity(entity)
    if "update" not in spec.get("writes", []):
        return {"refused": f"update is not supported/proven for {entity}",
                "why": spec.get("note", "")}

    client = _client()
    current = _read(client, entity, id)
    proposed = _strip({**current, **changes})

    diff = {k: {"from": current.get(k), "to": v}
            for k, v in changes.items() if current.get(k) != v}
    if not diff:
        return {"no_op": True, "reason": "every requested value already matches"}

    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"PUT {_path(entity, id)}", "diff": diff, "note": spec.get("note"),
                "rollback": "wxcc_update with the original values shown under "
                            "'from' above",
                "next": "re-call with confirm=True once the user approves"}

    status, body, stripped = _put_adaptive(client, _path(entity, id), proposed)
    if status >= 400:
        return {"updated": False, "http": status, "error": body,
                "note": spec.get("note")}

    after = _read(client, entity, id)

    # Only SCALARS can be compared reliably. The server enriches sub-objects with
    # ids/timestamps and reorders arrays (seen on teamIds and outdialANIEntries),
    # so equality on a complex value reports a correct write as "ignored". A safety
    # check that cries wolf gets ignored, so say "unverified" instead of guessing.
    ignored, applied, unverified = {}, {}, {}
    for k, v in changes.items():
        got = after.get(k)
        if isinstance(v, (list, dict)):
            unverified[k] = got
        elif got != v:
            ignored[k] = {"requested": v, "actual": got}
        else:
            applied[k] = got

    return {
        "TENANT": _tenant(client),
        "updated": True, "http": status,
        "confirmed_changed": applied or None,
        "stripped_for_feature_flag": ({
            "fields": stripped,
            "why": "The tenant is not entitled to write these (feature flag off); "
                   "they were dropped from the PUT so the rest could apply. Harmless "
                   "unless the user asked to change one - then it shows as ignored.",
        } if stripped else None),
        "SILENTLY_IGNORED": ignored or None,
        "warning": ("The API returned 200 but did NOT apply the fields under "
                    "SILENTLY_IGNORED. Tell the user; do not report success.")
                   if ignored else None,
        "needs_your_eyes": {
            "fields": sorted(unverified),
            "actual": unverified,
            "why": "Complex values cannot be auto-verified: the server adds ids and "
                   "timestamps and may reorder arrays. Read 'actual' and confirm it "
                   "is what the user asked for.",
        } if unverified else None,
        "rollback": {k: v["from"] for k, v in diff.items()},
    }


@mcp.tool()
def wxcc_delete(entity: str, id: str, confirm: bool = False) -> dict:
    """Delete a WxCC config object. Effectively irreversible.

    With confirm=False (default) this WRITES NOTHING: it shows exactly what would
    be destroyed. Deletes are not undoable by an API call - recreating means
    rebuilding the object by hand, and the new object gets a NEW id, so anything
    referencing the old id stays broken.
    """
    spec = _entity(entity)
    if "delete" not in spec.get("writes", []):
        return {"refused": f"delete is not supported/proven for {entity}",
                "why": spec.get("note", "")}

    client = _client()
    current = _read(client, entity, id)

    # Pre-flight references. This BLOCKS the delete - in the dry run AND on a
    # confirmed call - so the user gets an actionable list of what to fix rather
    # than a bare 412 after the fact. The API's own 412 is still the backstop.
    refs = _find_references(client, entity, id)
    if refs:
        return {
            "TENANT": _tenant(client),
            "blocked": True,
            "reason": f"{len(refs)} object(s) still reference this {entity}. "
                      "The API would reject the delete with HTTP 412.",
            "conflicting_references": refs,
            "resolve_first": [
                f"{r['entity']} '{r['name']}' ({r.get('id')})"
                for r in refs if "scan_failed" not in r
            ],
            "scan_failures": [r for r in refs if "scan_failed" in r] or None,
            "how": "Repoint or clear each reference above, then retry the delete. "
                   "For a team, that means removing it from each user's teamIds.",
            "deleted": False,
        }

    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"DELETE {_path(entity, id)}", "would_destroy": current, "note": spec.get("note"),
                "no_blocking_references": True,
                "rollback": "NONE - a delete cannot be undone via the API. "
                            "Recreating produces a new id; references to the old "
                            "id will not be restored.",
                "next": "re-call with confirm=True only after an explicit yes"}

    status, body = client.json("DELETE", _path(entity, id))
    if status >= 400:
        # referencedEntities is nested under the `error` object, not top-level.
        # Confirmed live on a 412: {"error": {"referencedEntities": ["user"]}}.
        inner = body.get("error", {}) if isinstance(body, dict) else {}
        refs = inner.get("referencedEntities") if isinstance(inner, dict) else None
        return {"deleted": False, "http": status, "error": body,
                "blocked_by_references": refs,
                "hint": (f"HTTP 412: still referenced by {refs}. Repoint or remove "
                         "those first - for a team, that means clearing the team "
                         "from each user's teamIds.") if status == 412 else None}

    gone_status, _ = client.json("GET", _path(entity, id))
    return {"TENANT": _tenant(client), "deleted": True, "http": status,
            "verified_gone": gone_status == 404,
            "reread_status": gone_status}


# --------------------------------------------------------------------------- #
# Sub-resource entries (address-book, outdial-ani)
#
# Both entities keep their items in a child collection AND echo them back in an
# array on the parent. Editing that array is a full replace - omit an entry and
# it is deleted, keep one without its id and you get 409. These endpoints touch
# one entry at a time, so they avoid both. Prefer them.
# --------------------------------------------------------------------------- #
def _child_spec(entity: str) -> dict[str, Any]:
    spec = _entity(entity)
    if not spec.get("child"):
        raise ValueError(
            f"{entity} has no entry sub-resource. Entities with one: "
            + ", ".join(sorted(e for e, s in ENTITIES.items() if s.get("child")))
        )
    return spec


def _child_path(entity: str, parent_id: str, child_id: str | None = None) -> str:
    spec = _child_spec(entity)
    tail = f"{spec['item'].replace('{id}', parent_id)}/{spec['child']}"
    if child_id:
        tail += f"/{child_id}"
    return f"organization/{{orgId}}/{tail}"


def _parent_entries(client: wxcc.WxccClient, entity: str, parent_id: str) -> list:
    """Entries are readable only from the parent - GET on the child collection 405s."""
    parent = _read(client, entity, parent_id)
    for key in ("addressBookEntries", "outdialANIEntries", "entries"):
        if isinstance(parent.get(key), list):
            return parent[key]
    return []


@mcp.tool()
def wxcc_list_entries(entity: str, parent_id: str) -> dict:
    """List the entries inside one address-book or outdial-ani.

    Read from the parent object: the child collection has no GET (405).
    """
    _child_spec(entity)
    client = _client()
    entries = _parent_entries(client, entity, parent_id)
    return {"tenant": _tenant(client), "entity": entity, "parent_id": parent_id,
            "count": len(entries), "entries": entries}


@mcp.tool()
def wxcc_add_entry(entity: str, parent_id: str, fields: dict,
                   confirm: bool = False) -> dict:
    """Add ONE entry to an address-book or outdial-ani.

    Prefer this over updating the parent's entries array: it cannot delete the
    other entries by omission, and it has no sub-entity-id 409 trap.

    confirm=False (default) writes nothing and returns a preview.
    """
    spec = _child_spec(entity)
    missing = [f for f in spec.get("child_create", []) if f not in fields]
    if missing:
        return {"error": "missing required fields", "missing": missing,
                "required": spec.get("child_create")}

    client = _client()
    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"POST {_child_path(entity, parent_id)}",
                "would_add": fields,
                "existing_count": len(_parent_entries(client, entity, parent_id)),
                "note": spec.get("note"),
                "rollback": "wxcc_remove_entry with the returned entry id",
                "next": "re-call with confirm=True once the user approves"}

    status, body = client.json("POST", _child_path(entity, parent_id), fields)
    if status >= 400:
        return {"added": False, "http": status, "error": body}
    new_id = _as_dict(body).get("id")
    entries = _parent_entries(client, entity, parent_id)
    return {"TENANT": _tenant(client), "added": True, "http": status, "id": new_id,
            "verified_in_parent": any(e.get("id") == new_id for e in entries),
            "entries_now": [{k: e.get(k) for k in ("id", "name", "number")}
                            for e in entries],
            "rollback": f"wxcc_remove_entry(entity='{entity}', "
                        f"parent_id='{parent_id}', entry_id='{new_id}', confirm=True)"}


@mcp.tool()
def wxcc_update_entry(entity: str, parent_id: str, entry_id: str, changes: dict,
                      confirm: bool = False) -> dict:
    """Change ONE entry in an address-book or outdial-ani (read-modify-write)."""
    spec = _child_spec(entity)
    client = _client()
    current = next((e for e in _parent_entries(client, entity, parent_id)
                    if e.get("id") == entry_id), None)
    if current is None:
        return {"error": f"entry {entry_id} not found on {entity}/{parent_id}"}

    diff = {k: {"from": current.get(k), "to": v}
            for k, v in changes.items() if current.get(k) != v}
    if not diff:
        return {"no_op": True, "reason": "every requested value already matches"}

    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"PUT {_child_path(entity, parent_id, entry_id)}",
                "diff": diff, "note": spec.get("note"),
                "rollback": "wxcc_update_entry with the values shown under 'from'",
                "next": "re-call with confirm=True once the user approves"}

    body = {**_strip(current), **changes, "id": entry_id}
    status, resp = client.json("PUT", _child_path(entity, parent_id, entry_id), body)
    if status >= 400:
        return {"updated": False, "http": status, "error": resp}

    after = next((e for e in _parent_entries(client, entity, parent_id)
                  if e.get("id") == entry_id), {})
    ignored = {k: {"requested": v, "actual": after.get(k)}
               for k, v in changes.items()
               if not isinstance(v, (list, dict)) and after.get(k) != v}
    return {"TENANT": _tenant(client), "updated": True, "http": status,
            "confirmed_changed": {k: after.get(k) for k in changes if k not in ignored},
            "SILENTLY_IGNORED": ignored or None,
            "rollback": {k: v["from"] for k, v in diff.items()}}


@mcp.tool()
def wxcc_remove_entry(entity: str, parent_id: str, entry_id: str,
                      confirm: bool = False) -> dict:
    """Remove ONE entry from an address-book or outdial-ani. Not reversible."""
    _child_spec(entity)
    client = _client()
    current = next((e for e in _parent_entries(client, entity, parent_id)
                    if e.get("id") == entry_id), None)
    if current is None:
        return {"error": f"entry {entry_id} not found on {entity}/{parent_id}"}

    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"DELETE {_child_path(entity, parent_id, entry_id)}",
                "would_remove": current,
                "rollback": "NONE via the API - re-adding produces a NEW entry id",
                "next": "re-call with confirm=True only after an explicit yes"}

    status, body = client.json("DELETE", _child_path(entity, parent_id, entry_id))
    if status >= 400:
        return {"removed": False, "http": status, "error": body}
    entries = _parent_entries(client, entity, parent_id)
    return {"TENANT": _tenant(client), "removed": True, "http": status,
            "verified_gone": not any(e.get("id") == entry_id for e in entries),
            "entries_now": [{k: e.get(k) for k in ("id", "name", "number")}
                            for e in entries]}


# --------------------------------------------------------------------------- #
# Bulk writes (verified live on the sandbox 2026-07-20/21)
#
# ONE nested envelope, but the routes AND which ops exist are PER-ENTITY and NOT
# uniform, so each entity's `bulk` block lists only the ops proven for it:
#   contact-service-queue : create/delete POST .../v2/bulk ; update PATCH .../bulk (partial)
#   auxiliary-code        : create/delete POST .../bulk    ; update PATCH .../bulk (partial)
#   entry-point           : create/update/delete all POST .../bulk (update = read-modify-write)
#   cad-variable          : create/update/delete all POST .../bulk (update = read-modify-write)
#   dial-number           : create + update POST .../bulk  (NO delete - would unmap a live number)
#   outdial-ani           : create + delete POST .../bulk  (NO update - id-bearing item -> 400
#                           "New configuration cannot have an id"; use wxcc_update / entry tools)
# Body:  {"items": [{"itemIdentifier": <int>, "item": {...}, "requestAction": "SAVE"|"DELETE"}]}
#   The array key is `items`, but each element wraps the object under `item` and
#   carries a client-assigned `itemIdentifier` the response echoes back. Sending
#   {"items":[{id,...}]} without the `item` wrapper is a 400 ("item ... null or blank").
# Response: HTTP 207 ALWAYS; per item either {itemIdentifier, status, operationType,
#   href} on success or {itemIdentifier, status, apiError:{error:{reason}}} on failure.
# TRAPS, all reproduced live:
#   - A DELETE item (and, where there is no partial route, an UPDATE item) needs the FULL
#     object, not just {id}: an id-only delete returns a misleading 400 "Cannot
#     Update/Delete system generated Entities". The tools fetch the object for you.
#   - An empty response items[] means NOTHING matched - a 207 is NOT proof of a write.
#   - The API self-guards references PER ITEM: a still-referenced delete -> 412 (across
#     flows and dial-number mappings alike), and the rest of the batch still applies.
#   - System-generated entities cannot be updated/deleted (per-item 400).
#   - Routes are NOT uniform (some have /v2, some a PATCH partial route, some neither), so
#     every entity is probed before it gets a `bulk` block whose per-op entry carries the
#     method, the path tail, and (for update) whether it is a native partial patch.
# --------------------------------------------------------------------------- #
def _bulk_spec(entity: str) -> dict[str, Any]:
    spec = _entity(entity)
    if not spec.get("bulk"):
        have = ", ".join(sorted(e for e, s in ENTITIES.items() if s.get("bulk")))
        raise ValueError(f"bulk is not verified for {entity!r}. "
                         f"Entities with bulk support: {have or '(none yet)'}.")
    return spec


def _bulk_ep(entity: str, op: str) -> dict[str, Any]:
    """Resolve a bulk op ('create'|'update'|'delete') to its method and full path, or
    raise if this entity does not support that op in bulk. `partial` (update only) is
    True where the API has a native partial-patch route; where False, wxcc_bulk_update
    read-modify-writes the full object."""
    bulk = _bulk_spec(entity)["bulk"]
    if op not in bulk:
        raise ValueError(f"bulk {op} is not supported/verified for {entity!r} "
                         f"(supported: {', '.join(sorted(bulk))}).")
    e = bulk[op]
    return {"method": e["method"], "partial": e.get("partial", False),
            "path": f"organization/{{orgId}}/{e['tail']}"}


def _bulk_collate(sent: list[tuple[int, dict]], body: Any) -> dict:
    """Map the 207 items[] back to what we sent, by itemIdentifier.

    An input with no matching result was NOT processed (the empty-items no-op) -
    surfaced loudly rather than counted as success.
    """
    results = (body or {}).get("items") if isinstance(body, dict) else None
    if not isinstance(results, list):
        return {"unexpected_response": body}
    by_id = {r.get("itemIdentifier"): r for r in results}
    ok, failed, missing = [], [], []
    for ident, label in sent:
        r = by_id.get(ident)
        if r is None:
            missing.append(label)
        elif isinstance(r.get("status"), int) and r["status"] < 300:
            ok.append({**label, "operation": r.get("operationType"),
                       "id": (r.get("href") or "").rsplit("/", 1)[-1] or label.get("id")})
        else:
            failed.append({**label, "status": r.get("status"),
                           "reason": _api_reason(r.get("apiError"))})
    out: dict[str, Any] = {"succeeded": ok or None, "failed": failed or None}
    if missing:
        out["NOT_PROCESSED"] = missing
        out["warning"] = ("The API returned 207 but gave no result for these items, so "
                          "they did NOT apply. A 207 is not proof - this is the "
                          "empty-items no-op.")
    return out


@mcp.tool()
def wxcc_bulk_update(entity: str, items: list, confirm: bool = False) -> dict:
    """Update MANY objects of one entity in a single call.

    Each item is {"id": "...", "<field>": <newvalue>, ...} - the id plus the fields to
    change. Where the entity has a native partial-patch endpoint (e.g. queues) only
    those fields are sent; where it does not (e.g. entry-point) the tool read-modify-
    writes, fetching each current object and merging your changes into a full-object
    save. Either way you pass only what changes. Bulk is verified per-entity - an
    unverified entity is refused with the list that is supported.

    confirm=False (default) writes nothing and previews. On a confirmed call the API
    returns a per-item 207 and this tool reports which items applied (with the operation)
    and which failed (with the API's own per-item reason).
    """
    # Resolve the op FIRST: an entity that has no bulk update at all must say so,
    # not report a problem with items it was never going to send.
    op = _bulk_ep(entity, "update")
    bad = [i for i, it in enumerate(items)
           if not isinstance(it, dict) or not it.get("id")]
    if bad:
        return {"error": "every bulk-update item needs an 'id' plus the fields to "
                         "change", "offending_indexes": bad}
    client = _client()
    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"{op['method']} {op['path']}", "count": len(items),
                "would_change": items,
                "update_style": ("partial patch (only your fields are sent)"
                                 if op["partial"] else
                                 "read-modify-write (no partial endpoint; each object is "
                                 "fetched and your fields merged into a full-object save)"),
                "rollback": "re-run wxcc_bulk_update with the prior field values "
                            "(read them first if you need them)",
                "next": "re-call with confirm=True once the user approves"}
    # Where there is no partial route, merge each change set onto the current object.
    not_found: list = []
    sent: list = []          # (label, item_to_send)
    if op["partial"]:
        sent = [({"id": it["id"]}, it) for it in items]
    else:
        for it in items:
            st, cur = client.json("GET", _path(entity, it["id"]))
            if st == 404 or not isinstance(cur, dict):
                not_found.append(it["id"])
            else:
                sent.append(({"id": it["id"]}, {**_strip(cur), **it}))
    labels = [(i, lbl) for i, (lbl, _o) in enumerate(sent)]
    wrapped = [{"itemIdentifier": i, "item": o, "requestAction": "SAVE"}
               for i, (_lbl, o) in enumerate(sent)]
    status, body = client.json(op["method"], op["path"], {"items": wrapped})
    if status >= 400 and not (isinstance(body, dict) and body.get("items")):
        return {"http": status, "error": body,
                "hint": "whole-request failure (not per-item) - check the item shapes"}
    out = {"TENANT": _tenant(client), "http": status, **_bulk_collate(labels, body)}
    if not_found:
        out["not_found"] = not_found
    return out


@mcp.tool()
def wxcc_bulk_create(entity: str, items: list, confirm: bool = False) -> dict:
    """Create MANY objects of one entity in a single call.

    Each item is a FULL create body - the same required fields wxcc_create enforces,
    checked here per item before the call. An item must NOT carry an 'id' (that is an
    update - use wxcc_bulk_update).

    confirm=False (default) previews and writes nothing.
    """
    spec = _bulk_spec(entity)
    # Resolve the op FIRST: an entity that has no bulk create at all must say so,
    # not complain about the fields of items it was never going to send.
    op = _bulk_ep(entity, "create")
    withid = [i for i, it in enumerate(items) if isinstance(it, dict) and it.get("id")]
    if withid:
        return {"error": "bulk-create items must not carry an 'id' (that is an update)",
                "offending_indexes": withid}
    req = spec.get("create", [])
    miss = {i: [f for f in req if f not in it] for i, it in enumerate(items)
            if isinstance(it, dict) and [f for f in req if f not in it]}
    if miss:
        return {"error": "items missing required fields (the API would 400 per item)",
                "missing_by_index": miss, "required": req, "note": spec.get("note")}
    if spec.get("clone_safe") is False:
        items = [_strip_nested_ids(it) for it in items]
    labels = [(i, {"name": it.get("name")}) for i, it in enumerate(items)]
    wrapped = [{"itemIdentifier": i, "item": it, "requestAction": "SAVE"}
               for i, it in enumerate(items)]
    client = _client()
    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"{op['method']} {op['path']}", "count": len(items),
                "would_create": items, "note": spec.get("note"),
                "rollback": "wxcc_bulk_delete (or wxcc_delete) the created ids",
                "next": "re-call with confirm=True once the user approves"}
    status, body = client.json(op["method"], op["path"], {"items": wrapped})
    if status >= 400 and not (isinstance(body, dict) and body.get("items")):
        return {"http": status, "error": body}
    return {"TENANT": _tenant(client), "http": status, **_bulk_collate(labels, body)}


@mcp.tool()
def wxcc_bulk_delete(entity: str, ids: list, confirm: bool = False) -> dict:
    """Delete MANY objects of one entity in a single call.

    Pass a list of ids. The bulk-delete endpoint rejects an id-only item with a
    misleading 'system generated' 400, so this tool fetches each FULL object first and
    sends that. The API self-guards references: a still-referenced object comes back as
    a per-item 412 and is NOT deleted, while the rest of the batch still applies.

    Irreversible. confirm=False (default) previews what each id is and writes nothing.
    """
    spec = _bulk_spec(entity)
    op = _bulk_ep(entity, "delete")
    client = _client()
    objs, not_found = [], []
    for _id in ids:
        st, body = client.json("GET", _path(entity, _id))
        if st == 404 or not isinstance(body, dict):
            not_found.append(_id)
        else:
            objs.append(_strip(body))
    labels = [(i, {"id": o.get("id"), "name": o.get("name")})
              for i, o in enumerate(objs)]
    if not confirm:
        return {"TENANT": _tenant(client), "dry_run": True,
                "action": f"{op['method']} {op['path']} (requestAction DELETE)",
                "count": len(objs),
                "would_delete": [dict(label) for _, label in labels],
                "not_found": not_found or None, "note": spec.get("note"),
                "rollback": "NONE - a delete is irreversible and recreating yields new "
                            "ids. Still-referenced objects are blocked by the API "
                            "(per-item 412), not deleted.",
                "next": "re-call with confirm=True only after an explicit yes"}
    wrapped = [{"itemIdentifier": i, "item": o, "requestAction": "DELETE"}
               for i, o in enumerate(objs)]
    status, body = client.json(op["method"], op["path"], {"items": wrapped})
    if status >= 400 and not (isinstance(body, dict) and body.get("items")):
        return {"http": status, "error": body}
    out = {"TENANT": _tenant(client), "http": status, **_bulk_collate(labels, body)}
    if not_found:
        out["not_found"] = not_found
    return out


# --------------------------------------------------------------------------- #
# APIs that do not fit the CRUD registry
# --------------------------------------------------------------------------- #
@mcp.tool()
def wxcc_search_tasks(query: str) -> dict:
    """Query interaction data (calls/tasks/agent sessions) via the GraphQL Search API.

    `query` is a GraphQL document string. The roots are task, agentSession, and
    taskDetails, and EVERY one REQUIRES `from` and `to` arguments in epoch
    MILLISECONDS - passing seconds silently returns nothing.

    Example:
      { task(from: 1720000000000, to: 1720600000000)
          { tasks { id status channelType } pageInfo { hasNextPage } } }

    Aggregations (verified live): pass `aggregations: [{field, type, name}]` on
    the root; types are count|sum|average|min|max|cardinality (NOT avg). The
    scalar fields you select in `tasks{}` become the GROUP BY keys, and each
    group's metrics arrive in its `aggregation {name value}` list:
      { task(from: F, to: T,
             aggregations: [{ field: "id", type: count, name: "calls" }])
          { tasks { lastQueue { name } aggregation { name value } } } }
    The queue field on Task is `lastQueue` - `queue` does not exist. A `filter:`
    argument composes with aggregations. Introspection is disabled; unknown
    fields fail with FieldUndefined naming the field.

    This is reporting data, not tenant config.
    """
    client = _client()
    status, body = client.json("POST", "search?orgId={orgId}", {"query": query})
    if status >= 400:
        return {"error": f"HTTP {status}", "body": body,
                "check": "from/to present, in epoch MILLISECONDS?"}
    return {"http": status, "result": body}


@mcp.tool()
def wxcc_webhooks(action: str, subscription_id: str = "",
                  body: dict | None = None, confirm: bool = False) -> dict:
    """Manage event subscriptions (webhooks). Host-root API, not under organization/.

    action: list_event_types | list | create | update | delete

    Updates use PATCH, not PUT. Limit is 20 subscriptions per org. The `secret` is
    write-only and never echoed back. `destinationUrl` is NOT validated for
    reachability - a typo silently sends your contact-center events to a stranger,
    so read the URL back to the user before creating.
    """
    client = _client()

    if action == "list_event_types":
        status, data = client.json("GET", "v1/event-types")
        return {"http": status, "event_types": data}
    if action == "list":
        status, data = client.json("GET", "v1/subscriptions")
        return {"http": status, "subscriptions": data}

    if action in ("create", "update", "delete") and not confirm:
        return {"dry_run": True, "action": action, "subscription_id": subscription_id,
                "would_send": body,
                "warning": "destinationUrl is never validated - confirm the exact "
                           "URL with the user before sending events to it.",
                "next": "re-call with confirm=True once the user approves"}

    if action == "create":
        status, data = client.json("POST", "v1/subscriptions", body)
    elif action == "update":
        status, data = client.json("PATCH", f"v1/subscriptions/{subscription_id}", body)
    elif action == "delete":
        status, data = client.json("DELETE", f"v1/subscriptions/{subscription_id}")
    else:
        return {"error": f"unknown action {action!r}"}
    return {"http": status, "result": data, "ok": status < 400}


if __name__ == "__main__":
    mcp.run()
