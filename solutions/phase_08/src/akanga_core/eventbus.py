from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

class EventBus:
    """Thread-safe event bus that bridges to asyncio using call_soon_threadsafe."""
    
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio loop to use for async handlers."""
        self._loop = loop

    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to an event."""
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Unsubscribe from an event."""
        with self._lock:
            if event in self._handlers:
                try:
                    self._handlers[event].remove(handler)
                except ValueError:
                    pass

    def publish(self, event: str, **kwargs: Any) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            # Snapshot handlers to avoid deadlocks if handler modifies subscriptions
            handlers = list(self._handlers.get(event, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    if self._loop and self._loop.is_running():
                        # Bridge to asyncio using call_soon_threadsafe
                        # We wrap in a lambda to ensure the handler is called with kwargs in the loop
                        self._loop.call_soon_threadsafe(
                            lambda h=handler, kw=kwargs: asyncio.create_task(h(**kw))
                        )
                    else:
                        logger.warning(f"Skipping async handler for {event}: no running loop")
                else:
                    handler(**kwargs)
            except Exception:
                logger.exception(f"Error in handler for event: {event}")
