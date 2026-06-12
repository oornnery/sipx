"""UDP transport implementation for SIP.

This module provides UdpTransport, which implements the Transport interface
using asyncio.DatagramTransport for UDP communication.

Refactored from sipx.sip.transport.SipUdpEndpoint to match the new
Transport abstraction. The original SipUdpEndpoint remains in place during
the transition period (removal scheduled for Task 32, Wave 10).
"""

from __future__ import annotations

import asyncio
import re
import secrets
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal

from sipx.exceptions import TransportError
from sipx.transport.base import Transport, TransportConfig

if TYPE_CHECKING:
    from sipx.models import Request, Response


class UdpTransport(Transport):
    """UDP transport implementation using asyncio.DatagramTransport.

    This transport handles raw UDP datagram send/receive operations for SIP
    communication. It is connectionless and does not implement connection
    pooling, retry logic, or NAT traversal.

    Usage:
        config = TransportConfig(local_host="127.0.0.1", local_port=5060)
        async with UdpTransport(config) as transport:
            await transport.send(b"message", ("remote.host", 5060))
            async for data, remote in transport.receive():
                print(f"Received {data} from {remote}")
    """

    def __init__(
        self,
        config: TransportConfig | None = None,
        *,
        local_host: str | None = None,
        local_port: int | None = None,
        max_message_size: int = 65535,
    ) -> None:
        """Initialize UDP transport with configuration.

        Args:
            config: Transport configuration specifying bind address and limits.
            local_host: Convenience parameter for local host (used if config is None).
            local_port: Convenience parameter for local port (used if config is None).
            max_message_size: Convenience parameter for max message size (used if config is None).

        Raises:
            TransportError: If configuration is invalid.
        """
        if config is None:
            if local_host is None:
                raise TransportError("local_host is required")
            if local_port is None:
                local_port = 0
            config = TransportConfig(
                local_host=local_host,
                local_port=local_port,
                max_message_size=max_message_size,
            )

        if not config.local_host:
            raise TransportError("local_host is required")
        if not 0 <= config.local_port < 65536:
            raise TransportError("local_port must be between 0 and 65535")
        if config.max_message_size <= 0:
            raise TransportError("max_message_size must be positive")

        self._config = config
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._inbox: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self._closed = False

    @property
    def local_address(self) -> tuple[str, int]:
        """Return the bound local address as (host, port).

        Raises:
            TransportError: If transport is not started.
        """
        transport = self._require_transport()
        sockname = transport.get_extra_info("sockname")
        return _normalize_address(sockname)

    @property
    def transport_type(self) -> Literal["udp"]:
        """Return the transport protocol identifier."""
        return "udp"

    async def start(self) -> UdpTransport:
        """Start the transport by binding to the configured address.

        Returns:
            Self for method chaining.

        Raises:
            TransportError: If binding fails or transport is already started.
        """
        if self._transport is not None:
            return self

        try:
            loop = asyncio.get_running_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _UdpProtocol(
                    inbox=self._inbox,
                    max_message_size=self._config.max_message_size,
                ),
                local_addr=(self._config.local_host, self._config.local_port),
            )
            self._transport = transport  # type: ignore[assignment]
            self._protocol = protocol  # type: ignore[assignment]
            return self
        except OSError as exc:
            raise TransportError(f"Failed to bind UDP socket: {exc}") from exc

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        """Send raw bytes to the remote address.

        Args:
            data: Bytes to send.
            remote: Remote address as (host, port).

        Raises:
            TransportError: If transport is not started or send fails.
        """
        transport = self._require_transport()

        if len(data) > self._config.max_message_size:
            raise TransportError(
                f"Message size {len(data)} exceeds maximum {self._config.max_message_size}"
            )

        try:
            address = _normalize_address(remote)
            transport.sendto(data, address)
        except Exception as exc:
            raise TransportError(f"Failed to send UDP datagram: {exc}") from exc

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        """Yield incoming datagrams as (data, remote_address) pairs.

        This is an async iterator that yields datagrams until the transport
        is closed. Each yielded item is a tuple of (data, (host, port)).

        Yields:
            Tuples of (data, remote_address) for each received datagram.
        """
        while not self._closed:
            try:
                # Use a timeout to check for closure periodically
                item = await asyncio.wait_for(self._inbox.get(), timeout=0.1)
                yield item
            except asyncio.TimeoutError:
                # Check if we should continue
                continue
            except Exception:
                # Transport closed or other error
                break

    async def close(self) -> None:
        """Close the transport and release resources."""
        if self._closed:
            return

        self._closed = True
        transport = self._transport
        protocol = self._protocol

        self._transport = None
        self._protocol = None

        if transport is not None:
            transport.close()

        if protocol is not None:
            try:
                await asyncio.wait_for(protocol.wait_closed(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def __aenter__(self) -> UdpTransport:
        """Enter async context manager, starting the transport."""
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager, closing the transport."""
        await self.close()

    def _require_transport(self) -> asyncio.DatagramTransport:
        """Return the underlying transport or raise if not started.

        Raises:
            TransportError: If transport is not started.
        """
        if self._transport is None:
            raise TransportError("UDP transport is not started")
        return self._transport

    def add_via_header(self, request: Request) -> None:
        """Add Via header with rport parameter to outbound request.

        Per RFC 3581, the rport parameter (without value) requests that the
        server fill in the actual source port and add a received parameter.

        Args:
            request: The SIP request to modify.
        """
        host = self._config.local_host
        port = self._config.local_port
        branch = f"z9hG4bK{secrets.token_hex(8)}"
        via = f"SIP/2.0/UDP {host}:{port};branch={branch};rport"
        request.headers["Via"] = via

    def parse_via_rport(self, response: Response) -> tuple[int | None, str | None]:
        """Parse rport and received parameters from Via header in response.

        Per RFC 3581, extracts the rport (port) and received (IP address)
        parameters that the server added to the Via header.

        Args:
            response: The SIP response to parse.

        Returns:
            Tuple of (rport, received) where rport is the port number or None,
            and received is the IP address string or None.
        """
        via = response.headers.get("Via", "")
        if isinstance(via, list):
            via = via[0] if via else ""
        if not via:
            return None, None

        rport = None
        received = None

        rport_match = re.search(r";rport(?:=(\d+))?", via)
        if rport_match and rport_match.group(1):
            rport = int(rport_match.group(1))

        received_match = re.search(r";received=([^;]+)", via)
        if received_match:
            received = received_match.group(1).strip()

        return rport, received

    def get_response_destination(
        self, via_header: str, source_addr: tuple[str, int]
    ) -> tuple[str, int]:
        """Determine where to send a response based on Via header and source address.

        Per RFC 3581, if rport is present in the Via header, send the response
        to the source address/port instead of the Via address. If received
        parameter is also present, use that IP address.

        Args:
            via_header: The Via header value from the request.
            source_addr: The actual source address where the request came from.

        Returns:
            The destination address (host, port) where the response should be sent.
        """
        if ";rport" not in via_header:
            return self._parse_via_address(via_header)

        source_host, source_port = source_addr

        received_match = re.search(r";received=([^;]+)", via_header)
        if received_match:
            source_host = received_match.group(1).strip()

        rport_match = re.search(r";rport(?:=(\d+))?", via_header)
        if rport_match and rport_match.group(1):
            source_port = int(rport_match.group(1))

        return source_host, source_port

    def _parse_via_address(self, via_header: str) -> tuple[str, int]:
        """Parse host and port from Via header address.

        Args:
            via_header: The Via header value.

        Returns:
            Tuple of (host, port) from the Via address.
        """
        match = re.search(r"SIP/2\.0/UDP\s+([^;]+)", via_header)
        if not match:
            raise TransportError(f"Invalid Via header format: {via_header}")

        address = match.group(1).strip()
        if ":" in address:
            host, port_str = address.rsplit(":", 1)
            return host, int(port_str)
        return address, 5060


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal protocol handler for UDP datagrams.

    Receives datagrams from asyncio and places them in the inbox queue.
    """

    def __init__(
        self,
        inbox: asyncio.Queue[tuple[bytes, tuple[str, int]]],
        max_message_size: int,
    ) -> None:
        """Initialize protocol with inbox queue and size limit.

        Args:
            inbox: Queue to place received datagrams into.
            max_message_size: Maximum allowed message size.
        """
        self._inbox = inbox
        self._max_message_size = max_message_size
        self._closed_event = asyncio.Event()

    def datagram_received(self, data: bytes, addr: Any) -> None:
        """Handle received datagram.

        Args:
            data: Received bytes.
            addr: Source address.
        """
        try:
            remote = _normalize_address(addr)
            # Check size limit
            if len(data) > self._max_message_size:
                # Drop oversized messages silently
                return
            self._inbox.put_nowait((data, remote))
        except Exception:
            # Drop malformed addresses
            pass

    def error_received(self, exc: Exception) -> None:
        """Handle UDP socket error.

        Args:
            exc: The exception that occurred.
        """
        # Log or handle errors - for now we continue operation
        pass

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection loss.

        Args:
            exc: Exception that caused the loss, if any.
        """
        self._closed_event.set()

    async def wait_closed(self) -> None:
        """Wait for the protocol to be closed."""
        await self._closed_event.wait()


def _normalize_address(addr: object) -> tuple[str, int]:
    """Normalize a socket address tuple.

    Args:
        addr: Address object from asyncio (typically a tuple).

    Returns:
        Normalized (host, port) tuple.

    Raises:
        TransportError: If address format is invalid.
    """
    if not isinstance(addr, tuple) or len(addr) < 2:
        raise TransportError(f"Invalid UDP address: {addr!r}")
    host, port = addr[:2]
    return str(host), int(port)
