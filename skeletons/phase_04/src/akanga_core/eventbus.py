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

Reference implementation: akanga_core/eventbus.py in the main repo.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict, deque
from typing import Callable

logger = logging.getLogger(__name__)


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
        """WHAT: Register the asyncio event loop for cross-thread dispatch,
        then drain any async dispatches that were buffered before the loop
        existed.

        WHY: When publish() is called from a watchdog daemon thread, async
        subscriber coroutines must be scheduled onto the asyncio loop — they
        cannot be called directly from a non-asyncio thread. Events that
        fired before the loop was registered (the BUG-04 startup race) were
        buffered by publish(); draining them here is REQUIRED behaviour —
        a bare ``self._loop = loop`` loses those events.

        HOW:
        1. Store the loop reference: ``self._loop = loop``.
        2. Drain the buffer (FIFO) — under ``self._lock``, pop entries until
           the deque is empty; for each ``(handler, kwargs)`` pair::

               while True:
                   with self._lock:
                       if not self._buffer:
                           break
                       handler, kwargs = self._buffer.popleft()
                   fut = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
                   fut.add_done_callback(self._log_future_exception)

           (Schedule OUTSIDE the lock — same lock discipline as publish().
            ``_log_future_exception`` is whatever helper/lambda you use in
            publish() step 3a to log a Future's exception, e.g.
            ``lambda f: f.exception() and logger.error("async handler failed: %r", f.exception())``.)

        CRITICAL: Call this as early as possible in startup — BEFORE starting
        the filesystem watcher. The buffer makes early events safe, not free:
        they are delayed until the loop exists.

        Args:
            loop: The running asyncio event loop (typically obtained via
                  ``asyncio.get_running_loop()`` inside an async context).
        """
        raise NotImplementedError(
            "Store self._loop = loop, then drain self._buffer (FIFO, popleft under "
            "the lock) scheduling each (handler, kwargs) with "
            "asyncio.run_coroutine_threadsafe and attaching the exception-logging "
            "done-callback to each Future."
        )

    def subscribe(self, event: str, handler: Callable) -> None:
        """WHAT: Register a handler function for the named event.

        WHY: Decoupling — the publisher does not need to know who listens.
        Multiple independent components can subscribe to the same event
        (e.g. the indexer and the TUI both subscribe to ``file_changed``).

        HOW:
        1. Acquire ``self._lock`` (protects the shared ``_handlers`` dict).
        2. Append *handler* to ``self._handlers[event]``.
        3. Release the lock (use a ``with`` block so it is always released).

        Thread-safe: multiple threads may subscribe concurrently.

        Args:
            event:   String event name, e.g. ``"file_changed"``.
            handler: Callable (sync or async) invoked when the event fires.
        """
        raise NotImplementedError(
            "Acquire self._lock, then append handler to self._handlers[event]"
        )

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """WHAT: Remove a previously registered handler.

        WHY: Components must be able to clean up their subscriptions
        when they are destroyed — e.g. a TUI widget that goes away
        should not receive stale events and should not keep objects alive.

        HOW:
        1. Acquire ``self._lock``.
        2. If *event* is in ``self._handlers`` and *handler* is in the list,
           call ``list.remove(handler)``.
        3. It is safe to call this even if *handler* was never subscribed
           — do not raise in that case.

        Args:
            event:   String event name.
            handler: The exact callable object that was passed to subscribe().
        """
        raise NotImplementedError(
            "Acquire self._lock, remove handler from self._handlers[event] if present"
        )

    def publish(self, event: str, **kwargs) -> None:
        """WHAT: Dispatch an event to all registered handlers.

        WHY: The central coordination point — one publish() call reaches
        all subscribers regardless of whether they are sync or async, and
        regardless of which thread calls publish().

        HOW:
        1. Acquire ``self._lock`` to get a **snapshot** of the handler list
           for *event* (copy it so you can release the lock before calling
           any handler — calling a handler while holding the lock would
           deadlock if the handler tries to subscribe/unsubscribe).
        2. Release the lock.
        3. For each handler in the snapshot:

           a. Async handler (``asyncio.iscoroutinefunction(handler)``) and
              ``self._loop`` IS set::

                fut = asyncio.run_coroutine_threadsafe(handler(**kwargs), self._loop)
                fut.add_done_callback(
                    lambda f: f.exception()
                    and logger.error("async handler failed: %r", f.exception())
                )

              The done-callback is REQUIRED: without it the Future's
              exception is never retrieved and async handler errors vanish
              silently — violating the error-isolation invariant.

           b. Async handler and ``self._loop`` is NOT yet set — BUFFER it,
              do NOT call the coroutine function directly (calling it from a
              watchdog thread is exactly the BUG-04 race)::

                with self._lock:
                    self._buffer.append((handler, dict(kwargs)))

              set_loop() drains the buffer as soon as the loop is registered.

           c. Sync handler: call ``handler(**kwargs)`` directly. This direct
              call is the ONLY no-loop fallback — it applies to sync
              handlers exclusively.

        4. Wrap **each individual handler dispatch** in its own ``try/except``.
           On exception: ``logger.exception(...)`` — **never re-raise**.
           Subscriber errors must not crash the bus or skip later subscribers.

        Args:
            event:  String event name, e.g. ``"file_changed"``.
            **kwargs: Arbitrary keyword arguments forwarded to each handler.
        """
        raise NotImplementedError(
            "Snapshot handlers under lock, release lock, then dispatch to each. "
            "Async + loop set: run_coroutine_threadsafe + add_done_callback that "
            "logs Future exceptions. Async + no loop: append (handler, kwargs) to "
            "self._buffer — never call the coroutine directly. Sync: call directly. "
            "Catch all exceptions per handler — error isolation is the key invariant."
        )
