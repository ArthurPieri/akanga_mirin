"""EventBus — thread-safe publish/subscribe message bus.

The bus decouples components: the file watcher publishes events without
knowing which components handle them. Subscribers register independently.

Thread safety requirement: publish() is called from watchdog daemon threads
(non-asyncio). Async subscribers are dispatched EXCLUSIVELY via
``asyncio.run_coroutine_threadsafe`` once an event loop is registered with
set_loop() — never by calling the coroutine function directly.

Startup-race rule (BUG-04): if publish() fires BEFORE set_loop() has been
called, async dispatches are NOT silently dropped and NOT called directly.
They are BUFFERED into ``self._buffer`` (a deque) and drained by set_loop()
the moment the loop is registered. Direct (immediate) calls are only ever
made for synchronous handlers.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _log_future_exception(future: concurrent.futures.Future) -> None:
    """Done-callback that surfaces an async handler's exception in the log.

    Without retrieving ``future.exception()`` the error vanishes silently
    (asyncio only warns about *never-retrieved* exceptions at GC time) —
    which would violate the bus's error-isolation invariant.
    """
    exc = future.exception()
    if exc is not None:
        logger.error("async handler failed: %r", exc)


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Supports both sync and async subscribers. Async subscribers are
    dispatched via ``asyncio.run_coroutine_threadsafe`` when called from
    a non-asyncio thread (e.g. watchdog daemon thread). Async dispatches
    that arrive before set_loop() are buffered (see module docstring).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # Pending async dispatches recorded by publish() before set_loop():
        # (handler, kwargs) pairs, drained in FIFO order by set_loop().
        self._buffer: deque[tuple[Callable, dict]] = deque()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the asyncio loop, then drain the pre-loop event buffer.

        Events published from non-asyncio threads before the loop existed
        were buffered by publish() (the BUG-04 startup race); flushing
        them here — exactly once, FIFO — is the delivery contract. Each
        entry is popped under the lock but SCHEDULED outside it, the same
        lock discipline publish() uses: never run dispatch machinery
        while holding the bus lock.

        Call this as early as possible in startup, BEFORE starting the
        filesystem watcher: the buffer makes early events safe, not free —
        they are delayed until the loop exists.
        """
        self._loop = loop
        while True:
            with self._lock:
                if not self._buffer:
                    break
                handler, kwargs = self._buffer.popleft()
            future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
            future.add_done_callback(_log_future_exception)

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register `handler` (sync or async) for the named event.

        Thread-safe: the shared handler registry is only touched under
        the lock, so concurrent subscribes from the watcher thread and
        the UI thread cannot corrupt the list.
        """
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Remove a previously registered handler; never raises.

        Unsubscribing a handler that was never registered is a silent
        no-op — components tearing down must not have to track whether
        their subscription ever happened.
        """
        with self._lock:
            if handler in self._handlers.get(event, []):
                self._handlers[event].remove(handler)

    def publish(self, event: str, **kwargs) -> None:
        """Dispatch an event to all registered handlers.

        The handler list is SNAPSHOT under the lock and dispatched after
        releasing it — calling a handler while holding the lock would
        deadlock the moment a handler tries to subscribe/unsubscribe.

        Per-handler routing:

        - async handler + loop set   → ``run_coroutine_threadsafe`` with a
          done-callback that logs the Future's exception (without it the
          error is silently dropped).
        - async handler + NO loop    → buffer ``(handler, kwargs)``; calling
          the coroutine function directly from a watchdog thread is exactly
          the BUG-04 race. set_loop() drains the buffer.
        - sync handler               → called directly (the only no-loop
          direct call).

        Error isolation: every individual dispatch is wrapped in its own
        try/except — one failing subscriber must never crash the bus or
        starve the subscribers after it.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    if self._loop is not None:
                        future = asyncio.run_coroutine_threadsafe(
                            handler(**kwargs), self._loop
                        )
                        future.add_done_callback(_log_future_exception)
                    else:
                        with self._lock:
                            self._buffer.append((handler, dict(kwargs)))
                else:
                    handler(**kwargs)
            except Exception:  # noqa: BLE001 — error isolation is the invariant
                logger.exception("handler for %r failed", event)
