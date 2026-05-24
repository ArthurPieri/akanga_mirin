"""
Phase 04 — EventBus Tests

Tests for eventbus.py:
    EventBus.subscribe(event, handler)
    EventBus.unsubscribe(event, handler)
    EventBus.publish(event, **kwargs)
    EventBus.set_loop(loop)
"""
import pytest


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
