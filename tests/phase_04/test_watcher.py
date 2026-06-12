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
import asyncio
import time
import threading
import os
from pathlib import Path

import pytest

from tests.phase_04.conftest import _load_eventbus, _load_watcher, _wait_until

EventBus = _load_eventbus()
VaultWatcher = _load_watcher()

# Short debounce to keep tests fast
DEBOUNCE_MS = 80
TIMEOUT_S = 2.0  # Max time to wait for events


def _atomic_write(path: Path, content: str):
    """Write content to path using atomic os.replace to ensure watcher sees one event."""
    tmp = path.with_suffix(path.suffix + f".{uuid_str()[:8]}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def uuid_str():
    import uuid
    return str(uuid.uuid4())


def _make_watcher_and_bus(vault: Path, debounce_ms: int = DEBOUNCE_MS):
    """Return (watcher, bus, events_list, event_ready)."""

    bus = EventBus()
    events = []
    event_ready = threading.Event()

    def capture(**kwargs):
        events.append(kwargs)
        event_ready.set()

    bus.subscribe("file_changed", capture)
    bus.subscribe("file_deleted", capture)

    watcher = VaultWatcher(vault, bus, debounce_ms=debounce_ms)
    return watcher, bus, events, event_ready


class TestWatcherBasicEvents:
    def test_watcher_fires_on_file_creation(self, tmp_vault: Path) -> None:
        """Creating a .md file inside the vault triggers a file_changed event."""
        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            _atomic_write(tmp_vault / "new_node.md", "# hello")
            assert ready.wait(timeout=TIMEOUT_S), "Timeout waiting for file_changed event"
            assert len(events) >= 1, "Expected at least one file_changed event on file creation"
        finally:
            watcher.stop()

    def test_watcher_fires_on_file_modification(self, tmp_vault: Path) -> None:
        """Modifying an existing file triggers a file_changed event."""
        target = tmp_vault / "existing.md"
        _atomic_write(target, "initial")

        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            # Clear any creation events
            ready.clear()
            events.clear()
            
            _atomic_write(target, "modified content")
            assert ready.wait(timeout=TIMEOUT_S), "Timeout waiting for file_changed event"
            assert len(events) >= 1, "Expected file_changed event on file modification"
        finally:
            watcher.stop()

    def test_watcher_fires_on_file_deletion(self, tmp_vault: Path) -> None:
        """Deleting a file triggers a file_deleted event."""
        target = tmp_vault / "to_delete.md"
        _atomic_write(target, "bye")

        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            ready.clear()
            events.clear()
            
            target.unlink()
            assert ready.wait(timeout=TIMEOUT_S), "Timeout waiting for file_deleted event"
            assert any(e.get("path") == target or str(e.get("path")) == str(target) for e in events)
        finally:
            watcher.stop()

    def test_watcher_event_contains_path(self, tmp_vault: Path) -> None:
        """The file_changed event payload must include the path of the changed file."""
        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            target = tmp_vault / "tracked.md"
            _atomic_write(target, "content")
            assert ready.wait(timeout=TIMEOUT_S)
            payload = events[0]
            assert "path" in payload, "Event payload must include a 'path' key"
            assert str(target) in str(payload["path"]) or Path(payload["path"]) == target
        finally:
            watcher.stop()


class TestWatcherDebounce:
    def test_watcher_debounces_rapid_saves(self, tmp_vault: Path) -> None:
        """10 rapid writes to the same file coalesce into a single event."""
        target = tmp_vault / "rapid.md"
        _atomic_write(target, "v0")

        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        try:
            # Clear initial creation event
            ready.clear()
            events.clear()

            for i in range(10):
                target.write_text(f"v{i + 1}", encoding="utf-8")
                # Rapid writes without atomic helper to trigger multiple raw events
                time.sleep(0.002)

            # Wait for debounce to settle
            assert ready.wait(timeout=TIMEOUT_S), "Debounce event never fired"
            # Debounce window is 80ms, 10 writes in ~20ms should coalesce
            # We allow up to 3 events due to OS-level event batching variations
            assert 1 <= len(events) <= 3, f"Expected 1-3 events after debounce, got {len(events)}"
        finally:
            watcher.stop()

    def test_watcher_parallel_saves_not_debounced(self, tmp_vault: Path) -> None:
        """Writes to DIFFERENT files must not be debounced into a single event."""
        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        try:
            target1 = tmp_vault / "file1.md"
            target2 = tmp_vault / "file2.md"

            _atomic_write(target1, "content1")
            _atomic_write(target2, "content2")

            # Wait for at least two events to arrive
            start_time = time.time()
            while len(events) < 2 and (time.time() - start_time) < TIMEOUT_S:
                ready.wait(0.1)
                ready.clear()

            assert len(events) >= 2, f"Expected at least 2 events for different files, got {len(events)}"
            paths = [str(e.get("path")) for e in events]
            assert any("file1.md" in p for p in paths)
            assert any("file2.md" in p for p in paths)
        finally:
            watcher.stop()


class TestWatcherFilters:
    def test_watcher_ignores_swp_files(self, tmp_vault: Path) -> None:
        """Writing a .swp file must not emit any event."""
        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            (tmp_vault / ".test.swp").write_text("swap", encoding="utf-8")
            assert not ready.wait(timeout=0.2), "Swap files must be ignored"
            assert len(events) == 0
        finally:
            watcher.stop()

    def test_watcher_ignores_tilde_files(self, tmp_vault: Path) -> None:
        """Writing a tilde-suffixed backup file must not emit any event."""
        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            (tmp_vault / "file.md~").write_text("backup", encoding="utf-8")
            assert not ready.wait(timeout=0.2), "Tilde files must be ignored"
            assert len(events) == 0
        finally:
            watcher.stop()

    def test_watcher_ignores_hidden_dirs(self, tmp_vault: Path) -> None:
        """Writing a file inside a hidden directory must not emit any event."""
        hidden = tmp_vault / ".hidden"
        hidden.mkdir()

        watcher, bus, events, ready = _make_watcher_and_bus(tmp_vault)
        watcher.start()
        try:
            (hidden / "secret.md").write_text("hidden", encoding="utf-8")
            assert not ready.wait(timeout=0.2), "Hidden directories must be ignored"
            assert len(events) == 0
        finally:
            watcher.stop()


class TestWatcherReschedule:
    """Deadline re-check on re-touch (adversarial-analysis-v3 finding #3).

    Round 3 graded the `_fire` copies: phase_04 re-checks the deadline,
    phase_07 fires EARLY on re-schedule, phase_05/06 resurrect cancelled
    events. This test pins the canonical contract: a re-touch inside the
    debounce window pushes the deadline back — one event, after the LAST
    deadline, never before.
    """

    def test_retouch_inside_window_postpones_fire(self, tmp_vault: Path) -> None:
        """Touch, re-touch inside the window → exactly ONE event after the LAST deadline.

        Timeline (debounce = 500ms):
          t=0      first write  → deadline ≈ t=500ms
          t≈150ms  re-touch     → deadline pushed to ≈ t=650ms
        The re-touch lands 350ms before the FIRST deadline, so even a badly
        starved CI runner delivers it inside the window. The single event must
        fire no earlier than ~debounce after the RE-TOUCH (measured with
        monotonic timestamps, so raw-event delivery latency cannot skew it).

        The two assertions are deliberately split: the early-fire bug produces
        TWO events (original deadline + rescheduled deadline) and trips the
        count assertion; a lone early event is far more likely to be the test
        thread getting starved than a watcher bug — its message says so.
        """
        debounce_ms = 500
        bus = EventBus()
        events: list[tuple[float, dict]] = []
        ready = threading.Event()

        def capture(**kwargs):
            events.append((time.monotonic(), kwargs))
            ready.set()

        bus.subscribe("file_changed", capture)
        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=debounce_ms)
        target = tmp_vault / "reschedule.md"
        watcher.start()
        try:
            time.sleep(0.2)  # let the observer arm before timing starts

            _atomic_write(target, "v1")          # t = 0: schedules the first deadline
            time.sleep(0.15)
            t_retouch = time.monotonic()
            _atomic_write(target, "v2")          # t ≈ 150ms: re-touch INSIDE the window

            assert ready.wait(timeout=TIMEOUT_S + 1), (
                "No event arrived after the LAST deadline — re-scheduling must "
                "postpone the fire, never cancel it. The final state of the "
                "file must still be delivered exactly once."
            )
            time.sleep(0.5)  # settle: let any (incorrect) second fire surface

            assert len(events) == 1, (
                f"Expected exactly ONE coalesced event after the last deadline, "
                f"got {len(events)}.\n"
                "Both touches are saves of the same file inside one debounce "
                "window — they must coalesce into a single file_changed."
            )

            fire_delay = events[0][0] - t_retouch
            assert fire_delay >= (debounce_ms / 1000) - 0.05, (
                f"The single event fired {fire_delay * 1000:.0f}ms after the "
                f"re-touch — before the re-touched {debounce_ms}ms deadline.\n"
                "If this fired early AND exactly once, suspect scheduler "
                "starvation in CI before suspecting _fire — re-run; the "
                "early-fire bug also produces TWO events (the count assertion "
                "above catches that). A reproducible single early fire means "
                "_fire must RE-CHECK the current deadline for the path when "
                "the timer wakes and go back to sleep if a later touch moved "
                "it — and deadlines must be computed with time.monotonic(), "
                "never time.time(): an NTP step mid-window makes wall-clock "
                "deadlines fire early."
            )
        finally:
            watcher.stop()


class TestWatcherDeleteGrace:
    """Create-cancels-pending-delete (adversarial-analysis-v3 findings #3c/#5).

    Real editors delete-and-recreate on save (vim's rename-backup makes every
    save a delete for the real path; sync clients flap files the same way).
    The adopted contract: deletes get a debounce grace window, and a create/
    modify of the same path INSIDE that window cancels the pending delete —
    the world sees one file_changed, never a spurious file_deleted.

    PLATFORM NOTE (adversarial-analysis-v4 #10): the watcher's exists-check
    branch (path still on disk when the delete grace expires → phantom delete,
    suppress it) is the macOS FSEvents case; on Linux/inotify an atomic
    replace arrives as MOVED_TO — never a coalesced delete — so Linux CI
    exercises a different code path and local macOS runs are the validation
    for that branch.
    """

    def test_recreate_within_grace_window_cancels_pending_delete(
        self, tmp_vault: Path
    ) -> None:
        """delete → immediate recreate must publish file_changed and NO file_deleted."""
        debounce_ms = 300
        target = tmp_vault / "flapper.md"
        _atomic_write(target, "v1")  # exists BEFORE the watcher starts → no event

        bus = EventBus()
        changed: list[dict] = []
        deleted: list[dict] = []
        changed_ready = threading.Event()

        def on_changed(**kwargs):
            changed.append(kwargs)
            changed_ready.set()

        def on_deleted(**kwargs):
            deleted.append(kwargs)

        bus.subscribe("file_changed", on_changed)
        bus.subscribe("file_deleted", on_deleted)

        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=debounce_ms)
        watcher.start()
        try:
            time.sleep(0.2)  # let the observer arm

            target.unlink()                      # vim-style delete...
            _atomic_write(target, "v2")          # ...recreated within the grace window

            assert changed_ready.wait(timeout=TIMEOUT_S), (
                "The recreated file never surfaced as file_changed — "
                "cancelling the pending delete must not swallow the create. "
                "The net effect of delete+recreate is a CHANGE."
            )
            # Give any (incorrectly) un-cancelled pending delete time to fire.
            time.sleep(debounce_ms / 1000 + 0.4)

            assert deleted == [], (
                f"file_deleted was published for a file that exists: "
                f"{[str(e.get('path')) for e in deleted]!r}.\n"
                "Deletes must be debounced too ('deletions never arrive in "
                "bursts' is false — vim's rename-backup save is a delete), "
                "and a create of the same path inside the grace window must "
                "CANCEL the pending delete. A spurious file_deleted tombstones "
                "a live note out of the index."
            )
        finally:
            watcher.stop()


class TestWatcherLifecycle:
    def test_watcher_stop_and_start(self, tmp_vault: Path) -> None:
        """start() then stop() must complete without raising an exception."""
        bus = EventBus()
        watcher = VaultWatcher(tmp_vault, bus, debounce_ms=DEBOUNCE_MS)
        watcher.start()
        watcher.stop()  # must not raise

    def test_watcher_nonexistent_vault_raises(self, tmp_path: Path) -> None:
        """VaultWatcher with a nonexistent vault path raises on start() or __init__."""
        bad_path = tmp_path / "does_not_exist"
        bus = EventBus()

        with pytest.raises(Exception):
            # Spec allows raising in __init__ or in start() — test both possibilities
            watcher = VaultWatcher(bad_path, bus, debounce_ms=DEBOUNCE_MS)
            watcher.start()
            watcher.stop()


class TestEventBusAsyncSubscriber:
    def test_async_subscriber_receives_event(self) -> None:
        """publish() from a non-asyncio thread must schedule async handlers via
        run_coroutine_threadsafe — the async subscriber must still be called.

        Setup:
          1. Create an asyncio event loop running in a background thread.
          2. Create an EventBus and call bus.set_loop(loop).
          3. Subscribe an async coroutine handler.
          4. Call bus.publish("test_event") from the main thread (not the asyncio thread).
          5. Wait briefly and assert the async handler ran.
        """
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()

        try:
            bus = EventBus()
            bus.set_loop(loop)

            called = []

            async def async_handler(**kwargs):
                called.append(kwargs)

            bus.subscribe("test_event", async_handler)

            # publish from the main (non-asyncio) thread
            bus.publish("test_event", source="main_thread")

            # Poll instead of a flat sleep (same _wait_until pattern as the
            # twin test in test_eventbus.py): fast when healthy, and a loaded
            # CI runner gets the full timeout instead of a flaky 200ms.
            assert _wait_until(lambda: len(called) == 1), (
                "Async subscriber was not called after publish() from a non-asyncio thread; "
                "check that EventBus.publish() uses run_coroutine_threadsafe for coroutines "
                "when a loop has been set via set_loop()."
            )
            assert called[0].get("source") == "main_thread", (
                "Async subscriber received unexpected payload: %r" % called[0]
            )
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)
            loop.close()
