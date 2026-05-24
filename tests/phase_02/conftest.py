"""Phase 02 conftest — resolves AKANGA_SRC and provides shared fixtures."""
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from tests.conftest import MINIMAL_VAULT_CONFIG, _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(2)


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory with a minimal akanga.yaml config file."""
    config_path = tmp_path / "akanga.yaml"
    config_path.write_text(yaml.dump(MINIMAL_VAULT_CONFIG), encoding="utf-8")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture()
def tmp_db(tmp_path: Path):
    """Return a path for a real SQLite database in tmp_path (file not yet created)."""
    return str(tmp_path / "test.db")


@pytest.fixture()
def populated_db(tmp_path: Path, tmp_vault: Path):
    """
    A GraphDatabase pre-loaded with 3 sample nodes and 2 edges:
      - node_a (id: aaa...) title="Node Alpha"
      - node_b (id: bbb...) title="Node Beta"
      - node_c (id: ccc...) title="Node Gamma"
      - edge: node_a -> node_b  (relation="supports")
      - edge: node_b -> node_c  (relation="contradicts")
    """
    from db import GraphDatabase  # noqa: PLC0415
    from parser import Node  # noqa: PLC0415

    db_path = str(tmp_path / "populated.db")
    db = GraphDatabase(db_path)

    node_a = Node(
        id="aaaaaaaa-0000-0000-0000-000000000001",
        path=str(tmp_vault / "node-alpha.md"),
        title="Node Alpha",
        type="note",
        tags=[],
        content_hash="hash_a",
    )
    node_b = Node(
        id="bbbbbbbb-0000-0000-0000-000000000002",
        path=str(tmp_vault / "node-beta.md"),
        title="Node Beta",
        type="note",
        tags=[],
        content_hash="hash_b",
    )
    node_c = Node(
        id="cccccccc-0000-0000-0000-000000000003",
        path=str(tmp_vault / "node-gamma.md"),
        title="Node Gamma",
        type="note",
        tags=[],
        content_hash="hash_c",
    )

    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_node(node_c)

    db.upsert_edge({
        "source_id": node_a.id,
        "target_id": node_b.id,
        "target_title": node_b.title,
        "relation": "supports",
        "relation_id": "EP-001",
    })
    db.upsert_edge({
        "source_id": node_b.id,
        "target_id": node_c.id,
        "target_title": node_c.title,
        "relation": "contradicts",
        "relation_id": "EP-002",
    })

    return db
