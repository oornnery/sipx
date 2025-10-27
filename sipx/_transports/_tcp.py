"""
TCP transport implementation for SIP.

TCP provides reliable, connection-oriented transport for SIP messages.
Suitable for large messages or when reliability is required.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Optional, Tuple

from .._types import (
    ConnectionError,
    ReadError,
    TimeoutError,
    TransportAddress,
    TransportConfig,
    TransportError,
    WriteError,
)
from ._base import AsyncBaseTransport, BaseTransport

from .._models._message import Request, Response


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

        except OSError as e:
            raise TransportError(f"Failed to initialize TCP socket: {e}") from e

    def _ensure_connected(self, destination: TransportAddress) -> None:
        """
        Ensure we have an active connection to destination.

        Args:
            destination: Target address

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected_to == destination:
            return  # Already connected

        # Close existing connection if any
        if self._connected_to is not None:
            self._disconnect()

        # Create new connection
        try:
            # Create a new client socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(self.config.connect_timeout)

            # Connect
            self._socket.connect((destination.host, destination.port))
            self._connected_to = destination

            # Set socket to non-blocking for I/O operations
            self._socket.settimeout(self.config.read_timeout)

        except OSError as e:
            raise ConnectionError(
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
            ConnectionError: If connection fails
            TimeoutError: If response timeout expires
        """
        from .._models._message import MessageParser

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
            ConnectionError: If not connected
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

        except OSError as e:
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
            TimeoutError: If timeout expires
            ReadError: If receive fails
        """
        if self._socket is None or self._closed:
            raise TransportError("Transport is closed")

        old_timeout = self._socket.gettimeout()
        try:
            if timeout is not None:
                self._socket.settimeout(timeout)

            # Read until we have complete SIP message
            chunks = []
            total_size = 0
            content_length: Optional[int] = None
            headers_end_pos: Optional[int] = None

            while True:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise ReadError("Connection closed by peer")

                chunks.append(chunk)
                total_size += len(chunk)
                data_so_far = b"".join(chunks)

                # Try to find end of headers
                if headers_end_pos is None:
                    headers_end_pos = data_so_far.find(b"\r\n\r\n")
                    if headers_end_pos != -1:
                        # Parse Content-Length from headers
                        headers = data_so_far[: headers_end_pos + 4]
                        content_length = self._parse_content_length(headers)

                # Check if we have complete message
                if headers_end_pos is not None:
                    body_start = headers_end_pos + 4
                    if content_length is not None:
                        # We know expected size
                        if total_size >= body_start + content_length:
                            # Complete message received
                            return (
                                data_so_far[: body_start + content_length],
                                self._connected_to or TransportAddress("", 0, "TCP"),
                            )
                    elif total_size > body_start:
                        # No Content-Length, assume message ends after headers
                        return (
                            data_so_far,
                            self._connected_to or TransportAddress("", 0, "TCP"),
                        )

        except socket.timeout as e:
            raise TimeoutError("TCP receive timeout") from e
        except OSError as e:
            raise ReadError(f"Failed to receive TCP data: {e}") from e
        finally:
            if timeout is not None:
                self._socket.settimeout(old_timeout)

    def _parse_content_length(self, headers: bytes) -> Optional[int]:
        """
        Parse Content-Length from SIP headers.

        Args:
            headers: Raw header bytes

        Returns:
            Content-Length value or None if not found
        """
        for line in headers.split(b"\r\n"):
            if line.lower().startswith(b"content-length:") or line.lower().startswith(
                b"l:"
            ):
                try:
                    value = line.split(b":", 1)[1].strip()
                    return int(value)
                except (IndexError, ValueError):
                    pass
        return None

    def close(self) -> None:
        """Close TCP connection and socket."""
        self._disconnect()
        self._closed = True

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
            ConnectionError: If connection fails
        """
        if self._connected_to == destination and self._writer is not None:
            return  # Already connected

        # Close existing connection if any
        if self._connected_to is not None:
            await self._disconnect()

        # Create new connection
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(destination.host, destination.port),
                timeout=self.config.connect_timeout,
            )
            self._connected_to = destination

        except asyncio.TimeoutError as e:
            raise ConnectionError(
                f"Connection timeout to {destination.host}:{destination.port}"
            ) from e
        except OSError as e:
            raise ConnectionError(
                f"Failed to connect to {destination.host}:{destination.port}: {e}"
            ) from e

    async def _disconnect(self) -> None:
        """Close current connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
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
            ConnectionError: If connection fails
            TimeoutError: If response timeout expires
        """
        from .._models._message import MessageParser

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
            raise TimeoutError("Response timeout") from e

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
            ConnectionError: If not connected
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
        except Exception as e:
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
            TimeoutError: If timeout expires
            ReadError: If receive fails
        """
        if self._reader is None or self._closed:
            raise TransportError("Transport is closed or not connected")

        try:
            # Read until we have complete SIP message
            chunks = []
            total_size = 0
            content_length: Optional[int] = None
            headers_end_pos: Optional[int] = None

            while True:
                chunk = await self._reader.read(4096)
                if not chunk:
                    raise ReadError("Connection closed by peer")

                chunks.append(chunk)
                total_size += len(chunk)
                data_so_far = b"".join(chunks)

                # Try to find end of headers
                if headers_end_pos is None:
                    headers_end_pos = data_so_far.find(b"\r\n\r\n")
                    if headers_end_pos != -1:
                        # Parse Content-Length from headers
                        headers = data_so_far[: headers_end_pos + 4]
                        content_length = self._parse_content_length(headers)

                # Check if we have complete message
                if headers_end_pos is not None:
                    body_start = headers_end_pos + 4
                    if content_length is not None:
                        # We know expected size
                        if total_size >= body_start + content_length:
                            # Complete message received
                            return (
                                data_so_far[: body_start + content_length],
                                self._connected_to or TransportAddress("", 0, "TCP"),
                            )
                    elif total_size > body_start:
                        # No Content-Length, assume message ends after headers
                        return (
                            data_so_far,
                            self._connected_to or TransportAddress("", 0, "TCP"),
                        )

        except Exception as e:
            raise ReadError(f"Failed to receive TCP data: {e}") from e

    def _parse_content_length(self, headers: bytes) -> Optional[int]:
        """
        Parse Content-Length from SIP headers.

        Args:
            headers: Raw header bytes

        Returns:
            Content-Length value or None if not found
        """
        for line in headers.split(b"\r\n"):
            if line.lower().startswith(b"content-length:") or line.lower().startswith(
                b"l:"
            ):
                try:
                    value = line.split(b":", 1)[1].strip()
                    return int(value)
                except (IndexError, ValueError):
                    pass
        return None

    async def close(self) -> None:
        """Close TCP connection."""
        await self._disconnect()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._closed = True

    def _get_protocol_name(self) -> str:
        """Return protocol name."""
        return "TCP"

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        connection = (
            f", connected to {self._connected_to}" if self._connected_to else ""
        )
        return f"<AsyncTCPTransport({self.local_address}, {status}{connection})>"
