"""SIP over TCP transport using asyncio streams.

Implements RFC 3261 §18.3 TCP transport requirements.
SIP messages are framed using Content-Length header.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Literal

from sipx.exceptions import TransportError
from sipx.transport.base import Transport, TransportConfig


class TcpTransport(Transport):
    """SIP over TCP transport using asyncio StreamReader/StreamWriter.

    Manages TCP connections to remote SIP endpoints and handles
    Content-Length-based message framing per RFC 3261 §18.3.
    """

    def __init__(self, config: TransportConfig | None = None) -> None:
        self._config = config or TransportConfig()
        self._connections: dict[
            tuple[str, int], tuple[asyncio.StreamReader, asyncio.StreamWriter]
        ] = {}
        self._receive_queue: asyncio.Queue[tuple[bytes, tuple[str, int]] | None] = (
            asyncio.Queue()
        )
        self._closed = False
        self._receive_tasks: set[asyncio.Task] = set()

    @property
    def local_address(self) -> tuple[str, int]:
        """Return the bound local address as (host, port)."""
        return (self._config.local_host, self._config.local_port)

    @property
    def transport_type(self) -> Literal["tcp"]:
        """Return the transport protocol identifier."""
        return "tcp"

    @property
    def connected(self) -> bool:
        """Return True if any connections are active."""
        return len(self._connections) > 0

    def is_connected_to(self, remote: tuple[str, int]) -> bool:
        """Return True if connected to the specified remote address."""
        return remote in self._connections

    async def connect(self, remote: tuple[str, int]) -> None:
        """Establish TCP connection to remote address.

        Raises:
            TransportError: If transport is closed or connection fails.
        """
        if self._closed:
            raise TransportError("Transport is closed")

        if remote in self._connections:
            return

        try:
            reader, writer = await asyncio.open_connection(remote[0], remote[1])
            self._connections[remote] = (reader, writer)
            task = asyncio.create_task(self._read_loop(reader, remote))
            self._receive_tasks.add(task)
            task.add_done_callback(self._receive_tasks.discard)
        except OSError as e:
            raise TransportError(f"Failed to connect to {remote}: {e}") from e

    async def reconnect(self, remote: tuple[str, int]) -> None:
        """Reconnect to a remote address after connection loss.

        Closes existing connection if present, then establishes new one.
        """
        if remote in self._connections:
            reader, writer = self._connections.pop(remote)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        await self.connect(remote)

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        """Send data to remote, auto-connecting if needed.

        Raises:
            TransportError: If transport is closed or send fails.
        """
        if self._closed:
            raise TransportError("Transport is closed")

        if remote not in self._connections:
            await self.connect(remote)

        reader, writer = self._connections[remote]
        try:
            writer.write(data)
            await writer.drain()
        except OSError as e:
            self._connections.pop(remote, None)
            raise TransportError(f"Failed to send to {remote}: {e}") from e

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        """Yield incoming SIP messages from all connections.

        Messages are framed using Content-Length header.
        Stops when transport is closed or no connections remain.
        """
        while not self._closed:
            try:
                item = await asyncio.wait_for(
                    self._receive_queue.get(),
                    timeout=self._config.timeout,
                )
                if item is None:
                    break  # Sentinel value, transport is closing
                yield item
            except asyncio.TimeoutError:
                if not self._connections:
                    break  # No connections, stop iterating

    async def close(self) -> None:
        """Close all connections and release resources."""
        self._closed = True

        # Cancel receive tasks
        for task in self._receive_tasks:
            task.cancel()
        if self._receive_tasks:
            await asyncio.gather(*self._receive_tasks, return_exceptions=True)
        self._receive_tasks.clear()

        # Close connections
        for reader, writer in self._connections.values():
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        self._connections.clear()

        # Signal receive loop to stop
        await self._receive_queue.put(None)

    async def _read_loop(
        self, reader: asyncio.StreamReader, remote: tuple[str, int]
    ) -> None:
        """Read and frame SIP messages from a connection."""
        buffer = b""
        try:
            while not self._closed:
                chunk = await reader.read(self._config.max_message_size)
                if not chunk:
                    break  # Connection closed by peer
                buffer += chunk

                # Extract complete messages
                while True:
                    msg, buffer = self._extract_message(buffer)
                    if msg is None:
                        break
                    await self._receive_queue.put((msg, remote))
        except asyncio.CancelledError:
            raise
        except OSError:
            pass  # Connection error
        finally:
            self._connections.pop(remote, None)

    def _extract_message(self, buffer: bytes) -> tuple[bytes | None, bytes]:
        """Extract one complete SIP message from buffer.

        SIP messages are framed by:
        1. Double CRLF (end of headers)
        2. Content-Length header specifying body size

        Returns:
            Tuple of (message or None, remaining buffer).
        """
        # Find end of headers
        header_end = buffer.find(b"\r\n\r\n")
        if header_end == -1:
            return None, buffer

        headers_part = buffer[:header_end]
        body_start = header_end + 4

        # Parse Content-Length
        content_length = 0
        for line in headers_part.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                value = line.split(b":", 1)[1].strip()
                try:
                    content_length = int(value)
                except ValueError:
                    raise TransportError(f"Invalid Content-Length: {value!r}")
                break

        # Check if we have the full body
        total_length = body_start + content_length
        if len(buffer) < total_length:
            return None, buffer

        message = buffer[:total_length]
        remaining = buffer[total_length:]
        return message, remaining
