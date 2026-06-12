"""Phase 04 conftest — resolves AKANGA_SRC and provides concurrency fixtures."""
import time
from pathlib import Path

import pytest



def _wait_until(predicate, timeout: float = 2.0) -> bool:
    """Poll *predicate* until it is truthy or *timeout* seconds elapse.

    The canonical replacement for flat `time.sleep(X); assert ...` in async
    tests: it returns as soon as the condition holds (fast on healthy runs)
    and only burns the full timeout when the assertion is about to fail.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


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


def _load_sync_worker():
    """Import SyncWorker from 'sync_worker' or 'akanga_core.sync_worker'."""
    try:
        from sync_worker import SyncWorker  # noqa: PLC0415
        return SyncWorker
    except ModuleNotFoundError:
        try:
            from akanga_core.sync_worker import SyncWorker  # noqa: PLC0415
            return SyncWorker
        except ModuleNotFoundError:
            pytest.fail("Cannot import SyncWorker from 'sync_worker' or 'akanga_core.sync_worker'")


def _load_db():
    """Import GraphDatabase from 'db' or 'akanga_core.db' (built in Phase 02)."""
    try:
        from db import GraphDatabase  # noqa: PLC0415
        return GraphDatabase
    except ModuleNotFoundError:
        try:
            from akanga_core.db import GraphDatabase  # noqa: PLC0415
            return GraphDatabase
        except ModuleNotFoundError:
            pytest.fail("Cannot import GraphDatabase from 'db' or 'akanga_core.db'")


def _load_sync_queue():
    """Import the sync_queue module from 'sync_queue' or 'akanga_core.sync_queue'."""
    try:
        import sync_queue as m  # noqa: PLC0415
        return m
    except ModuleNotFoundError:
        try:
            from akanga_core import sync_queue as m  # noqa: PLC0415
            return m
        except ModuleNotFoundError:
            pytest.fail("Cannot import 'sync_queue' or 'akanga_core.sync_queue'")


@pytest.fixture()
def event_bus():
    """A fresh EventBus instance for each test."""
    EventBus = _load_eventbus()
    return EventBus()


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory (no config file required for watcher tests)."""
    return tmp_path
