"""Tests for sipx._subscription (Subscription, SubscriptionState)."""

from __future__ import annotations

from unittest.mock import MagicMock

from sipx._subscription import Subscription, SubscriptionState
from sipx._models._message import Response


class TestSubscriptionState:
    def test_enum_values(self):
        assert SubscriptionState.INIT is not None
        assert SubscriptionState.PENDING is not None
        assert SubscriptionState.ACTIVE is not None
        assert SubscriptionState.TERMINATED is not None

    def test_enum_members_are_distinct(self):
        states = [
            SubscriptionState.INIT,
            SubscriptionState.PENDING,
            SubscriptionState.ACTIVE,
            SubscriptionState.TERMINATED,
        ]
        assert len(set(states)) == 4


class TestSubscriptionHandleNotify:
    def _make_sub(self, on_notify=None) -> Subscription:
        """Create a Subscription with a mock client (not used for handle_notify)."""
        return Subscription(
            client=None,  # type: ignore[arg-type]
            uri="sip:alice@example.com",
            event="presence",
            on_notify=on_notify,
        )

    def test_handle_notify_active(self):
        sub = self._make_sub()
        sub.handle_notify("<presence/>", "active")
        assert sub.state == SubscriptionState.ACTIVE

    def test_handle_notify_terminated(self):
        sub = self._make_sub()
        sub.state = SubscriptionState.ACTIVE
        sub.handle_notify("<presence/>", "terminated")
        assert sub.state == SubscriptionState.TERMINATED

    def test_handle_notify_pending(self):
        sub = self._make_sub()
        sub.handle_notify("<presence/>", "pending")
        assert sub.state == SubscriptionState.PENDING

    def test_handle_notify_stores_body(self):
        sub = self._make_sub()
        sub.handle_notify("<presence>online</presence>", "active")
        assert sub.last_notify_body == "<presence>online</presence>"

    def test_handle_notify_calls_callback(self):
        received = []
        sub = self._make_sub(on_notify=lambda body: received.append(body))
        sub.handle_notify("test-body", "active")
        assert received == ["test-body"]

    def test_handle_notify_no_state_change_on_empty(self):
        sub = self._make_sub()
        sub.state = SubscriptionState.ACTIVE
        sub.handle_notify("body", "")
        # No state keyword matched, state unchanged
        assert sub.state == SubscriptionState.ACTIVE

    def test_handle_notify_case_insensitive(self):
        sub = self._make_sub()
        sub.handle_notify("body", "Active;expires=3600")
        assert sub.state == SubscriptionState.ACTIVE


class TestSubscriptionIsActive:
    def _make_sub(self) -> Subscription:
        return Subscription(
            client=None,  # type: ignore[arg-type]
            uri="sip:alice@example.com",
            event="presence",
        )

    def test_is_active_when_active(self):
        sub = self._make_sub()
        sub.state = SubscriptionState.ACTIVE
        assert sub.is_active is True

    def test_is_active_when_pending(self):
        sub = self._make_sub()
        sub.state = SubscriptionState.PENDING
        assert sub.is_active is True

    def test_is_active_when_terminated(self):
        sub = self._make_sub()
        sub.state = SubscriptionState.TERMINATED
        assert sub.is_active is False

    def test_is_active_when_init(self):
        sub = self._make_sub()
        assert sub.state == SubscriptionState.INIT
        assert sub.is_active is False


class TestSubscriptionSubscribe:
    def _make_mock_client(self, status_code: int) -> MagicMock:
        client = MagicMock()
        resp = Response(status_code=status_code)
        client.subscribe.return_value = resp
        return client

    def test_subscribe_200_sets_active(self):
        client = self._make_mock_client(200)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        r = sub.subscribe(expires=3600)
        assert sub.state == SubscriptionState.ACTIVE
        assert r is not None
        assert r.status_code == 200
        sub._cancel_refresh()

    def test_subscribe_202_sets_pending(self):
        client = self._make_mock_client(202)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.subscribe()
        assert sub.state == SubscriptionState.PENDING
        sub._cancel_refresh()

    def test_subscribe_failure_sets_terminated(self):
        client = self._make_mock_client(403)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.subscribe()
        assert sub.state == SubscriptionState.TERMINATED

    def test_subscribe_none_response_sets_terminated(self):
        client = MagicMock()
        client.subscribe.return_value = None
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.subscribe()
        assert sub.state == SubscriptionState.TERMINATED

    def test_subscribe_custom_expires(self):
        client = self._make_mock_client(200)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.subscribe(expires=600)
        assert sub.expires == 600
        sub._cancel_refresh()


class TestSubscriptionUnsubscribe:
    def test_unsubscribe_sends_expires_zero(self):
        client = MagicMock()
        client.subscribe.return_value = Response(status_code=200)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.state = SubscriptionState.ACTIVE
        sub.unsubscribe()
        assert sub.state == SubscriptionState.TERMINATED
        client.subscribe.assert_called_once_with(
            uri="sip:alice@example.com",
            event="presence",
            expires=0,
        )


class TestSubscriptionRefresh:
    def test_refresh_success_increments_count(self):
        client = MagicMock()
        client.subscribe.return_value = Response(status_code=200)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.state = SubscriptionState.ACTIVE
        sub.refresh()
        assert sub.refresh_count == 1
        sub._cancel_refresh()

    def test_refresh_failure_terminates(self):
        client = MagicMock()
        client.subscribe.return_value = Response(status_code=408)
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.state = SubscriptionState.ACTIVE
        sub.refresh()
        assert sub.state == SubscriptionState.TERMINATED

    def test_do_refresh_skips_when_terminated(self):
        client = MagicMock()
        sub = Subscription(client=client, uri="sip:alice@example.com", event="presence")
        sub.state = SubscriptionState.TERMINATED
        sub._do_refresh()
        client.subscribe.assert_not_called()
