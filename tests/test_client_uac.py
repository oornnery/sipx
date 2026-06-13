"""Tests for AsyncClient UAC methods (invite, register, message, options, subscribe)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio

from sipx.client import (
    AsyncClient,
    _new_branch,
    _new_call_id,
    _new_tag,
    _parse_remote,
    _parse_response,
)
from sipx.config import ClientConfig
from sipx.exceptions import TimeoutError as SipTimeoutError
from sipx.models import Request
from sipx.protocol.auth import AuthFlow


from sipx.wire import extract_branch_from_via


class MockTransport:
    """Mock transport for testing UAC methods."""

    def __init__(self):
        self.transport_type = "udp"
        self.sent_data: list[tuple[bytes, tuple[str, int]]] = []
        self._response_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._last_remote: tuple[str, int] = ("127.0.0.1", 5060)
        self._closed = False

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        self.sent_data.append((data, remote))
        self._last_remote = remote

    async def receive(self):
        while not self._closed:
            try:
                data = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
                yield data, self._last_remote
                await asyncio.sleep(0.01)
            except asyncio.TimeoutError:
                continue

    async def close(self) -> None:
        self._closed = True

    @property
    def local_address(self) -> tuple[str, int]:
        return ("127.0.0.1", 5060)

    def add_response(
        self,
        status_code: int,
        reason: str,
        headers: dict | None = None,
        body: bytes | None = None,
        *,
        branch: str = "z9hG4bKtest",
    ):
        """Add a response to be returned by the mock transport."""
        header_lines = []
        merged = dict(headers or {})
        merged.setdefault("Via", f"SIP/2.0/UDP 127.0.0.1:5060;branch={branch}")
        for name, value in merged.items():
            if isinstance(value, list):
                for v in value:
                    header_lines.append(f"{name}: {v}")
            else:
                header_lines.append(f"{name}: {value}")

        response_text = f"SIP/2.0 {status_code} {reason}\r\n"
        response_text += "\r\n".join(header_lines)
        response_text += "\r\n\r\n"
        if body:
            response_text += body.decode("utf-8") if isinstance(body, bytes) else body

        self._response_queue.put_nowait(response_text.encode("utf-8"))


def _branch_from_sent(sent: bytes, *, fallback: str = "z9hG4bKtest") -> str:
    for line in sent.decode("utf-8", errors="replace").split("\r\n"):
        if line.lower().startswith("via:"):
            branch = extract_branch_from_via(line[4:].strip())
            if branch:
                return branch
    return fallback


def make_response(
    status_code: int,
    reason: str,
    call_id: str,
    cseq: str,
    headers: dict | None = None,
    body: bytes | None = None,
    *,
    branch: str = "z9hG4bKtest",
) -> bytes:
    """Build a raw SIP response for testing."""
    header_lines = [
        f"Call-ID: {call_id}",
        f"CSeq: {cseq}",
        f"Via: SIP/2.0/UDP 127.0.0.1:5060;branch={branch}",
        "From: <sip:user@example.com>;tag=abc123",
        "To: <sip:bob@example.com>;tag=def456",
    ]
    if headers:
        for name, value in headers.items():
            if isinstance(value, list):
                for v in value:
                    header_lines.append(f"{name}: {v}")
            else:
                header_lines.append(f"{name}: {value}")

    response_text = f"SIP/2.0 {status_code} {reason}\r\n"
    response_text += "\r\n".join(header_lines)
    response_text += "\r\n\r\n"
    if body:
        response_text += body.decode("utf-8") if isinstance(body, bytes) else body

    return response_text.encode("utf-8")


@pytest_asyncio.fixture
async def mock_transport():
    """Create a mock transport for testing."""
    return MockTransport()


@pytest_asyncio.fixture
async def client_with_mock(mock_transport):
    """Create an AsyncClient with a mock transport."""
    config = ClientConfig(local_host="127.0.0.1", local_port=5060, timeout=5.0)
    client = AsyncClient(config=config)
    client._transport = mock_transport
    client._closed = False
    with patch("sipx.client._new_branch", return_value="z9hG4bKtest"):
        client._receive_task = asyncio.create_task(client._receive_loop())
        yield client
    await client.aclose()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_new_call_id_generates_unique_values(self):
        """_new_call_id must generate unique Call-IDs."""
        id1 = _new_call_id()
        id2 = _new_call_id()
        assert id1 != id2
        assert len(id1) > 0

    def test_new_tag_generates_unique_values(self):
        """_new_tag must generate unique tags."""
        tag1 = _new_tag()
        tag2 = _new_tag()
        assert tag1 != tag2
        assert len(tag1) == 8

    def test_new_branch_starts_with_magic_cookie(self):
        """_new_branch must start with z9hG4bK per RFC 3261."""
        branch = _new_branch()
        assert branch.startswith("z9hG4bK")
        assert len(branch) > 7

    def test_parse_remote_with_simple_uri(self):
        """_parse_remote must parse simple SIP URIs."""
        host, port = _parse_remote("sip:bob@example.com")
        assert host == "example.com"
        assert port == 5060

    def test_parse_remote_with_port(self):
        """_parse_remote must parse URIs with explicit port."""
        host, port = _parse_remote("sip:bob@example.com:5080")
        assert host == "example.com"
        assert port == 5080

    def test_parse_remote_with_sips(self):
        """_parse_remote must handle SIPS URIs."""
        host, port = _parse_remote("sips:bob@example.com")
        assert host == "example.com"
        assert port == 5060

    def test_parse_response_basic(self):
        """_parse_response must parse basic SIP responses."""
        request = Request(method="OPTIONS", uri="sip:bob@example.com", headers={})
        data = b"SIP/2.0 200 OK\r\nVia: SIP/2.0/UDP 127.0.0.1:5060\r\n\r\n"
        response = _parse_response(data, request)
        assert response.status_code == 200
        assert response.reason == "OK"
        assert "Via" in response.headers


class TestUACMethods:
    """Tests for UAC methods."""

    @pytest.mark.asyncio
    async def test_options_method_exists(self, client_with_mock):
        """AsyncClient must have an options method."""
        assert hasattr(client_with_mock, "options")
        assert callable(client_with_mock.options)
        await client_with_mock.aclose()

    @pytest.mark.asyncio
    async def test_invite_method_exists(self, client_with_mock):
        """AsyncClient must have an invite method."""
        assert hasattr(client_with_mock, "invite")
        assert callable(client_with_mock.invite)
        await client_with_mock.aclose()

    @pytest.mark.asyncio
    async def test_register_method_exists(self, client_with_mock):
        """AsyncClient must have a register method."""
        assert hasattr(client_with_mock, "register")
        assert callable(client_with_mock.register)
        await client_with_mock.aclose()

    @pytest.mark.asyncio
    async def test_message_method_exists(self, client_with_mock):
        """AsyncClient must have a message method."""
        assert hasattr(client_with_mock, "message")
        assert callable(client_with_mock.message)
        await client_with_mock.aclose()

    @pytest.mark.asyncio
    async def test_subscribe_method_exists(self, client_with_mock):
        """AsyncClient must have a subscribe method."""
        assert hasattr(client_with_mock, "subscribe")
        assert callable(client_with_mock.subscribe)
        await client_with_mock.aclose()

    @pytest.mark.asyncio
    async def test_options_sends_request(self, client_with_mock, mock_transport):
        """options() must send an OPTIONS request."""
        call_id = "test-call-id-options"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.options("sip:bob@example.com")

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"OPTIONS sip:bob@example.com SIP/2.0" in sent_data

    @pytest.mark.asyncio
    async def test_invite_sends_request(self, client_with_mock, mock_transport):
        """invite() must send an INVITE request."""
        call_id = "test-call-id-invite"
        mock_transport.add_response(
            200,
            "OK",
            {
                "Call-ID": call_id,
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@127.0.0.1>",
            },
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.invite("sip:bob@example.com")

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"INVITE sip:bob@example.com SIP/2.0" in sent_data

    @pytest.mark.asyncio
    async def test_register_sends_request(self, client_with_mock, mock_transport):
        """register() must send a REGISTER request."""
        call_id = "test-call-id-register"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 REGISTER"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.register("sip:example.com")

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"REGISTER sip:example.com SIP/2.0" in sent_data

    @pytest.mark.asyncio
    async def test_message_sends_request_with_body(
        self, client_with_mock, mock_transport
    ):
        """message() must send a MESSAGE request with body."""
        call_id = "test-call-id-message"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message(
                "sip:bob@example.com", "Hello, World!"
            )

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"MESSAGE sip:bob@example.com SIP/2.0" in sent_data
        assert b"Hello, World!" in sent_data

    @pytest.mark.asyncio
    async def test_subscribe_sends_request_with_event(
        self, client_with_mock, mock_transport
    ):
        """subscribe() must send a SUBSCRIBE request with Event header."""
        call_id = "test-call-id-subscribe"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 SUBSCRIBE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.subscribe(
                "sip:bob@example.com", event="presence"
            )

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"SUBSCRIBE sip:bob@example.com SIP/2.0" in sent_data
        assert b"Event: presence" in sent_data


class TestGenericRequest:
    """Tests for the generic request() method."""

    @pytest.mark.asyncio
    async def test_request_sends_arbitrary_method(
        self, client_with_mock, mock_transport
    ):
        """request() must send a request with the given method."""
        call_id = "test-generic-info"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 INFO"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.request(
                "INFO", "sip:bob@example.com", body=b"Signal=1"
            )

        assert response.status_code == 200
        sent_data = mock_transport.sent_data[0][0]
        assert b"INFO sip:bob@example.com SIP/2.0" in sent_data
        assert b"Signal=1" in sent_data

    @pytest.mark.asyncio
    async def test_request_uppercases_method(self, client_with_mock, mock_transport):
        """request() must normalize the method to uppercase."""
        call_id = "test-generic-lower"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.request("options", "sip:bob@example.com")

        assert response.status_code == 200
        assert b"OPTIONS sip:bob@example.com SIP/2.0" in mock_transport.sent_data[0][0]


class TestAckAndBye:
    """Tests for in-dialog ACK and BYE."""

    async def _establish_dialog(self, client, mock_transport, call_id: str) -> None:
        mock_transport.add_response(
            200,
            "OK",
            {
                "Call-ID": call_id,
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@127.0.0.1:5070>",
                "From": "<sip:alice@example.com>;tag=abc123",
                "To": "<sip:bob@example.com>;tag=def456",
            },
        )
        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client.invite("sip:bob@example.com")
        assert response.status_code == 200
        assert client.dialog(call_id) is not None

    @pytest.mark.asyncio
    async def test_ack_sends_in_dialog_request(self, client_with_mock, mock_transport):
        """ack() must send an ACK to the dialog remote target."""
        call_id = "test-ack"
        await self._establish_dialog(client_with_mock, mock_transport, call_id)

        await client_with_mock.ack(call_id)

        sent_data, remote = mock_transport.sent_data[-1]
        assert sent_data.startswith(b"ACK sip:bob@127.0.0.1:5070 SIP/2.0")
        assert remote == ("127.0.0.1", 5070)
        assert b"CSeq: 1 ACK" in sent_data
        assert f"Call-ID: {call_id}".encode() in sent_data
        assert b"tag=def456" in sent_data

    @pytest.mark.asyncio
    async def test_bye_terminates_dialog(self, client_with_mock, mock_transport):
        """bye() must send a BYE, wait for 200, and drop the dialog."""
        call_id = "test-bye"
        await self._establish_dialog(client_with_mock, mock_transport, call_id)

        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "2 BYE"},
        )
        response = await client_with_mock.bye(call_id)

        assert response.status_code == 200
        sent_data = mock_transport.sent_data[-1][0]
        assert sent_data.startswith(b"BYE sip:bob@127.0.0.1:5070 SIP/2.0")
        assert b"CSeq: 2 BYE" in sent_data
        assert client_with_mock.dialog(call_id) is None

    @pytest.mark.asyncio
    async def test_ack_without_dialog_raises(self, client_with_mock):
        """ack() must raise ProtocolError when no dialog is tracked."""
        from sipx.exceptions import ProtocolError

        with pytest.raises(ProtocolError):
            await client_with_mock.ack("missing-call-id")

    @pytest.mark.asyncio
    async def test_bye_without_dialog_raises(self, client_with_mock):
        """bye() must raise ProtocolError when no dialog is tracked."""
        from sipx.exceptions import ProtocolError

        with pytest.raises(ProtocolError):
            await client_with_mock.bye("missing-call-id")


class TestTransactionManagement:
    """Tests for transaction management."""

    @pytest.mark.asyncio
    async def test_transaction_created_for_request(
        self, client_with_mock, mock_transport
    ):
        """UAC methods must create ClientTransaction for state tracking."""
        call_id = "test-transaction"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.options("sip:bob@example.com")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_provisional_response_triggers_hook(
        self, client_with_mock, mock_transport
    ):
        """Provisional responses (1xx) must trigger provisional hooks."""
        call_id = "test-provisional"
        provisional_called = []

        async def provisional_hook(response):
            provisional_called.append(response.status_code)

        client_with_mock._event_hooks["provisional"] = [provisional_hook]

        mock_transport.add_response(
            180,
            "Ringing",
            {"Call-ID": call_id, "CSeq": "1 INVITE"},
        )
        mock_transport.add_response(
            200,
            "OK",
            {
                "Call-ID": call_id,
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@127.0.0.1>",
            },
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.invite("sip:bob@example.com")

        assert response.status_code == 200
        assert 180 in provisional_called
        assert [r.status_code for r in response.history] == [180]
        assert response.history[0].request is not None

    @pytest.mark.asyncio
    async def test_history_collects_multiple_provisionals(
        self, client_with_mock, mock_transport
    ):
        """The final response must carry every provisional in arrival order."""
        call_id = "test-history-prov"
        for status, reason in ((100, "Trying"), (180, "Ringing"), (183, "Progress")):
            mock_transport.add_response(
                status, reason, {"Call-ID": call_id, "CSeq": "1 INVITE"}
            )
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 INVITE", "Contact": "<sip:bob@127.0.0.1>"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.invite("sip:bob@example.com")

        assert response.status_code == 200
        assert [r.status_code for r in response.history] == [100, 180, 183]
        assert all(r.request is not None for r in response.history)

    @pytest.mark.asyncio
    async def test_rejects_forged_response_wrong_branch(
        self, client_with_mock, mock_transport
    ):
        """Responses with a mismatched Via branch must be ignored."""
        call_id = "test-forged-branch"
        client_with_mock._config = client_with_mock._config.merge(timeout=0.2)
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
            branch="z9hG4bKwrong",
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            with pytest.raises(SipTimeoutError):
                await client_with_mock.options("sip:bob@example.com")


class TestRportAndAck:
    """Tests for RFC 3581 rport and RFC 3261 §17.1.1.3 non-2xx ACK."""

    @pytest.mark.asyncio
    async def test_outgoing_via_includes_rport(self, client_with_mock, mock_transport):
        """UDP requests must carry an rport parameter on the Via header."""
        call_id = "test-rport"
        mock_transport.add_response(
            200, "OK", {"Call-ID": call_id, "CSeq": "1 OPTIONS"}
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            await client_with_mock.options("sip:bob@example.com")

        sent = mock_transport.sent_data[0][0]
        via_line = next(
            line
            for line in sent.decode().split("\r\n")
            if line.lower().startswith("via:")
        )
        assert ";rport" in via_line

    @pytest.mark.asyncio
    async def test_rport_disabled_omits_parameter(self, mock_transport):
        """With rport disabled, the Via must not include rport."""
        config = ClientConfig(
            local_host="127.0.0.1", local_port=5060, timeout=5.0, rport=False
        )
        client = AsyncClient(config=config)
        client._transport = mock_transport
        client._closed = False
        client._receive_task = asyncio.create_task(client._receive_loop())

        call_id = "test-no-rport"
        mock_transport.add_response(
            200, "OK", {"Call-ID": call_id, "CSeq": "1 OPTIONS"}
        )
        with (
            patch("sipx.client._new_call_id", return_value=call_id),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
        ):
            await client.options("sip:bob@example.com")

        sent = mock_transport.sent_data[0][0]
        via_line = next(
            line
            for line in sent.decode().split("\r\n")
            if line.lower().startswith("via:")
        )
        assert ";rport" not in via_line
        await client.aclose()

    @pytest.mark.asyncio
    async def test_learns_public_address_from_via(
        self, client_with_mock, mock_transport
    ):
        """received/rport echoed by the server must populate learned_address."""
        call_id = "test-learn"
        mock_transport.add_response(
            200,
            "OK",
            {
                "Call-ID": call_id,
                "CSeq": "1 OPTIONS",
                "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest"
                ";received=203.0.113.5;rport=44444",
            },
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            await client_with_mock.options("sip:bob@example.com")

        assert client_with_mock.learned_address == ("203.0.113.5", 44444)

    @pytest.mark.asyncio
    async def test_invite_non_2xx_sends_ack(self, client_with_mock, mock_transport):
        """A non-2xx INVITE final response must be auto-ACKed on the same branch."""
        call_id = "test-fail-ack"
        mock_transport.add_response(
            486,
            "Busy Here",
            {
                "Call-ID": call_id,
                "CSeq": "1 INVITE",
                "To": "<sip:bob@example.com>;tag=busy99",
            },
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.invite("sip:bob@example.com")

        assert response.status_code == 486
        assert call_id not in client_with_mock._dialogs
        ack = mock_transport.sent_data[-1][0]
        assert ack.startswith(b"ACK sip:bob@example.com SIP/2.0")
        assert b"CSeq: 1 ACK" in ack
        assert b"tag=busy99" in ack
        assert b"branch=z9hG4bKtest" in ack

    @pytest.mark.asyncio
    async def test_cancel_sends_matching_cancel(self, client_with_mock, mock_transport):
        """cancel() must send a CANCEL matching the pending INVITE branch/CSeq."""
        call_id = "test-cancel"
        mock_transport.add_response(
            100, "Trying", {"Call-ID": call_id, "CSeq": "1 INVITE"}
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            invite_task = asyncio.create_task(
                client_with_mock.invite("sip:bob@example.com")
            )
            for _ in range(100):
                if call_id in client_with_mock._pending_invites:
                    break
                await asyncio.sleep(0.01)

            mock_transport.add_response(
                200, "OK", {"Call-ID": call_id, "CSeq": "1 CANCEL"}
            )
            cancel_response = await client_with_mock.cancel(call_id)

            mock_transport.add_response(
                487,
                "Request Terminated",
                {
                    "Call-ID": call_id,
                    "CSeq": "1 INVITE",
                    "To": "<sip:bob@example.com>;tag=term1",
                },
            )
            invite_response = await invite_task

        assert cancel_response.status_code == 200
        assert invite_response.status_code == 487
        cancels = [d for d, _ in mock_transport.sent_data if d.startswith(b"CANCEL")]
        assert cancels
        assert b"CSeq: 1 CANCEL" in cancels[0]
        assert b"branch=z9hG4bKtest" in cancels[0]

    @pytest.mark.asyncio
    async def test_cancel_without_pending_invite_raises(self, client_with_mock):
        """cancel() must raise ProtocolError when no INVITE is pending."""
        from sipx.exceptions import ProtocolError

        with pytest.raises(ProtocolError):
            await client_with_mock.cancel("missing")


class TestDialogManagement:
    """Tests for dialog management."""

    @pytest.mark.asyncio
    async def test_dialog_created_on_invite_success(
        self, client_with_mock, mock_transport
    ):
        """INVITE with 2xx response must create a Dialog."""
        call_id = "test-dialog"
        mock_transport.add_response(
            200,
            "OK",
            {
                "Call-ID": call_id,
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@127.0.0.1>",
                "From": "<sip:alice@example.com>;tag=abc123",
                "To": "<sip:bob@example.com>;tag=def456",
            },
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.invite("sip:bob@example.com")

        assert response.status_code == 200
        assert call_id in client_with_mock._dialogs


class TestAuthFlow:
    """Tests for authentication flow integration."""

    @pytest.mark.asyncio
    async def test_auth_flow_handles_401(self, mock_transport):
        """AuthFlow must handle 401 Unauthorized challenges."""
        config = ClientConfig(local_host="127.0.0.1", local_port=5060, timeout=5.0)
        auth = AuthFlow(username="alice", password="secret")
        client = AsyncClient(config=config, auth=auth)
        client._transport = mock_transport
        client._closed = False
        client._receive_task = asyncio.create_task(client._receive_loop())

        call_id = "test-auth-401"
        mock_transport.add_response(
            401,
            "Unauthorized",
            {
                "Call-ID": call_id,
                "CSeq": "1 REGISTER",
                "WWW-Authenticate": 'Digest realm="example.com", nonce="abc123"',
            },
        )
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 REGISTER"},
        )

        with (
            patch("sipx.client._new_call_id", return_value=call_id),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
        ):
            response = await client.register("sip:example.com")

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 2
        assert any(r.status_code == 401 for r in response.history)
        challenge = next(r for r in response.history if r.status_code == 401)
        assert challenge.request is not None
        await client.aclose()

    @pytest.mark.asyncio
    async def test_auth_flow_handles_407(self, mock_transport):
        """AuthFlow must handle 407 Proxy Authentication Required."""
        config = ClientConfig(local_host="127.0.0.1", local_port=5060, timeout=5.0)
        auth = AuthFlow(username="alice", password="secret")
        client = AsyncClient(config=config, auth=auth)
        client._transport = mock_transport
        client._closed = False
        client._receive_task = asyncio.create_task(client._receive_loop())

        call_id = "test-auth-407"
        mock_transport.add_response(
            407,
            "Proxy Authentication Required",
            {
                "Call-ID": call_id,
                "CSeq": "1 OPTIONS",
                "Proxy-Authenticate": 'Digest realm="proxy.example.com", nonce="xyz789"',
            },
        )
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with (
            patch("sipx.client._new_call_id", return_value=call_id),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
        ):
            response = await client.options("sip:bob@example.com")

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 2
        await client.aclose()


class TestEventHooks:
    """Tests for event hooks integration."""

    @pytest.mark.asyncio
    async def test_request_hook_called(self, client_with_mock, mock_transport):
        """Request hooks must be called before sending."""
        call_id = "test-request-hook"
        request_hook_called = []

        def request_hook(request):
            request_hook_called.append(request.method)

        client_with_mock._event_hooks["request"] = [request_hook]

        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            await client_with_mock.options("sip:bob@example.com")

        assert "OPTIONS" in request_hook_called

    @pytest.mark.asyncio
    async def test_response_hook_called(self, client_with_mock, mock_transport):
        """Response hooks must be called after receiving."""
        call_id = "test-response-hook"
        response_hook_called = []

        def response_hook(response):
            response_hook_called.append(response.status_code)

        client_with_mock._event_hooks["response"] = [response_hook]

        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 OPTIONS"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            await client_with_mock.options("sip:bob@example.com")

        assert 200 in response_hook_called


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_raises_sip_timeout_error(
        self, client_with_mock, mock_transport
    ):
        """Timeout must raise SipTimeoutError."""
        client_with_mock._config.timeout = 0.1

        with pytest.raises(SipTimeoutError):
            await client_with_mock.options("sip:bob@example.com")


class TestRetransmission:
    """Tests for RFC 3261 §17 client retransmission."""

    @pytest.mark.asyncio
    async def test_retransmits_until_response(self, mock_transport):
        """A non-INVITE request must be retransmitted while no response arrives."""
        config = ClientConfig(local_host="127.0.0.1", local_port=5060, timeout=5.0)
        client = AsyncClient(config=config)
        client._transport = mock_transport
        client._closed = False

        call_id = "test-retransmit"
        with (
            patch("sipx.client._new_call_id", return_value=call_id),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
            patch("sipx.client.T1", 0.05),
            patch("sipx.client.T2", 0.2),
        ):
            client._receive_task = asyncio.create_task(client._receive_loop())

            async def respond_late():
                await asyncio.sleep(0.18)
                mock_transport.add_response(
                    200, "OK", {"Call-ID": call_id, "CSeq": "1 OPTIONS"}
                )

            asyncio.create_task(respond_late())
            response = await client.options("sip:bob@example.com")

        assert response.status_code == 200
        # initial send + at least one retransmission before the late response
        assert len(mock_transport.sent_data) >= 2
        await client.aclose()

    @pytest.mark.asyncio
    async def test_no_retransmit_when_disabled(self, mock_transport):
        """With retransmit disabled, only the initial request is sent."""
        config = ClientConfig(
            local_host="127.0.0.1", local_port=5060, timeout=0.2, retransmit=False
        )
        client = AsyncClient(config=config)
        client._transport = mock_transport
        client._closed = False

        with (
            patch("sipx.client._new_call_id", return_value="no-rtx"),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
            patch("sipx.client.T1", 0.05),
        ):
            client._receive_task = asyncio.create_task(client._receive_loop())
            with pytest.raises(SipTimeoutError):
                await client.options("sip:bob@example.com")

        assert len(mock_transport.sent_data) == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_invite_stops_retransmit_after_provisional(self, mock_transport):
        """INVITE must stop retransmitting once a provisional response arrives."""
        config = ClientConfig(local_host="127.0.0.1", local_port=5060, timeout=5.0)
        client = AsyncClient(config=config)
        client._transport = mock_transport
        client._closed = False

        call_id = "test-inv-rtx"
        with (
            patch("sipx.client._new_call_id", return_value=call_id),
            patch("sipx.client._new_branch", return_value="z9hG4bKtest"),
            patch("sipx.client.T1", 0.05),
        ):
            client._receive_task = asyncio.create_task(client._receive_loop())
            mock_transport.add_response(
                100, "Trying", {"Call-ID": call_id, "CSeq": "1 INVITE"}
            )

            async def respond_final():
                await asyncio.sleep(0.4)
                mock_transport.add_response(
                    200,
                    "OK",
                    {
                        "Call-ID": call_id,
                        "CSeq": "1 INVITE",
                        "Contact": "<sip:bob@127.0.0.1>",
                    },
                )

            asyncio.create_task(respond_final())
            response = await client.invite("sip:bob@example.com")

        assert response.status_code == 200
        # Only the initial INVITE is sent; no retransmissions after the 100.
        invites = [d for d, _ in mock_transport.sent_data if d.startswith(b"INVITE")]
        assert len(invites) == 1
        await client.aclose()
