"""
Phase 04 — VaultWatcher Tests

Tests for watcher.py:
    VaultWatcher(vault, eventbus, debounce_ms)
    VaultWatcher.start()
    VaultWatcher.stop()

NOTE: These tests use real filesystem operations and time.sleep() — this is
unavoidable for debounce/event integration testing. A short debounce_ms is
used (DEBOUNCE_MS = 80) and sleeps are proportional.
"""
import time
import threading
from pathlib import Path

import pytest

# Short debounce to keep tests fast; sleep = debounce + generous buffer
DEBOUNCE_MS = 80
SETTLE_S = (DEBOUNCE_MS / 1000) + 0.35  # seconds to wait for event to settle


def _make_watcher_and_bus(vault: Path, debounce_ms: int = DEBOUNCE_MS):
    """Return (watcher, bus, events_list) where events_list collects published events."""
    from eventbus import EventBus
    from watcher import VaultWatcher

    bus = EventBus()
    events = []

    def capture(**kwargs):
        events.append(kwargs)

    bus.subscribe("file_changed", capture)
    bus.subscribe("file_deleted", capture)

    watcher = VaultWatcher(vault, bus, debounce_ms=debounce_ms)
    return watcher, bus, events


class TestWatcherBasicEvents:
    def test_watcher_fires_on_file_creation(self, tmp_vault: Path) -> None:
        """Creating a .md file inside the vault triggers a file_changed event."""
        watcher, bus, events = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            (tmp_vault / "new_node.md").write_text("# hello", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(events) >= 1, "Expected at least one file_changed event on file creation"
        finally:
            watcher.stop()

    def test_watcher_fires_on_file_modification(self, tmp_vault: Path) -> None:
        """Modifying an existing file triggers a file_changed event."""
        target = tmp_vault / "existing.md"
        target.write_text("initial", encoding="utf-8")

        watcher, bus, events = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            time.sleep(0.05)  # let watcher settle after start
            target.write_text("modified content", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(events) >= 1, "Expected file_changed event on file modification"
        finally:
            watcher.stop()

    def test_watcher_fires_on_file_deletion(self, tmp_vault: Path) -> None:
        """Deleting a file triggers a file_deleted event."""
        target = tmp_vault / "to_delete.md"
        target.write_text("bye", encoding="utf-8")

        from eventbus import EventBus
        from watcher import VaultWatcher

        bus = EventBus()
        deleted_events = []
        bus.subscribe("file_deleted", lambda **kw: deleted_events.append(kw))

        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        try:
            time.sleep(0.05)
            target.unlink()
            time.sleep(SETTLE_S)
            assert len(deleted_events) >= 1, "Expected file_deleted event after file removal"
        finally:
            watcher.stop()

    def test_watcher_event_contains_path(self, tmp_vault: Path) -> None:
        """The file_changed event payload must include the path of the changed file."""
        from eventbus import EventBus
        from watcher import VaultWatcher

        bus = EventBus()
        received = []
        bus.subscribe("file_changed", lambda **kw: received.append(kw))

        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        try:
            target = tmp_vault / "tracked.md"
            target.write_text("content", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(received) >= 1
            payload = received[0]
            assert "path" in payload, "Event payload must include a 'path' key"
            # path value should reference the file that changed
            assert str(target) in str(payload["path"]) or Path(payload["path"]) == target
        finally:
            watcher.stop()


class TestWatcherDebounce:
    def test_watcher_debounces_rapid_saves(self, tmp_vault: Path) -> None:
        """10 rapid writes to the same file coalesce into a single event."""
        target = tmp_vault / "rapid.md"
        target.write_text("v0", encoding="utf-8")

        watcher, bus, events = _make_watcher_and_bus(tmp_vault, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        try:
            time.sleep(0.05)  # let observer settle
            for i in range(10):
                target.write_text(f"v{i + 1}", encoding="utf-8")
                time.sleep(0.005)  # 5ms between writes — within debounce window

            time.sleep(SETTLE_S)
            assert len(events) <= 3, (
                f"Expected debounce to coalesce 10 rapid saves; got {len(events)} events"
            )
            assert len(events) >= 1, "At least one event must be emitted after rapid saves"
        finally:
            watcher.stop()


class TestWatcherFilters:
    def test_watcher_ignores_swp_files(self, tmp_vault: Path) -> None:
        """Writing a .swp file must not emit any event."""
        watcher, bus, events = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            time.sleep(0.05)
            (tmp_vault / ".test.swp").write_text("swap", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(events) == 0, "Swap files must be ignored by the watcher"
        finally:
            watcher.stop()

    def test_watcher_ignores_tilde_files(self, tmp_vault: Path) -> None:
        """Writing a tilde-suffixed backup file must not emit any event."""
        watcher, bus, events = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            time.sleep(0.05)
            (tmp_vault / "file.md~").write_text("backup", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(events) == 0, "Tilde backup files must be ignored by the watcher"
        finally:
            watcher.stop()

    def test_watcher_ignores_hidden_dirs(self, tmp_vault: Path) -> None:
        """Writing a file inside a hidden directory must not emit any event."""
        hidden = tmp_vault / ".hidden"
        hidden.mkdir()

        watcher, bus, events = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            time.sleep(0.05)
            (hidden / "secret.md").write_text("hidden", encoding="utf-8")
            time.sleep(SETTLE_S)
            assert len(events) == 0, "Files in hidden directories must be ignored"
        finally:
            watcher.stop()


class TestWatcherLifecycle:
    def test_watcher_stop_and_start(self, tmp_vault: Path) -> None:
        """start() then stop() must complete without raising an exception."""
        from eventbus import EventBus
        from watcher import VaultWatcher

        bus = EventBus()
        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        watcher.stop()  # must not raise

    def test_watcher_nonexistent_vault_raises(self, tmp_path: Path) -> None:
        """VaultWatcher with a nonexistent vault path raises on start() or __init__."""
        from eventbus import EventBus
        from watcher import VaultWatcher

        bad_path = tmp_path / "does_not_exist"
        bus = EventBus()

        with pytest.raises(Exception):
            # Spec allows raising in __init__ or in start() — test both possibilities
            watcher = VaultWatcher(bad_path, bus, debounce_ms=DEBOUNCE_MS)
            watcher.start()
            watcher.stop()
