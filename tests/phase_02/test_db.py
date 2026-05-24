"""Phase 02 tests — GraphDatabase: upsert, delete, list, FTS5, edges, WAL."""
import sqlite3
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(node_id: str, title: str, tmp_vault: Path, *, tags=None, content_hash=None):
    """Construct a minimal Node instance for use in tests."""
    from parser import Node  # noqa: PLC0415

    return Node(
        id=node_id,
        path=str(tmp_vault / f"{node_id[:8]}.md"),
        title=title,
        type="note",
        tags=tags or [],
        content_hash=content_hash or f"hash_{node_id[:8]}",
    )


# ---------------------------------------------------------------------------
# 1. upsert_node / get_node
# ---------------------------------------------------------------------------

def test_upsert_and_get_node(tmp_db: str, tmp_vault: Path):
    """Upserting a node and retrieving it by id returns matching fields."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaaaaaa-0001-0001-0001-000000000001", "Cognitive Load", tmp_vault)
    db.upsert_node(node)

    fetched = db.get_node(node.id)
    assert fetched is not None
    assert fetched.id == node.id
    assert fetched.title == node.title
    assert fetched.type == node.type


def test_upsert_is_idempotent(tmp_db: str, tmp_vault: Path):
    """Upserting the same node twice results in exactly one row in the DB."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaaaaaa-0002-0002-0002-000000000002", "Idempotent Node", tmp_vault)
    db.upsert_node(node)
    db.upsert_node(node)

    conn = sqlite3.connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM nodes WHERE id = ?", (node.id,)).fetchone()[0]
    conn.close()
    assert count == 1


def test_upsert_updates_existing(tmp_db: str, tmp_vault: Path):
    """Upserting a node with a changed title overwrites the previous title."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaaaaaa-0003-0003-0003-000000000003", "Original Title", tmp_vault)
    db.upsert_node(node)

    node.title = "Updated Title"
    db.upsert_node(node)

    fetched = db.get_node(node.id)
    assert fetched.title == "Updated Title"


def test_delete_node(tmp_db: str, tmp_vault: Path):
    """Deleting a node by id means get_node returns None afterwards."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaaaaaa-0004-0004-0004-000000000004", "To Delete", tmp_vault)
    db.upsert_node(node)
    db.delete_node(node.id)

    assert db.get_node(node.id) is None


# ---------------------------------------------------------------------------
# 2. list_nodes
# ---------------------------------------------------------------------------

def test_list_nodes(tmp_db: str, tmp_vault: Path):
    """After upserting 3 nodes, list_nodes returns all 3."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    for i in range(3):
        db.upsert_node(_make_node(f"bbbbbbbb-000{i}-000{i}-000{i}-00000000000{i}", f"List Node {i}", tmp_vault))

    nodes = db.list_nodes()
    assert len(nodes) >= 3


def test_list_nodes_limit_offset(tmp_db: str, tmp_vault: Path):
    """list_nodes respects limit and offset for pagination."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    for i in range(5):
        node_id = f"cccccccc-{i:04d}-{i:04d}-{i:04d}-{i:012d}"
        db.upsert_node(_make_node(node_id, f"Page Node {i}", tmp_vault))

    page = db.list_nodes(limit=2, offset=2)
    assert len(page) == 2


# ---------------------------------------------------------------------------
# 3. FTS5 search
# ---------------------------------------------------------------------------

def test_search_fts_basic(tmp_db: str, tmp_vault: Path):
    """A node titled 'Cognitive Load' is returned when searching 'cognitive'."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("dddddddd-0001-0001-0001-000000000001", "Cognitive Load", tmp_vault, tags=["cognition"])
    db.upsert_node(node)

    results = db.search_fts("cognitive")
    assert any(r.id == node.id for r in results)


def test_search_fts_no_operator_injection(tmp_db: str, tmp_vault: Path):
    """FTS5 operator-like input must not crash (SEC-06: terms are double-quoted)."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    # Should return an empty list (or any list), never raise an exception.
    try:
        results = db.search_fts("* OR title:*")
        assert isinstance(results, list)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"search_fts raised an unexpected exception on operator input: {exc}")


# ---------------------------------------------------------------------------
# 4. Edges — neighbors and backlinks
# ---------------------------------------------------------------------------

def test_upsert_edge_and_get_neighbors(tmp_db: str, tmp_vault: Path):
    """After inserting an edge A→B, get_neighbors(A.id) includes B."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node_a = _make_node("eeeeeeee-0001-0001-0001-000000000001", "Source Node", tmp_vault)
    node_b = _make_node("eeeeeeee-0002-0002-0002-000000000002", "Target Node", tmp_vault)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge({
        "source_id": node_a.id,
        "target_id": node_b.id,
        "target_title": node_b.title,
        "relation": "supports",
        "relation_id": "EP-001",
    })

    neighbors = db.get_neighbors(node_a.id)
    assert any(n.id == node_b.id for n in neighbors)


def test_get_backlinks(tmp_db: str, tmp_vault: Path):
    """After inserting edge A→B, get_backlinks(B.id) includes A."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node_a = _make_node("ffffffff-0001-0001-0001-000000000001", "Backlink Source", tmp_vault)
    node_b = _make_node("ffffffff-0002-0002-0002-000000000002", "Backlink Target", tmp_vault)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge({
        "source_id": node_a.id,
        "target_id": node_b.id,
        "target_title": node_b.title,
        "relation": "contradicts",
        "relation_id": "EP-002",
    })

    backlinks = db.get_backlinks(node_b.id)
    assert any(n.id == node_a.id for n in backlinks)


def test_delete_node_removes_edges(tmp_db: str, tmp_vault: Path):
    """Deleting the source node cascades to remove its outgoing edges."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node_a = _make_node("11111111-0001-0001-0001-000000000001", "Cascade Source", tmp_vault)
    node_b = _make_node("22222222-0002-0002-0002-000000000002", "Cascade Target", tmp_vault)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge({
        "source_id": node_a.id,
        "target_id": node_b.id,
        "target_title": node_b.title,
        "relation": "supports",
        "relation_id": "EP-001",
    })

    db.delete_node(node_a.id)

    # B must still exist; edge must be gone
    assert db.get_node(node_b.id) is not None
    backlinks = db.get_backlinks(node_b.id)
    assert not any(n.id == node_a.id for n in backlinks)


# ---------------------------------------------------------------------------
# 5. WAL mode
# ---------------------------------------------------------------------------

def test_wal_mode(tmp_db: str):
    """After GraphDatabase.__init__, SQLite journal_mode must be 'wal'."""
    from db import GraphDatabase  # noqa: PLC0415

    GraphDatabase(tmp_db)
    conn = sqlite3.connect(tmp_db)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


# ---------------------------------------------------------------------------
# 6. Error paths
# ---------------------------------------------------------------------------

def test_get_node_not_found(tmp_db: str):
    """get_node with a non-existent id returns None without raising."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    result = db.get_node("nonexistent-id-that-does-not-exist")
    assert result is None


def test_delete_nonexistent_node(tmp_db: str):
    """delete_node with a non-existent id does not raise an exception."""
    from db import GraphDatabase  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    # Must complete without raising.
    db.delete_node("nonexistent-id-that-does-not-exist")
