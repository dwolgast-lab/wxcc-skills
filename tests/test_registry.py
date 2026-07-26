"""Offline invariants for the ENTITIES registry.

Needs no tenant, no token, and no `mcp` package - the registry is read by parsing
`mcp_server.py` with `ast`, the same way `scripts/build_api_reference.py` does, so
this runs on a bare Python install:

    python -m unittest discover tests -v

Every assertion here traces to a line in `mcp_server.py` that consumes the key. A
test that does not protect a real consumer does not belong in this file - the point
is to catch a registry edit that breaks a live call, not to admire the schema.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from build_api_reference import load_entities  # noqa: E402

ENTITIES = load_entities()

BULK_OPS = {"create", "update", "delete"}
BULK_METHODS = {"POST", "PATCH", "PUT"}
WRITE_OPS = {"create", "update", "delete"}

# `_path` documents the rule: "List (GET) uses the v2 path; item AND create-collection
# paths drop v2." user-profile is the deliberate exception - it is pinned to v3 on both,
# which is why the registry comment calls it out. A NEW entity landing here is a bug.
VERSIONED_ITEM_OK = {"user-profile"}

# Every entity is supposed to carry its probe findings in `note` - that is where this
# project keeps the things the vendor spec gets wrong. entry-point is the one entity
# that never got one. Known gap, tracked in TODO.md; not a licence to add more.
NOTE_OPTIONAL = {"entry-point"}


class RegistryShape(unittest.TestCase):
    """Keys that mcp_server.py reads with [] rather than .get() - absence is a crash."""

    def test_registry_is_not_empty(self):
        self.assertGreater(len(ENTITIES), 0, "ast parse of ENTITIES returned nothing")

    def test_every_entity_has_list_and_item(self):
        # mcp_server.py:707,711 - spec["item"] / spec["list"], both unguarded.
        for name, spec in ENTITIES.items():
            with self.subTest(entity=name):
                self.assertTrue(spec.get("list"), f"{name}: no 'list' path")
                self.assertTrue(spec.get("item"), f"{name}: no 'item' path")

    def test_item_path_ends_with_id_placeholder(self):
        """The create/collection path is derived by stripping '/{id}' from `item`.

        mcp_server.py:709 - `spec["item"].replace("/{id}", "")`. If `item` does not
        contain that exact substring the replace is a silent no-op and every CREATE
        for the entity POSTs to the item path instead of the collection.
        """
        for name, spec in ENTITIES.items():
            with self.subTest(entity=name):
                item = spec["item"]
                self.assertIn("/{id}", item,
                              f"{name}: item {item!r} lacks '/{{id}}' - create would "
                              f"silently POST to the item path")
                self.assertTrue(item.endswith("/{id}"),
                                f"{name}: item {item!r} must end with '/{{id}}' so "
                                f"stripping it yields a clean collection path")

    def test_paths_are_relative_and_unprefixed(self):
        """`_path` builds 'organization/{orgId}/' + tail (mcp_server.py:710)."""
        for name, spec in ENTITIES.items():
            for key in ("list", "item"):
                with self.subTest(entity=name, key=key):
                    p = spec[key]
                    self.assertFalse(p.startswith("/"),
                                     f"{name}.{key}={p!r} - leading slash doubles the "
                                     f"separator after organization/{{orgId}}")
                    self.assertNotIn("organization/", p,
                                     f"{name}.{key}={p!r} already carries the org "
                                     f"prefix that _path prepends")

    def test_item_path_drops_the_version_prefix(self):
        for name, spec in ENTITIES.items():
            if name in VERSIONED_ITEM_OK:
                continue
            with self.subTest(entity=name):
                self.assertIsNone(
                    re.match(r"^v\d+/", spec["item"]),
                    f"{name}: item {spec['item']!r} keeps a version prefix. GET v2/x "
                    f"lists but the item and create paths drop it. If this entity is a "
                    f"real exception, probe it and add it to VERSIONED_ITEM_OK.")

    def test_every_entity_carries_its_probe_findings(self):
        for name, spec in ENTITIES.items():
            if name in NOTE_OPTIONAL:
                continue
            with self.subTest(entity=name):
                self.assertTrue(spec.get("note"), f"{name}: no 'note'")


class WriteDeclarations(unittest.TestCase):

    def test_writes_only_names_known_ops(self):
        for name, spec in ENTITIES.items():
            with self.subTest(entity=name):
                self.assertLessEqual(set(spec.get("writes") or []), WRITE_OPS,
                                     f"{name}: unknown op in 'writes'")

    def test_create_op_has_a_required_field_list(self):
        """wxcc_create reports required fields from spec['create'] (mcp_server.py:1011).

        Declaring create support without them means the tool cannot pre-validate and
        the caller learns the requirement from a live 400.
        """
        for name, spec in ENTITIES.items():
            if "create" not in (spec.get("writes") or []):
                continue
            with self.subTest(entity=name):
                fields = spec.get("create")
                self.assertTrue(fields, f"{name}: declares create but has no 'create'")
                self.assertIsInstance(fields, list)
                for f in fields:
                    self.assertIsInstance(f, str, f"{name}: non-str create field {f!r}")

    def test_update_requires_file_implies_an_upload_route(self):
        """mcp_server.py:1069 refuses update without file_path when this is set.

        On an entity with no `upload` block that is unsatisfiable - every update is
        rejected and no code path can ever supply the file.
        """
        for name, spec in ENTITIES.items():
            if spec.get("update_requires_file"):
                with self.subTest(entity=name):
                    self.assertTrue(spec.get("upload"),
                                    f"{name}: update_requires_file with no upload block "
                                    f"- update is unsatisfiable")

    def test_upload_block_is_complete(self):
        # mcp_server.py:1112 - spec["upload"], then its three fields.
        for name, spec in ENTITIES.items():
            up = spec.get("upload")
            if not up:
                continue
            with self.subTest(entity=name):
                for key in ("field", "info_field", "file_type"):
                    self.assertIn(key, up, f"{name}.upload missing {key!r}")


class BulkDeclarations(unittest.TestCase):
    """_bulk_ep reads e["method"] and e["tail"] unguarded (mcp_server.py:1473-1475)."""

    def test_bulk_ops_are_known_and_complete(self):
        for name, spec in ENTITIES.items():
            for op, ep in (spec.get("bulk") or {}).items():
                with self.subTest(entity=name, op=op):
                    self.assertIn(op, BULK_OPS, f"{name}: unknown bulk op {op!r}")
                    self.assertIn("method", ep, f"{name}.bulk.{op}: no method")
                    self.assertIn("tail", ep, f"{name}.bulk.{op}: no tail")
                    self.assertIn(ep["method"], BULK_METHODS,
                                  f"{name}.bulk.{op}: odd method {ep['method']!r}")
                    self.assertFalse(ep["tail"].startswith("/"),
                                     f"{name}.bulk.{op}: tail has a leading slash")

    def test_partial_flag_only_on_update(self):
        """_bulk_ep only reads `partial` for update; elsewhere it is silently ignored,
        which makes it a lie sitting in the registry."""
        for name, spec in ENTITIES.items():
            for op, ep in (spec.get("bulk") or {}).items():
                if op != "update":
                    with self.subTest(entity=name, op=op):
                        self.assertNotIn("partial", ep,
                                         f"{name}.bulk.{op}: 'partial' is only read for "
                                         f"update - it does nothing here")


class ChildEntities(unittest.TestCase):

    def test_child_and_child_create_travel_together(self):
        """The entry tools gate on `child` (mcp_server.py:1269) then report required
        fields from `child_create` (mcp_server.py:1333)."""
        for name, spec in ENTITIES.items():
            with self.subTest(entity=name):
                self.assertEqual(
                    bool(spec.get("child")), bool(spec.get("child_create")),
                    f"{name}: 'child' and 'child_create' must both be present or "
                    f"both absent")


if __name__ == "__main__":
    unittest.main()
