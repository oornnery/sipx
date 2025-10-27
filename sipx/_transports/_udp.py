"""
UDP transport implementation for SIP.

UDP is the most common transport for SIP, providing connectionless datagram service.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Optional, Tuple

from .._types import (
    ReadError,
    TimeoutError,
    TransportAddress,
    TransportConfig,
    TransportError,
    WriteError,
)
from ._base import AsyncBaseTransport, BaseTransport
from .._models._message import Request, Response


class UDPTransport(BaseTransport):
    """
    Synchronous UDP transport for SIP.

    UDP is connectionless and unreliable, suitable for most SIP scenarios
    where upper layers handle retransmission (SIP transaction layer).
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize UDP transport.

        Args:
            config: Transport configuration
        """
        super().__init__(config)
        self._socket: Optional[socket.socket] = None
        self._initialize_socket()

    def _initialize_socket(self) -> None:
        """Create and bind UDP socket."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Set timeouts
            self._socket.settimeout(self.config.read_timeout)

            # Bind to local address
            self._socket.bind((self.config.local_host, self.config.local_port))

            # Update config with actual bound port (in case port was 0)
            actual_addr = self._socket.getsockname()
            self.config.local_port = actual_addr[1]

        except OSError as e:
            raise TransportError(f"Failed to initialize UDP socket: {e}") from e

    def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send SIP request and receive response.

        Args:
            request: SIP request to send
            destination: Destination address

        Returns:
            SIP response

        Raises:
            TransportError: On send/receive failure
            TimeoutError: If response timeout expires
        """
        from .._models._message import MessageParser

        # Serialize request
        data = request.to_bytes()

        # Send
        self.send(data, destination)

        # Receive responses (loop until final response)
        parser = MessageParser()
        final_response = None

        while True:
            # Receive response
            response_data, source = self.receive(timeout=self.config.read_timeout)

            # Parse response
            response = parser.parse(response_data)

            if not isinstance(response, Response):
                raise TransportError(
                    f"Expected Response but got {type(response).__name__}"
                )

            # Attach metadata
            response.raw = response_data
            response.request = request
            response.transport_info = {
                "protocol": "UDP",
                "local": str(self.local_address),
                "remote": str(source),
            }

            # Check if final response (2xx-6xx)
            if response.status_code >= 200:
                final_response = response
                break
            # Provisional response (1xx) - continue waiting
            # but store it in case we timeout
            if final_response is None:
                final_response = response

        return final_response

    def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes via UDP.

        Args:
            data: Bytes to send
            destination: Destination address

        Raises:
            WriteError: If send fails
        """
        if self._socket is None or self._closed:
            raise TransportError("Transport is closed")

        try:
            sent = self._socket.sendto(data, (destination.host, destination.port))
            if sent != len(data):
                raise WriteError(f"Incomplete send: sent {sent} of {len(data)} bytes")
        except OSError as e:
            raise WriteError(f"Failed to send UDP datagram: {e}") from e

    def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes via UDP.

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

            data, addr = self._socket.recvfrom(self.config.buffer_size)

            source = TransportAddress(
                host=addr[0],
                port=addr[1],
                protocol="UDP",
            )

            return data, source

        except socket.timeout as e:
            raise TimeoutError("UDP receive timeout") from e
        except OSError as e:
            raise ReadError(f"Failed to receive UDP datagram: {e}") from e
        finally:
            if timeout is not None:
                self._socket.settimeout(old_timeout)

    def close(self) -> None:
        """Close UDP socket."""
        if self._socket and not self._closed:
            self._socket.close()
            self._socket = None
            self._closed = True

    def _get_protocol_name(self) -> str:
        """Return protocol name."""
        return "UDP"

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<UDPTransport({self.local_address}, {status})>"


class AsyncUDPTransport(AsyncBaseTransport):
    """
    Asynchronous UDP transport for SIP using asyncio.

    Uses asyncio's DatagramProtocol for async UDP operations.
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize async UDP transport.

        Args:
            config: Transport configuration
        """
        super().__init__(config)
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[_UDPProtocol] = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure transport is initialized."""
        if self._initialized:
            return

        loop = asyncio.get_running_loop()

        # Create endpoint
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self.config.buffer_size),
            local_addr=(self.config.local_host, self.config.local_port),
        )

        # Update config with actual bound port
        sock = self._transport.get_extra_info("socket")
        if sock:
            actual_addr = sock.getsockname()
            self.config.local_port = actual_addr[1]

        self._initialized = True

    async def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send SIP request and receive response (async).

        Args:
            request: SIP request to send
            destination: Destination address

        Returns:
            SIP response

        Raises:
            TransportError: On send/receive failure
            TimeoutError: If response timeout expires
        """
        from .._models._message import MessageParser

        await self._ensure_initialized()

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
            "protocol": "UDP",
            "local": str(self.local_address),
            "remote": str(source),
        }

        return response

    async def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes via UDP (async).

        Args:
            data: Bytes to send
            destination: Destination address

        Raises:
            WriteError: If send fails
        """
        await self._ensure_initialized()

        if self._transport is None or self._closed:
            raise TransportError("Transport is closed")

        try:
            self._transport.sendto(data, (destination.host, destination.port))
        except Exception as e:
            raise WriteError(f"Failed to send UDP datagram: {e}") from e

    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes via UDP (async).

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (data, source_address)

        Raises:
            TimeoutError: If timeout expires
            ReadError: If receive fails
        """
        await self._ensure_initialized()

        if self._protocol is None or self._closed:
            raise TransportError("Transport is closed")

        try:
            if timeout is not None:
                data, addr = await asyncio.wait_for(
                    self._protocol.receive(),
                    timeout=timeout,
                )
            else:
                data, addr = await self._protocol.receive()

            source = TransportAddress(
                host=addr[0],
                port=addr[1],
                protocol="UDP",
            )

            return data, source

        except asyncio.TimeoutError as e:
            raise TimeoutError("UDP receive timeout") from e
        except Exception as e:
            raise ReadError(f"Failed to receive UDP datagram: {e}") from e

    async def close(self) -> None:
        """Close UDP transport."""
        if self._transport and not self._closed:
            self._transport.close()
            self._transport = None
            self._protocol = None
            self._initialized = False
            self._closed = True

    def _get_protocol_name(self) -> str:
        """Return protocol name."""
        return "UDP"

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<AsyncUDPTransport({self.local_address}, {status})>"


class _UDPProtocol(asyncio.DatagramProtocol):
    """
    Internal DatagramProtocol for async UDP transport.

    Queues received datagrams for consumption by AsyncUDPTransport.
    """

    def __init__(self, buffer_size: int = 65535) -> None:
        """
        Initialize protocol.

        Args:
            buffer_size: Maximum datagram size
        """
        self.buffer_size = buffer_size
        self._queue: asyncio.Queue[Tuple[bytes, Tuple[str, int]]] = asyncio.Queue()
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when connection is made."""
        self.transport = transport  # type: ignore

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Called when a datagram is received.

        Args:
            data: Received bytes
            addr: Source address (host, port)
        """
        self._queue.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        """
        Called when an error is received.

        Args:
            exc: The exception
        """
        # Log error or handle as needed
        # For now, we'll just ignore protocol-level errors
        pass

    async def receive(self) -> Tuple[bytes, Tuple[str, int]]:
        """
        Receive a datagram from the queue.

        Returns:
            Tuple of (data, (host, port))
        """
        return await self._queue.get()
