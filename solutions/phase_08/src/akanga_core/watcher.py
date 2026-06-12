"""VaultWatcher — filesystem event monitoring with debounce.

Uses the ``watchdog`` library to monitor the vault directory for file
changes.  Debounces rapid file events (an editor save can produce 5-10
OS events in 50 ms) into a single ``file_changed`` or ``file_deleted``
event after the burst settles.

Key design decisions:
- Debounce is per-path so unrelated files fire independently.
- ONE background worker thread polls the pending fire-times and fires
  expired entries — never a ``threading.Timer`` per path (a timer per path
  exhausts threads during bulk operations like a git checkout).
- Hidden directories (.git/, .obsidian/) and editor temp files are filtered.
- Atomic saves (``os.replace`` of a temp file onto the target — the macOS
  norm) surface as MOVE events, so ``on_moved`` schedules the DESTINATION
  path; ignoring moves would silently drop every atomic save.
- DELETES ARE DEBOUNCED TOO, through the same per-path deadline table.
  Real editors and sync engines emit *transient* deletes: vim's
  rename-backup save deletes the real path and immediately recreates it,
  ``sed -i`` and Dropbox/iCloud "replace" do the same dance. A
  create/modify for the same path inside the debounce window OVERWRITES
  the pending delete — one grace window, no phantom ``file_deleted`` for
  a file that still exists. A genuine deletion simply fires one debounce
  interval late.
- Observer and worker run as daemon threads so they do not block process
  exit; ``stop()`` still shuts both down explicitly — OBSERVER FIRST (it
  is the event source), then the worker, then the pending table.
- ALL deadline arithmetic uses ``time.monotonic()``, never ``time.time()``:
  the wall clock can step forwards or backwards under NTP adjustment
  (firing debounced events early or wedging them), and the test suite
  measures the debounce window with monotonic timestamps — deadlines must
  live on the same clock.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from .eventbus import EventBus

logger = logging.getLogger(__name__)

# File suffixes that should never trigger re-indexing
IGNORED_SUFFIXES = (".swp", ".swo", ".tmp")
# File name prefixes to ignore (catches hidden files like .DS_Store)
IGNORED_PREFIXES = (".",)


class _VaultEventHandler(FileSystemEventHandler):
    """Routes raw watchdog callbacks into the watcher's debounce logic.

    Runs on the watchdog OBSERVER thread: every method does O(1)
    bookkeeping only (record a deadline in the pending table) and never
    blocks — the debounce worker does the real publishing.
    """

    def __init__(self, watcher: "VaultWatcher") -> None:
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._schedule(os.fsdecode(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._schedule(os.fsdecode(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_delete(os.fsdecode(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        # Atomic saves (os.replace of tmp → target, the macOS norm) arrive
        # as MOVE events: treat the source as deleted (debounced — see
        # _handle_delete) and the destination as changed. _handle_delete /
        # _should_ignore filter temp-file halves (e.g. *.tmp → *.md keeps
        # only the .md side).
        if event.is_directory:
            return
        self._watcher._handle_delete(os.fsdecode(event.src_path))
        self._watcher._schedule(os.fsdecode(event.dest_path))


class VaultWatcher:
    """Monitors a vault directory and publishes file events onto the EventBus.

    Attributes:
        vault:       Absolute path to the vault root.
        eventbus:    The shared EventBus instance.
        debounce_ms: Milliseconds to wait after the last OS event before
                     publishing ``file_changed`` / ``file_deleted``.
                     Default 500 ms. This is also the grace window in
                     which a create/modify cancels a pending delete.
    """

    def __init__(
        self,
        vault: Path,
        eventbus: "EventBus",
        debounce_ms: int = 500,
    ) -> None:
        self.vault = Path(vault)
        self.eventbus = eventbus
        self.debounce_ms = debounce_ms
        self._observer: Observer | None = None        # watchdog Observer, set in start()
        # Per-path debounce table: path -> (deadline, event name). The
        # event name is "file_changed" or "file_deleted"; recording it in
        # the SAME slot is what makes a create/modify cancel a pending
        # delete (and vice versa) — last writer wins, one event per path.
        self._pending: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()          # signals _worker_loop to exit
        self._worker: threading.Thread | None = None  # single debounce worker

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the watchdog observer and the single debounce worker thread.

        The observer runs in a background daemon thread, calling our
        event handler whenever the OS reports a filesystem change; the
        worker thread polls the per-path deadlines and fires the ones
        whose debounce window has expired.

        Restartable: both threads are created HERE, not in ``__init__``,
        and a FRESH ``threading.Event`` replaces the old stop signal —
        so start() after stop() gets a clean worker that a stale, already
        set event can never wedge.

        Raises:
            FileNotFoundError: when the vault directory does not exist —
                silently watching nothing would be far worse than failing.
        """
        if not self.vault.is_dir():
            raise FileNotFoundError(f"Vault directory does not exist: {self.vault}")

        observer = Observer()
        observer.schedule(_VaultEventHandler(self), str(self.vault), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_loop, name="vault-watcher-debounce", daemon=True
        )
        self._worker.start()

    def stop(self) -> None:
        """Stop the observer, then the debounce worker; drop pending events.

        Shutdown order matters and goes SOURCE-FIRST:

        1. Stop + join the OBSERVER — it is the event source. Stopping
           the worker first would leave the observer free to keep
           appending to ``_pending`` (or worse, publish deletes) into a
           watcher that nothing will ever drain.
        2. Signal + join the WORKER (with a timeout — a wedged thread
           must not hang shutdown; both threads are daemons anyway).
        3. Clear ``_pending`` — events still inside their debounce window
           at shutdown are deliberately dropped, never fired late onto a
           bus whose subscribers may already be torn down.
        """
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        with self._lock:
            self._pending.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_ignore(self, path: str) -> bool:
        """Return True if this filesystem path should be silently ignored.

        Editor temp files and hidden directories generate noise events
        that would trigger unnecessary re-indexing. Ignored when:

        - the path ends with an ``IGNORED_SUFFIXES`` entry (.swp/.swo/.tmp)
        - the path ends with ``~`` (Vim backup files)
        - any vault-relative path component starts with ``'.'`` — hidden
          files AND hidden directories like ``.git/``, ``.obsidian/``
        - the file does not end with ``.md`` (only Markdown matters)
        """
        if path.endswith(IGNORED_SUFFIXES) or path.endswith("~"):
            return True
        if any(part.startswith(IGNORED_PREFIXES) for part in self._relative_parts(path)):
            return True
        return not path.endswith(".md")

    def _relative_parts(self, path: str) -> tuple[str, ...]:
        """Vault-relative components of *path*, symlink-normalised.

        macOS reports FSEvents paths through resolved symlinks (e.g.
        ``/private/var/...`` while the vault was opened as ``/var/...``),
        so both sides are resolved before computing relativity. Paths
        outside the vault fall back to their own components.
        """
        candidate = Path(path)
        try:
            return candidate.resolve().relative_to(self.vault.resolve()).parts
        except (OSError, ValueError):
            return candidate.parts

    def _normalize(self, path: str) -> Path:
        """Re-anchor a watchdog-reported path under ``self.vault`` as given.

        Published payloads must match the caller's notion of the vault
        path — not the symlink-resolved spelling the OS reports (see
        ``_relative_parts``). Paths outside the vault pass through as-is.
        """
        candidate = Path(path)
        try:
            rel = candidate.resolve().relative_to(self.vault.resolve())
        except (OSError, ValueError):
            return candidate
        return self.vault / rel

    def _worker_loop(self) -> None:
        """The single debounce worker — fires expired entries until stopped.

        ONE polling thread serves the whole watcher: a ``threading.Timer``
        per path would spawn a thread per file event and exhaust threads
        during bulk operations (a git checkout touching hundreds of
        files). One worker scales to any event rate at the cost of at
        most one poll-interval of extra latency. ``Event.wait`` (not
        ``time.sleep``) between polls makes stop() take effect at once.
        """
        poll_interval = min(0.05, max(self.debounce_ms / 1000.0 / 4.0, 0.005))
        while not self._stop_event.is_set():
            now = time.monotonic()
            with self._lock:
                due = [
                    path
                    for path, (deadline, _event) in self._pending.items()
                    if deadline <= now
                ]
            # Fire OUTSIDE the lock — _fire takes the lock itself and then
            # publishes onto the eventbus, which must never run under our lock.
            for path in due:
                self._fire(path)
            self._stop_event.wait(timeout=poll_interval)

    def _schedule(self, path: str) -> None:
        """Record (or push back) a debounced ``file_changed`` for *path*.

        A single editor save can produce 5-10 OS events within 50 ms;
        re-recording the deadline on every event IS the debounce — the
        burst keeps moving the deadline until it stops, then the worker
        fires once. O(1), no per-path threads, no notification needed
        (the worker polls on its own schedule).

        Cancellation side of the delete grace window: writing the
        "file_changed" entry OVERWRITES any pending "file_deleted" for the
        same path — vim's rename-backup save, ``sed -i``, and sync-engine
        replaces all delete-then-recreate, and must surface as a single
        change, never as a phantom deletion.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = (
                time.monotonic() + self.debounce_ms / 1000.0,
                "file_changed",
            )

    def _fire(self, path: str) -> None:
        """Publish the recorded event once the burst has settled for *path*.

        Runs after ``debounce_ms`` of silence, meaning the editor has
        finished writing and the file is stable. The deadline is
        RE-CHECKED under the lock before popping: if the path was
        re-scheduled (or its entry replaced by a delete/create) between
        the worker's poll snapshot and this call, the newer deadline wins
        and nothing fires yet; if the entry was removed, the cancellation
        is respected and nothing fires at all.
        """
        with self._lock:
            entry = self._pending.get(path)
            if entry is None:
                return  # cancelled since the poll snapshot
            deadline, event = entry
            if deadline > time.monotonic():
                return  # re-debounced since the poll snapshot — newer deadline wins
            del self._pending[path]
        if event == "file_deleted" and os.path.exists(path):
            # Phantom delete: macOS FSEvents coalesces an atomic replace
            # (os.replace onto an existing path) into a "deleted" flag for
            # the TARGET path — which is alive and holding new content.
            # Trust the disk over the event stream: deliver the change.
            # This branch is exercised by macOS FSEvents coalescing; on
            # inotify (Linux CI) the replace arrives as MOVED_TO instead,
            # so green Linux CI never executes it.
            event = "file_changed"
        self.eventbus.publish(event, path=self._normalize(path))

    def _handle_delete(self, path: str) -> None:
        """Record a debounced ``file_deleted`` for *path*.

        Deletions go through the SAME deadline table as changes — not
        because deletes burst (they don't), but as a GRACE WINDOW:
        editors and sync engines routinely emit a transient delete that
        is followed within milliseconds by a create for the same path
        (vim rename-backup saves, ``sed -i``, Dropbox/iCloud replace).
        If that create/modify arrives inside the window, ``_schedule``
        overwrites this entry and the deletion never fires. A genuine
        deletion fires ``debounce_ms`` late — a fair price for never
        evicting a node whose file still exists.

        Writing the "file_deleted" entry also supersedes any pending
        change event for the path: delete-after-modify means the file is
        gone, and gone wins.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = (
                time.monotonic() + self.debounce_ms / 1000.0,
                "file_deleted",
            )
