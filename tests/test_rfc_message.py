"""Tests for RFC 3428 MESSAGE method."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio

from sipx.client import AsyncClient
from sipx.config import ClientConfig
from sipx.exceptions import ProtocolError
from sipx.models import Request


class MockTransport:
    """Mock transport for testing MESSAGE method."""

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
    ):
        """Add a response to be returned by the mock transport."""
        header_lines = []
        merged = dict(headers or {})
        merged.setdefault("Via", "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest")
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


class TestMessageMethod:
    """Tests for MESSAGE method per RFC 3428."""

    @pytest.mark.asyncio
    async def test_message_method_exists(self, client_with_mock):
        """AsyncClient must have a message method."""
        assert hasattr(client_with_mock, "message")
        assert callable(client_with_mock.message)

    @pytest.mark.asyncio
    async def test_message_with_text_plain_body(self, client_with_mock, mock_transport):
        """MESSAGE with str body must set text/plain Content-Type."""
        call_id = "test-message-plain"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message(
                "sip:bob@example.com", "Hello, Bob!"
            )

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"MESSAGE sip:bob@example.com SIP/2.0" in sent_data
        assert b"Content-Type: text/plain" in sent_data
        assert b"Hello, Bob!" in sent_data

    @pytest.mark.asyncio
    async def test_message_with_text_html_body(self, client_with_mock, mock_transport):
        """MESSAGE with text/html body must set correct Content-Type."""
        call_id = "test-message-html"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        html_body = b"<html><body>Hello</body></html>"
        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message(
                "sip:bob@example.com",
                html_body,
                **{"Content-Type": "text/html"},
            )

        assert response.status_code == 200
        assert len(mock_transport.sent_data) == 1
        sent_data = mock_transport.sent_data[0][0]
        assert b"Content-Type: text/html" in sent_data
        assert b"<html><body>Hello</body></html>" in sent_data

    @pytest.mark.asyncio
    async def test_message_content_length_header(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE must include correct Content-Length header."""
        call_id = "test-message-length"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        body = "Hello, World!"
        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message("sip:bob@example.com", body)

        assert response.status_code == 200
        sent_data = mock_transport.sent_data[0][0]
        expected_length = str(len(body.encode("utf-8")))
        assert f"Content-Length: {expected_length}".encode() in sent_data

    @pytest.mark.asyncio
    async def test_message_4xx_raises_protocol_error(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE with 4xx response must raise ProtocolError."""
        call_id = "test-message-4xx"
        mock_transport.add_response(
            404,
            "Not Found",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            with pytest.raises(ProtocolError) as exc_info:
                await client_with_mock.message("sip:bob@example.com", "Hello")

        assert "404" in str(exc_info.value)
        assert "Not Found" in str(exc_info.value)
        assert exc_info.value.rfc_ref == "RFC 3428"

    @pytest.mark.asyncio
    async def test_message_5xx_raises_protocol_error(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE with 5xx response must raise ProtocolError."""
        call_id = "test-message-5xx"
        mock_transport.add_response(
            500,
            "Server Internal Error",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            with pytest.raises(ProtocolError) as exc_info:
                await client_with_mock.message("sip:bob@example.com", "Hello")

        assert "500" in str(exc_info.value)
        assert "Server Internal Error" in str(exc_info.value)
        assert exc_info.value.rfc_ref == "RFC 3428"

    @pytest.mark.asyncio
    async def test_message_with_bytes_body_and_explicit_content_type(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE with bytes body and explicit Content-Type must use provided type."""
        call_id = "test-message-bytes"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        body = b"\x00\x01\x02\x03"
        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message(
                "sip:bob@example.com",
                body,
                **{"Content-Type": "application/octet-stream"},
            )

        assert response.status_code == 200
        sent_data = mock_transport.sent_data[0][0]
        assert b"Content-Type: application/octet-stream" in sent_data
        assert b"\x00\x01\x02\x03" in sent_data

    @pytest.mark.asyncio
    async def test_message_with_empty_body(self, client_with_mock, mock_transport):
        """MESSAGE with empty body must set Content-Length to 0."""
        call_id = "test-message-empty"
        mock_transport.add_response(
            200,
            "OK",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            response = await client_with_mock.message("sip:bob@example.com", "")

        assert response.status_code == 200
        sent_data = mock_transport.sent_data[0][0]
        assert b"Content-Length: 0" in sent_data

    @pytest.mark.asyncio
    async def test_message_480_raises_protocol_error(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE with 480 Temporarily Unavailable must raise ProtocolError."""
        call_id = "test-message-480"
        mock_transport.add_response(
            480,
            "Temporarily Unavailable",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            with pytest.raises(ProtocolError) as exc_info:
                await client_with_mock.message("sip:bob@example.com", "Hello")

        assert "480" in str(exc_info.value)
        assert exc_info.value.details["status_code"] == 480

    @pytest.mark.asyncio
    async def test_message_503_raises_protocol_error(
        self, client_with_mock, mock_transport
    ):
        """MESSAGE with 503 Service Unavailable must raise ProtocolError."""
        call_id = "test-message-503"
        mock_transport.add_response(
            503,
            "Service Unavailable",
            {"Call-ID": call_id, "CSeq": "1 MESSAGE"},
        )

        with patch("sipx.client._new_call_id", return_value=call_id):
            with pytest.raises(ProtocolError) as exc_info:
                await client_with_mock.message("sip:bob@example.com", "Hello")

        assert "503" in str(exc_info.value)
        assert exc_info.value.details["reason"] == "Service Unavailable"


class TestMessageRequestModel:
    """Tests for MESSAGE request model behavior."""

    def test_message_request_with_content_type(self):
        """Request model must preserve Content-Type for MESSAGE."""
        req = Request(
            method="MESSAGE",
            uri="sip:bob@example.com",
            headers={"Content-Type": "text/plain"},
            body=b"Hello, Bob!",
        )
        assert req.headers["Content-Type"] == "text/plain"
        assert req.body == b"Hello, Bob!"

    def test_message_request_with_html_body(self):
        """Request model must preserve HTML body for MESSAGE."""
        html_body = b"<html><body>Hello</body></html>"
        req = Request(
            method="MESSAGE",
            uri="sip:bob@example.com",
            headers={"Content-Type": "text/html"},
            body=html_body,
        )
        assert req.headers["Content-Type"] == "text/html"
        assert req.body == html_body
