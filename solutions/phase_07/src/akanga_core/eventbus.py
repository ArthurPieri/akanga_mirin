"""EventBus — thread-safe publish/subscribe message bus.

The bus decouples components: the file watcher publishes events without
knowing which components handle them. Subscribers register independently.

Thread safety: publish() is called from watchdog daemon threads
(non-asyncio). Async subscribers are dispatched EXCLUSIVELY via
``asyncio.run_coroutine_threadsafe`` once an event loop is registered
with set_loop() — never by calling the coroutine function directly.

Startup-race rule (BUG-04): if publish() fires BEFORE set_loop() has been
called, async dispatches are NOT silently dropped and NOT called
directly. They are BUFFERED into ``self._buffer`` (a deque) and drained
by set_loop() the moment the loop is registered — delivery, not loss, is
the contract. Direct (immediate) calls are only ever made for
synchronous handlers.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import Future

logger = logging.getLogger(__name__)


def _log_future_exception(fut: Future) -> None:
    """Done-callback that surfaces async handler failures.

    REQUIRED on every Future returned by ``run_coroutine_threadsafe`` —
    without it the Future's exception is never retrieved and async
    handler errors vanish silently, violating the error-isolation
    invariant the synchronous path already guarantees.
    """
    try:
        exc = fut.exception()
    except (asyncio.CancelledError, Exception):  # noqa: BLE001 — never raise from a callback
        return
    if exc is not None:
        logger.error("async handler failed: %r", exc)


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Supports both sync and async subscribers. Async subscribers are
    dispatched via ``asyncio.run_coroutine_threadsafe`` when called from
    a non-asyncio thread (e.g. the watchdog daemon thread). Async
    dispatches that arrive before set_loop() are buffered (see module
    docstring).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # Pending async dispatches recorded by publish() before set_loop():
        # (handler, kwargs) pairs, drained in FIFO order by set_loop().
        self._buffer: deque[tuple[Callable, dict]] = deque()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the asyncio loop, then drain pre-loop buffered dispatches.

        Call this as early as possible in startup — BEFORE starting the
        filesystem watcher. The buffer makes early events safe, not free:
        they are delayed until the loop exists, and a bare
        ``self._loop = loop`` would lose them entirely (the BUG-04 race).

        Scheduling happens OUTSIDE the lock — the same lock discipline as
        publish(): never run user code (or loop machinery) while holding
        the bus lock.
        """
        self._loop = loop
        while True:
            with self._lock:
                if not self._buffer:
                    break
                handler, kwargs = self._buffer.popleft()
            fut = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
            fut.add_done_callback(_log_future_exception)

    def subscribe(self, event: str, handler: Callable) -> None:
        """Register *handler* (sync or async) for the named event.

        Decoupling: the publisher never needs to know who listens, and
        multiple independent components may subscribe to the same event.
        Thread-safe — the shared ``_handlers`` dict is only touched under
        the lock.
        """
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Remove a previously registered handler.

        Safe to call for a handler that was never subscribed — components
        cleaning up on teardown must not have to track whether their
        subscription actually happened.
        """
        with self._lock:
            handlers = self._handlers.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: str, **kwargs) -> None:
        """Dispatch an event to all registered handlers.

        The handler list is SNAPSHOTTED under the lock and dispatched
        after releasing it — calling a handler while holding the lock
        would deadlock the moment a handler tries to (un)subscribe.

        Per-handler routing:

        - async handler + loop set  → ``run_coroutine_threadsafe`` with a
          done-callback that logs the Future's exception;
        - async handler + NO loop   → buffer ``(handler, kwargs)`` for
          set_loop() to drain (never call the coroutine directly — that
          is exactly the BUG-04 race);
        - sync handler              → direct call.

        Every individual dispatch is wrapped in its own try/except: a
        failing subscriber is logged and never prevents later subscribers
        from firing (error isolation), and publish() itself never raises.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, ()))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    if self._loop is not None:
                        fut = asyncio.run_coroutine_threadsafe(
                            handler(**kwargs), self._loop
                        )
                        fut.add_done_callback(_log_future_exception)
                    else:
                        with self._lock:
                            self._buffer.append((handler, dict(kwargs)))
                else:
                    handler(**kwargs)
            except Exception:  # noqa: BLE001 — error isolation is the key invariant
                logger.exception("handler for %r failed", event)
