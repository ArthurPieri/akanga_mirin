"""Phase 02 tests — GraphDatabase: upsert, delete, list, FTS5, edges, WAL."""
import sqlite3
from pathlib import Path

import pytest

from tests.phase_02.conftest import _load_db, _load_parser

# Bound by the autouse fixture below at fixture time -- not import time -- so
# a missing/broken learner module is reported through the AKANGA_SRC guard's
# diagnostics instead of a raw collection error (adversarial-analysis-v5 #2).
GraphDatabase = None
_parser_mod = None


@pytest.fixture(scope="module", autouse=True)
def _bind_learner_modules():
    global GraphDatabase, _parser_mod
    GraphDatabase = _load_db()
    _parser_mod = _load_parser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(node_id: str, title: str, vault_dir: Path, *, tags=None, content_hash=None):
    """Construct a minimal Node instance for use in tests."""
    Node = _parser_mod.Node

    return Node(
        id=node_id,
        path=str(vault_dir / f"{node_id}.md"),  # full id — node paths are UNIQUE in the DB schema
        title=title,
        type="note",
        tags=tags or [],
        content_hash=content_hash or f"hash_{node_id[:8]}",
    )


# ---------------------------------------------------------------------------
# 1. upsert_node / get_node
# ---------------------------------------------------------------------------

def test_upsert_and_get_node(db_path: str, vault_dir: Path):
    """Upserting a node and retrieving it by id returns matching fields."""


    db = GraphDatabase(db_path)
    node = _make_node("aaaaaaaa-0001-0001-0001-000000000001", "Cognitive Load", vault_dir)
    db.upsert_node(node)

    fetched = db.get_node(node.id)
    assert fetched is not None
    assert fetched.id == node.id
    assert fetched.title == node.title
    assert fetched.type == node.type


def test_upsert_is_idempotent(db_path: str, vault_dir: Path):
    """Upserting the same node twice results in exactly one row in the DB."""


    db = GraphDatabase(db_path)
    node = _make_node("aaaaaaaa-0002-0002-0002-000000000002", "Idempotent Node", vault_dir)
    db.upsert_node(node)
    db.upsert_node(node)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM nodes WHERE id = ?", (node.id,)).fetchone()[0]
    conn.close()
    assert count == 1


def test_upsert_updates_existing(db_path: str, vault_dir: Path):
    """Upserting a node with a changed title overwrites the previous title."""


    db = GraphDatabase(db_path)
    node = _make_node("aaaaaaaa-0003-0003-0003-000000000003", "Original Title", vault_dir)
    db.upsert_node(node)

    node.title = "Updated Title"
    db.upsert_node(node)

    fetched = db.get_node(node.id)
    assert fetched.title == "Updated Title"


def test_delete_node(db_path: str, vault_dir: Path):
    """Deleting a node by id means get_node returns None afterwards."""


    db = GraphDatabase(db_path)
    node = _make_node("aaaaaaaa-0004-0004-0004-000000000004", "To Delete", vault_dir)
    db.upsert_node(node)
    db.delete_node(node.id)

    assert db.get_node(node.id) is None


# ---------------------------------------------------------------------------
# 2. list_nodes
# ---------------------------------------------------------------------------

def test_list_nodes(db_path: str, vault_dir: Path):
    """After upserting 3 nodes, list_nodes returns all 3."""


    db = GraphDatabase(db_path)
    for i in range(3):
        db.upsert_node(_make_node(f"bbbbbbbb-000{i}-000{i}-000{i}-00000000000{i}", f"List Node {i}", vault_dir))

    nodes = db.list_nodes()
    assert len(nodes) >= 3


def test_list_nodes_limit_offset(db_path: str, vault_dir: Path):
    """list_nodes respects limit and offset for pagination."""


    db = GraphDatabase(db_path)
    for i in range(5):
        node_id = f"cccccccc-{i:04d}-{i:04d}-{i:04d}-{i:012d}"
        db.upsert_node(_make_node(node_id, f"Page Node {i}", vault_dir))

    page = db.list_nodes(limit=2, offset=2)
    assert len(page) == 2


# ---------------------------------------------------------------------------
# 3. FTS5 search
# ---------------------------------------------------------------------------

def test_search_fts_basic(db_path: str, vault_dir: Path):
    """A node titled 'Cognitive Load' is returned when searching 'cognitive'."""


    db = GraphDatabase(db_path)
    node = _make_node("dddddddd-0001-0001-0001-000000000001", "Cognitive Load", vault_dir, tags=["cognition"])
    db.upsert_node(node)

    results = db.search_fts("cognitive")
    assert any(r.id == node.id for r in results)


def test_search_fts_no_operator_injection(db_path: str, vault_dir: Path):
    """FTS5 operator-like input must not crash (SEC-06: terms are double-quoted)."""


    db = GraphDatabase(db_path)
    # Should return an empty list (or any list), never raise an exception.
    try:
        results = db.search_fts("* OR title:*")
        assert isinstance(results, list)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"search_fts raised an unexpected exception on operator input: {exc}")


def test_search_fts_operator_treated_as_literal(db_path: str, vault_dir: Path):
    """SEC-06 semantic check: searching 'OR' must match a node titled with the literal word.

    An implementation that swallows the FTS5 error (try/except: return []) passes
    the no-crash test above but fails this one — the quoted-term mitigation must
    actually treat operators as searchable literal text.
    """
    db = GraphDatabase(db_path)
    node = _make_node("dddddddd-0002-0002-0002-000000000002", "Boolean OR Logic", vault_dir)
    db.upsert_node(node)

    results = db.search_fts("OR")
    assert any(r.id == node.id for r in results), (
        "search_fts('OR') must return the node titled 'Boolean OR Logic'.\n"
        "The FTS5 operator 'OR' must be treated as a literal search term — wrap "
        'each term in double quotes ( \'"\' + term + \'"\' ) before MATCH.\n'
        "Swallowing the FTS5 error and returning [] is NOT a fix for SEC-06."
    )


def test_search_fts_embedded_double_quote_does_not_raise(db_path: str, vault_dir: Path):
    """SEC-06: a user term containing a double quote must not break the FTS5 query.

    The reference implementation needed exactly this handling: strip embedded
    quotes from the term before wrapping it ( term.replace('\"', '') ).
    """
    db = GraphDatabase(db_path)
    node = _make_node("dddddddd-0003-0003-0003-000000000003", "Cognition Quoted", vault_dir)
    db.upsert_node(node)

    try:
        results = db.search_fts('cogn"ition')
        assert isinstance(results, list), (
            f"search_fts on a term with an embedded double quote must return a "
            f"list, got {type(results).__name__!r}."
        )
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            "search_fts('cogn\"ition') raised — an embedded double quote in the "
            "user's term breaks naive quoting. Strip embedded quotes before "
            f"wrapping the term: term.replace('\"', ''). Got {type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# 4. Edges — neighbors and backlinks
# ---------------------------------------------------------------------------

def test_upsert_edge_and_get_neighbors(db_path: str, vault_dir: Path):
    """After inserting an edge A→B, get_neighbors(A.id) includes B."""


    db = GraphDatabase(db_path)
    node_a = _make_node("eeeeeeee-0001-0001-0001-000000000001", "Source Node", vault_dir)
    node_b = _make_node("eeeeeeee-0002-0002-0002-000000000002", "Target Node", vault_dir)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge(node_a.id, node_b.id, "supports", "EP-001")

    neighbors = db.get_neighbors(node_a.id)
    assert any(n.id == node_b.id for n in neighbors)


def test_get_backlinks(db_path: str, vault_dir: Path):
    """After inserting edge A→B, get_backlinks(B.id) includes A."""


    db = GraphDatabase(db_path)
    node_a = _make_node("ffffffff-0001-0001-0001-000000000001", "Backlink Source", vault_dir)
    node_b = _make_node("ffffffff-0002-0002-0002-000000000002", "Backlink Target", vault_dir)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge(node_a.id, node_b.id, "contradicts", "EP-002")

    backlinks = db.get_backlinks(node_b.id)
    assert any(n.id == node_a.id for n in backlinks)


def test_delete_node_removes_edges(db_path: str, vault_dir: Path):
    """Deleting the source node cascades to remove its outgoing edges."""


    db = GraphDatabase(db_path)
    node_a = _make_node("11111111-0001-0001-0001-000000000001", "Cascade Source", vault_dir)
    node_b = _make_node("22222222-0002-0002-0002-000000000002", "Cascade Target", vault_dir)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge(node_a.id, node_b.id, "supports", "EP-001")

    db.delete_node(node_a.id)

    # B must still exist; edge must be gone
    assert db.get_node(node_b.id) is not None
    backlinks = db.get_backlinks(node_b.id)
    assert not any(n.id == node_a.id for n in backlinks)


def test_get_edges_from(db_path: str, vault_dir: Path):
    """get_edges_from(A.id) returns [(Node, relation, relation_id)] for outgoing edges.

    Unlike get_neighbors, this preserves the relation label and registry id —
    Phase 3 ego graphs and Phase 8 RAG triples need them (a bare node list
    forces relation='' downstream and guts the 72-type vocabulary).
    """
    db = GraphDatabase(db_path)
    node_a = _make_node("33333333-0001-0001-0001-000000000001", "Edge From Source", vault_dir)
    node_b = _make_node("33333333-0002-0002-0002-000000000002", "Edge From Target", vault_dir)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge(node_a.id, node_b.id, "depends_on", "SC-001")

    edges = db.get_edges_from(node_a.id)
    assert len(edges) == 1, (
        f"Expected exactly 1 outgoing edge from A, got {len(edges)}.\n"
        "get_edges_from must return a list of (Node, relation, relation_id) tuples."
    )
    target, relation, relation_id = edges[0]
    assert target.id == node_b.id, (
        f"get_edges_from(A.id) must return the TARGET node, got {target.id!r}."
    )
    assert relation == "depends_on", (
        f"Expected relation 'depends_on', got {relation!r}. "
        "Select edges.relation alongside the joined node row."
    )
    assert relation_id == "SC-001", (
        f"Expected relation_id 'SC-001', got {relation_id!r}. "
        "Select edges.relation_id alongside the joined node row — the registry id "
        "must reach the DB and come back out."
    )


def test_get_edges_to(db_path: str, vault_dir: Path):
    """get_edges_to(B.id) returns [(Node, relation, relation_id)] for incoming edges."""
    db = GraphDatabase(db_path)
    node_a = _make_node("44444444-0001-0001-0001-000000000001", "Edge To Source", vault_dir)
    node_b = _make_node("44444444-0002-0002-0002-000000000002", "Edge To Target", vault_dir)
    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_edge(node_a.id, node_b.id, "uses", "SC-003")

    edges = db.get_edges_to(node_b.id)
    assert len(edges) == 1, (
        f"Expected exactly 1 incoming edge to B, got {len(edges)}.\n"
        "get_edges_to must return a list of (Node, relation, relation_id) tuples."
    )
    source, relation, relation_id = edges[0]
    assert source.id == node_a.id, (
        f"get_edges_to(B.id) must return the SOURCE node, got {source.id!r}."
    )
    assert relation == "uses", (
        f"Expected relation 'uses', got {relation!r}."
    )
    assert relation_id == "SC-003", (
        f"Expected relation_id 'SC-003', got {relation_id!r}."
    )


# ---------------------------------------------------------------------------
# 5. WAL mode
# ---------------------------------------------------------------------------

def test_wal_mode(db_path: str):
    """After GraphDatabase.__init__, SQLite journal_mode must be 'wal'."""


    GraphDatabase(db_path)
    conn = sqlite3.connect(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


# ---------------------------------------------------------------------------
# 6. Error paths
# ---------------------------------------------------------------------------

def test_get_node_not_found(db_path: str):
    """get_node with a non-existent id returns None without raising."""


    db = GraphDatabase(db_path)
    result = db.get_node("nonexistent-id-that-does-not-exist")
    assert result is None


def test_delete_nonexistent_node(db_path: str):
    """delete_node with a non-existent id does not raise an exception."""


    db = GraphDatabase(db_path)
    # Must complete without raising.
    db.delete_node("nonexistent-id-that-does-not-exist")


class _FailingConn:
    """A stand-in connection whose every statement raises sqlite3.Error.

    Simulates a disk-level write failure deterministically — the previous
    chmod-the-file approach gave OS-dependent verdicts under WAL because the
    connection (and WAL sidecar files) were already open.
    """

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error (simulated by test)")

    def executescript(self, *args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error (simulated by test)")

    def commit(self):
        raise sqlite3.OperationalError("disk I/O error (simulated by test)")

    def close(self):
        pass


def test_write_failure_propagates_sqlite_error(
    db_path: str, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """A failing connection must surface sqlite3.Error to the caller — not be swallowed.

    The caller (indexer, watcher handler) decides how to log/retry. Catching
    the error inside GraphDatabase and returning silently would hide data loss.
    """
    db = GraphDatabase(db_path)
    node = _make_node("00000000-0000-0000-0000-000000000000", "Initial", vault_dir)
    db.upsert_node(node)

    conn_attr = next((a for a in ("conn", "_conn") if hasattr(db, a)), None)
    if conn_attr is None:
        pytest.skip(
            "GraphDatabase exposes neither 'conn' nor '_conn' — cannot inject "
            "a failing connection. The skeleton stores the connection as self.conn."
        )
    monkeypatch.setattr(db, conn_attr, _FailingConn())

    with pytest.raises(sqlite3.Error):
        db.upsert_node(node)
    # If this fails with DID NOT RAISE: do not wrap your SQL in a bare
    # try/except — let sqlite3.Error propagate to the caller.
