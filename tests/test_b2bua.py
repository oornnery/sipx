"""Tests for sipx.contrib.B2BUA and AsyncB2BUA."""

from __future__ import annotations

from unittest.mock import MagicMock

from sipx.contrib._b2bua import B2BUA, AsyncB2BUA
from sipx.models._message import Request, Response
from sipx._types import TransportAddress


# ============================================================================
# Helpers
# ============================================================================


def _make_request(method: str, call_id: str = "call1@test") -> Request:
    return Request(
        method=method,
        uri="sip:bob@127.0.0.1",
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
            "From": "<sip:alice@127.0.0.1>;tag=abc",
            "To": "<sip:bob@127.0.0.1>",
            "Call-ID": call_id,
            "CSeq": f"1 {method}",
            "Content-Length": "0",
        },
    )


def _make_response(status: int, reason: str, request: Request | None = None) -> Response:
    resp = Response(
        status_code=status,
        reason_phrase=reason,
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest",
            "From": "<sip:alice@127.0.0.1>;tag=abc",
            "To": "<sip:bob@127.0.0.1>;tag=def",
            "Call-ID": "call1@test",
            "CSeq": "1 INVITE",
            "Content-Length": "0",
        },
    )
    resp.request = request
    return resp


def _mock_server():
    """Return a mock SIPServer that records registered handlers."""
    server = MagicMock()
    server._handlers: dict = {}

    def register_handler(method, fn):
        server._handlers[method] = fn

    server.register_handler.side_effect = register_handler
    return server


def _mock_client():
    return MagicMock()


SOURCE = TransportAddress(host="127.0.0.1", port=5060)


# ============================================================================
# B2BUA construction
# ============================================================================


class TestB2BUAInit:
    def test_registers_invite_handler(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert "INVITE" in server._handlers

    def test_registers_bye_handler(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert "BYE" in server._handlers

    def test_registers_cancel_handler(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert "CANCEL" in server._handlers

    def test_initial_active_calls_zero(self):
        server = _mock_server()
        client = _mock_client()
        b2b = B2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert b2b.active_calls == 0

    def test_repr(self):
        server = _mock_server()
        client = _mock_client()
        b2b = B2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert "B2BUA" in repr(b2b)
        assert "sip:pbx@127.0.0.1" in repr(b2b)


# ============================================================================
# INVITE bridging
# ============================================================================


class TestB2BUAInvite:
    def _setup(self, b_status=200, b_reason="OK"):
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(b_status, b_reason, request=invite_req)
        client.invite.return_value = b_resp
        client.ack.return_value = None
        b2b = B2BUA(server, client, target="sip:pbx@127.0.0.1")
        return b2b, server, client, invite_req

    def test_invite_calls_client_invite(self):
        b2b, server, client, req = self._setup()
        handler = server._handlers["INVITE"]
        handler(req, SOURCE)
        client.invite.assert_called_once()

    def test_invite_acks_b_leg(self):
        b2b, server, client, req = self._setup()
        handler = server._handlers["INVITE"]
        handler(req, SOURCE)
        client.ack.assert_called_once()

    def test_invite_returns_200_on_success(self):
        b2b, server, client, req = self._setup()
        handler = server._handlers["INVITE"]
        resp = handler(req, SOURCE)
        assert resp.status_code == 200

    def test_invite_stores_call(self):
        b2b, server, client, req = self._setup()
        handler = server._handlers["INVITE"]
        handler(req, SOURCE)
        assert "call1@test" in b2b._calls
        assert b2b.active_calls == 1

    def test_invite_fires_on_bridge_callback(self):
        bridge_calls = []
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(200, "OK", request=invite_req)
        client.invite.return_value = b_resp
        B2BUA(
            server, client,
            target="sip:pbx@127.0.0.1",
            on_bridge=lambda req, resp: bridge_calls.append((req, resp)),
        )
        handler = server._handlers["INVITE"]
        handler(invite_req, SOURCE)
        assert len(bridge_calls) == 1

    def test_invite_b_leg_rejected_returns_503(self):
        b2b, server, client, req = self._setup(b_status=503, b_reason="Service Unavailable")
        handler = server._handlers["INVITE"]
        resp = handler(req, SOURCE)
        assert resp.status_code == 503

    def test_invite_b_leg_busy_returns_486(self):
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(486, "Busy Here")
        client.invite.return_value = b_resp
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        handler = server._handlers["INVITE"]
        resp = handler(invite_req, SOURCE)
        assert resp.status_code == 486

    def test_invite_timeout_returns_503(self):
        server = _mock_server()
        client = _mock_client()
        client.invite.return_value = None  # timeout
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        req = _make_request("INVITE")
        handler = server._handlers["INVITE"]
        resp = handler(req, SOURCE)
        assert resp.status_code == 503


# ============================================================================
# BYE handling
# ============================================================================


class TestB2BUABye:
    def test_bye_terminates_b_leg(self):
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(200, "OK", request=invite_req)
        client.invite.return_value = b_resp
        client.bye.return_value = _make_response(200, "OK")
        b2b = B2BUA(server, client, target="sip:pbx@127.0.0.1")

        # Establish call
        server._handlers["INVITE"](invite_req, SOURCE)
        assert b2b.active_calls == 1

        # Tear down
        bye_req = _make_request("BYE")
        resp = server._handlers["BYE"](bye_req, SOURCE)
        assert resp.status_code == 200
        client.bye.assert_called_once()
        assert b2b.active_calls == 0

    def test_bye_removes_call_from_dict(self):
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(200, "OK", request=invite_req)
        client.invite.return_value = b_resp
        b2b = B2BUA(server, client, target="sip:pbx@127.0.0.1")
        server._handlers["INVITE"](invite_req, SOURCE)
        server._handlers["BYE"](_make_request("BYE"), SOURCE)
        assert "call1@test" not in b2b._calls

    def test_bye_fires_on_terminate_callback(self):
        terminated = []
        server = _mock_server()
        client = _mock_client()
        invite_req = _make_request("INVITE")
        b_resp = _make_response(200, "OK", request=invite_req)
        client.invite.return_value = b_resp
        B2BUA(
            server, client,
            target="sip:pbx@127.0.0.1",
            on_terminate=lambda cid: terminated.append(cid),
        )
        server._handlers["INVITE"](invite_req, SOURCE)
        server._handlers["BYE"](_make_request("BYE"), SOURCE)
        assert "call1@test" in terminated

    def test_bye_unknown_call_still_returns_200(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1")
        resp = server._handlers["BYE"](_make_request("BYE", call_id="unknown"), SOURCE)
        assert resp.status_code == 200


# ============================================================================
# Lifecycle
# ============================================================================


class TestB2BUALifecycle:
    def test_start_calls_server_start(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1").start()
        server.start.assert_called_once()

    def test_stop_calls_server_stop(self):
        server = _mock_server()
        client = _mock_client()
        B2BUA(server, client, target="sip:pbx@127.0.0.1").stop()
        server.stop.assert_called_once()

    def test_context_manager(self):
        server = _mock_server()
        client = _mock_client()
        with B2BUA(server, client, target="sip:pbx@127.0.0.1"):
            server.start.assert_called_once()
        server.stop.assert_called_once()


# ============================================================================
# AsyncB2BUA — construction only (async invocation tested via loopback)
# ============================================================================


class TestAsyncB2BUAInit:
    def test_registers_handlers(self):
        server = _mock_server()
        client = _mock_client()
        AsyncB2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert "INVITE" in server._handlers
        assert "BYE" in server._handlers
        assert "CANCEL" in server._handlers

    def test_initial_active_calls_zero(self):
        server = _mock_server()
        client = _mock_client()
        b2b = AsyncB2BUA(server, client, target="sip:pbx@127.0.0.1")
        assert b2b.active_calls == 0
