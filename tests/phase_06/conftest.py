"""Phase 06 conftest — resolves AKANGA_SRC and provides FastAPI server fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest
from tests._helpers import load_attr

# Re-exported: tests/phase_06/test_server.py imports _write_node from this
# conftest; the single definition lives in tests/_helpers.py.
from tests._helpers import _write_node  # noqa: F401


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary, empty vault directory (tests create nodes via the API)."""
    return tmp_path


@pytest.fixture()
def test_client(tmp_vault: Path, tmp_path: Path):
    """
    A synchronous ``TestClient`` wrapping the learner's FastAPI app.

    Resolution order for the app factory:
      1. ``server.create_app``   (flat layout)
      2. ``akanga_core.server.create_app``  (package layout)

    The client is configured to point at *tmp_vault* and a fresh SQLite db
    in *tmp_path*.  The Starlette ``TestClient`` manages the ASGI lifespan
    (startup / shutdown) within the ``with`` block.

    Yields the open client.
    """
    pytest.importorskip("fastapi", reason="fastapi not installed — skipping server tests")
    pytest.importorskip("httpx", reason="httpx not installed — skipping server tests")

    from starlette.testclient import TestClient

    create_app = _load_create_app()
    db_path = str(tmp_path / "server_test.db")

    app = create_app(vault=str(tmp_vault), db_path=db_path)

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def _load_create_app():
    """Import the learner's ``create_app`` factory from server module."""
    return load_attr(
        ("server", "create_app"),
        ("akanga_core.server", "create_app"),
        hint="a 'create_app' FastAPI factory (server.py or akanga_core/server.py)",
    )
