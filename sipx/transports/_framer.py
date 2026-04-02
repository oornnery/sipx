"""SIP message framing utilities for stream-oriented transports (TCP, TLS).

SIP over TCP/TLS uses Content-Length framing: the receiver reads until it has
consumed exactly Content-Length bytes after the blank-line header separator.
This module provides both sync and async versions of the accumulation loop so
TCPTransport, TLSTransport, AsyncTCPTransport, and AsyncTLSTransport all share
a single implementation.
"""

from __future__ import annotations

from typing import Optional

from ._utils import parse_content_length


# ---------------------------------------------------------------------------
# Shared state container
# ---------------------------------------------------------------------------


class _FrameBuffer:
    """Accumulates raw bytes and detects complete SIP message boundaries."""

    __slots__ = ("_chunks", "_total_size", "_headers_end", "_content_length")

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._total_size: int = 0
        self._headers_end: Optional[int] = None
        self._content_length: Optional[int] = None

    def feed(self, chunk: bytes) -> Optional[bytes]:
        """Feed a new chunk and return a complete message bytes object if ready.

        Returns:
            Complete SIP message bytes if we have one, otherwise ``None``.
        """
        self._chunks.append(chunk)
        self._total_size += len(chunk)
        data = b"".join(self._chunks)

        # Try to locate end of headers
        if self._headers_end is None:
            pos = data.find(b"\r\n\r\n")
            if pos != -1:
                self._headers_end = pos
                self._content_length = parse_content_length(data[: pos + 4])

        if self._headers_end is None:
            return None

        body_start = self._headers_end + 4
        if self._content_length is not None:
            if self._total_size >= body_start + self._content_length:
                return data[: body_start + self._content_length]
        else:
            # No Content-Length header — assume message ends after headers
            if self._total_size > body_start:
                return data

        return None


# ---------------------------------------------------------------------------
# Sync framing loop
# ---------------------------------------------------------------------------


def read_sip_message_sync(recv_fn, chunk_size: int = 4096) -> bytes:
    """Read exactly one complete SIP message from a synchronous recv callable.

    Args:
        recv_fn: Callable that accepts a byte count and returns ``bytes``.
                 Should raise ``socket.timeout`` / ``OSError`` on errors.
        chunk_size: Maximum bytes to read per call.

    Returns:
        Raw bytes of one complete SIP message.

    Raises:
        ReadError: If the connection is closed mid-message.
    """
    from .._types import ReadError

    buf = _FrameBuffer()
    while True:
        chunk = recv_fn(chunk_size)
        if not chunk:
            raise ReadError("Connection closed by peer")
        result = buf.feed(chunk)
        if result is not None:
            return result


# ---------------------------------------------------------------------------
# Async framing loop
# ---------------------------------------------------------------------------


async def read_sip_message_async(reader, chunk_size: int = 4096) -> bytes:
    """Read exactly one complete SIP message from an asyncio StreamReader.

    Args:
        reader: ``asyncio.StreamReader`` instance.
        chunk_size: Maximum bytes to read per call.

    Returns:
        Raw bytes of one complete SIP message.

    Raises:
        ReadError: If the connection is closed mid-message.
    """
    from .._types import ReadError

    buf = _FrameBuffer()
    while True:
        chunk = await reader.read(chunk_size)
        if not chunk:
            raise ReadError("Connection closed by peer")
        result = buf.feed(chunk)
        if result is not None:
            return result
