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
- Observer and worker run as daemon threads so they do not block process
  exit; ``stop()`` still shuts both down explicitly (set the stop event,
  join the worker, stop+join the observer).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .eventbus import EventBus

logger = logging.getLogger(__name__)

# File suffixes that should never trigger re-indexing
IGNORED_SUFFIXES = (".swp", ".swo", ".tmp")
# File name prefixes to ignore (catches hidden files like .DS_Store)
IGNORED_PREFIXES = (".",)


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
        self._observer = None                         # watchdog Observer, set in start()
        self._pending: dict[str, float] = {}          # per-path scheduled fire times
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

        Raises:
            FileNotFoundError: when the vault directory does not exist —
                silently watching nothing would be far worse than failing.
        """
        if not self.vault.is_dir():
            raise FileNotFoundError(f"Vault directory does not exist: {self.vault}")

        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        watcher = self

        class _VaultEventHandler(FileSystemEventHandler):
            """Routes raw watchdog callbacks into the watcher's debounce logic."""

            def on_created(self, event) -> None:
                if event.is_directory:
                    return
                path = os.fsdecode(event.src_path)
                if not watcher._should_ignore(path):
                    watcher._schedule(path)

            def on_modified(self, event) -> None:
                if event.is_directory:
                    return
                path = os.fsdecode(event.src_path)
                if not watcher._should_ignore(path):
                    watcher._schedule(path)

            def on_deleted(self, event) -> None:
                if event.is_directory:
                    return
                watcher._handle_delete(os.fsdecode(event.src_path))

            def on_moved(self, event) -> None:
                # Atomic saves (os.replace of tmp → target, the macOS norm)
                # arrive as MOVE events: treat the source as deleted and the
                # destination as changed. _handle_delete/_should_ignore
                # filter temp-file halves (e.g. *.tmp → *.md keeps only the
                # .md side).
                if event.is_directory:
                    return
                watcher._handle_delete(os.fsdecode(event.src_path))
                dest = os.fsdecode(event.dest_path)
                if not watcher._should_ignore(dest):
                    watcher._schedule(dest)

        observer = Observer()
        observer.schedule(_VaultEventHandler(), str(self.vault), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop, name="vault-watcher-debounce", daemon=True
        )
        self._worker.start()

    def stop(self) -> None:
        """Stop the debounce worker and the observer; cancel pending events.

        The worker MUST be joined — otherwise it could still fire a
        debounced event onto the bus after the rest of the app has shut
        down. Joins use timeouts so a wedged thread cannot hang shutdown
        forever (both are daemons, so they never block process exit).
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
            now = time.time()
            with self._lock:
                due = [path for path, deadline in self._pending.items() if deadline <= now]
            # Fire OUTSIDE the lock — _fire takes the lock itself and then
            # publishes onto the eventbus, which must never run under our lock.
            for path in due:
                self._fire(path)
            self._stop_event.wait(timeout=poll_interval)

    def _schedule(self, path: str) -> None:
        """Record (or push back) the debounced fire time for *path*.

        A single editor save can produce 5-10 OS events within 50 ms;
        re-recording the deadline on every event IS the debounce — the
        burst keeps moving the deadline until it stops, then the worker
        fires once. O(1), no per-path threads, no notification needed
        (the worker polls on its own schedule).
        """
        with self._lock:
            self._pending[path] = time.time() + self.debounce_ms / 1000.0

    def _fire(self, path: str) -> None:
        """Publish ``file_changed`` once the burst has settled for *path*.

        Runs after ``debounce_ms`` of silence, meaning the editor has
        finished writing and the file is stable. If the path was
        re-scheduled between the worker's poll and this call, the newer
        deadline wins and nothing fires yet.
        """
        with self._lock:
            deadline = self._pending.get(path)
            if deadline is None or deadline > time.time():
                return  # cancelled or re-debounced since the poll snapshot
            del self._pending[path]
        self.eventbus.publish("file_changed", path=self._normalize(path))

    def _handle_delete(self, path: str) -> None:
        """Immediately publish ``file_deleted`` (no debounce).

        Deletions have no event burst to coalesce, and the node must
        leave the index as soon as possible. Any pending debounce record
        is dropped first — a deletion supersedes a pending change event.
        """
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending.pop(path, None)
        self.eventbus.publish("file_deleted", path=self._normalize(path))
