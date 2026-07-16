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

import json
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
                "`userLevelSummariesInclusion` is SILENTLY IGNORED on a 200.",
    },
    "team": {
        "list": "v2/team", "item": "team/{id}",
        "create": ["name", "active", "siteId", "teamStatus", "teamType"],
        "writes": ["create", "update", "delete"],
    },
    "site": {
        "list": "v2/site", "item": "site/{id}",
        "writes": [],
        "note": "Read-only here: site writes have never been probed.",
    },
    "contact-service-queue": {
        "list": "v2/contact-service-queue", "item": "contact-service-queue/{id}",
        "create": ["name", "queueType", "channelType", "serviceLevelThreshold",
                   "maxActiveContacts", "maxTimeInQueue", "active", "routingType",
                   "monitoringPermitted", "parkingPermitted", "recordingPermitted",
                   "recordingAllCallsPermitted", "pauseRecordingPermitted"],
        "writes": ["create", "update", "delete"],
        "note": "The queue entity is `contact-service-queue`; `/queue` 404s. The "
                "five *Permitted booleans are REQUIRED on create, not defaulted.",
    },
    "entry-point": {
        "list": "v2/entry-point", "item": "entry-point/{id}",
        "create": ["name", "entryPointType", "channelType", "serviceLevelThreshold",
                   "active", "maximumActiveContacts"],
        "writes": ["create", "update", "delete"],
    },
    "dial-number": {
        "list": "v2/dial-number", "item": "dial-number/{id}",
        "create": ["dialledNumber", "entryPointId", "location", "regionId"],
        "writes": ["create", "update"],
        "note": "Field is `dialledNumber` (double L). Numbers CANNOT be invented: "
                "create 404s with 'Dialed number does not exist' unless the number "
                "is already in the Webex Calling location inventory. Filtering on a "
                "raw '+' silently returns 0 records - use dialledNumberDigits==. "
                "DELETE is unprobed and would unmap a live number.",
    },
    "skill": {
        "list": "v2/skill", "item": "skill/{id}",
        "create": ["name", "active", "skillType", "serviceLevelThreshold"],
        "writes": ["create", "update", "delete"],
        "note": "skillType ENUM additionally requires enumSkillValues:[{name}]. "
                "Deleting a skill still referenced by a profile returns 412 with "
                "referencedEntities - delete the profiles first.",
    },
    "skill-profile": {
        "list": "v2/skill-profile", "item": "skill-profile/{id}",
        "create": ["name"],
        "writes": ["create", "update", "delete"],
        "note": "activeSkills entries are {skillId, booleanValue|proficiencyValue|"
                "textValue}. activeEnumSkills entries carry {enumSkillValueId} ONLY "
                "- adding skillId there returns HTTP 500. On update, every KEPT "
                "activeSkills entry must resend its own sub-entity `id` or you get "
                "409 duplicate-entry.",
    },
    "auxiliary-code": {
        "list": "v2/auxiliary-code", "item": "auxiliary-code/{id}",
        "create": ["active", "name", "workTypeCode", "defaultCode", "workTypeId"],
        "writes": ["create", "update", "delete"],
        "note": "workTypeId is not derivable - copy it from an existing code with "
                "the same workTypeCode (WRAP_UP_CODE or IDLE_CODE).",
    },
    "address-book": {
        "list": "v2/address-book", "item": "address-book/{id}",
        "create": ["name", "parentType"],
        "writes": ["create", "update", "delete"],
        "note": "Entries are a sub-resource: address-book/{id}/entry.",
    },
    "outdial-ani": {
        "list": "v2/outdial-ani", "item": "outdial-ani/{id}",
        "create": ["name", "outdialANIEntries"],
        "writes": ["create", "delete"],
        "note": "Entries are embedded, not a sub-resource. UPDATE is untested.",
    },
    "agent-profile": {
        "list": "v2/agent-profile", "item": "agent-profile/{id}",
        "writes": ["update"],
        "note": "This is a DESKTOP PROFILE. The `agent-profile` path is backwards "
                "compatibility only - always say 'Desktop Profile' to the user. "
                "dialPlanEnabled/dialPlans still appear but Dial Plan is DEPRECATED "
                "in WxCC - ignore them. Create/delete unprobed.",
    },
    "desktop-layout": {
        "list": "v2/desktop-layout", "item": "desktop-layout/{id}",
        "create": ["name", "jsonFileName", "jsonFileContent",
                   "defaultJsonModified", "status", "editedBy"],
        "writes": ["create", "update", "delete"],
        "note": "jsonFileContent is the ENTIRE layout JSON as an embedded string "
                "(~20KB), and only appears on the item GET, not the list. It is NOT "
                "validated at POST - a malformed layout fails at agent-desktop load. "
                "Never modify the systemDefault Global Layout.",
    },
}


# Who points AT whom. Used to pre-flight a delete so the user gets a list of
# conflicts to resolve, instead of a bare 412 from the API after the fact.
# The API's 412 remains the backstop - this map is a courtesy, not the authority.
#   412-CONFIRMED live: team<-user.teamIds, skill<-skill-profile.activeSkills
#   The rest are inferred from observed record shapes and are NOT yet 412-proven.
REFERENCED_BY: dict[str, list[tuple[str, str]]] = {
    "team":           [("user", "teamIds")],                          # confirmed
    "skill":          [("skill-profile", "activeSkills[].skillId")],  # confirmed
    "site":           [("team", "siteId"), ("user", "siteId")],
    "entry-point":    [("dial-number", "entryPointId")],
    "skill-profile":  [("team", "skillProfileId")],
    "agent-profile":  [("user", "agentProfileId")],
    "desktop-layout": [("team", "desktopLayoutId")],
    "outdial-ani":    [("agent-profile", "outdialANIId")],
}


def _label(rec: dict) -> str:
    name = rec.get("name")
    if name:
        return name
    who = f"{rec.get('firstName', '')} {rec.get('lastName', '')}".strip()
    return who or rec.get("email") or rec.get("id", "?")


def _field_hits(rec: dict, spec: str, target: str) -> bool:
    """Does `rec` reference `target` via `spec`? Handles scalars, id-lists, and
    list-of-dicts (`activeSkills[].skillId`)."""
    if "[]." in spec:
        listkey, _, subkey = spec.partition("[].")
        return any(isinstance(i, dict) and i.get(subkey) == target
                   for i in (rec.get(listkey) or []))
    val = rec.get(spec)
    return target in val if isinstance(val, list) else val == target


def _find_references(client: wxcc.WxccClient, entity: str, target: str) -> list[dict]:
    hits: list[dict] = []
    for ref_entity, spec in REFERENCED_BY.get(entity, []):
        try:
            records, _ = client.list_all(_path(ref_entity) + "?pageSize=100")
        except Exception as exc:            # a failed scan must not read as "clean"
            hits.append({"entity": ref_entity, "scan_failed": str(exc)})
            continue
        hits += [{"entity": ref_entity, "id": r.get("id"), "name": _label(r),
                  "via_field": spec}
                 for r in records if _field_hits(r, spec, target)]
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
    if client.org_id in _org_cache:
        return _org_cache[client.org_id]
    try:
        status, body = client.json("GET", f"organization/{client.org_id}")
    except Exception:
        status, body = 0, None
    if status != 200 or not isinstance(body, dict):
        return {"name": "(org name unavailable)", "org_id": client.org_id,
                "production": None}
    info = {
        "name": body.get("name"),
        "org_id": client.org_id,
        "subscription": body.get("subscriptionType"),
        "environment": body.get("environment"),
        # A paying subscription is a real customer tenant. Trials are sandboxes.
        "production": body.get("subscriptionType") == "SUBSCRIPTION",
    }
    _org_cache[client.org_id] = info
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


def _read(client: wxcc.WxccClient, entity: str, item_id: str) -> dict:
    status, body = client.json("GET", _path(entity, item_id))
    if status >= 400:
        raise ValueError(f"cannot read {entity}/{item_id}: HTTP {status} {body}")
    return body


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
    filter     : FIQL, e.g. `name==Sales`. Values must be UNQUOTED - quoting
                 them returns 400. A raw '+' in a value silently returns 0 rows.
    search     : substring match across fields.
    attributes : projection, e.g. `id,name,active`.
    all_pages  : follow pagination to exhaustion.
    """
    spec = _entity(entity)
    client = _client()
    q = [f"pageSize={page_size}"]
    for key, val in (("filter", filter), ("search", search),
                     ("attributes", attributes)):
        if val:
            q.append(f"{key}={val}")
    path = _path(entity) + "?" + "&".join(q)

    if all_pages:
        records, pages = client.list_all(path)
        return {"tenant": _tenant(client), "entity": entity,
                "totalRecords": len(records), "pagesFetched": pages,
                "data": records, "note": spec.get("note")}
    status, body = client.json("GET", path)
    if status >= 400:
        return {"error": f"HTTP {status}", "body": body}
    return {"tenant": _tenant(client), "entity": entity, "meta": body.get("meta"),
            "data": body.get("data"), "note": spec.get("note")}


@mcp.tool()
def wxcc_get(entity: str, id: str) -> dict:
    """Read one WxCC config object by id. Returns the full object."""
    spec = _entity(entity)
    client = _client()
    obj = _read(client, entity, id)
    return {"tenant": _tenant(client), "entity": entity, "data": obj,
            "note": spec.get("note")}


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
    new_id = (body or {}).get("id")
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

    status, body = client.json("PUT", _path(entity, id), proposed)
    if status >= 400:
        return {"updated": False, "http": status, "error": body,
                "note": spec.get("note")}

    after = _read(client, entity, id)
    ignored = {k: {"requested": v, "actual": after.get(k)}
               for k, v in changes.items() if after.get(k) != v}
    return {
        "TENANT": _tenant(client),
        "updated": True, "http": status,
        "confirmed_changed": {k: after.get(k) for k in changes if k not in ignored},
        "SILENTLY_IGNORED": ignored or None,
        "warning": ("The API returned 200 but did NOT apply the fields under "
                    "SILENTLY_IGNORED. Tell the user.") if ignored else None,
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
                f"{r['entity']} '{r['name']}' ({r.get('id')}) via `{r['via_field']}`"
                for r in refs if "scan_failed" not in r
            ],
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
