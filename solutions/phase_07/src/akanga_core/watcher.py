"""VaultWatcher — filesystem event monitoring with debounce.

Uses the ``watchdog`` library to monitor the vault directory for file
changes. Debounces rapid file events (an editor save can produce 5–10
OS events in 50 ms) into a single ``file_changed`` or ``file_deleted``
event after the burst settles.

Key design decisions:

- Debounce is per-path so unrelated files fire independently.
- ONE background worker thread polls the pending fire-times and fires
  expired entries — never a ``threading.Timer`` per path (a timer per
  path exhausts threads during bulk operations like a git checkout).
- Hidden directories (.git/, .obsidian/) and editor temp files are
  filtered before they ever reach the debounce table.
- Observer and worker run as daemon threads so they do not block process
  exit; ``stop()`` still shuts both down explicitly.
"""
from __future__ import annotations

import logging
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
IGNORED_SUFFIXES = {".swp", ".swo", ".tmp"}
# File name prefixes to ignore (catches hidden files like .DS_Store)
IGNORED_PREFIXES = {"."}


class _VaultEventHandler(FileSystemEventHandler):
    """Thin watchdog adapter — every callback delegates to the watcher.

    Runs on the watchdog OBSERVER thread: it must do O(1) bookkeeping
    only (record a fire time / publish a delete) and never block.
    """

    def __init__(self, watcher: "VaultWatcher") -> None:
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._schedule(str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._schedule(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_delete(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        # A move is a delete at the old path plus a change at the new one.
        # Atomic editor saves (`os.replace(tmp, target)`) arrive as moves
        # whose src is an ignored .tmp file — only the destination fires.
        if event.is_directory:
            return
        self._watcher._handle_delete(str(event.src_path))
        self._watcher._schedule(str(event.dest_path))


class VaultWatcher:
    """Monitors a vault directory and publishes file events onto the EventBus.

    Attributes:
        vault:       Absolute path to the vault root.
        eventbus:    The shared EventBus instance.
        debounce_ms: Milliseconds to wait after the last OS event before
                     publishing ``file_changed``. Default 500 ms.
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
        self._pending: dict[str, float] = {}          # per-path scheduled fire times
        self._lock = threading.Lock()
        self._stop_event = threading.Event()          # signals _worker_loop to exit
        self._worker: threading.Thread | None = None  # single debounce worker

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the watchdog observer and the single debounce worker.

        Raises FileNotFoundError when the vault directory does not exist —
        silently watching nothing would be a far harder bug to diagnose
        than an immediate failure at startup.
        """
        if not self.vault.is_dir():
            raise FileNotFoundError(f"Vault directory does not exist: {self.vault}")

        observer = Observer()
        observer.schedule(_VaultEventHandler(self), str(self.vault), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

        self._stop_event.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        logger.info("Watching %s (debounce %d ms)", self.vault, self.debounce_ms)

    def stop(self) -> None:
        """Stop the debounce worker and the observer; drop pending events.

        The worker MUST be joined — otherwise it could still fire a
        debounced event onto the bus after the rest of the app has shut
        down. Joins use timeouts so a wedged thread cannot hang shutdown.
        """
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        with self._lock:
            self._pending.clear()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_ignore(self, path: str) -> bool:
        """Return True when a filesystem path should be silently dropped.

        Editor temp files (.swp/.swo/.tmp/~), anything under a hidden
        directory (.git/, .obsidian/ — any dot-component relative to the
        vault), and non-Markdown files generate noise events that would
        only waste indexer cycles.
        """
        if path.endswith("~"):
            return True
        if any(path.endswith(suffix) for suffix in IGNORED_SUFFIXES):
            return True

        try:
            relative = Path(path).resolve().relative_to(self.vault.resolve())
        except (ValueError, OSError):
            relative = Path(path)
        if any(part.startswith(".") for part in relative.parts):
            return True

        return not path.endswith(".md")

    def _worker_loop(self) -> None:
        """The single debounce worker — fires expired pending entries.

        ONE polling thread for the whole watcher: a ``threading.Timer``
        per path would spawn a thread per file event and exhaust threads
        during bulk operations. One worker scales to any event rate at
        the cost of at most one poll-interval of extra latency.

        ``Event.wait`` (not ``time.sleep``) paces the loop so ``stop()``
        takes effect immediately instead of after a full sleep.
        """
        poll_interval = min(0.05, max(self.debounce_ms / 1000 / 4, 0.005))
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                due = [path for path, fire_at in self._pending.items() if fire_at <= now]
            for path in due:
                # Outside the lock: _fire takes the lock itself and publishes
                # onto the eventbus, which must never run under our lock.
                self._fire(path)
            self._stop_event.wait(timeout=poll_interval)

    def _schedule(self, path: str) -> None:
        """Record (or push back) the debounced fire time for *path*.

        Re-recording an existing path moves its deadline forward — that
        IS the debounce: a burst of saves keeps moving the deadline until
        the burst stops, and only then does ``_worker_loop`` fire once.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = time.time() + (self.debounce_ms / 1000)

    def _fire(self, path: str) -> None:
        """Publish ``file_changed`` after the burst settled for *path*.

        Runs on the worker thread once ``debounce_ms`` of silence has
        elapsed — the editor has finished writing and the file is stable.
        """
        with self._lock:
            removed = self._pending.pop(path, None)
        if removed is None:
            return  # already fired (or cancelled by stop/delete)
        self.eventbus.publish("file_changed", path=Path(path))

    def _handle_delete(self, path: str) -> None:
        """Publish ``file_deleted`` immediately (no debounce).

        Deletions never arrive in bursts for a single file, and the node
        must leave the index as soon as possible. A pending change event
        for the same path is superseded and dropped.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_deleted", path=Path(path))
