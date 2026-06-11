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

Lock discipline (the subtle part): publish() makes its buffer-vs-schedule
decision and the buffer append under ONE lock acquisition, and set_loop()
stores the loop under that same lock BEFORE draining. Checking ``_loop``
outside the lock looks harmless but is a TOCTOU race: publish() could see
"no loop", get descheduled, set_loop() could drain an (empty) buffer, and
only then would publish() append — stranding the event in a buffer nothing
will ever drain again. That is exactly the silent loss this class exists
to prevent.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _log_future_exception(future: concurrent.futures.Future) -> None:
    """Done-callback that surfaces an async handler's exception in the log.

    ``run_coroutine_threadsafe`` returns a ``concurrent.futures.Future``
    (not an ``asyncio.Future`` — the caller is on a plain thread). Without
    retrieving ``future.exception()`` the error vanishes silently (asyncio
    only warns about never-retrieved exceptions at GC time) — which would
    violate the bus's error-isolation invariant for async handlers.
    Cancellation is not an error and is ignored: ``future.exception()``
    would RAISE CancelledError on a cancelled future instead of returning
    it, so the guard must come first.
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
        # _loop is only ever read or written while holding _lock — see the
        # module docstring for why an unlocked read in publish() loses events.
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

        Ordering matters: the loop is stored UNDER the lock *before* the
        drain starts. Any publish() that acquired the lock earlier and saw
        no loop has already appended to the buffer (same critical
        section), so the drain below picks it up; any publish() acquiring
        the lock later sees the loop and schedules directly. There is no
        window in which an event can land in the buffer after the final
        drain pass.

        Call this as early as possible in startup — BEFORE starting the
        filesystem watcher. The buffer makes early events safe, not free:
        they are delayed until the loop exists.
        """
        with self._lock:
            self._loop = loop
        # Drain FIFO; pop under the lock, schedule OUTSIDE it (same lock
        # discipline as publish() — never run scheduling/user code while
        # holding the bus lock). Each entry is popped exactly once, so a
        # buffered event can never be replayed.
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

    def publish(self, event: str, **kwargs: Any) -> None:
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

        The loop check and the buffer append happen inside ONE lock
        acquisition: reading ``self._loop`` outside the lock would race
        set_loop() and could strand the event in the buffer forever (see
        the module docstring). The actual scheduling call still happens
        OUTSIDE the lock.

        Error isolation: each dispatch is wrapped in its own try/except —
        a failing subscriber is logged and never crashes the bus or
        skips later subscribers.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, ()))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    with self._lock:
                        loop = self._loop
                        if loop is None:
                            # Startup window: no loop yet — buffer, never
                            # drop, never call the coroutine directly. The
                            # append shares the critical section with the
                            # loop check, so set_loop()'s drain (which sets
                            # _loop first, under this lock) cannot miss it.
                            self._buffer.append((handler, dict(kwargs)))
                    if loop is not None:
                        future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
                        future.add_done_callback(_log_future_exception)
                else:
                    handler(**kwargs)
            except Exception:
                logger.exception(
                    "handler %r failed for event %r — continuing", handler, event
                )
