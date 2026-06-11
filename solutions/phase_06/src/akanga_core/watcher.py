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
- Observer and worker run as daemon threads so they do not block process
  exit; ``stop()`` still shuts both down explicitly (set the stop event,
  join the worker, stop+join the observer).
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
    """Translates raw watchdog callbacks into watcher schedule/delete calls.

    Watchdog invokes these methods on its own daemon thread; every method
    therefore does the minimum — filter, then hand off to the watcher's
    O(1) bookkeeping. The debounce worker does the real publishing.
    """

    def __init__(self, watcher: VaultWatcher) -> None:
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
        """A rename is a delete at the old path plus a change at the new one.

        This is also how atomic saves surface: editors write `x.md.tmp`
        then ``os.replace`` it onto `x.md` — the move's destination is the
        real node file, while the temp-file source is filtered out by
        ``_should_ignore`` inside ``_handle_delete``.
        """
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
                     publishing ``file_changed``.  Default 500 ms.
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
        silently watching nothing would be far harder to debug than an
        immediate failure at startup.
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

    def stop(self) -> None:
        """Stop the debounce worker and observer; cancel all pending events.

        The worker MUST be joined before clearing the pending map —
        otherwise it could still fire a debounced event onto the bus after
        the rest of the application has shut down. Joins use timeouts so a
        wedged thread cannot hang shutdown forever.
        """
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
        with self._lock:
            self._pending.clear()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_ignore(self, path: str) -> bool:
        """Return True if this filesystem path should be silently ignored.

        Filters editor temp files (.swp/.swo/.tmp, trailing ``~``), any
        path with a hidden component (`.git/`, `.obsidian/`, dot-files),
        and everything that is not a Markdown file. Filtering here keeps
        the indexer from wasting cycles on irrelevant noise events.
        """
        p = Path(path)
        if p.suffix in IGNORED_SUFFIXES or path.endswith("~"):
            return True
        try:
            parts = p.relative_to(self.vault).parts
        except ValueError:
            parts = p.parts  # outside the vault — still apply the hidden check
        if any(part.startswith(".") for part in parts):
            return True
        return not path.endswith(".md")

    def _worker_loop(self) -> None:
        """The single debounce worker: poll ``_pending``, fire expired paths.

        ONE polling thread for the whole watcher is the required design —
        a ``threading.Timer`` per path would spawn a thread per file event
        and exhaust threads during bulk operations (a git checkout touching
        hundreds of files). One worker scales to any event rate at the cost
        of at most one poll-interval of extra latency.

        ``Event.wait`` (not ``time.sleep``) paces the loop so ``stop()``
        takes effect immediately instead of after a full sleep.
        """
        poll_interval = min(0.05, self.debounce_ms / 1000 / 4)
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                due = [p for p, fire_at in self._pending.items() if fire_at <= now]
            for path in due:
                # Outside the lock: _fire takes the lock itself and publishes
                # onto the eventbus, which must never run under our lock.
                self._fire(path)
            self._stop_event.wait(timeout=poll_interval)

    def _schedule(self, path: str) -> None:
        """Record (or push back) the debounced fire time for *path*.

        Re-recording an existing path moves its deadline forward — that IS
        the debounce: a burst of saves keeps pushing the fire time until
        the burst stops. O(1) per OS event; the worker loop does the rest.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = time.time() + (self.debounce_ms / 1000)

    def _fire(self, path: str) -> None:
        """Publish ``file_changed`` once the burst has settled for *path*.

        Runs on the worker thread after ``debounce_ms`` of silence — the
        editor has finished writing and the file is stable enough to index.
        """
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_changed", path=Path(path))

    def _handle_delete(self, path: str) -> None:
        """Publish ``file_deleted`` immediately (no debounce).

        Deletions have no save-burst to coalesce, and the node should
        leave the index as soon as possible. A deletion also supersedes
        any pending change event for the same path.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_deleted", path=Path(path))
