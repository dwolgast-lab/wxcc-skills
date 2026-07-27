"""Negative test for the schema-drift detector. NOT part of the offline suite.

`python -m unittest discover tests` will not collect this file (the default pattern
is test*.py) because it fetches the live spec. Run it by hand after changing
`schema_shape`, `body_hash` or `check_drift`:

    python tests/verify_drift_detection.py

A drift check that has only ever printed "no changes" is not evidence it works - the
route fingerprint earned its trust by being deliberately corrupted, and the schema
half is held to the same bar. This plants six mutations and asserts the detector
reacts to exactly the three that matter:

  1. a renamed property in a request-body schema       -> MUST trip
  2. a renamed property in a *DTO QUERY-PARAM schema   -> MUST trip
  3. a request body added to a query-DTO-only op       -> MUST trip
  4. a description-only reword                         -> must NOT trip (noise)
  5. an edit to a deliberately-refused route           -> must NOT trip (out of scope)
  6. a new OPTIONAL query parameter                    -> must NOT trip (noise)

Case 2 is the one this file exists for. `team`, `skill`, `skill-profile` and
`agent-profile` declare NO requestBody - they take the object as a required query
parameter (`?teamDTO=`, `?payloadDTO=`, `?skillProfileDTO=`, `?agentProfileDTO=`)
holding urlencoded JSON. A detector that hashed only request bodies would silently
skip create AND update on four core entities, which is exactly what the first cut of
this did. Case 3 is the realistic future: Cisco making those routes consistent with
the rest by giving them a body.

Cases 4-6 are the noise guards. A detector that fires on reworded prose, on routes
nobody calls, or on an optional parameter gets muted, and a muted detector is worse
than none.
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


def _run(real_spec, mutate, label, expect_drift):
    spec = copy.deepcopy(real_spec)
    detail = mutate(spec)
    B.fetch = lambda url, accept_json=True: spec
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = B.check_drift()
    out = buf.getvalue()
    drifted = rc == 1 and "SCHEMA DRIFT" in out
    ok = drifted == expect_drift
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"        {detail}")
    print(f"        expected drift={expect_drift}  got={drifted}  exit={rc}")
    for line in out.splitlines():
        if line.strip().startswith("~") or "SCHEMA DRIFT" in line:
            print(f"        | {line.strip()}")
    print()
    return ok


def rename_in_body_schema(spec):
    s = spec["components"]["schemas"]["BulkRequestDTOTeamDTO"]
    props = s.get("properties") or {}
    old = sorted(props)[0]
    props[f"{old}_RENAMED"] = props.pop(old)
    return f"renamed property {old!r} in BulkRequestDTOTeamDTO (a request BODY schema)"


def rename_in_query_dto_schema(spec):
    """The case the first cut of the detector missed entirely."""
    s = spec["components"]["schemas"]["TeamDTO"]
    props = s.get("properties") or {}
    old = sorted(props)[0]
    props[f"{old}_RENAMED"] = props.pop(old)
    return f"renamed property {old!r} in TeamDTO (reached only via ?teamDTO=)"


def add_body_to_query_dto_op(spec):
    spec["paths"]["/organization/{orgid}/team"]["post"]["requestBody"] = {
        "content": {"application/json": {"schema": {
            "type": "object", "required": ["name"],
            "properties": {"name": {"type": "string"}}}}}}
    return "gave POST team a requestBody alongside its ?teamDTO= param"


def add_optional_query_param(spec):
    spec["paths"]["/organization/{orgid}/team"]["post"].setdefault(
        "parameters", []).append(
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
    p = "/organization/{orgid}/team/purge-inactive-entities"
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
             "renamed field in a request-BODY schema", True),
        _run(real, rename_in_query_dto_schema,
             "renamed field in a ?teamDTO= QUERY-PARAM schema", True),
        _run(real, add_body_to_query_dto_op,
             "requestBody added to a query-DTO-only op", True),
        _run(real, reword_description,
             "description-only edit (must NOT trip)", False),
        _run(real, touch_refused_route,
             "edit to a refused route (must NOT trip)", False),
        _run(real, add_optional_query_param,
             "new OPTIONAL query parameter (must NOT trip)", False),
    ]
    print("=" * 60)
    ok = all(results)
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
