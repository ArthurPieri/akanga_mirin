"""Phase 02 tests — indexer: index_file, full_scan_and_index, edge cases."""
import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest

from tests.phase_02.conftest import _load_db, _load_indexer

GraphDatabase = _load_db()
_indexer_mod = _load_indexer()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_md(directory: Path, filename: str, node_id: str, title: str, body: str = "") -> Path:
    """Write a minimal .md file with YAML frontmatter to *directory*."""
    content = dedent(f"""\
        ---
        id: {node_id}
        title: {title}
        type: note
        tags: []
        edges: []
        ---

        {body}
        """)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. index_file
# ---------------------------------------------------------------------------

def test_index_single_file(tmp_db: str, tmp_vault: Path):
    """index_file() parses a .md file and upserts the node into the DB."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    path = _write_md(tmp_vault, "single.md", "aaaa0001-0000-0000-0000-000000000001", "Single Node")

    index_file(str(path), db, str(tmp_vault))

    node = db.get_node("aaaa0001-0000-0000-0000-000000000001")
    assert node is not None
    assert node.title == "Single Node"


# ---------------------------------------------------------------------------
# 2. full_scan_and_index
# ---------------------------------------------------------------------------

def test_full_scan_indexes_all_files(tmp_db: str, tmp_vault: Path):
    """full_scan_and_index() indexes every .md file in the vault."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    _write_md(tmp_vault, "node1.md", "bbbb0001-0000-0000-0000-000000000001", "Alpha")
    _write_md(tmp_vault, "node2.md", "bbbb0002-0000-0000-0000-000000000002", "Beta")
    _write_md(tmp_vault, "node3.md", "bbbb0003-0000-0000-0000-000000000003", "Gamma")

    full_scan_and_index(str(tmp_vault), db)

    ids = {"bbbb0001-0000-0000-0000-000000000001",
           "bbbb0002-0000-0000-0000-000000000002",
           "bbbb0003-0000-0000-0000-000000000003"}
    for node_id in ids:
        assert db.get_node(node_id) is not None


def test_full_scan_skips_hidden_dirs(tmp_db: str, tmp_vault: Path):
    """Files inside hidden directories (e.g. .git/) are not indexed."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    hidden_dir = tmp_vault / ".git"
    hidden_dir.mkdir()
    _write_md(hidden_dir, "secret.md", "cccc0001-0000-0000-0000-000000000001", "Hidden Node")

    full_scan_and_index(str(tmp_vault), db)

    assert db.get_node("cccc0001-0000-0000-0000-000000000001") is None


def test_full_scan_skips_non_md_files(tmp_db: str, tmp_vault: Path):
    """Non-.md files in the vault directory are silently skipped."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    txt_file = tmp_vault / "notes.txt"
    txt_file.write_text("this is plain text\n", encoding="utf-8")
    # Also add one valid node so the scan has something to process
    _write_md(tmp_vault, "valid.md", "dddd0001-0000-0000-0000-000000000001", "Valid Node")

    # Must not raise even though notes.txt is not a markdown file.
    full_scan_and_index(str(tmp_vault), db)

    assert db.get_node("dddd0001-0000-0000-0000-000000000001") is not None


def test_full_scan_returns_count(tmp_db: str, tmp_vault: Path):
    """full_scan_and_index() returns the number of nodes successfully indexed."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    for i in range(3):
        _write_md(tmp_vault, f"count_{i}.md", f"eeee000{i}-0000-0000-0000-00000000000{i}", f"Count Node {i}")

    count = full_scan_and_index(str(tmp_vault), db)
    assert count == 3


def test_reindex_updates_node(tmp_db: str, tmp_vault: Path):
    """Re-indexing a file whose title changed updates the DB record."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    path = _write_md(tmp_vault, "reindex.md", "ffff0001-0000-0000-0000-000000000001", "Old Title")
    index_file(str(path), db, str(tmp_vault))

    # Overwrite with a new title
    _write_md(tmp_vault, "reindex.md", "ffff0001-0000-0000-0000-000000000001", "New Title")
    index_file(str(path), db, str(tmp_vault))

    node = db.get_node("ffff0001-0000-0000-0000-000000000001")
    assert node.title == "New Title"


# ---------------------------------------------------------------------------
# 3. Two-pass edge resolution + DB expendability (the phase's core promises)
# ---------------------------------------------------------------------------

def test_two_pass_edge_resolution(tmp_db: str, tmp_vault: Path):
    """A wikilink [[Beta]] in alpha.md must become a resolved edge A→B in the DB.

    alpha.md sorts before beta.md, so a single-pass indexer would try to
    resolve the link before Beta exists. The two-pass design (index all nodes
    first, then extract edges) is what makes this resolve.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    id_alpha = "abab0001-0000-0000-0000-000000000001"
    id_beta  = "abab0002-0000-0000-0000-000000000002"
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="This links to [[Beta]].")
    _write_md(tmp_vault, "b-beta.md",  id_beta,  "Beta")

    full_scan_and_index(str(tmp_vault), db)

    neighbors = db.get_neighbors(id_alpha)
    assert any(n.id == id_beta for n in neighbors), (
        "After full_scan_and_index, the wikilink [[Beta]] in alpha.md must "
        "exist as an edge Alpha→Beta in the edges table.\n"
        f"get_neighbors(Alpha) returned: {[getattr(n, 'title', n) for n in neighbors]!r}\n"
        "Pass 2 must re-read each node's body from disk (parse_node_file), call "
        "extract_wikilinks, resolve_wikilink, then db.upsert_edge. An indexer "
        "that extracts zero edges silently breaks Phases 3, 5, and 8."
    )


def test_db_is_expendable(tmp_db: str, tmp_vault: Path):
    """Delete the DB file, re-index, and get back the identical graph (doc Deliverable).

    This is the core architectural promise of the phase: the DB is a derived
    index, the .md files are the source of truth.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    id_alpha = "cdcd0001-0000-0000-0000-000000000001"
    id_beta  = "cdcd0002-0000-0000-0000-000000000002"
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="This links to [[Beta]].")
    _write_md(tmp_vault, "b-beta.md",  id_beta,  "Beta")

    def _snapshot(db) -> tuple[set, set]:
        node_ids = {n.id for n in db.list_nodes(limit=10_000)}
        conn = sqlite3.connect(tmp_db)
        edges = set(
            conn.execute("SELECT source_id, target_id FROM edges").fetchall()
        )
        conn.close()
        return node_ids, edges

    db = GraphDatabase(tmp_db)
    full_scan_and_index(str(tmp_vault), db)
    nodes_before, edges_before = _snapshot(db)
    assert len(nodes_before) == 2, "Precondition: both nodes must be indexed."
    db.close()

    # Destroy the derived index (including WAL sidecar files).
    for suffix in ("", "-wal", "-shm"):
        sidecar = Path(tmp_db + suffix)
        if sidecar.exists():
            sidecar.unlink()
    assert not Path(tmp_db).exists(), "Precondition: DB file must be gone."

    db2 = GraphDatabase(tmp_db)
    full_scan_and_index(str(tmp_vault), db2)
    nodes_after, edges_after = _snapshot(db2)
    db2.close()

    assert nodes_after == nodes_before, (
        "After deleting the DB and re-indexing, the node set must be identical.\n"
        f"Before: {sorted(nodes_before)!r}\nAfter:  {sorted(nodes_after)!r}\n"
        "If this fails, some node state lives only in the DB — the DB must be "
        "fully derivable from the .md files."
    )
    assert edges_after == edges_before, (
        "After deleting the DB and re-indexing, the edge set must be identical.\n"
        f"Before: {sorted(edges_before)!r}\nAfter:  {sorted(edges_after)!r}\n"
        "Edges must be re-derived from wikilinks on every full scan — never "
        "stored only in the DB."
    )


# ---------------------------------------------------------------------------
# 4. Error path
# ---------------------------------------------------------------------------

def test_index_missing_file_raises(tmp_db: str, tmp_vault: Path):
    """index_file() on a non-existent path raises an exception (FileNotFoundError or similar)."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    missing = str(tmp_vault / "does-not-exist.md")

    with pytest.raises(Exception):
        index_file(missing, db, str(tmp_vault))
