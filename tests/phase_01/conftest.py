"""Phase 01 conftest — resolves AKANGA_SRC and provides shared fixtures."""
import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from tests.conftest import MINIMAL_VAULT_CONFIG
from tests._helpers import load_attr


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory with a minimal akanga.yaml config file."""
    config_path = tmp_path / "akanga.yaml"
    config_path.write_text(yaml.dump(MINIMAL_VAULT_CONFIG), encoding="utf-8")
    return tmp_path


def _load_sync_queue():
    """Import the learner's sync_queue module (flat, then package layout)."""
    return load_attr(("sync_queue", None), ("akanga_core.sync_queue", None), hint="the sync_queue module")


@pytest.fixture()
def tmp_db(tmp_path: Path):
    """A bare SQLite connection with the sync_queue table already created."""
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            new_name TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def sample_node(tmp_vault: Path) -> Path:
    """A well-formed .md file with empty edges block in tmp_vault."""
    content = dedent("""\
        ---
        id: a3f7c2be-1234-5678-abcd-ef0123456789
        title: Test Node
        type: note
        tags:
          - test
        edges: []
        ---

        Body content here.
        """)
    node_file = tmp_vault / "test-node.md"
    node_file.write_text(content, encoding="utf-8")
    return node_file
