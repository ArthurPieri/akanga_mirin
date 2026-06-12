"""Phase 05 conftest — resolves AKANGA_SRC and provides TUI fixtures."""
from __future__ import annotations

import uuid
from pathlib import Path
from textwrap import dedent

import pytest
from tests._helpers import load_attr



# ---------------------------------------------------------------------------
# Dual-try import helpers
# ---------------------------------------------------------------------------

def _load_db():
    """Import GraphDatabase from 'db' or 'akanga_core.db'."""
    return load_attr(("db", "GraphDatabase"), ("akanga_core.db", "GraphDatabase"))


def _load_indexer():
    """Import full_scan_and_index from 'indexer' or 'akanga_core.indexer'.

    NOTE: unlike phase_02's _load_indexer (which returns the MODULE), this
    returns the FUNCTION — phase-5 call sites take the callable directly.
    """
    return load_attr(
        ("indexer", "full_scan_and_index"),
        ("akanga_core.indexer", "full_scan_and_index"),
    )


# ---------------------------------------------------------------------------
# Vault + DB helpers
# ---------------------------------------------------------------------------

def _write_node(vault: Path, filename: str, *, title: str, node_type: str = "note") -> Path:
    """Write a minimal well-formed .md node file into *vault*."""
    node_id = str(uuid.uuid4())
    content = dedent(f"""\
        ---
        id: {node_id}
        title: {title}
        type: {node_type}
        tags: []
        ---

        Content of {title}.
        """)
    path = vault / filename
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """
    A temporary vault directory pre-populated with three sample nodes:
        - alpha.md  ("Alpha Node")
        - beta.md   ("Beta Node")
        - gamma.md  ("Gamma Node")
    """
    _write_node(tmp_path, "alpha.md", title="Alpha Node")
    _write_node(tmp_path, "beta.md", title="Beta Node")
    _write_node(tmp_path, "gamma.md", title="Gamma Node")
    return tmp_path


@pytest.fixture()
def empty_vault(tmp_path: Path) -> Path:
    """A temporary vault directory with no node files."""
    return tmp_path


@pytest.fixture()
def tmp_db(tmp_vault: Path, tmp_path: Path):
    """
    A GraphDatabase with the three nodes from *tmp_vault* already indexed.

    Yields the open database; closes it after the test.
    """
    GraphDatabase = _load_db()
    full_scan_and_index = _load_indexer()

    db_path = tmp_path / "test.db"
    db = GraphDatabase(str(db_path))
    full_scan_and_index(str(tmp_vault), db)
    yield db
    db.close()


@pytest.fixture()
def empty_db(empty_vault: Path, tmp_path: Path):
    """A GraphDatabase backed by an empty vault (zero nodes)."""
    GraphDatabase = _load_db()

    db_path = tmp_path / "empty.db"
    db = GraphDatabase(str(db_path))
    yield db
    db.close()
