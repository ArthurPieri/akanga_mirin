"""Phase 04 conftest — resolves AKANGA_SRC and provides concurrency fixtures."""
import time
from pathlib import Path

import pytest
from tests._helpers import load_attr



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
    return load_attr(("eventbus", "EventBus"), ("akanga_core.eventbus", "EventBus"))


def _load_watcher():
    """Import VaultWatcher from 'watcher' or 'akanga_core.watcher'."""
    return load_attr(("watcher", "VaultWatcher"), ("akanga_core.watcher", "VaultWatcher"))


def _load_sync_worker():
    """Import SyncWorker from 'sync_worker' or 'akanga_core.sync_worker'."""
    return load_attr(("sync_worker", "SyncWorker"), ("akanga_core.sync_worker", "SyncWorker"))


def _load_db():
    """Import GraphDatabase from 'db' or 'akanga_core.db' (built in Phase 02)."""
    return load_attr(("db", "GraphDatabase"), ("akanga_core.db", "GraphDatabase"))


def _load_sync_queue():
    """Import the sync_queue module from 'sync_queue' or 'akanga_core.sync_queue'."""
    return load_attr(("sync_queue", None), ("akanga_core.sync_queue", None), hint="the sync_queue module")


@pytest.fixture()
def event_bus():
    """A fresh EventBus instance for each test."""
    EventBus = _load_eventbus()
    return EventBus()


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory (no config file required for watcher tests)."""
    return tmp_path
