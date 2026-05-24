"""
Phase 03 — Graph Algorithm Tests

Tests for graph.py:
    build_ego_graph(root_id, db, max_depth) -> EgoGraph
    render_ascii(ego) -> str
"""
import uuid
from pathlib import Path

import pytest

from tests.phase_03.conftest import _load_graph

_graph_mod = _load_graph()
build_ego_graph = _graph_mod.build_ego_graph
render_ascii = _graph_mod.render_ascii
EgoGraph = _graph_mod.EgoGraph
EdgeDirection = _graph_mod.EdgeDirection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_chain_db(tmp_path: Path):
    """Return a db + (id_a, id_b, id_c) for a simple A → B → C chain."""
    from akanga_core.db import GraphDatabase

    db_path = tmp_path / "chain.db"
    db = GraphDatabase(str(db_path))

    id_a = str(uuid.UUID("aaaaaaaa-1111-1111-1111-000000000001"))
    id_b = str(uuid.UUID("bbbbbbbb-1111-1111-1111-000000000002"))
    id_c = str(uuid.UUID("cccccccc-1111-1111-1111-000000000003"))

    for nid, title, fname in [
        (id_a, "Alpha", "alpha.md"),
        (id_b, "Beta", "beta.md"),
        (id_c, "Gamma", "gamma.md"),
    ]:
        db.upsert_node(
            {
                "id": nid,
                "title": title,
                "type": "note",
                "tags": [],
                "path": str(tmp_path / fname),
                "content": "",
                "content_hash": f"hash_{nid[:4]}",
            }
        )

    db.upsert_edge(id_a, id_b, relation="links_to")
    db.upsert_edge(id_b, id_c, relation="links_to")

    return db, id_a, id_b, id_c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildEgoGraphDepth:
    def test_build_ego_graph_depth_1(self, tmp_path: Path) -> None:
        """depth=1 from A in A→B→C: only A and B, not C."""


        db, id_a, id_b, id_c = _simple_chain_db(tmp_path)
        try:
            ego = build_ego_graph(id_a, db, max_depth=1)
            assert id_a in ego.nodes, "root A must be in nodes"
            assert id_b in ego.nodes, "direct neighbor B must be in nodes at depth 1"
            assert id_c not in ego.nodes, "C is 2 hops away; must NOT be in nodes at depth 1"
        finally:
            db.close()

    def test_build_ego_graph_depth_2(self, tmp_path: Path) -> None:
        """depth=2 from A in A→B→C: A, B, and C all present."""


        db, id_a, id_b, id_c = _simple_chain_db(tmp_path)
        try:
            ego = build_ego_graph(id_a, db, max_depth=2)
            assert id_a in ego.nodes
            assert id_b in ego.nodes
            assert id_c in ego.nodes
        finally:
            db.close()

    def test_ego_graph_max_depth_zero(self, tmp_path: Path) -> None:
        """max_depth=0: only the root node, no neighbors."""


        db, id_a, id_b, id_c = _simple_chain_db(tmp_path)
        try:
            # Spec says depth=0 → only root. If impl raises ValueError that is
            # also acceptable — but it must not include neighbor nodes.
            try:
                ego = build_ego_graph(id_a, db, max_depth=0)
            except ValueError:
                return  # raising is acceptable
            assert id_a in ego.nodes, "root must still be present"
            assert id_b not in ego.nodes, "no traversal at depth 0"
            assert id_c not in ego.nodes
        finally:
            db.close()


class TestBuildEgoGraphStructure:
    def test_build_ego_graph_includes_root(self, populated_graph_db) -> None:
        """Root node is always present in ego.nodes regardless of depth."""


        db = populated_graph_db
        ego = build_ego_graph(db.id_a, db, max_depth=1)
        assert ego.root is not None
        assert db.id_a in ego.nodes
        assert ego.nodes[db.id_a] is ego.root

    def test_build_ego_graph_cycle_handling(self, populated_graph_db) -> None:
        """Cycle A→B→A at depth=3: terminates without infinite loop."""


        db = populated_graph_db
        # Should complete — pytest timeout is the implicit guard here
        ego = build_ego_graph(db.id_a, db, max_depth=3)
        # Both A and B must be present; graph did not blow up
        assert db.id_a in ego.nodes
        assert db.id_b in ego.nodes

    def test_build_ego_graph_both_directions(self, tmp_path: Path) -> None:
        """A→B (outgoing) and C→A (incoming): depth=1 from A includes both B and C."""
        from akanga_core.db import GraphDatabase


        db_path = tmp_path / "bidir.db"
        db = GraphDatabase(str(db_path))

        id_a = str(uuid.UUID("aaaaaaaa-2222-2222-2222-000000000001"))
        id_b = str(uuid.UUID("bbbbbbbb-2222-2222-2222-000000000002"))
        id_c = str(uuid.UUID("cccccccc-2222-2222-2222-000000000003"))

        for nid, title, fname in [
            (id_a, "Center", "center.md"),
            (id_b, "Out", "out.md"),
            (id_c, "In", "in.md"),
        ]:
            db.upsert_node(
                {
                    "id": nid,
                    "title": title,
                    "type": "note",
                    "tags": [],
                    "path": str(tmp_path / fname),
                    "content": "",
                    "content_hash": f"h{nid[:4]}",
                }
            )

        db.upsert_edge(id_a, id_b, relation="outgoing")  # A → B
        db.upsert_edge(id_c, id_a, relation="incoming")  # C → A

        try:
            ego = build_ego_graph(id_a, db, max_depth=1)
            assert id_b in ego.nodes, "B is an outgoing neighbor of A"
            assert id_c in ego.nodes, "C points TO A (incoming); must also be included"
        finally:
            db.close()

    def test_build_ego_graph_edge_directions(self, tmp_path: Path) -> None:
        """EgoEdge objects carry the correct EdgeDirection value."""


        db_path = tmp_path / "dir.db"

        from akanga_core.db import GraphDatabase

        db = GraphDatabase(str(db_path))

        id_root = str(uuid.UUID("aaaaaaaa-3333-3333-3333-000000000001"))
        id_out = str(uuid.UUID("bbbbbbbb-3333-3333-3333-000000000002"))
        id_in = str(uuid.UUID("cccccccc-3333-3333-3333-000000000003"))

        for nid, title, fname in [
            (id_root, "Root", "root.md"),
            (id_out, "Outgoing", "out.md"),
            (id_in, "Incoming", "in.md"),
        ]:
            db.upsert_node(
                {
                    "id": nid,
                    "title": title,
                    "type": "note",
                    "tags": [],
                    "path": str(tmp_path / fname),
                    "content": "",
                    "content_hash": f"h{nid[:4]}",
                }
            )

        db.upsert_edge(id_root, id_out, relation="links_to")  # root → out
        db.upsert_edge(id_in, id_root, relation="points_at")  # in → root

        try:
            ego = build_ego_graph(id_root, db, max_depth=1)
            directions = {(e.source_id, e.target_id): e.direction for e in ego.edges}

            # root → out should be OUTGOING (relative to root)
            assert (id_root, id_out) in directions
            assert directions[(id_root, id_out)] == EdgeDirection.OUTGOING

            # in → root should be INCOMING (relative to root)
            assert (id_in, id_root) in directions
            assert directions[(id_in, id_root)] == EdgeDirection.INCOMING
        finally:
            db.close()

    def test_build_ego_graph_empty_graph(self, tmp_path: Path) -> None:
        """Node with no edges: ego contains only the root, no edges."""
        from akanga_core.db import GraphDatabase


        db_path = tmp_path / "empty.db"
        db = GraphDatabase(str(db_path))
        lone_id = str(uuid.UUID("ffffffff-0000-0000-0000-000000000001"))
        db.upsert_node(
            {
                "id": lone_id,
                "title": "Lone Node",
                "type": "note",
                "tags": [],
                "path": str(tmp_path / "lone.md"),
                "content": "",
                "content_hash": "hash_lone",
            }
        )

        try:
            ego = build_ego_graph(lone_id, db, max_depth=2)
            assert lone_id in ego.nodes
            assert len(ego.nodes) == 1
            assert len(ego.edges) == 0
        finally:
            db.close()

    def test_build_ego_graph_nonexistent_root(self, populated_graph_db) -> None:
        """Nonexistent root_id: implementation must raise (not silently return None)."""


        db = populated_graph_db
        bad_id = str(uuid.UUID("00000000-dead-beef-0000-000000000000"))
        with pytest.raises(Exception):
            build_ego_graph(bad_id, db, max_depth=1)


class TestRenderAscii:
    def test_render_ascii_returns_string(self, populated_graph_db) -> None:
        """render_ascii must return a non-empty string without crashing."""


        db = populated_graph_db
        ego = build_ego_graph(db.id_a, db, max_depth=1)
        result = render_ascii(ego)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_ascii_contains_node_title(self, populated_graph_db) -> None:
        """The root node's title must appear somewhere in the ASCII output."""


        db = populated_graph_db
        ego = build_ego_graph(db.id_a, db, max_depth=1)
        result = render_ascii(ego)
        assert ego.root.title in result, (
            f"Expected root title {ego.root.title!r} to appear in render_ascii output"
        )
