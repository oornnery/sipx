"""Tests for RFC 3261 §19.3 INVITE forking support."""

from __future__ import annotations

from unittest.mock import patch

from sipx.client import Client
from sipx.client._base import ForkTracker, _extract_tag
from sipx.models._message import Response
from sipx._types import TransportAddress
from sipx.transports._base import BaseTransport


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


def _make_200(to_tag: str) -> bytes:
    resp = Response(
        status_code=200,
        reason_phrase="OK",
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
            "From": "<sip:alice@127.0.0.1>;tag=abc",
            "To": f"<sip:bob@127.0.0.1>;tag={to_tag}",
            "Call-ID": "testcall@127.0.0.1",
            "CSeq": "1 INVITE",
            "Content-Length": "0",
        },
    )
    return resp.to_bytes()


# ============================================================================
# _extract_tag
# ============================================================================


class TestExtractTag:
    def test_extracts_tag(self):
        assert _extract_tag("<sip:bob@host>;tag=xyz123") == "xyz123"

    def test_no_tag_returns_empty(self):
        assert _extract_tag("<sip:bob@host>") == ""

    def test_case_insensitive(self):
        assert _extract_tag("<sip:bob@host>;TAG=abc") == "abc"


# ============================================================================
# ForkTracker
# ============================================================================


class TestForkTracker:
    def _resp(self, tag: str) -> Response:
        return Response(
            status_code=200,
            reason_phrase="OK",
            headers={"To": f"<sip:bob@host>;tag={tag}", "Content-Length": "0"},
        )

    def test_first_response_added(self):
        ft = ForkTracker()
        assert ft.add(self._resp("tag1")) is True
        assert len(ft.responses) == 1

    def test_duplicate_tag_rejected(self):
        ft = ForkTracker()
        ft.add(self._resp("tag1"))
        assert ft.add(self._resp("tag1")) is False
        assert len(ft.responses) == 1

    def test_new_tag_accepted(self):
        ft = ForkTracker()
        ft.add(self._resp("tag1"))
        assert ft.add(self._resp("tag2")) is True
        assert len(ft.responses) == 2

    def test_best_is_first(self):
        ft = ForkTracker()
        r1 = self._resp("tag1")
        r2 = self._resp("tag2")
        ft.add(r1)
        ft.add(r2)
        assert ft.best is r1

    def test_extra_excludes_best(self):
        ft = ForkTracker()
        r1 = self._resp("tag1")
        r2 = self._resp("tag2")
        ft.add(r1)
        ft.add(r2)
        assert ft.extra == [r2]

    def test_empty_tracker(self):
        ft = ForkTracker()
        assert ft.best is None
        assert ft.extra == []


# ============================================================================
# Client: single 200 — no forking side-effects
# ============================================================================


class TestNoForking:
    @patch("sipx.client._sync._create_sync_transport")
    def test_returns_first_200(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_200("tag1"))

        client = Client()
        resp = client.invite("sip:bob@127.0.0.1")
        assert resp is not None
        assert resp.status_code == 200

    @patch("sipx.client._sync._create_sync_transport")
    def test_no_extra_bye_without_forking(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_200("tag1"))

        client = Client()
        client.invite("sip:bob@127.0.0.1")

        methods = [d.split(b"\r\n")[0].split()[0] for d, _ in transport.sent]
        assert b"BYE" not in methods


# ============================================================================
# Client: forked 200 OKs
# ============================================================================


class TestForkingClient:
    @patch("sipx.client._sync._create_sync_transport")
    def test_returns_first_fork(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        # Two 200s with different To-tags (forked branches)
        transport._queue.append(_make_200("tagA"))
        transport._queue.append(_make_200("tagB"))

        client = Client(fork_policy="first")
        resp = client.invite("sip:bob@127.0.0.1")

        assert resp is not None
        assert resp.status_code == 200
        assert "tagA" in resp.headers.get("To", "")

    @patch("sipx.client._sync._create_sync_transport")
    def test_extra_forked_leg_ack_and_bye_sent(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_200("tagA"))
        transport._queue.append(_make_200("tagB"))

        client = Client(fork_policy="first")
        client.invite("sip:bob@127.0.0.1")

        methods = [d.split(b"\r\n")[0].split()[0] for d, _ in transport.sent]
        # INVITE + ACK (for tagB) + BYE (for tagB)
        assert b"ACK" in methods
        assert b"BYE" in methods
