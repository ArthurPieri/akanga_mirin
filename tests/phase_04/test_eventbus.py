"""
Phase 04 — EventBus Tests

Tests for eventbus.py:
    EventBus.subscribe(event, handler)
    EventBus.unsubscribe(event, handler)
    EventBus.publish(event, **kwargs)
    EventBus.set_loop(loop)
"""
import asyncio
import threading
import time


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    """Poll *predicate* until it is truthy or *timeout* seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


class TestSubscribeAndPublish:
    def test_subscribe_and_publish(self, event_bus) -> None:
        """A subscribed handler is called when the matching event is published."""
        calls = []
        event_bus.subscribe("node_created", lambda **kw: calls.append(kw))
        event_bus.publish("node_created")
        assert len(calls) == 1

    def test_publish_passes_kwargs(self, event_bus) -> None:
        """Keyword arguments passed to publish() reach the handler unchanged."""
        received = {}

        def handler(**kwargs):
            received.update(kwargs)

        event_bus.subscribe("file_changed", handler)
        event_bus.publish("file_changed", path="/vault/a.md", extra=42)
        assert received.get("path") == "/vault/a.md"
        assert received.get("extra") == 42

    def test_multiple_subscribers(self, event_bus) -> None:
        """Two subscribers to the same event are both called on publish."""
        calls_a = []
        calls_b = []
        event_bus.subscribe("node_updated", lambda **kw: calls_a.append(kw))
        event_bus.subscribe("node_updated", lambda **kw: calls_b.append(kw))
        event_bus.publish("node_updated", node_id="abc")
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_multiple_events(self, event_bus) -> None:
        """Subscribing to 'event_a' does not trigger on 'event_b' publish."""
        calls_a = []
        calls_b = []
        event_bus.subscribe("event_a", lambda **kw: calls_a.append(kw))
        event_bus.subscribe("event_b", lambda **kw: calls_b.append(kw))

        event_bus.publish("event_a")
        assert len(calls_a) == 1, "event_a handler must fire"
        assert len(calls_b) == 0, "event_b handler must NOT fire on event_a publish"


class TestUnsubscribe:
    def test_unsubscribe(self, event_bus) -> None:
        """After unsubscribe the handler is no longer called on publish."""
        calls = []

        def handler(**kwargs):
            calls.append(kwargs)

        event_bus.subscribe("node_deleted", handler)
        event_bus.unsubscribe("node_deleted", handler)
        event_bus.publish("node_deleted")
        assert len(calls) == 0

    def test_unsubscribe_nonexistent_handler_is_safe(self, event_bus) -> None:
        """Unsubscribing a handler that was never registered must not raise."""
        def orphan(**kwargs):
            pass  # never subscribed

        # Must complete without raising any exception
        event_bus.unsubscribe("some_event", orphan)


class TestErrorIsolation:
    def test_subscriber_error_isolation(self, event_bus) -> None:
        """A failing handler does not prevent other subscribers from firing."""
        calls = []

        def bad_handler(**kwargs):
            raise RuntimeError("intentional failure")

        def good_handler(**kwargs):
            calls.append(kwargs)

        event_bus.subscribe("risky_event", bad_handler)
        event_bus.subscribe("risky_event", good_handler)

        # publish() itself must not raise even though bad_handler fails
        event_bus.publish("risky_event")
        assert len(calls) == 1, "good_handler must still be called despite bad_handler failure"

    def test_no_subscribers_publish_is_safe(self, event_bus) -> None:
        """Publishing an event with no subscribers must not raise."""
        # Must complete without exception
        event_bus.publish("ghost_event", data="nothing")


class TestAsyncBridge:
    """The thread → event-loop bridge: the hard concurrency artifact of this phase."""

    def test_async_subscriber_receives_event_after_set_loop(self, event_bus) -> None:
        """publish() from a non-asyncio thread must schedule async subscribers on the loop.

        Verifies the run_coroutine_threadsafe bridge (doc Deliverable sketch):
        an async handler must run ON the event loop even when publish() is
        called from a plain thread (the watchdog daemon thread in real use).
        """
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            event_bus.set_loop(loop)

            called = []

            async def async_handler(**kwargs):
                called.append(kwargs)

            event_bus.subscribe("test_event", async_handler)
            event_bus.publish("test_event", source="main_thread")

            assert _wait_until(lambda: len(called) == 1), (
                "Async subscriber was never called after publish() from a "
                "non-asyncio thread.\n"
                "Bridge coroutine handlers with "
                "asyncio.run_coroutine_threadsafe(handler(**kwargs), self._loop) "
                "— calling the coroutine function directly only creates a "
                "coroutine object, it never runs."
            )
            assert called[0].get("source") == "main_thread", (
                f"kwargs must reach the async handler unchanged, got {called[0]!r}."
            )
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)
            loop.close()

    def test_publish_before_set_loop_buffers_events(self, event_bus) -> None:
        """Events published before set_loop() must be buffered, then delivered on set_loop.

        BUG-04 regression guard: the naive fallback ('if loop not set, call the
        handler directly') either crashes or silently drops async events during
        the startup window before the loop exists. The contract is: buffer the
        event and deliver it exactly once when set_loop() is called — assert
        delivery, not loss.
        """
        called = []

        async def async_handler(**kwargs):
            called.append(kwargs)

        event_bus.subscribe("early_event", async_handler)

        # Publish BEFORE any loop exists — must not raise, must not be lost.
        event_bus.publish("early_event", payload="published-before-loop")
        assert len(called) == 0, (
            "Async handler must NOT run synchronously when no loop is set — "
            "that is the BUG-04 race. Buffer the event until set_loop()."
        )

        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            event_bus.set_loop(loop)

            assert _wait_until(lambda: len(called) == 1), (
                "The event published before set_loop() was lost.\n"
                "EventBus must buffer pre-loop publishes and flush them via "
                "run_coroutine_threadsafe once set_loop(loop) is called — "
                "delivery, not loss, is the contract."
            )
            assert called[0].get("payload") == "published-before-loop", (
                f"Buffered event kwargs must be delivered unchanged, got {called[0]!r}."
            )

            # And it must be delivered exactly once — not replayed on later publishes.
            event_bus.publish("early_event", payload="second")
            assert _wait_until(lambda: len(called) >= 2), (
                "Post-set_loop publish must still be delivered normally."
            )
            time.sleep(0.2)  # allow any (incorrect) buffer replay to surface
            assert len(called) == 2, (
                f"Buffered events must be flushed exactly once, got {len(called)} calls.\n"
                "Clear the buffer after flushing it in set_loop()."
            )
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)
            loop.close()
