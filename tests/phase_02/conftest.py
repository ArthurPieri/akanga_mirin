"""Phase 02 conftest — resolves AKANGA_SRC and provides shared fixtures."""
from pathlib import Path

import pytest
import yaml

from tests.conftest import MINIMAL_VAULT_CONFIG
from tests._helpers import load_attr


# ---------------------------------------------------------------------------
# Dual-try import helpers (flat layout first, then akanga_core.* package)
# ---------------------------------------------------------------------------

def _load_db():
    """Import GraphDatabase from 'db' or 'akanga_core.db'."""
    return load_attr(("db", "GraphDatabase"), ("akanga_core.db", "GraphDatabase"))


def _load_indexer():
    """Import the indexer module from 'indexer' or 'akanga_core.indexer'."""
    return load_attr(("indexer", None), ("akanga_core.indexer", None), hint="the indexer module")


def _load_links():
    """Import the links module from 'links' or 'akanga_core.links'."""
    return load_attr(("links", None), ("akanga_core.links", None), hint="the links module")


def _load_parser():
    """Import the parser module from 'parser' or 'akanga_core.parser'."""
    return load_attr(
        ("parser", None),
        ("akanga_core.parser", None),
        guard=lambda m: hasattr(m, "Node"),
        guard_desc="no Node class — not the learner's parser",
        hint="the parser module",
    )


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """An empty vault subdirectory, with a minimal akanga.yaml next to it.

    NOTE: the config file lives in the RETURNED DIRECTORY'S PARENT
    (``tmp_path/akanga.yaml``), NOT inside the returned vault dir — config
    discovery is expected to look upward from the vault.
    """
    config_path = tmp_path / "akanga.yaml"
    config_path.write_text(yaml.dump(MINIMAL_VAULT_CONFIG), encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


@pytest.fixture()
def db_path(tmp_path: Path):
    """A string path for a SQLite database in tmp_path — the file does NOT exist yet."""
    return str(tmp_path / "test.db")


@pytest.fixture()
def populated_db(tmp_path: Path, vault_dir: Path):
    """
    A GraphDatabase pre-loaded with 3 sample nodes and 2 edges:
      - node_a (id: aaa...) title="Node Alpha"
      - node_b (id: bbb...) title="Node Beta"
      - node_c (id: ccc...) title="Node Gamma"
      - edge: node_a -> node_b  (relation="supports")
      - edge: node_b -> node_c  (relation="contradicts")

    Contract note: upsert_node accepts a Node object or a plain dict — phase
    3's fixtures exercise the dict form, so don't make your implementation
    Node-only.
    """
    GraphDatabase = _load_db()
    Node = _load_parser().Node

    db = GraphDatabase(str(tmp_path / "populated.db"))

    node_a = Node(
        id="aaaaaaaa-0000-0000-0000-000000000001",
        path=str(vault_dir / "node-alpha.md"),
        title="Node Alpha",
        type="note",
        tags=[],
        content_hash="hash_a",
    )
    node_b = Node(
        id="bbbbbbbb-0000-0000-0000-000000000002",
        path=str(vault_dir / "node-beta.md"),
        title="Node Beta",
        type="note",
        tags=[],
        content_hash="hash_b",
    )
    node_c = Node(
        id="cccccccc-0000-0000-0000-000000000003",
        path=str(vault_dir / "node-gamma.md"),
        title="Node Gamma",
        type="note",
        tags=[],
        content_hash="hash_c",
    )

    db.upsert_node(node_a)
    db.upsert_node(node_b)
    db.upsert_node(node_c)

    # upsert_edge signature: upsert_edge(source_id, target_id=None,
    # relation=None, relation_id=None) — keyword calls are equally fine
    # (phase 3's fixture uses keywords); positional is used here for brevity.
    db.upsert_edge(node_a.id, node_b.id, "supports", "EP-001")
    db.upsert_edge(node_b.id, node_c.id, "contradicts", "EP-002")

    yield db
    db.close()
