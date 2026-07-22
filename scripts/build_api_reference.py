#!/usr/bin/env python3
"""Generate the API reference artifacts from Cisco's OpenAPI spec + our registry.

Emits three things, all derived - never hand-edit them:

  docs/api-coverage.md          human reference: every operation, and either the
                                tool that reaches it or why it is refused
  docs/api-fingerprint.json     small drift detector: upstream commit + the route
                                inventory, so `--check` can name what changed
  .claude/skills/wxcc-api-map/SKILL.md
                                thin index for development work: entity -> routes
                                -> which skill owns the detail. Deliberately does
                                NOT restate traps; the skills own those.

Run from anywhere:
  python scripts/build_api_reference.py            regenerate all three
  python scripts/build_api_reference.py --check    fetch live spec, diff against
                                                   the fingerprint, exit 1 if the
                                                   published API moved

The spec is NOT vendored: upstream republishes it roughly weekly, so a static
copy would be stale within days. Only the fingerprint is committed.

Reads ENTITIES by parsing mcp_server.py with `ast` rather than importing it, so
this runs with no dependencies, no MCP package, and no tenant config.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC_URL = ("https://raw.githubusercontent.com/webex/webex-openapi-specs/main/"
            "public-spec/webex-contact-center.json")
COMMITS_URL = ("https://api.github.com/repos/webex/webex-openapi-specs/commits"
               "?path=public-spec/webex-contact-center.json&per_page=1")
SPEC_HTML = ("https://github.com/webex/webex-openapi-specs/blob/main/"
             "public-spec/webex-contact-center.json")

OUT_COVERAGE = REPO / "docs" / "api-coverage.md"
OUT_FINGERPRINT = REPO / "docs" / "api-fingerprint.json"
OUT_MAP = REPO / ".claude" / "skills" / "wxcc-api-map" / "SKILL.md"

VERBS = ("get", "post", "put", "patch", "delete")
ORG_PATH = re.compile(r"^/organization/\{orgid\}/(?:(v\d)/)?([a-z0-9-]+)(/.*)?$", re.I)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def fetch(url: str, accept_json: bool = True):
    req = urllib.request.Request(url, headers={"User-Agent": "wxcc-skills-docs"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if accept_json else raw


def upstream_commit() -> tuple[str, str]:
    """(sha, iso date) of the newest commit touching the spec. Never fatal."""
    try:
        c = fetch(COMMITS_URL)[0]
        return c["sha"], c["commit"]["committer"]["date"]
    except Exception as exc:                       # offline, rate-limited, moved
        print(f"  ! could not read upstream commit ({exc}); provenance degraded",
              file=sys.stderr)
        return "(unknown)", "(unknown)"


def load_entities() -> dict:
    """ENTITIES out of mcp_server.py without importing it.

    The registry is pure literals on purpose, so `ast.literal_eval` is enough.
    Importing instead would drag in the MCP package and a tenant config, which a
    docs build has no business requiring.
    """
    tree = ast.parse((REPO / "mcp_server.py").read_text(encoding="utf-8"))
    for node in tree.body:
        # ENTITIES carries a type annotation, so it parses as AnnAssign, not Assign.
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "ENTITIES" and node.value is not None:
                return ast.literal_eval(node.value)
    raise SystemExit("ENTITIES not found in mcp_server.py - did it get renamed?")


# Skills that speak about EVERY entity by design. Listing them against each row
# turns the ownership column into noise, so they are named once instead.
CROSS_CUTTING = {"wxcc-api-map", "wxcc-bulk", "wxcc-connect"}


def skill_owners(entities: dict) -> dict[str, dict[str, list[str]]]:
    """entity -> the skills that actually own its detail, derived so it cannot drift.

    Ownership is claimed by *calling* the entity (`entity="x"` in an example), not
    by mentioning it. A bare backtick mention is the fallback only when nothing
    calls it, otherwise cross-referencing skills look like owners.
    """
    strong: dict[str, set[str]] = collections.defaultdict(set)
    weak: dict[str, set[str]] = collections.defaultdict(set)
    for skill in sorted((REPO / ".claude" / "skills").glob("*/SKILL.md")):
        name = skill.parent.name
        if name in CROSS_CUTTING:
            continue
        text = skill.read_text(encoding="utf-8")
        for ent in entities:
            if re.search(rf'entity\s*=\s*[\'"]{re.escape(ent)}[\'"]', text):
                strong[ent].add(name)
            elif f"`{ent}`" in text:
                weak[ent].add(name)
    # Keep the two apart in the output: a skill that merely NAMES an entity is not
    # its owner, and rendering it as one hides a missing skill.
    return {ent: {"owns": sorted(strong.get(ent, set())),
                  "mentions": sorted(weak.get(ent, set()) - strong.get(ent, set()))}
            for ent in entities}


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
# Routes served by purpose-built tools rather than the generic CRUD ones.
FINDERS = {
    ("user", None, "/with-user-profile", "GET"): "wxcc_find_users(by='with_profile')",
    ("user", None, "/with-user-profile/{id}", "GET"): "wxcc_find_users(by='with_profile_by_id')",
    ("user", None, "/by-ci-user-id/{id}", "GET"): "wxcc_find_users(by='ci_user_id')",
    ("user", None, "/by-dynamic-skill-id/{skillId}", "GET"): "wxcc_find_users(by='dynamic_skill')",
    ("user", None, "/by-call-monitoring-id/{id}", "GET"): "wxcc_find_users(by='call_monitoring_id')",
    ("user", None, "/fetch-user-details-by-ids", "POST"): "wxcc_find_users(by='ids')",
    ("user", None, "/fetch-by-skill-requirements", "POST"): "wxcc_find_users(by='skill_requirements')",
    ("contact-service-queue", "v2", "/by-user-id/{userid}/team-based-queues", "GET"):
        "wxcc_find_queues(by='team_based_for_user')",
    ("contact-service-queue", "v2", "/by-user-id/{userid}/agent-based-queues", "GET"):
        "wxcc_find_queues(by='agent_based_for_user')",
    ("contact-service-queue", "v2", "/by-user-id/{userid}/skill-based-queues", "GET"):
        "wxcc_find_queues(by='skill_based_for_user')",
    ("contact-service-queue", None, "/by-skill-profile-id/{id}", "GET"):
        "wxcc_find_queues(by='for_skill_profile')",
    ("contact-service-queue", None, "/fetch-by-userId-skillProfileId", "POST"):
        "wxcc_find_queues(by='for_user_and_skill_profile')",
    ("contact-service-queue", None, "/fetch-by-dynamic-skills-and-skillProfile", "POST"):
        "wxcc_find_queues(by='for_dynamic_skills')",
}

PURGE = ("403 tenant-wide for a full-rights admin (confirmed on auxiliary-code, "
         "desktop-layout and agent-profile 2026-07-22). Use wxcc_bulk_delete on ids "
         "you chose.")


def refusal(ent: str, ver, tail: str, meth: str) -> str | None:
    """Why a route is deliberately unexposed. Keeps 'decided' apart from 'missed'."""
    if "purge-inactive-entities" in tail:
        return PURGE
    if "bulk-export" in tail:
        return "Bulk export is out of scope for these tools."
    if ent == "contact-number" and tail == "/all-numbers":
        return ("Returns bare strings with no ids, so it cannot drive an update or "
                "delete. v2/contact-number is the list path.")
    if ent == "dial-number" and meth == "DELETE":
        return ("DELETE would unmap a live number; unprobed and deliberately not "
                "exposed.")
    if ent == "user" and tail == "/{id}/reskill":
        return ("403 'User must have a supervisor profile to reskill agents' - a "
                "Supervisor Desktop endpoint. Reachable instead by PATCHing "
                "skillProfileId via wxcc_update.")
    if ent == "user" and ver == "v2" and tail == "/by-ci-user-id/{id}":
        return "Duplicate of the non-v2 route, which is the one wxcc_find_users calls."
    if ent == "contact-service-queue" and tail == "/fetch-manually-assignable-queues":
        return ("404 for all six users tried, each with a valid ciUserId from their own "
                "record (2026-07-22). Unexplained, so refused rather than shipped flaky.")
    if ent == "contact-service-queue" and tail == "/fetch-by-grouped-assistant-skill":
        return "412 'License check failed for Suggested responses' - entitlement-gated."
    if ent == "contact-service-queue" and tail.endswith("/reassign-agents"):
        return ("Operates on AGENT-BASED queues; this tenant has none (all INBOUND/"
                "OUTBOUND), so it cannot be verified. Refused rather than shipped "
                "untested.")
    if tail.endswith("/entry/bulk"):
        return ("Route confirmed (207 + items) but its accepted ops are UNPROBED, so "
                "the bulk tools refuse it.")
    return None


def tool_for(entities: dict, ent: str, ver, tail: str, meth: str) -> str | None:
    spec = entities.get(ent)
    if not spec:
        return None
    if (hit := FINDERS.get((ent, ver, tail, meth))):
        return hit
    bulk = spec.get("bulk") or {}
    child = spec.get("child")
    t = tail or ""
    if t == "":
        if meth == "GET":
            return "wxcc_list"
        if meth == "POST":
            return "wxcc_create" if "create" in spec.get("writes", []) else None
    if t == "/{id}":
        if meth == "GET":
            return "wxcc_get"
        if meth == "PUT":
            return "wxcc_update" if "update" in spec.get("writes", []) else None
        if meth == "DELETE":
            return "wxcc_delete" if "delete" in spec.get("writes", []) else None
        if meth == "PATCH":
            return "wxcc_update (PATCH)" if spec.get("patch_item") else None
    if t == "/{id}/incoming-references" and meth == "GET":
        return "wxcc_references"
    if t.endswith("/bulk"):
        ops = sorted(k for k, v in bulk.items()
                     if v["tail"].endswith(t.lstrip("/")) and v["method"] == meth)
        return "wxcc_bulk_" + "/".join(ops) if ops else None
    if child:
        if re.fullmatch(rf"/\{{\w+\}}/{child}", t):
            return "wxcc_add_entry / wxcc_list_entries"
        if re.fullmatch(rf"/\{{\w+\}}/{child}/\{{\w+\}}", t):
            return "wxcc_update_entry / wxcc_remove_entry"
    return None


def parse_spec(spec: dict, entities: dict):
    org, other = [], []
    for path, item in spec.get("paths", {}).items():
        for meth, op in item.items():
            if meth.lower() not in VERBS:
                continue
            rec = {"method": meth.upper(), "path": path,
                   "tag": (op.get("tags") or ["(untagged)"])[0],
                   "summary": (op.get("summary") or "").strip()}
            mm = ORG_PATH.match(path)
            if mm:
                rec |= {"ver": mm.group(1), "entity": mm.group(2),
                        "tail": mm.group(3) or ""}
                rec["tool"] = tool_for(entities, rec["entity"], rec["ver"],
                                       rec["tail"], rec["method"])
                rec["why"] = refusal(rec["entity"], rec["ver"], rec["tail"],
                                     rec["method"])
                org.append(rec)
            else:
                other.append(rec)
    return org, other


def disp(rec: dict) -> str:
    return f"{(rec['ver'] + '/') if rec['ver'] else ''}{rec['entity']}{rec['tail']}"


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #
BANNER = ("<!-- GENERATED by scripts/build_api_reference.py - do not hand-edit. -->\n"
          "<!-- Re-run that script instead; edits here are lost on regeneration. -->\n")

CAVEAT = ("> **The spec maps what EXISTS, not what WORKS.** It declares "
          "`application/json` as an accepted body for `POST`/`PUT` on `audio-file`; "
          "live probing shows every JSON shape returns 500 and only multipart "
          "succeeds. Schema quality is uneven too - `PATCH user/{id}` documents its "
          "body as `JsonValue` with one field. **Where the spec and a live probe "
          "disagree, the probe wins**, and the probe's finding belongs in the "
          "registry note.\n")


def write_coverage(org, other, entities, sha, date):
    reg = sorted({o["entity"] for o in org if o["entity"] in entities})
    unreg = sorted({o["entity"] for o in org if o["entity"] not in entities})
    onreg = [o for o in org if o["entity"] in entities]
    reachable = sum(1 for o in onreg if o["tool"])

    L = [BANNER, "# WxCC API coverage\n",
         f"Cisco's OpenAPI spec ([`webex-contact-center.json`]({SPEC_HTML})) diffed "
         f"against this project's entity registry.\n",
         f"Upstream commit **`{sha[:12]}`** ({date}) · registry has "
         f"**{len(entities)} entities**.\n", CAVEAT, "## Totals\n",
         "| | count |", "|---|---|",
         f"| Operations in spec | {len(org) + len(other)} |",
         f"| Org-scoped config operations | {len(org)} |",
         f"| Non-org-scoped (Tasks/Flows/Journey/…) | {len(other)} |",
         f"| Config path roots — registered | {len(reg)} |",
         f"| Config path roots — not registered | {len(unreg)} |",
         f"| Ops on registered entities | {len(onreg)} |",
         f"| — reachable by a tool | **{reachable}** |",
         f"| — gaps | **{len(onreg) - reachable}** |", ""]

    L += ["## Registered entities\n",
          "`GAP` means nothing reaches it. **decided** means it is deliberately "
          "unexposed, with the reason.\n"]
    for ent in reg:
        items = sorted([o for o in org if o["entity"] == ent],
                       key=lambda r: (r["tail"], r["method"]))
        ok = sum(1 for i in items if i["tool"])
        L += [f"\n### `{ent}` — {ok}/{len(items)} reachable\n",
              "| Method | Path | Summary | Tool / status |", "|---|---|---|---|"]
        for i in items:
            status = (f"`{i['tool']}`" if i["tool"]
                      else f"**decided** — {i['why']}" if i["why"] else "**GAP**")
            L.append(f"| {i['method']} | `{disp(i)}` | {i['summary']} | {status} |")

    L += ["\n## Config roots not in the registry\n"]
    for ent in unreg:
        items = sorted([o for o in org if o["entity"] == ent],
                       key=lambda r: (r["tail"], r["method"]))
        tags = ", ".join(sorted({i["tag"] for i in items}))
        L += [f"\n### `{ent}` — {len(items)} operations ({tags})\n",
              "| Method | Path | Summary |", "|---|---|---|"]
        L += [f"| {i['method']} | `{disp(i)}` | {i['summary']} |" for i in items]

    L += ["\n## Non-org-scoped operations\n",
          "Different API families - reporting, flows, journey, campaigns. Listed for "
          "completeness; this project's tools do not cover them.\n"]
    bytag = collections.defaultdict(list)
    for o in other:
        bytag[o["tag"]].append(o)
    for tag in sorted(bytag, key=lambda t: (-len(bytag[t]), t)):
        L += [f"\n### {tag} — {len(bytag[tag])} operations\n",
              "| Method | Path | Summary |", "|---|---|---|"]
        L += [f"| {o['method']} | `{o['path']}` | {o['summary']} |"
              for o in sorted(bytag[tag], key=lambda r: (r["path"], r["method"]))]

    OUT_COVERAGE.write_text("\n".join(L) + "\n", encoding="utf-8")
    return len(onreg), reachable


def write_fingerprint(org, other, sha, date):
    routes = sorted(f"{o['method']} {o['path']}" for o in org + other)
    OUT_FINGERPRINT.write_text(json.dumps({
        "_comment": "Drift detector for Cisco's OpenAPI spec. Regenerate with "
                    "scripts/build_api_reference.py; compare with --check. The spec "
                    "itself is deliberately not vendored - it changes ~weekly.",
        "spec_url": SPEC_URL,
        "upstream_commit": sha,
        "upstream_committed": date,
        "captured": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operation_count": len(routes),
        "routes": routes,
    }, indent=2) + "\n", encoding="utf-8")


def write_map(org, entities, owners, sha, date, onreg_total, reachable):
    """Thin index for development work. Points at the skills; never restates them."""
    # Frontmatter MUST be the first thing in a SKILL.md - the generated-file banner
    # goes below it, or the skill does not parse.
    L = ["---",
         "name: wxcc-api-map",
         "description: Use when EXTENDING this project rather than administering a "
         "tenant - adding an entity to the registry, wiring a new endpoint, checking "
         "whether a route is already covered or deliberately refused, or asking "
         "\"what does the WxCC API actually publish for X\". An index of Cisco's "
         "OpenAPI spec mapped to our tools and skills. Not for answering admin "
         "questions - the per-entity skills own those.",
         "---", "", BANNER,
         "# wxcc-api-map — where everything lives\n",
         f"Generated from Cisco's OpenAPI spec (upstream `{sha[:12]}`, {date}) against "
         f"a registry of **{len(entities)} entities**. "
         f"**{reachable}/{onreg_total}** operations on registered entities are "
         "reachable.\n",
         "**This is an index, not a manual.** It says what exists and who owns the "
         "detail. Every trap, field rule and payload shape lives in the entity's "
         "skill and in the `ENTITIES` note in [mcp_server.py](../../../mcp_server.py) "
         "- one home per fact. Do not copy those here.\n",
         CAVEAT,
         "## Before adding an endpoint\n",
         "1. Check the row below - it may already be covered, or **deliberately "
         "refused** with a reason in [docs/api-coverage.md](../../../docs/api-coverage.md).",
         "2. Read the spec's schema for required fields; do **not** probe an empty "
         "body first. That method mapped 21 entities and then failed completely on "
         "`audio-file`, which answers 500 rather than naming its fields.",
         "3. Verify live anyway. The spec is wrong about `audio-file` accepting JSON.",
         "4. Record what you confirmed in the entity's `note`, and re-run "
         "`python scripts/build_api_reference.py`.\n",
         "## House rules the spec confirms\n",
         "- List path carries the version prefix (`v2/<entity>`); the item path "
         "usually **drops** it. `user-profile` is the exception - it keeps `v3`.",
         "- `POST <entity>` creates, `PUT <entity>/{id}` replaces, "
         "`DELETE <entity>/{id}` removes.",
         "- `GET <entity>/{id}/incoming-references` answers \"what breaks if I touch "
         "this\" - **except `contact-number`, which has no such path at all**.",
         "- `POST <entity>/bulk` takes `{items:[{itemIdentifier, item, requestAction}]}` "
         "and answers **207** with per-item results.",
         "- `POST <entity>/purge-inactive-entities` exists widely and is **403 for "
         "everyone** - see the canonical note in `wxcc-bulk`.\n",
         "## Entity index\n",
         "Cross-cutting skills are omitted from the rows below because they speak "
         "about every entity: **wxcc-bulk** (all bulk routes and the purge note) and "
         "**wxcc-connect** (auth, tenants, 401/403).\n",
         "| Entity | Ops (reachable/total) | Skills that own the detail |",
         "|---|---|---|"]

    orphans = []
    for ent in sorted(entities):
        items = [o for o in org if o["entity"] == ent]
        ok = sum(1 for i in items if i["tool"])
        own = owners.get(ent, {}).get("owns") or []
        seen = owners.get(ent, {}).get("mentions") or []
        if own:
            cell = ", ".join(f"**{s}**" for s in own)
        elif seen:
            cell = ("**NO OWNING SKILL** — only mentioned by "
                    + ", ".join(f"_{s}_" for s in seen))
            orphans.append(ent)
        else:
            cell = "**NO OWNING SKILL**"
            orphans.append(ent)
        L.append(f"| `{ent}` | {ok}/{len(items)} | {cell} |")

    if orphans:
        one = len(orphans) == 1
        L += ["", f"> **{len(orphans)} registered entit"
                  f"{'y has' if one else 'ies have'} no owning skill**: "
              + ", ".join(f"`{e}`" for e in orphans)
              + f". The tools reach {'it' if one else 'them'}, but nothing tells a "
                f"caller how or warns about {'its' if one else 'their'} traps. A skill "
                "that merely names an entity in a list is not its owner."]

    unreg = sorted({o["entity"] for o in org if o["entity"] not in entities})
    L += ["\n## Config roots with no registry entry\n",
          "Candidates for the next entity, with their operation counts. Full route "
          "lists in [docs/api-coverage.md](../../../docs/api-coverage.md).\n",
          "| Root | Ops | Note |", "|---|---|---|"]
    known = {
        "work-type": "**Deprecated** in WxCC - do not register. `auxiliary-code."
                     "workTypeId` stays a value copied from an existing code.",
        "dial-plan": "**Deprecated** in WxCC - the `agent-profile` fields that "
                     "reference it are ignored.",
    }
    for ent in unreg:
        n = sum(1 for o in org if o["entity"] == ent)
        L.append(f"| `{ent}` | {n} | {known.get(ent, 'Unregistered and unprobed.')} |")

    L += ["\n## Everything else\n",
          "Non-org-scoped families (Tasks, Flows, Journey, Campaigns, Subscriptions) "
          "are listed in [docs/api-coverage.md](../../../docs/api-coverage.md). Flows "
          "are **out of scope for this project** - Cisco ships its own `flow-store` "
          "MCP server. Reporting over interaction data is **wxcc-tasks-search**; "
          "event subscriptions are **wxcc-webhooks**.\n"]

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    OUT_MAP.write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
def check_drift() -> int:
    if not OUT_FINGERPRINT.exists():
        print("no fingerprint yet - run without --check first.")
        return 1
    old = json.loads(OUT_FINGERPRINT.read_text(encoding="utf-8"))
    spec = fetch(SPEC_URL)
    sha, date = upstream_commit()
    org, other = parse_spec(spec, load_entities())
    now = sorted(f"{o['method']} {o['path']}" for o in org + other)
    added = [r for r in now if r not in set(old["routes"])]
    removed = [r for r in old["routes"] if r not in set(now)]

    # Count the routes actually compared, not the stored field - if the two ever
    # disagree, the stored one is the lie.
    print(f"fingerprint : {old['upstream_commit'][:12]} ({old['upstream_committed']}), "
          f"{len(old['routes'])} ops")
    print(f"upstream now: {sha[:12]} ({date}), {len(now)} ops")
    if not added and not removed:
        print("\nNo route changes. (Schemas may still have changed - the fingerprint "
              "tracks routes only.)")
        return 0
    print(f"\nDRIFT: +{len(added)} / -{len(removed)}")
    for r in added:
        print("  + ", r)
    for r in removed:
        print("  - ", r)
    print("\nRe-run without --check to regenerate, then re-probe anything affected.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report route drift against the committed fingerprint; "
                         "exit 1 if the published API moved")
    args = ap.parse_args()
    if args.check:
        return check_drift()

    print("fetching spec ...")
    spec = fetch(SPEC_URL)
    sha, date = upstream_commit()
    entities = load_entities()
    org, other = parse_spec(spec, entities)
    owners = skill_owners(entities)

    total, reachable = write_coverage(org, other, entities, sha, date)
    write_fingerprint(org, other, sha, date)
    write_map(org, entities, owners, sha, date, total, reachable)

    print(f"  spec        {len(org) + len(other)} ops (upstream {sha[:12]}, {date})")
    print(f"  coverage    {reachable}/{total} reachable -> {OUT_COVERAGE.relative_to(REPO)}")
    print(f"  fingerprint {len(org) + len(other)} routes -> {OUT_FINGERPRINT.relative_to(REPO)}")
    print(f"  map         {len(entities)} entities -> {OUT_MAP.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
