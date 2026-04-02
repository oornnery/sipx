"""
TCP transport implementation for SIP.

TCP provides reliable, connection-oriented transport for SIP messages.
Suitable for large messages or when reliability is required.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Optional, Tuple

from ._framer import read_sip_message_sync, read_sip_message_async
from .._types import (
    SIPConnectionError,
    ReadError,
    SIPTimeoutError,
    TransportAddress,
    TransportConfig,
    TransportError,
    WriteError,
)
from ._base import AsyncBaseTransport, BaseTransport

from ..models._message import Request, Response
from .._utils import logger

_log = logger.getChild("transport.tcp")


class TCPTransport(BaseTransport):
    """
    Synchronous TCP transport for SIP.

    TCP is connection-oriented and reliable, suitable for:
    - Large SIP messages (> MTU)
    - When reliability is critical
    - NAT traversal scenarios
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize TCP transport.

        Args:
            config: Transport configuration
        """
        super().__init__(config)
        self._socket: Optional[socket.socket] = None
        self._connected_to: Optional[TransportAddress] = None
        self._initialize_socket()

    def _initialize_socket(self) -> None:
        """Create and bind TCP socket."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Set timeouts
            self._socket.settimeout(self.config.connect_timeout)

            # Bind to local address
            self._socket.bind((self.config.local_host, self.config.local_port))

            # Update config with actual bound port
            actual_addr = self._socket.getsockname()
            self.config.local_port = actual_addr[1]

            # Listen for incoming connections (for server mode)
            self._socket.listen(5)

            _log.info(
                "TCP bound to %s:%d", self.config.local_host, self.config.local_port
            )

        except OSError as e:
            _log.error("TCP socket init failed: %s", e)
            raise TransportError(f"Failed to initialize TCP socket: {e}") from e

    def _ensure_connected(self, destination: TransportAddress) -> None:
        """
        Ensure we have an active connection to destination.

        Args:
            destination: Target address

        Raises:
            SIPConnectionError: If connection fails
        """
        if self._connected_to == destination:
            return  # Already connected

        # Close existing connection if any
        if self._connected_to is not None:
            self._disconnect()

        # Create new connection
        try:
            _log.info("TCP connecting to %s:%d", destination.host, destination.port)

            # Create a new client socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(self.config.connect_timeout)

            # Connect
            self._socket.connect((destination.host, destination.port))
            self._connected_to = destination

            # Set socket to non-blocking for I/O operations
            self._socket.settimeout(self.config.read_timeout)

            _log.info("TCP connected")

        except OSError as e:
            _log.error("TCP connection error: %s", e)
            raise SIPConnectionError(
                f"Failed to connect to {destination.host}:{destination.port}: {e}"
            ) from e

    def _disconnect(self) -> None:
        """Close current connection."""
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed
            self._socket.close()
            self._socket = None
        self._connected_to = None

    def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send SIP request and receive response over TCP.

        Args:
            request: SIP request to send
            destination: Destination address

        Returns:
            SIP response

        Raises:
            TransportError: On send/receive failure
            SIPConnectionError: If connection fails
            SIPTimeoutError: If response timeout expires
        """
        from ..models._message import MessageParser

        # Ensure connection
        self._ensure_connected(destination)

        # Serialize request
        data = request.to_bytes()

        # Send
        self.send(data, destination)

        # Receive response
        response_data, source = self.receive(timeout=self.config.read_timeout)

        # Parse response
        parser = MessageParser()
        response = parser.parse(response_data)

        if not isinstance(response, Response):
            raise TransportError(f"Expected Response but got {type(response).__name__}")

        # Attach metadata
        response.raw = response_data
        response.request = request
        response.transport_info = {
            "protocol": "TCP",
            "local": str(self.local_address),
            "remote": str(source),
        }

        return response

    def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes via TCP.

        Args:
            data: Bytes to send
            destination: Destination address

        Raises:
            WriteError: If send fails
            SIPConnectionError: If not connected
        """
        if self._socket is None or self._closed:
            raise TransportError("Transport is closed")

        # Ensure connected
        self._ensure_connected(destination)

        try:
            total_sent = 0
            while total_sent < len(data):
                sent = self._socket.send(data[total_sent:])
                if sent == 0:
                    raise WriteError("Socket connection broken")
                total_sent += sent

            _log.debug("TCP send %d bytes", len(data))

        except OSError as e:
            _log.error("TCP send failed: %s", e)
            raise WriteError(f"Failed to send TCP data: {e}") from e

    def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes via TCP.

        TCP is stream-oriented, so we read until we have a complete SIP message.
        We detect message boundary by parsing Content-Length header.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (data, source_address)

        Raises:
            SIPTimeoutError: If timeout expires
            ReadError: If receive fails
        """
        if self._socket is None or self._closed:
            raise TransportError("Transport is closed")

        old_timeout = self._socket.gettimeout()
        try:
            if timeout is not None:
                self._socket.settimeout(timeout)

            data = read_sip_message_sync(self._socket.recv)
            _log.debug("TCP recv %d bytes", len(data))
            return data, self._connected_to or TransportAddress("", 0, "TCP")

        except socket.timeout as e:
            raise SIPTimeoutError("TCP receive timeout") from e
        except OSError as e:
            _log.error("TCP receive failed: %s", e)
            raise ReadError(f"Failed to receive TCP data: {e}") from e
        finally:
            if timeout is not None:
                self._socket.settimeout(old_timeout)

    def close(self) -> None:
        """Close TCP connection and socket."""
        self._disconnect()
        self._closed = True
        _log.info("TCP closed")

    def _get_protocol_name(self) -> str:
        """Return protocol name."""
        return "TCP"

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        connection = (
            f", connected to {self._connected_to}" if self._connected_to else ""
        )
        return f"<TCPTransport({self.local_address}, {status}{connection})>"


class AsyncTCPTransport(AsyncBaseTransport):
    """
    Asynchronous TCP transport for SIP using asyncio.

    Uses asyncio streams for async TCP operations.
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize async TCP transport.

        Args:
            config: Transport configuration
        """
        super().__init__(config)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected_to: Optional[TransportAddress] = None
        self._server: Optional[asyncio.Server] = None

    async def _ensure_connected(self, destination: TransportAddress) -> None:
        """
        Ensure we have an active connection to destination.

        Args:
            destination: Target address

        Raises:
            SIPConnectionError: If connection fails
        """
        if self._connected_to == destination and self._writer is not None:
            return  # Already connected

        # Close existing connection if any
        if self._connected_to is not None:
            await self._disconnect()

        # Create new connection
        try:
            _log.info("TCP connecting to %s:%d", destination.host, destination.port)

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(destination.host, destination.port),
                timeout=self.config.connect_timeout,
            )
            self._connected_to = destination

            _log.info("TCP connected")

        except asyncio.TimeoutError as e:
            _log.error(
                "TCP connection timeout to %s:%d", destination.host, destination.port
            )
            raise SIPConnectionError(
                f"Connection timeout to {destination.host}:{destination.port}"
            ) from e
        except OSError as e:
            _log.error("TCP connection error: %s", e)
            raise SIPConnectionError(
                f"Failed to connect to {destination.host}:{destination.port}: {e}"
            ) from e

    async def _disconnect(self) -> None:
        """Close current connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (OSError, ConnectionError, asyncio.TimeoutError):
                pass  # Ignore errors during close
            self._writer = None
            self._reader = None
        self._connected_to = None

    async def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send SIP request and receive response over TCP (async).

        Args:
            request: SIP request to send
            destination: Destination address

        Returns:
            SIP response

        Raises:
            TransportError: On send/receive failure
            SIPConnectionError: If connection fails
            SIPTimeoutError: If response timeout expires
        """
        from ..models._message import MessageParser

        # Ensure connection
        await self._ensure_connected(destination)

        # Serialize request
        data = request.to_bytes()

        # Send
        await self.send(data, destination)

        # Receive response with timeout
        try:
            response_data, source = await asyncio.wait_for(
                self.receive(),
                timeout=self.config.read_timeout,
            )
        except asyncio.TimeoutError as e:
            raise SIPTimeoutError("Response timeout") from e

        # Parse response
        parser = MessageParser()
        response = parser.parse(response_data)

        if not isinstance(response, Response):
            raise TransportError(f"Expected Response but got {type(response).__name__}")

        # Attach metadata
        response.raw = response_data
        response.request = request
        response.transport_info = {
            "protocol": "TCP",
            "local": str(self.local_address),
            "remote": str(source),
        }

        return response

    async def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes via TCP (async).

        Args:
            data: Bytes to send
            destination: Destination address

        Raises:
            WriteError: If send fails
            SIPConnectionError: If not connected
        """
        if self._closed:
            raise TransportError("Transport is closed")

        # Ensure connected
        await self._ensure_connected(destination)

        if self._writer is None:
            raise TransportError("No active connection")

        try:
            self._writer.write(data)
            await self._writer.drain()
            _log.debug("TCP send %d bytes", len(data))
        except (OSError, ConnectionError, RuntimeError) as e:
            _log.error("TCP send failed: %s", e)
            raise WriteError(f"Failed to send TCP data: {e}") from e

    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes via TCP (async).

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (data, source_address)

        Raises:
            SIPTimeoutError: If timeout expires
            ReadError: If receive fails
        """
        if self._reader is None or self._closed:
            raise TransportError("Transport is closed or not connected")

        try:
            data = await read_sip_message_async(self._reader)
            _log.debug("TCP recv %d bytes", len(data))
            return data, self._connected_to or TransportAddress("", 0, "TCP")

        except ReadError:
            raise
        except (
            OSError,
            ConnectionError,
            RuntimeError,
            asyncio.IncompleteReadError,
        ) as e:
            _log.error("TCP receive failed: %s", e)
            raise ReadError(f"Failed to receive TCP data: {e}") from e

    @staticmethod
    def _parse_content_length(headers: bytes) -> Optional[int]:
        from ._utils import parse_content_length

        return parse_content_length(headers)

    async def close(self) -> None:
        """Close TCP connection."""
        await self._disconnect()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._closed = True
        _log.info("TCP closed")

    def _get_protocol_name(self) -> str:
        """Return protocol name."""
        return "TCP"

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        connection = (
            f", connected to {self._connected_to}" if self._connected_to else ""
        )
        return f"<AsyncTCPTransport({self.local_address}, {status}{connection})>"
