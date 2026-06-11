"""EventBus — thread-safe publish/subscribe message bus.

The bus decouples components: the file watcher publishes events without
knowing which components handle them. Subscribers register independently.

Thread-safety requirement: ``publish()`` is called from watchdog daemon
threads (non-asyncio). Async subscribers are dispatched EXCLUSIVELY via
``asyncio.run_coroutine_threadsafe`` once an event loop is registered
with ``set_loop()`` — never by calling the coroutine function directly
(calling it only creates a coroutine object; it never runs).

Startup-race rule (BUG-04): if ``publish()`` fires BEFORE ``set_loop()``
has been called, async dispatches are NOT silently dropped and NOT called
directly. They are BUFFERED into ``self._buffer`` (a deque) and drained
by ``set_loop()`` the moment the loop is registered — delivery, not loss,
is the contract. Direct (immediate) calls are only ever made for
synchronous handlers.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections import defaultdict, deque
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Supports both sync and async subscribers. Async subscribers are
    dispatched via ``asyncio.run_coroutine_threadsafe`` when called from
    a non-asyncio thread (e.g. a watchdog daemon thread). Async dispatches
    that arrive before ``set_loop()`` are buffered (see module docstring).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # Pending async dispatches recorded by publish() before set_loop():
        # (handler, kwargs) pairs, drained in FIFO order by set_loop().
        self._buffer: deque[tuple[Callable, dict]] = deque()

    # ------------------------------------------------------------------
    # Loop registration + buffer drain
    # ------------------------------------------------------------------

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the asyncio loop, then drain the pre-loop buffer (FIFO).

        WHY drain here: events that fired before the loop existed (the
        BUG-04 startup race) were buffered by ``publish()``; a bare
        ``self._loop = loop`` would lose them forever. Each buffered
        ``(handler, kwargs)`` pair is scheduled exactly once — popping
        under the lock empties the deque, so a later ``publish()`` can
        never replay it.

        Scheduling happens OUTSIDE the lock — same lock discipline as
        ``publish()``: never run foreign code while holding our lock.
        """
        self._loop = loop
        while True:
            with self._lock:
                if not self._buffer:
                    break
                handler, kwargs = self._buffer.popleft()
            future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
            future.add_done_callback(self._log_future_exception)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register *handler* (sync or async) for the named event.

        WHY: decoupling — the publisher does not need to know who listens;
        multiple independent components can subscribe to the same event.
        Thread-safe: the shared ``_handlers`` dict is only touched under
        ``self._lock``.
        """
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Remove a previously registered handler.

        Safe to call with a handler that was never subscribed — components
        cleaning up on shutdown must never crash the bus.
        """
        with self._lock:
            handlers = self._handlers.get(event)
            if handlers is not None and handler in handlers:
                handlers.remove(handler)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def publish(self, event: str, **kwargs: Any) -> None:
        """Dispatch an event to all registered handlers.

        The handler list is SNAPSHOTTED under the lock and the lock is
        released before any handler runs — calling a handler while holding
        the lock would deadlock if it tries to subscribe/unsubscribe.

        Per-handler dispatch rules:

        - async handler + loop set:   ``run_coroutine_threadsafe`` onto the
          loop, with a done-callback that logs the Future's exception —
          without it async handler errors vanish silently.
        - async handler + NO loop:    buffer ``(handler, kwargs)``; never
          call the coroutine function directly (BUG-04).
        - sync handler:               call directly. This is the ONLY
          no-loop fallback, and it applies to sync handlers exclusively.

        Error isolation: each dispatch is wrapped in its own try/except —
        a failing subscriber is logged and never prevents later
        subscribers from firing or crashes the bus.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, ()))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    loop = self._loop
                    if loop is None:
                        with self._lock:
                            self._buffer.append((handler, dict(kwargs)))
                    else:
                        future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
                        future.add_done_callback(self._log_future_exception)
                else:
                    handler(**kwargs)
            except Exception:
                logger.exception("Handler for event %r failed", event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_future_exception(future: concurrent.futures.Future) -> None:
        """Done-callback that surfaces async handler errors in the log.

        ``run_coroutine_threadsafe`` returns a concurrent Future whose
        exception is never raised anywhere unless someone retrieves it —
        this callback is that someone.
        """
        if future.cancelled():
            return
        exc = future.exception()
        if exc is not None:
            logger.error("async handler failed: %r", exc)
