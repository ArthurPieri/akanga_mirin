"""
Phase 03 — Graph Algorithm Tests

Tests for graph.py:
    build_ego_graph(root_id, db, max_depth) -> EgoGraph
    render_ascii(ego) -> str
"""
import uuid
from pathlib import Path

import pytest

from tests.phase_03.conftest import _load_graph, _load_db

# Bound by the autouse fixture below at fixture time -- not import time -- so
# a missing/broken learner module is reported through the AKANGA_SRC guard's
# diagnostics instead of a raw collection error (adversarial-analysis-v5 #2).
_graph_mod = None
build_ego_graph = None
render_ascii = None
EgoGraph = None
EdgeDirection = None


@pytest.fixture(scope="module", autouse=True)
def _bind_learner_modules():
    global _graph_mod, build_ego_graph, render_ascii, EgoGraph, EdgeDirection
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
    GraphDatabase = _load_db()

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

    def test_circular_graph_resolution(self, tmp_path: Path) -> None:
        """BFS traversal must handle cycles (A→B, B→A) without infinite loops or duplicate edges."""
        GraphDatabase = _load_db()
        db_path = tmp_path / "circular.db"
        db = GraphDatabase(str(db_path))

        id_a = str(uuid.UUID("aaaaaaaa-4444-4444-4444-000000000001"))
        id_b = str(uuid.UUID("bbbbbbbb-4444-4444-4444-000000000002"))

        for nid, title, fname in [
            (id_a, "A", "a.md"),
            (id_b, "B", "b.md"),
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

        db.upsert_edge(id_a, id_b, relation="links")
        db.upsert_edge(id_b, id_a, relation="links")

        try:
            ego = build_ego_graph(id_a, db, max_depth=5)
            assert id_a in ego.nodes
            assert id_b in ego.nodes
            assert len(ego.nodes) == 2

            # Verify no duplicate edges in the EgoGraph
            edge_signatures = set()
            for e in ego.edges:
                sig = (e.source_id, e.target_id, e.relation, e.direction)
                assert sig not in edge_signatures, f"Duplicate edge found: {sig}"
                edge_signatures.add(sig)
        finally:
            db.close()

    def test_build_ego_graph_both_directions(self, tmp_path: Path) -> None:
        """A→B (outgoing) and C→A (incoming): depth=1 from A includes both B and C."""
        GraphDatabase = _load_db()


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

        GraphDatabase = _load_db()

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
        GraphDatabase = _load_db()


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


# ---------------------------------------------------------------------------
# Node budget (C4 / N8): build_ego_graph(..., limit=) caps node count and
# reports truncation. Assert COUNTS and the flag only — never WHICH neighbours
# survived (the budget order is an implementation detail).
# ---------------------------------------------------------------------------


def _star_db(tmp_path: Path):
    """Return a db + root id for a star: root → n1..n5 (5 outgoing edges)."""
    GraphDatabase = _load_db()
    db = GraphDatabase(str(tmp_path / "star.db"))

    root_id = str(uuid.UUID("aaaaaaaa-0000-0000-0000-000000000000"))
    ids = [root_id] + [
        str(uuid.UUID(f"bbbbbbbb-0000-0000-0000-00000000000{i}")) for i in range(1, 6)
    ]
    for n, nid in enumerate(ids):
        db.upsert_node(
            {
                "id": nid,
                "title": f"Node-{n}",            # unique per node, never collide
                "type": "note",
                "tags": [],
                "path": str(tmp_path / f"node-{nid}.md"),   # full UUID = unique path
                "content": "",
                "content_hash": f"hash_{nid[:8]}",
            }
        )
    for nid in ids[1:]:
        db.upsert_edge(root_id, nid, relation="links_to")
    return db, root_id


class TestEgoGraphNodeBudget:
    def test_ego_graph_limit_truncates(self, tmp_path: Path) -> None:
        """limit=3 on a root with 5 neighbours: exactly 3 nodes, truncated=True,
        and every recorded edge has both endpoints inside nodes."""
        db, root_id = _star_db(tmp_path)
        try:
            ego = build_ego_graph(root_id, db, max_depth=1, limit=3)
            assert len(ego.nodes) == 3, "limit=3 must cap nodes at 3 (root + 2)"
            assert ego.truncated is True, "truncation must be reported to the caller"
            node_ids = set(ego.nodes)
            for edge in ego.edges:
                assert edge.source_id in node_ids, "edge source must be a kept node"
                assert edge.target_id in node_ids, "edge target must be a kept node"
        finally:
            db.close()

    def test_ego_graph_no_limit_not_truncated(self, tmp_path: Path) -> None:
        """limit=None (default) keeps every neighbour and never flags truncation."""
        db, root_id = _star_db(tmp_path)
        try:
            ego = build_ego_graph(root_id, db, max_depth=1)
            assert len(ego.nodes) == 6, "unbounded build keeps root + 5 neighbours"
            assert ego.truncated is False, "an unbounded build is never truncated"
        finally:
            db.close()
