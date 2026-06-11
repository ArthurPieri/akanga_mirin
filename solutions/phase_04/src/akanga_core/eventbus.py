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
import logging
import threading
from collections import defaultdict, deque
from typing import Callable

logger = logging.getLogger(__name__)


def _log_future_exception(future: "asyncio.Future") -> None:
    """Done-callback that surfaces an async handler's exception in the log.

    Without retrieving ``future.exception()`` the error vanishes silently
    (asyncio only warns about never-retrieved exceptions at GC time) —
    which would violate the bus's error-isolation invariant for async
    handlers. Cancellation is not an error and is ignored.
    """
    if future.cancelled():
        return
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
        """Register the asyncio event loop, then drain buffered dispatches.

        Async subscriber coroutines cannot be called directly from a
        non-asyncio thread; they must be scheduled onto the loop. Events
        that fired before the loop was registered (the BUG-04 startup
        race) were buffered by publish() — draining them here, FIFO and
        exactly once, is required behaviour: a bare ``self._loop = loop``
        loses those events.

        Call this as early as possible in startup — BEFORE starting the
        filesystem watcher. The buffer makes early events safe, not free:
        they are delayed until the loop exists.
        """
        self._loop = loop
        # Drain FIFO; schedule OUTSIDE the lock (same lock discipline as
        # publish() — never run scheduling/user code while holding it).
        while True:
            with self._lock:
                if not self._buffer:
                    break
                handler, kwargs = self._buffer.popleft()
            future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
            future.add_done_callback(_log_future_exception)

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register a handler (sync or async) for the named event.

        Decoupling: the publisher does not need to know who listens, and
        multiple independent components may subscribe to the same event.
        Thread-safe — multiple threads may subscribe concurrently.
        """
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Remove a previously registered handler.

        Safe to call even when *handler* was never subscribed — a
        component tearing itself down must not have to track whether its
        subscription ever succeeded.
        """
        with self._lock:
            handlers = self._handlers.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: str, **kwargs) -> None:
        """Dispatch an event to all registered handlers.

        A SNAPSHOT of the handler list is taken under the lock, then the
        lock is released before any handler runs — calling a handler
        while holding the lock would deadlock if it tried to
        subscribe/unsubscribe.

        Dispatch rules per handler:

        - async + loop set:   ``run_coroutine_threadsafe`` onto the loop,
          with a done-callback that logs the Future's exception.
        - async + no loop:    BUFFER ``(handler, kwargs)`` — never call
          the coroutine function directly (the BUG-04 race); set_loop()
          drains the buffer.
        - sync:               called directly; this direct call is the
          ONLY no-loop fallback.

        Error isolation: each dispatch is wrapped in its own try/except —
        a failing subscriber is logged and never crashes the bus or
        skips later subscribers.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, ()))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    if self._loop is not None:
                        future = asyncio.run_coroutine_threadsafe(
                            handler(**kwargs), self._loop
                        )
                        future.add_done_callback(_log_future_exception)
                    else:
                        # Startup window: no loop yet — buffer, never drop,
                        # never call the coroutine directly.
                        with self._lock:
                            self._buffer.append((handler, dict(kwargs)))
                else:
                    handler(**kwargs)
            except Exception:
                logger.exception(
                    "handler %r failed for event %r — continuing", handler, event
                )
