"""Core test fixtures for sipx test suite."""

from __future__ import annotations

from collections import deque
from typing import Optional, Tuple

import pytest

from sipx.models._body import SDPBody
from sipx.models._message import Request, Response
from sipx.transports._base import BaseTransport
from sipx._types import TransportAddress, TransportConfig


# ============================================================================
# MockTransport
# ============================================================================


class MockTransport(BaseTransport):
    """In-memory transport that captures sent data and returns queued responses.

    Usage:
        transport = MockTransport()
        transport.queue_response(b"SIP/2.0 200 OK\\r\\n...")
        response = transport.handle_request(request, dest)
        assert transport.sent[0] == (request.to_bytes(), dest)
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        super().__init__(config)
        self.sent: list[tuple[bytes, TransportAddress]] = []
        self._response_queue: deque[bytes] = deque()
        self._source_address = TransportAddress(
            host="127.0.0.1", port=5060, protocol="UDP"
        )

    def queue_response(self, data: bytes) -> None:
        """Enqueue raw response bytes to be returned by receive()."""
        self._response_queue.append(data)

    def send(self, data: bytes, destination: TransportAddress) -> None:
        """Append sent data to self.sent."""
        self.sent.append((data, destination))

    def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """Return next queued response or raise TimeoutError."""
        if not self._response_queue:
            raise TimeoutError("No queued responses available")
        return self._response_queue.popleft(), self._source_address

    def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """Send the request bytes then receive and parse the response."""
        from sipx.models._message import MessageParser

        self.send(request.to_bytes(), destination)
        data, _ = self.receive()
        parsed = MessageParser.parse(data)
        if not isinstance(parsed, Response):
            raise ValueError(f"Expected Response, got {type(parsed).__name__}")
        parsed.request = request
        return parsed

    def close(self) -> None:
        """Mark transport as closed."""
        self._closed = True

    def _get_protocol_name(self) -> str:
        return "UDP"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_transport() -> MockTransport:
    """Return a fresh MockTransport instance."""
    return MockTransport()


@pytest.fixture
def make_request():
    """Factory fixture that builds SIP Request objects.

    Usage:
        req = make_request("INVITE", "sip:bob@example.com",
                           Via="SIP/2.0/UDP 10.0.0.1;branch=z9hG4bK776")
    """

    def _factory(method: str, uri: str, **headers) -> Request:
        return Request(method=method, uri=uri, headers=headers if headers else None)

    return _factory


@pytest.fixture
def make_response():
    """Factory fixture that builds SIP Response objects.

    Usage:
        resp = make_response(200, Via="SIP/2.0/UDP 10.0.0.1;branch=z9hG4bK776")
    """

    def _factory(status_code: int, **headers) -> Response:
        return Response(status_code=status_code, headers=headers if headers else None)

    return _factory


@pytest.fixture
def make_sdp_offer():
    """Factory fixture that returns a basic audio SDPBody offer.

    Usage:
        sdp = make_sdp_offer()
    """

    def _factory() -> SDPBody:
        return SDPBody.create_offer(
            session_name="Test Call",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="1000",
            media_specs=[
                {
                    "media": "audio",
                    "port": 49170,
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                    ],
                }
            ],
        )

    return _factory
