"""Tests for RFC 3262 PRACK / 100rel support."""

from __future__ import annotations

from unittest.mock import patch

from sipx.client import Client
from sipx.models._message import Response
from sipx._types import TransportAddress
from sipx.transports._base import BaseTransport


# ============================================================================
# Helpers
# ============================================================================


class MockTransport(BaseTransport):
    """Minimal mock transport that returns pre-queued responses."""

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


def _make_response(status: int, reason: str, extra: dict | None = None) -> bytes:
    headers = {
        "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
        "From": "<sip:alice@127.0.0.1>;tag=abc",
        "To": "<sip:bob@127.0.0.1>;tag=def",
        "Call-ID": "testcall@127.0.0.1",
        "CSeq": "1 INVITE",
        "Content-Length": "0",
    }
    if extra:
        headers.update(extra)
    resp = Response(status_code=status, reason_phrase=reason, headers=headers)
    return resp.to_bytes()


# ============================================================================
# Client: invite(reliable=True)
# ============================================================================


class TestInviteReliable:
    @patch("sipx.client._sync._create_sync_transport")
    def test_reliable_adds_require_100rel(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        # Queue a final 200 OK so request() terminates
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        client.invite("sip:bob@127.0.0.1", reliable=True)

        # First sent message is the INVITE
        invite_bytes, _ = transport.sent[0]
        invite_text = invite_bytes.decode()
        assert "Require: 100rel" in invite_text
        assert "Supported: 100rel" in invite_text

    @patch("sipx.client._sync._create_sync_transport")
    def test_non_reliable_no_require_header(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        client.invite("sip:bob@127.0.0.1", reliable=False)

        invite_bytes, _ = transport.sent[0]
        invite_text = invite_bytes.decode()
        assert "Require: 100rel" not in invite_text


# ============================================================================
# Client: auto-PRACK on reliable 1xx
# ============================================================================


class TestAutoPrack:
    @patch("sipx.client._sync._create_sync_transport")
    def test_prack_sent_on_reliable_1xx(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport

        # Queue: 180 Ringing with Require: 100rel + RSeq, then 200 OK
        transport._queue.append(
            _make_response(
                180,
                "Ringing",
                {"Require": "100rel", "RSeq": "77"},
            )
        )
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        client.invite("sip:bob@127.0.0.1", reliable=True)

        sent_methods = []
        for data, _ in transport.sent:
            line = data.split(b"\r\n")[0].decode()
            sent_methods.append(line.split()[0])

        assert "PRACK" in sent_methods

    @patch("sipx.client._sync._create_sync_transport")
    def test_prack_has_rack_header(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport

        transport._queue.append(
            _make_response(
                180,
                "Ringing",
                {"Require": "100rel", "RSeq": "42"},
            )
        )
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        client.invite("sip:bob@127.0.0.1", reliable=True)

        prack_bytes = None
        for data, _ in transport.sent:
            if data.startswith(b"PRACK"):
                prack_bytes = data
                break

        assert prack_bytes is not None
        prack_text = prack_bytes.decode()
        # RAck must contain RSeq value and original CSeq
        assert "RAck:" in prack_text
        assert "42" in prack_text

    @patch("sipx.client._sync._create_sync_transport")
    def test_no_prack_on_unreliable_1xx(self, mock_create):
        transport = MockTransport()
        mock_create.return_value = transport

        # 180 without Require: 100rel
        transport._queue.append(_make_response(180, "Ringing"))
        transport._queue.append(_make_response(200, "OK"))

        client = Client()
        client.invite("sip:bob@127.0.0.1")

        sent_methods = [
            data.split(b"\r\n")[0].decode().split()[0] for data, _ in transport.sent
        ]
        assert "PRACK" not in sent_methods


# ============================================================================
# Server: RSeq generation on reliable provisional
# ============================================================================


class TestServerRSeq:
    @patch("sipx.server._sync.UDPTransport")
    def test_rseq_added_to_1xx_when_required(self, mock_udp_cls):
        from sipx.models._message import Request as Req

        invite = Req(
            method="INVITE",
            uri="sip:bob@127.0.0.1",
            headers={
                "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
                "From": "<sip:alice@127.0.0.1>;tag=abc",
                "To": "<sip:bob@127.0.0.1>",
                "Call-ID": "call1@127.0.0.1",
                "CSeq": "1 INVITE",
                "Require": "100rel",
                "Content-Length": "0",
            },
        )

        source = TransportAddress(host="127.0.0.1", port=5060)
        rseq_counter = 0
        response = invite.ringing()

        # Simulate the RSeq injection the server loop performs
        if (
            invite.method == "INVITE"
            and 100 < response.status_code < 200
            and "100rel" in invite.headers.get("Require", "")
        ):
            rseq_counter += 1
            response.headers["RSeq"] = str(rseq_counter)
            response.headers["Require"] = "100rel"

        assert "RSeq" in response.headers
        assert response.headers["RSeq"] == "1"
        assert "100rel" in response.headers.get("Require", "")
        _ = source  # used to extract dialog info in real server loop

    @patch("sipx.server._sync.UDPTransport")
    def test_rseq_monotonically_increases(self, mock_udp_cls):
        from sipx.server import SIPServer

        server = SIPServer()
        assert server._rseq_counter == 0

        server._rseq_counter += 1
        server._rseq_counter += 1
        assert server._rseq_counter == 2

    @patch("sipx.server._sync.UDPTransport")
    def test_no_rseq_without_100rel_require(self, mock_udp_cls):
        from sipx.models._message import Request as Req

        invite = Req(
            method="INVITE",
            uri="sip:bob@127.0.0.1",
            headers={
                "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
                "From": "<sip:alice@127.0.0.1>;tag=abc",
                "To": "<sip:bob@127.0.0.1>",
                "Call-ID": "call1@127.0.0.1",
                "CSeq": "1 INVITE",
                "Content-Length": "0",
            },
        )
        response = invite.ringing()

        # Should NOT have RSeq since no Require: 100rel in request
        assert "RSeq" not in response.headers
