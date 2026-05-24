"""Phase 03 conftest — resolves AKANGA_SRC and provides graph fixtures."""
import tempfile
import uuid
from pathlib import Path

import pytest

from tests.conftest import _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(3)


# ---------------------------------------------------------------------------
# Dual-try import helper for graph module
# ---------------------------------------------------------------------------

def _load_graph():
    """Import the graph module from 'graph' or 'akanga_core.graph'."""
    try:
        import graph as m  # noqa: PLC0415
        return m
    except ModuleNotFoundError:
        try:
            from akanga_core import graph as m  # noqa: PLC0415
            return m
        except ModuleNotFoundError:
            pytest.fail("Cannot import 'graph' or 'akanga_core.graph'")


def _make_node_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def populated_graph_db(tmp_path: Path):
    """
    A GraphDatabase pre-loaded with a chain A → B → C → D plus a cycle B → A.

    Node UUIDs are stable strings exposed on the returned object as attributes:
        db.id_a, db.id_b, db.id_c, db.id_d
    """
    from akanga_core.db import GraphDatabase

    db_path = tmp_path / "graph_test.db"
    db = GraphDatabase(str(db_path))

    id_a = str(uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"))
    id_b = str(uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"))
    id_c = str(uuid.UUID("cccccccc-0000-0000-0000-000000000003"))
    id_d = str(uuid.UUID("dddddddd-0000-0000-0000-000000000004"))

    nodes = [
        {
            "id": id_a,
            "title": "Node A",
            "type": "note",
            "tags": [],
            "path": str(tmp_path / "a.md"),
            "content": "",
            "content_hash": "hash_a",
        },
        {
            "id": id_b,
            "title": "Node B",
            "type": "note",
            "tags": [],
            "path": str(tmp_path / "b.md"),
            "content": "",
            "content_hash": "hash_b",
        },
        {
            "id": id_c,
            "title": "Node C",
            "type": "note",
            "tags": [],
            "path": str(tmp_path / "c.md"),
            "content": "",
            "content_hash": "hash_c",
        },
        {
            "id": id_d,
            "title": "Node D",
            "type": "note",
            "tags": [],
            "path": str(tmp_path / "d.md"),
            "content": "",
            "content_hash": "hash_d",
        },
    ]

    for node in nodes:
        db.upsert_node(node)

    # Chain: A → B → C → D
    db.upsert_edge(id_a, id_b, relation="links_to")
    db.upsert_edge(id_b, id_c, relation="links_to")
    db.upsert_edge(id_c, id_d, relation="links_to")
    # Cycle: B → A
    db.upsert_edge(id_b, id_a, relation="links_back")

    # Attach stable IDs as attributes for test convenience
    db.id_a = id_a
    db.id_b = id_b
    db.id_c = id_c
    db.id_d = id_d

    yield db
    db.close()
