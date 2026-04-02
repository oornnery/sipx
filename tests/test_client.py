"""Tests for sipx._client module: Client (sync) interface tests.

Uses MockTransport from conftest.py to avoid real network calls.
"""

from __future__ import annotations

from unittest.mock import patch


from sipx.client import SIPClient
from sipx._events import Events, EventContext
from sipx.models._auth import Auth
from sipx.models._message import Request
from sipx._types import TransportAddress
from sipx.transports._base import BaseTransport


class MockTransport(BaseTransport):
    """Minimal mock transport for testing Client without network."""

    def __init__(self, config=None):
        super().__init__(config)
        self.sent = []
        self._response_queue = []

    def send(self, data, destination):
        self.sent.append((data, destination))

    def receive(self, timeout=None):
        if not self._response_queue:
            raise TimeoutError("No queued responses")
        return self._response_queue.pop(0), TransportAddress(
            host="127.0.0.1", port=5060
        )

    def handle_request(self, request, destination):
        raise NotImplementedError

    def close(self):
        self._closed = True

    def _get_protocol_name(self):
        return "UDP"


# ============================================================================
# Client creation
# ============================================================================


class TestClientCreation:
    @patch("sipx.client._sync._create_sync_transport")
    def test_defaults(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        assert client.config.local_host == "0.0.0.0"
        assert client.config.local_port == 5060
        assert client.transport_protocol == "UDP"
        assert client._events is None
        assert client._auth is None
        assert client._closed is False

    @patch("sipx.client._sync._create_sync_transport")
    def test_custom_params(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient(
            local_host="192.168.1.1",
            local_port=5080,
            transport="TCP",
        )
        assert client.config.local_host == "192.168.1.1"
        assert client.config.local_port == 5080
        assert client.transport_protocol == "TCP"

    @patch("sipx.client._sync._create_sync_transport")
    def test_with_events(self, mock_create):
        mock_create.return_value = MockTransport()
        ev = Events()
        client = SIPClient(events=ev)
        assert client._events is ev

    @patch("sipx.client._sync._create_sync_transport")
    def test_with_auth(self, mock_create):
        mock_create.return_value = MockTransport()
        creds = Auth.Digest("alice", "secret")
        client = SIPClient(auth=creds)
        assert client._auth is creds


# ============================================================================
# events property
# ============================================================================


class TestEventsProperty:
    @patch("sipx.client._sync._create_sync_transport")
    def test_get_events(self, mock_create):
        mock_create.return_value = MockTransport()
        ev = Events()
        client = SIPClient(events=ev)
        assert client.events is ev

    @patch("sipx.client._sync._create_sync_transport")
    def test_set_events(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        assert client.events is None
        ev = Events()
        client.events = ev
        assert client.events is ev

    @patch("sipx.client._sync._create_sync_transport")
    def test_set_events_to_none(self, mock_create):
        mock_create.return_value = MockTransport()
        ev = Events()
        client = SIPClient(events=ev)
        client.events = None
        assert client.events is None


# ============================================================================
# auth property
# ============================================================================


class TestAuthProperty:
    @patch("sipx.client._sync._create_sync_transport")
    def test_get_auth(self, mock_create):
        mock_create.return_value = MockTransport()
        creds = Auth.Digest("alice", "secret")
        client = SIPClient(auth=creds)
        assert client.auth is creds

    @patch("sipx.client._sync._create_sync_transport")
    def test_set_auth(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        assert client.auth is None
        creds = Auth.Digest("bob", "pass")
        client.auth = creds
        assert client.auth is creds


# ============================================================================
# Context manager
# ============================================================================


class TestClientContextManager:
    @patch("sipx.client._sync._create_sync_transport")
    def test_enter_returns_client(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        result = client.__enter__()
        assert result is client
        client.__exit__(None, None, None)

    @patch("sipx.client._sync._create_sync_transport")
    def test_exit_closes_transport(self, mock_create):
        mt = MockTransport()
        mock_create.return_value = mt
        client = SIPClient()
        client.__enter__()
        client.__exit__(None, None, None)
        assert client._closed is True

    @patch("sipx.client._sync._create_sync_transport")
    def test_with_statement(self, mock_create):
        mt = MockTransport()
        mock_create.return_value = mt
        with SIPClient() as client:
            assert isinstance(client, SIPClient)
            assert client._closed is False
        assert client._closed is True


class TestClientDecorators:
    @patch("sipx.client._sync._create_sync_transport")
    def test_invite_decorator_registers_response_handler(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()

        @client.invite(status=200)
        def on_invite_ok(response):
            return response

        assert client.events is not None
        assert len(client.events._handlers) == 1
        handler, methods, statuses = client.events._handlers[0]
        assert methods == ("INVITE",)
        assert statuses == (200,)
        assert getattr(handler, "_event_handler_options", {}).get("phase") == "response"

    @patch("sipx.client._sync._create_sync_transport")
    def test_client_on_phase_request_runs_in_request_pipeline(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        seen = []

        @client.message(phase="request")
        def on_message_request(request, context):
            seen.append((request.method, context.request is request))
            request.headers["X-Test"] = "1"
            return request

        req = Request(method="MESSAGE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        result = client.events._call_request_handlers(req, ctx)  # type: ignore[union-attr]
        assert seen == [("MESSAGE", True)]
        assert result.headers["X-Test"] == "1"

    @patch("sipx.client._sync._create_sync_transport")
    def test_client_response_handler_flexible_signature(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient()
        seen = []

        @client.invite(status=200)
        def on_invite_ok(response, context):
            seen.append((response.status_code, context.request.method))
            return response

        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = req.ok()
        ctx = EventContext(request=req, response=resp)
        result = client.events._call_response_handlers(resp, ctx)  # type: ignore[union-attr]
        assert result is resp
        assert seen == [(200, "INVITE")]


# ============================================================================
# _ensure_required_headers
# ============================================================================


class TestEnsureRequiredHeaders:
    def _make_client_with_mock(self):
        """Create a Client with injected MockTransport."""
        mt = MockTransport()
        with patch("sipx.client._sync._create_sync_transport", return_value=mt):
            client = SIPClient()
        client._transport = mt
        return client

    def test_adds_via(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "Via" in result.headers
        assert "SIP/2.0/UDP" in result.headers["Via"]
        assert "branch=" in result.headers["Via"]

    def test_adds_from(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "From" in result.headers
        assert "tag=" in result.headers["From"]

    def test_adds_to(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "To" in result.headers
        assert "sip:bob@example.com" in result.headers["To"]

    def test_adds_call_id(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "Call-ID" in result.headers
        assert "@" in result.headers["Call-ID"]

    def test_adds_cseq(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "CSeq" in result.headers
        assert "INVITE" in result.headers["CSeq"]

    def test_adds_max_forwards(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert result.headers["Max-Forwards"] == "70"

    def test_adds_content_length(self):
        client = self._make_client_with_mock()
        req = Request(method="INVITE", uri="sip:bob@example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        raw = result.to_bytes()
        assert b"Content-Length: 0" in raw

    def test_does_not_override_existing_via(self):
        client = self._make_client_with_mock()
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Via": "SIP/2.0/UDP custom;branch=z9hG4bKcustom"},
        )
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "custom" in result.headers["Via"]

    def test_does_not_override_existing_from(self):
        client = self._make_client_with_mock()
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"From": "<sip:custom@example.com>;tag=abc"},
        )
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert "custom@example.com" in result.headers["From"]

    def test_adds_user_agent_from_auth(self):
        client = self._make_client_with_mock()
        client._auth = Auth.Digest("alice", "secret", user_agent="TestAgent/1.0")
        req = Request(method="REGISTER", uri="sip:example.com", headers={})
        result = client._ensure_required_headers(req, "example.com", 5060)
        assert result.headers["User-Agent"] == "TestAgent/1.0"


# ============================================================================
# _extract_host_port
# ============================================================================


class TestExtractHostPort:
    def test_sip_uri(self):
        from sipx.client._base import _extract_host_port

        host, port = _extract_host_port("sip:bob@example.com")
        assert host == "example.com"
        assert port == 5060

    def test_sip_uri_with_port(self):
        """SipURI parser correctly extracts explicit port from SIP URI."""
        from sipx.client._base import _extract_host_port

        host, port = _extract_host_port("sip:bob@example.com:5080")
        assert host == "example.com"
        assert port == 5080

    def test_sips_uri(self):
        from sipx.client._base import _extract_host_port

        host, port = _extract_host_port("sips:bob@example.com")
        assert host == "example.com"
        assert port == 5061  # SIPS default per RFC 3261

    def test_bare_uri_gets_sip_prefix(self):
        from sipx.client._base import _extract_host_port

        host, port = _extract_host_port("bob@example.com")
        assert host == "example.com"


# ============================================================================
# _build_auth_header
# ============================================================================


class TestBuildAuthHeader:
    def test_generates_digest_header(self):
        from sipx.models._auth import DigestChallenge
        from sipx.client._base import _build_auth_header

        creds = Auth.Digest("alice", "secret")
        challenge = DigestChallenge(
            realm="example.com",
            nonce="abc123",
            algorithm="MD5",
        )
        header = _build_auth_header(challenge, creds, "REGISTER", "sip:example.com")
        assert header.startswith("Digest ")
        assert 'username="alice"' in header
        assert 'realm="example.com"' in header
        assert 'nonce="abc123"' in header


# ============================================================================
# Tuple auth conversion
# ============================================================================


class TestTupleAuth:
    @patch("sipx.client._sync._create_sync_transport")
    def test_tuple_auth_converts_to_credentials(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient(local_port=0)
        client.auth = ("alice", "secret")
        assert client.auth is not None
        assert client.auth.username == "alice"
        assert client.auth.password == "secret"
        client.close()

    @patch("sipx.client._sync._create_sync_transport")
    def test_auth_digest_still_works(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient(local_port=0)
        client.auth = Auth.Digest("alice", "secret")
        assert client.auth is not None
        assert client.auth.username == "alice"
        client.close()

    @patch("sipx.client._sync._create_sync_transport")
    def test_auto_auth_default_true(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient(local_port=0)
        assert client._auto_auth is True
        client.close()

    @patch("sipx.client._sync._create_sync_transport")
    def test_auto_auth_false(self, mock_create):
        mock_create.return_value = MockTransport()
        client = SIPClient(local_port=0, auto_auth=False)
        assert client._auto_auth is False
        client.close()


# ============================================================================
# SDPBody.audio() factory
# ============================================================================


class TestSDPAudioFactory:
    def test_sdp_audio_basic(self):
        from sipx.models._body import SDPBody

        sdp = SDPBody.audio(ip="10.0.0.1", port=8000)
        assert sdp.get_connection_address() == "10.0.0.1"
        ports = sdp.get_media_ports()
        assert ports["audio"] == 8000
        codecs = sdp.get_codecs_summary()
        assert "PCMU" in codecs.get("audio", [])
        assert "PCMA" in codecs.get("audio", [])

    def test_sdp_audio_custom_codecs(self):
        from sipx.models._body import SDPBody

        sdp = SDPBody.audio(ip="10.0.0.1", port=9000, codecs=["PCMU"])
        codecs = sdp.get_codecs_summary()
        assert "PCMU" in codecs.get("audio", [])

    def test_sdp_audio_default_session_name(self):
        from sipx.models._body import SDPBody

        sdp = SDPBody.audio(ip="10.0.0.1", port=8000)
        assert sdp.session_name == "sipx"
