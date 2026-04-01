"""
WebSocket transport for SIP protocol (RFC 7118).

Provides both synchronous and asynchronous WebSocket transports
for SIP over WebSocket communication using the "sip" subprotocol.

Requires the optional ``websockets`` package.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Optional, Tuple

from .._types import TransportAddress, TransportConfig
from ._base import AsyncBaseTransport, BaseTransport
from .._utils import logger

_log = logger.getChild("transport.ws")

if TYPE_CHECKING:
    from ..models._message import Request, Response


def _import_websockets():
    """Lazy import websockets library."""
    try:
        import websockets

        return websockets
    except ImportError:
        raise ImportError(
            "WebSocket transport requires the 'websockets' package. "
            "Install it with: pip install websockets"
        ) from None


def _import_websockets_sync():
    """Lazy import websockets synchronous client."""
    try:
        from websockets.sync.client import connect

        return connect
    except ImportError:
        raise ImportError(
            "WebSocket transport requires the 'websockets' package. "
            "Install it with: pip install websockets"
        ) from None


class WSTransport(BaseTransport):
    """
    Synchronous WebSocket transport for SIP (RFC 7118).

    SIP messages are sent as WebSocket text frames using the "sip" subprotocol.
    Uses ``websockets.sync.client.connect()`` for the synchronous connection.
    """

    def __init__(
        self,
        config: Optional[TransportConfig] = None,
        uri: str = "ws://localhost:8080",
    ) -> None:
        super().__init__(config)
        self._uri = uri
        self._ws = None
        self._lock = threading.Lock()

    def _ensure_connected(self) -> None:
        """
        Lazily connect to the WebSocket endpoint.

        Uses ``websockets.sync.client.connect`` with the "sip" subprotocol.
        """
        if self._ws is not None and not self._closed:
            return

        _log.info("WS connecting to %s", self._uri)
        connect = _import_websockets_sync()
        self._ws = connect(
            self._uri,
            subprotocols=["sip"],
            open_timeout=self.config.connect_timeout,
        )
        _log.info("WS connected")

    def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send a SIP request over WebSocket and receive the response.

        Args:
            request: The SIP request to send.
            destination: Target address (used for addressing context).

        Returns:
            Parsed SIP response.
        """
        from ..models._message import MessageParser

        with self._lock:
            self._ensure_connected()
            data = request.to_bytes()
            self._ws.send(data.decode("utf-8"))
            raw = self._ws.recv(timeout=self.config.read_timeout)
            message = MessageParser.parse(
                raw if isinstance(raw, bytes) else raw.encode("utf-8")
            )
            return message  # type: ignore[return-value]

    def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes as a WebSocket text frame.

        Args:
            data: Raw SIP message bytes.
            destination: Target address (used for addressing context).
        """
        with self._lock:
            self._ensure_connected()
            self._ws.send(data.decode("utf-8"))
            _log.debug("WS send %d bytes", len(data))

    def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive a WebSocket text frame.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (data, source_address).
        """
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected. Call send() first.")

        t = timeout if timeout is not None else self.config.read_timeout
        raw = self._ws.recv(timeout=t)
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        _log.debug("WS recv %d bytes", len(data))
        return data, self.local_address

    def close(self) -> None:
        """Close the WebSocket connection and release resources."""
        if self._closed:
            return
        self._closed = True

        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        _log.info("WS closed")

    def _get_protocol_name(self) -> str:
        return "WS"


class AsyncWSTransport(AsyncBaseTransport):
    """
    Asynchronous WebSocket transport for SIP (RFC 7118).

    SIP messages are sent as WebSocket text frames using the "sip" subprotocol.
    Uses ``websockets.connect()`` for the async connection.
    """

    def __init__(
        self,
        config: Optional[TransportConfig] = None,
        uri: str = "ws://localhost:8080",
    ) -> None:
        super().__init__(config)
        self._uri = uri
        self._ws = None

    async def _ensure_connected(self) -> None:
        """
        Lazily connect to the WebSocket endpoint.

        Uses ``websockets.connect`` with the "sip" subprotocol.
        """
        if self._ws is not None and not self._closed:
            return

        _log.info("WS connecting to %s", self._uri)
        websockets = _import_websockets()
        self._ws = await websockets.connect(
            self._uri,
            subprotocols=["sip"],
            open_timeout=self.config.connect_timeout,
        )
        _log.info("WS connected")

    async def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send a SIP request over WebSocket and receive the response.

        Args:
            request: The SIP request to send.
            destination: Target address (used for addressing context).

        Returns:
            Parsed SIP response.
        """
        from ..models._message import MessageParser

        await self._ensure_connected()
        data = request.to_bytes()
        await self._ws.send(data.decode("utf-8"))

        raw = await asyncio.wait_for(
            self._ws.recv(),
            timeout=self.config.read_timeout,
        )
        message = MessageParser.parse(
            raw if isinstance(raw, bytes) else raw.encode("utf-8")
        )
        return message  # type: ignore[return-value]

    async def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes as a WebSocket text frame.

        Args:
            data: Raw SIP message bytes.
            destination: Target address (used for addressing context).
        """
        await self._ensure_connected()
        await self._ws.send(data.decode("utf-8"))
        _log.debug("WS send %d bytes", len(data))

    async def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive a WebSocket text frame.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (data, source_address).
        """
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected. Call send() first.")

        t = timeout if timeout is not None else self.config.read_timeout
        raw = await asyncio.wait_for(self._ws.recv(), timeout=t)
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        _log.debug("WS recv %d bytes", len(data))
        return data, self.local_address

    async def close(self) -> None:
        """Close the WebSocket connection and release resources."""
        if self._closed:
            return
        self._closed = True

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        _log.info("WS closed")

    def _get_protocol_name(self) -> str:
        return "WS"


__all__ = [
    "WSTransport",
    "AsyncWSTransport",
]
