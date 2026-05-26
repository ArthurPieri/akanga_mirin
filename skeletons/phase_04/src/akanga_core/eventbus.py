"""EventBus — thread-safe publish/subscribe message bus.

The bus decouples components: the file watcher publishes events without
knowing which components handle them. Subscribers register independently.

Thread safety requirement: publish() is called from watchdog daemon threads
(non-asyncio). When an asyncio event loop is registered (via set_loop),
async subscribers must be scheduled using asyncio.run_coroutine_threadsafe().

Reference implementation: akanga_core/eventbus.py in the main repo.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Supports both sync and async subscribers. Async subscribers are
    dispatched via ``asyncio.run_coroutine_threadsafe`` when called from
    a non-asyncio thread (e.g. watchdog daemon thread).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """WHAT: Register the asyncio event loop for cross-thread dispatch.

        WHY: When publish() is called from a watchdog daemon thread, async
        subscriber coroutines must be scheduled onto the asyncio loop — they
        cannot be called directly from a non-asyncio thread.  Without this
        registration, async subscribers would silently be skipped or crash.

        HOW: Simply store the loop reference::

            self._loop = loop

        CRITICAL: This MUST be called before starting the filesystem watcher.
        If the watcher fires events before the loop is registered, async
        subscribers will be skipped, causing a startup race condition.

        The stored reference is later read inside publish() to decide
        whether to use ``asyncio.run_coroutine_threadsafe`` or a direct call.

        Args:
            loop: The running asyncio event loop (typically obtained via
                  ``asyncio.get_running_loop()`` inside an async context).
        """
        raise NotImplementedError(
            "Store the loop reference: self._loop = loop"
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

           a. If ``asyncio.iscoroutinefunction(handler)`` is True **and**
              ``self._loop`` is set and running::

                asyncio.run_coroutine_threadsafe(handler(**kwargs), self._loop)

           b. Otherwise call ``handler(**kwargs)`` directly (synchronous path).

        4. Wrap **each individual handler call** in its own ``try/except``.
           On exception: ``logger.exception(...)`` — **never re-raise**.
           Subscriber errors must not crash the bus or skip later subscribers.

        Args:
            event:  String event name, e.g. ``"file_changed"``.
            **kwargs: Arbitrary keyword arguments forwarded to each handler.
        """
        raise NotImplementedError(
            "Snapshot handlers under lock, release lock, then dispatch to each. "
            "Use run_coroutine_threadsafe for async handlers when self._loop is set. "
            "Catch all exceptions per handler — error isolation is the key invariant."
        )
