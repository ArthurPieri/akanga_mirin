from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

class Debouncer:
    """Debounces events using a single background thread and a pending dict."""
    
    def __init__(self, callback: Callable[[str], None], debounce_ms: int = 500) -> None:
        self.callback = callback
        self.debounce_ms = debounce_ms
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="DebouncerThread")
        self._thread.start()

    def submit(self, path: str) -> None:
        """Submit a path for debounced processing."""
        with self._lock:
            self._pending[path] = time.time() + (self.debounce_ms / 1000.0)

    def cancel(self, path: str) -> None:
        """Cancel pending processing for a path."""
        with self._lock:
            self._pending.pop(path, None)

    def _run(self) -> None:
        """Worker thread loop that polls for expired timers."""
        while not self._stop_event.is_set():
            now = time.time()
            to_fire = []
            
            with self._lock:
                for path, fire_time in list(self._pending.items()):
                    if now >= fire_time:
                        to_fire.append(path)
                        del self._pending[path]
            
            for path in to_fire:
                try:
                    self.callback(path)
                except Exception:
                    logger.exception("Error in debouncer callback")
            
            time.sleep(0.05) # Poll every 50ms to keep CPU usage low but response snappy

    def stop(self) -> None:
        """Stop the debouncer thread."""
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

class VaultWatcher:
    """Monitors a vault directory and publishes events to an EventBus."""
    
    def __init__(self, vault: Path, eventbus: Any, debounce_ms: int = 500) -> None:
        self.vault = Path(vault).absolute()
        self.eventbus = eventbus
        self.debouncer = Debouncer(self._fire, debounce_ms)
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start the watchdog observer."""
        class Handler(FileSystemEventHandler):
            def __init__(self, watcher: VaultWatcher) -> None:
                self.watcher = watcher

            def on_modified(self, event: Any) -> None:
                if not event.is_directory:
                    self.watcher._schedule(event.src_path)

            def on_created(self, event: Any) -> None:
                if not event.is_directory:
                    self.watcher._schedule(event.src_path)

            def on_deleted(self, event: Any) -> None:
                if not event.is_directory:
                    self.watcher._handle_delete(event.src_path)

            def on_moved(self, event: Any) -> None:
                if not event.is_directory:
                    self.watcher._handle_delete(event.src_path)
                    self.watcher._schedule(event.dest_path)

        self._observer = Observer()
        self._observer.schedule(Handler(self), str(self.vault), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop(self) -> None:
        """Stop the observer and debouncer."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self.debouncer.stop()

    def _should_ignore(self, path: str) -> bool:
        """Filter out noise events like hidden files and temp files."""
        p = Path(path)
        try:
            rel_path = p.relative_to(self.vault)
            # Ignore if any part of the path starts with '.'
            if any(part.startswith(".") for part in rel_path.parts):
                return True
        except ValueError:
            return True
            
        if p.suffix in {".swp", ".swo", ".tmp"} or p.name.endswith("~"):
            return True
        if p.suffix != ".md":
            return True
        return False

    def _schedule(self, path: str) -> None:
        """Schedule a debounced change event."""
        if not self._should_ignore(path):
            self.debouncer.submit(path)

    def _fire(self, path: str) -> None:
        """Actually publish the change event to the EventBus."""
        self.eventbus.publish("file_changed", path=Path(path))

    def _handle_delete(self, path: str) -> None:
        """Immediately publish a delete event and cancel any pending changes."""
        if not self._should_ignore(path):
            self.debouncer.cancel(path)
            self.eventbus.publish("file_deleted", path=Path(path))
