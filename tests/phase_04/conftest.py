"""Phase 04 conftest — resolves AKANGA_SRC and provides concurrency fixtures."""
from pathlib import Path

import pytest

from tests.conftest import MINIMAL_VAULT_CONFIG, _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(4)


# ---------------------------------------------------------------------------
# Dual-try import helpers (flat layout first, then akanga_core.* package)
# ---------------------------------------------------------------------------

def _load_eventbus():
    """Import EventBus from 'eventbus' or 'akanga_core.eventbus'."""
    try:
        from eventbus import EventBus  # noqa: PLC0415
        return EventBus
    except ModuleNotFoundError:
        try:
            from akanga_core.eventbus import EventBus  # noqa: PLC0415
            return EventBus
        except ModuleNotFoundError:
            pytest.fail("Cannot import EventBus from 'eventbus' or 'akanga_core.eventbus'")


def _load_watcher():
    """Import VaultWatcher from 'watcher' or 'akanga_core.watcher'."""
    try:
        from watcher import VaultWatcher  # noqa: PLC0415
        return VaultWatcher
    except ModuleNotFoundError:
        try:
            from akanga_core.watcher import VaultWatcher  # noqa: PLC0415
            return VaultWatcher
        except ModuleNotFoundError:
            pytest.fail("Cannot import VaultWatcher from 'watcher' or 'akanga_core.watcher'")


@pytest.fixture()
def event_bus():
    """A fresh EventBus instance for each test."""
    EventBus = _load_eventbus()
    return EventBus()


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory (no config file required for watcher tests)."""
    return tmp_path
