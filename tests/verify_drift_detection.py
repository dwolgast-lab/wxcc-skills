"""Negative test for the schema-drift detector. NOT part of the offline suite.

`python -m unittest discover tests` will not collect this file (the default pattern
is test*.py) because it fetches the live spec. Run it by hand after changing
`schema_shape`, `payload_hash` or `check_drift`:

    python tests/verify_drift_detection.py

A drift check that has only ever printed "no changes" is not evidence it works - the
route fingerprint earned its trust by being deliberately corrupted, and the payload
half is held to the same bar. This plants nine mutations and asserts the detector
reports EXACTLY the routes that should have moved:

  1. a renamed property in a request-body schema        -> team/bulk only
  2-5. a renamed property in each *DTO QUERY-PARAM      -> create + update + bulk
  6. a request body added to a query-DTO-only op        -> that create only
  7. a description-only reword                          -> nothing (noise)
  8. an edit to a deliberately-refused route            -> nothing (out of scope)
  9. a new OPTIONAL query parameter                     -> nothing (noise)

WHY THIS ASSERTS ROUTES AND NOT MERELY "did it trip":
Cases 2-5 exist to prove the detector reads *DTO query parameters, since `team`,
`skill`, `skill-profile` and `agent-profile` declare NO requestBody - they take the
object as a required query parameter (`?teamDTO=`, `?payloadDTO=`, `?skillProfileDTO=`,
`?agentProfileDTO=`) holding urlencoded JSON. The first cut of this file only asserted
that SOME drift was reported, and that assertion was worthless: every one of those four
DTOs is ALSO `$ref`d from its own bulk-request envelope, so a body-only detector still
trips - via `POST <entity>/bulk`, a route that was never in question. Measured against
a reconstruction of the pre-fix implementation, a `TeamDTO` rename moved 1 route
(`POST team/bulk`) rather than 3. The test passed against the exact bug it was written
to catch. Asserting the full route set is what makes it discriminate: the create and
update routes are reachable ONLY through the query parameter.

Cases 7-9 are the noise guards. A detector that fires on reworded prose, on routes
nobody calls, or on an optional parameter gets muted, and a muted detector is worse
than none.

A failure here can also mean the committed fingerprint is simply stale - if upstream
genuinely moved, every case picks up the same extra routes. Run
`python scripts/build_api_reference.py --check` first to tell the two apart.
"""
from __future__ import annotations

import copy
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_api_reference as B  # noqa: E402

ORG = "/organization/{orgid}"

# The four entities whose create/update payload is a required query parameter rather
# than a request body, and the schema each one points at.
QUERY_DTO_ENTITIES = {
    "team": ("teamDTO", "TeamDTO"),
    "skill": ("payloadDTO", "SkillDTO"),
    "skill-profile": ("skillProfileDTO", "SkillProfileDTO"),
    "agent-profile": ("agentProfileDTO", "AgentProfileDTO"),
}


def _changed_routes(out: str) -> set[str]:
    """The routes check_drift named as having moved, from its own output."""
    return {line.strip()[1:].strip()
            for line in out.splitlines() if line.strip().startswith("~")}


def _run(real_spec, mutate, label, expect_routes: set[str]):
    spec = copy.deepcopy(real_spec)
    detail = mutate(spec)
    B.fetch = lambda url, accept_json=True: spec
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = B.check_drift()
    out = buf.getvalue()

    got = _changed_routes(out)
    drifted = rc == 1 and "SCHEMA DRIFT" in out
    ok = got == expect_routes and drifted == bool(expect_routes)

    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"        {detail}")
    if expect_routes:
        print(f"        expected {len(expect_routes)} route(s) to move:")
        for r in sorted(expect_routes):
            print(f"          - {r}")
    else:
        print("        expected NO routes to move")
    if got != expect_routes:
        for r in sorted(got - expect_routes):
            print(f"        UNEXPECTED  + {r}")
        for r in sorted(expect_routes - got):
            print(f"        MISSING     - {r}")
    else:
        print(f"        got exactly that (exit={rc})")
    print()
    return ok


def _rename_first_prop(spec, schema_name):
    props = spec["components"]["schemas"][schema_name].get("properties") or {}
    old = sorted(props)[0]
    props[f"{old}_RENAMED"] = props.pop(old)
    return old


def rename_in_body_schema(spec):
    old = _rename_first_prop(spec, "BulkRequestDTOTeamDTO")
    return f"renamed property {old!r} in BulkRequestDTOTeamDTO (a request BODY schema)"


def make_query_dto_case(entity):
    """Rename a property in a DTO reached by create/update ONLY via ?<param>=.

    The bulk route moves too - the same DTO is $ref'd from the bulk envelope - and
    that is precisely why this case must assert all three routes rather than 'trips'.
    """
    param, schema = QUERY_DTO_ENTITIES[entity]

    def mutate(spec):
        old = _rename_first_prop(spec, schema)
        return (f"renamed property {old!r} in {schema} "
                f"(create/update reach it only via ?{param}=)")

    return mutate, {
        f"POST {ORG}/{entity}",
        f"PUT {ORG}/{entity}/{{id}}",
        f"POST {ORG}/{entity}/bulk",
    }


def add_body_to_query_dto_op(spec):
    spec["paths"][f"{ORG}/team"]["post"]["requestBody"] = {
        "content": {"application/json": {"schema": {
            "type": "object", "required": ["name"],
            "properties": {"name": {"type": "string"}}}}}}
    return "gave POST team a requestBody alongside its ?teamDTO= param"


def add_optional_query_param(spec):
    spec["paths"][f"{ORG}/team"]["post"].setdefault("parameters", []).append(
        {"name": "zzzOptional", "in": "query", "required": False,
         "schema": {"type": "string"}})
    return "added an OPTIONAL query parameter to POST team"


def reword_description(spec):
    s = spec["components"]["schemas"]["BulkRequestDTOTeamDTO"]
    s["description"] = "Totally reworded prose that should not matter."
    for v in (s.get("properties") or {}).values():
        if isinstance(v, dict):
            v["description"] = "reworded"
    return "changed only descriptions on BulkRequestDTOTeamDTO"


def touch_refused_route(spec):
    p = f"{ORG}/team/purge-inactive-entities"
    spec["paths"][p]["post"]["requestBody"] = {"content": {"application/json": {
        "schema": {"type": "object", "properties": {"zzz": {"type": "string"}}}}}}
    return "changed the body of a REFUSED route (team/purge-inactive-entities)"


def main() -> int:
    if not B.OUT_FINGERPRINT.exists():
        print("no fingerprint - run scripts/build_api_reference.py first.")
        return 1
    print("fetching live spec for the baseline ...\n")
    real = B.fetch(B.SPEC_URL)
    B.upstream_commit = lambda: ("deadbeef" * 5, "1970-01-01T00:00:00Z")

    results = [
        _run(real, rename_in_body_schema,
             "renamed field in a request-BODY schema",
             {f"POST {ORG}/team/bulk"}),
    ]
    for entity in QUERY_DTO_ENTITIES:
        mutate, expect = make_query_dto_case(entity)
        results.append(_run(
            real, mutate,
            f"renamed field in the {entity} ?DTO= QUERY-PARAM schema", expect))
    results += [
        _run(real, add_body_to_query_dto_op,
             "requestBody added to a query-DTO-only op", {f"POST {ORG}/team"}),
        _run(real, reword_description,
             "description-only edit (must NOT trip)", set()),
        _run(real, touch_refused_route,
             "edit to a refused route (must NOT trip)", set()),
        _run(real, add_optional_query_param,
             "new OPTIONAL query parameter (must NOT trip)", set()),
    ]
    print("=" * 60)
    ok = all(results)
    print(f"{sum(results)}/{len(results)} checks passed")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
