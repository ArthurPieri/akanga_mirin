"""Phase 04 conftest — resolves AKANGA_SRC and provides concurrency fixtures."""
from pathlib import Path

import pytest

from tests.conftest import MINIMAL_VAULT_CONFIG, _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(4)


@pytest.fixture()
def event_bus():
    """A fresh EventBus instance for each test."""
    from eventbus import EventBus

    return EventBus()


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory (no config file required for watcher tests)."""
    return tmp_path
