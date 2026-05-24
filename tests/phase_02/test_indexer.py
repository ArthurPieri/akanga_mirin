"""Phase 02 tests — indexer: index_file, full_scan_and_index, edge cases."""
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
# 3. Error path
# ---------------------------------------------------------------------------

def test_index_missing_file_raises(tmp_db: str, tmp_vault: Path):
    """index_file() on a non-existent path raises an exception (FileNotFoundError or similar)."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    missing = str(tmp_vault / "does-not-exist.md")

    with pytest.raises(Exception):
        index_file(missing, db, str(tmp_vault))
