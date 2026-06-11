"""VaultWatcher — filesystem event monitoring with debounce.

Uses the ``watchdog`` library to monitor the vault directory for file
changes. Debounces rapid file events (an editor save can produce 5-10
OS events in 50 ms) into a single ``file_changed`` or ``file_deleted``
event after the burst settles.

Key design decisions:

- Debounce is per-path so unrelated files fire independently.
- ONE background worker thread polls the pending fire-times and fires
  expired entries — never a ``threading.Timer`` per path (a timer per
  path exhausts threads during bulk operations like a git checkout).
- Hidden directories (.git/, .obsidian/) and editor temp files are
  filtered before they ever reach the debounce table.
- Atomic editor saves arrive as ``on_moved`` (tmp file → real name): the
  destination is scheduled as a change and the (ignored, non-``.md``)
  source is treated as a delete, so one save → one event.
- Observer and worker run as daemon threads so they do not block process
  exit; ``stop()`` still shuts both down explicitly.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:  # pragma: no cover — import only for type checkers
    from .eventbus import EventBus

logger = logging.getLogger(__name__)

# File suffixes that should never trigger re-indexing
IGNORED_SUFFIXES = (".swp", ".swo", ".tmp")
# File name prefixes to ignore (catches hidden files like .DS_Store)
IGNORED_PREFIXES = (".",)


class _VaultEventHandler(FileSystemEventHandler):
    """Forwards raw watchdog callbacks to the owning VaultWatcher.

    A thin adapter: filtering and debouncing live on the watcher itself so
    they can be unit-tested without a running observer.
    """

    def __init__(self, watcher: VaultWatcher) -> None:
        self._watcher = watcher

    def on_created(self, event: Any) -> None:
        if not event.is_directory:
            self._watcher._schedule(os.fsdecode(event.src_path))

    def on_modified(self, event: Any) -> None:
        if not event.is_directory:
            self._watcher._schedule(os.fsdecode(event.src_path))

    def on_deleted(self, event: Any) -> None:
        if not event.is_directory:
            self._watcher._handle_delete(os.fsdecode(event.src_path))

    def on_moved(self, event: Any) -> None:
        # A rename is a delete of the old path + a change at the new path.
        # Atomic saves (`os.replace(tmp, target)`) hit this hook: the tmp
        # source is filtered out by _should_ignore, leaving exactly one
        # debounced file_changed for the real target.
        if not event.is_directory:
            self._watcher._handle_delete(os.fsdecode(event.src_path))
            self._watcher._schedule(os.fsdecode(event.dest_path))


class VaultWatcher:
    """Monitors a vault directory and publishes file events onto the EventBus.

    Attributes:
        vault:       Path to the vault root (must exist).
        eventbus:    The shared EventBus instance.
        debounce_ms: Milliseconds to wait after the last OS event before
                     publishing ``file_changed``. Default 500 ms.
    """

    def __init__(
        self,
        vault: Path,
        eventbus: EventBus,
        debounce_ms: int = 500,
    ) -> None:
        self.vault = Path(vault)
        if not self.vault.is_dir():
            # Failing fast here (rather than letting the observer thread die
            # silently later) gives the caller an actionable error.
            raise FileNotFoundError(f"Vault directory does not exist: {self.vault}")
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

        Both run as daemon threads: the observer feeds raw OS events into
        ``_schedule`` / ``_handle_delete``; the worker turns settled bursts
        into ``file_changed`` publications.
        """
        observer = Observer()
        observer.schedule(_VaultEventHandler(self), str(self.vault), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop, daemon=True, name="VaultWatcherDebounce"
        )
        self._worker.start()

    def stop(self) -> None:
        """Stop the debounce worker and observer; cancel all pending events.

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
        """Return True if this filesystem path should be silently ignored.

        Editor temp files and hidden directories generate noise events
        that would trigger unnecessary re-indexing. Anything that is not a
        Markdown file inside the (non-hidden part of the) vault is dropped.
        """
        name = os.path.basename(path)
        if name.endswith("~"):
            return True  # Vim backup files
        if any(path.endswith(suffix) for suffix in IGNORED_SUFFIXES):
            return True  # editor swap/temp files
        if not name.endswith(".md"):
            return True  # only Markdown files matter

        # Hidden-component check on the vault-relative path. realpath on
        # both sides keeps macOS /var vs /private/var symlinks consistent.
        rel = os.path.relpath(os.path.realpath(path), os.path.realpath(str(self.vault)))
        if rel == ".." or rel.startswith(".." + os.sep):
            return True  # outside the vault entirely
        return any(part.startswith(".") for part in Path(rel).parts)

    def _worker_loop(self) -> None:
        """The single debounce worker — polls ``_pending`` and fires expired
        entries. Runs until ``self._stop_event`` is set.

        WHY one polling thread: a ``threading.Timer`` per path would spawn
        a thread per file event and exhaust threads during bulk operations
        (a git checkout touching hundreds of files). One worker scales to
        any event rate at the cost of at most one poll-interval of latency.
        """
        poll_interval = max(0.005, min(0.05, self.debounce_ms / 1000 / 4))
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                due = [path for path, fire_at in self._pending.items() if fire_at <= now]
            for path in due:
                # OUTSIDE the lock: _fire takes the lock itself, and it
                # publishes onto the eventbus, which must never happen
                # while holding our lock.
                self._fire(path)
            # Event.wait (not time.sleep) makes stop() take effect immediately.
            self._stop_event.wait(timeout=poll_interval)

    def _schedule(self, path: str) -> None:
        """Record (or push back) the debounced fire time for *path*.

        Re-recording an existing path moves its deadline — that IS the
        debounce: the burst keeps pushing the fire time until it stops.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = time.time() + (self.debounce_ms / 1000)

    def _fire(self, path: str) -> None:
        """Publish ``file_changed`` after the burst settled for *path*."""
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_changed", path=Path(path))

    def _handle_delete(self, path: str) -> None:
        """Publish ``file_deleted`` immediately (no debounce).

        Deletions have no event burst, and the node must leave the index
        as soon as possible. A deletion supersedes any pending change.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_deleted", path=Path(path))
