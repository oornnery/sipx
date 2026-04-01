"""Tests for RFC 3515 REFER / refer_and_wait + ReferSubscription."""

from __future__ import annotations

from unittest.mock import patch

from sipx.client import Client
from sipx.models._message import Request, Response
from sipx._types import TransportAddress
from sipx.transports._base import BaseTransport
from sipx.session import ReferSubscription, SubscriptionState


# ============================================================================
# Helpers
# ============================================================================


class MockTransport(BaseTransport):
    def __init__(self, config=None):
        super().__init__(config)
        self.sent: list[tuple[bytes, TransportAddress]] = []
        self._queue: list[bytes] = []

    def send(self, data, destination):
        self.sent.append((data, destination))

    def receive(self, timeout=None):
        if not self._queue:
            raise TimeoutError("No queued responses")
        return self._queue.pop(0), TransportAddress(host="127.0.0.1", port=5060)

    def handle_request(self, request, destination):
        raise NotImplementedError

    def close(self):
        self._closed = True

    def _get_protocol_name(self):
        return "UDP"


def _make_response(status: int, reason: str) -> bytes:
    return Response(
        status_code=status,
        reason_phrase=reason,
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
            "From": "<sip:alice@127.0.0.1>;tag=abc",
            "To": "<sip:bob@127.0.0.1>;tag=def",
            "Call-ID": "testcall@127.0.0.1",
            "CSeq": "1 REFER",
            "Content-Length": "0",
        },
    ).to_bytes()


def _make_notify(sipfrag: str, sub_state: str = "active") -> bytes:
    body = sipfrag.encode()
    return Request(
        method="NOTIFY",
        uri="sip:alice@127.0.0.1",
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKnotify",
            "From": "<sip:bob@127.0.0.1>;tag=def",
            "To": "<sip:alice@127.0.0.1>;tag=abc",
            "Call-ID": "testcall@127.0.0.1",
            "CSeq": "1 NOTIFY",
            "Event": "refer",
            "Subscription-State": sub_state,
            "Content-Type": "message/sipfrag",
            "Content-Length": str(len(body)),
        },
        content=sipfrag,
    ).to_bytes()


# ============================================================================
# ReferSubscription
# ============================================================================


class TestReferSubscription:
    def test_initial_state(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        assert sub.state == SubscriptionState.ACTIVE
        assert sub.final_status is None
        assert not sub.is_complete

    def test_provisional_sipfrag_not_complete(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        done = sub.update("SIP/2.0 180 Ringing\r\n")
        assert done is False
        assert not sub.is_complete

    def test_final_2xx_sipfrag_completes(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        done = sub.update("SIP/2.0 200 OK\r\n")
        assert done is True
        assert sub.is_complete
        assert sub.final_status == 200
        assert sub.succeeded

    def test_final_4xx_sipfrag_completes(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        done = sub.update("SIP/2.0 486 Busy Here\r\n")
        assert done is True
        assert sub.is_complete
        assert sub.final_status == 486
        assert not sub.succeeded

    def test_terminated_sub_state_completes(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        done = sub.update("SIP/2.0 180 Ringing\r\n", subscription_state="terminated")
        assert done is True
        assert sub.is_complete

    def test_sipfrag_history_accumulated(self):
        sub = ReferSubscription(refer_to="sip:carol@pbx.com")
        sub.update("SIP/2.0 100 Trying\r\n")
        sub.update("SIP/2.0 180 Ringing\r\n")
        sub.update("SIP/2.0 200 OK\r\n")
        assert len(sub.sipfrag_history) == 3


# ============================================================================
# Client.refer()
# ============================================================================


class TestReferMethod:
    @patch("sipx.client._sync._create_sync_transport")
    def test_refer_sends_refer_to_header(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))

        client = Client()
        client.refer("sip:bob@127.0.0.1", refer_to="sip:carol@127.0.0.1")

        refer_bytes = transport.sent[0][0]
        assert b"REFER" in refer_bytes.split(b"\r\n")[0]
        assert b"Refer-To:" in refer_bytes or b"Refer-To" in refer_bytes

    @patch("sipx.client._sync._create_sync_transport")
    def test_refer_returns_202(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))

        client = Client()
        r = client.refer("sip:bob@127.0.0.1", refer_to="sip:carol@127.0.0.1")
        assert r is not None
        assert r.status_code == 202


# ============================================================================
# Client.refer_and_wait()
# ============================================================================


class TestReferAndWait:
    @patch("sipx.client._sync._create_sync_transport")
    def test_returns_notify_on_success(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))
        transport._queue.append(_make_notify("SIP/2.0 200 OK\r\n", "terminated"))

        client = Client()
        result = client.refer_and_wait(
            "sip:bob@127.0.0.1",
            refer_to="sip:carol@127.0.0.1",
        )

        assert result is not None
        assert isinstance(result, Request)
        assert result.method == "NOTIFY"

    @patch("sipx.client._sync._create_sync_transport")
    def test_notify_auto_200_acked(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))
        transport._queue.append(_make_notify("SIP/2.0 200 OK\r\n", "terminated"))

        client = Client()
        client.refer_and_wait("sip:bob@127.0.0.1", refer_to="sip:carol@127.0.0.1")

        # Last sent message should be 200 OK to NOTIFY
        last_sent = transport.sent[-1][0]
        assert b"SIP/2.0 200 OK" in last_sent

    @patch("sipx.client._sync._create_sync_transport")
    def test_stops_on_provisional_then_final(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))
        transport._queue.append(_make_notify("SIP/2.0 180 Ringing\r\n", "active"))
        transport._queue.append(_make_notify("SIP/2.0 200 OK\r\n", "terminated"))

        client = Client()
        result = client.refer_and_wait(
            "sip:bob@127.0.0.1",
            refer_to="sip:carol@127.0.0.1",
        )

        assert result is not None
        assert "200" in result.content_text

    @patch("sipx.client._sync._create_sync_transport")
    def test_returns_none_on_refer_rejection(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(403, "Forbidden"))

        client = Client()
        # refer() returns 403, refer_and_wait returns it directly (not None)
        result = client.refer_and_wait(
            "sip:bob@127.0.0.1",
            refer_to="sip:carol@127.0.0.1",
        )

        assert result is not None
        assert result.status_code == 403

    @patch("sipx.client._sync._create_sync_transport")
    def test_returns_none_on_timeout(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(202, "Accepted"))
        # No NOTIFY queued → receive() always raises TimeoutError

        client = Client()
        result = client.refer_and_wait(
            "sip:bob@127.0.0.1",
            refer_to="sip:carol@127.0.0.1",
            timeout=0.05,  # very short timeout
        )

        assert result is None
