"""
Async wrappers for RTP, DTMF, and CallSession.

Thin async layer that delegates blocking I/O to ``asyncio.to_thread``,
matching the ``AsyncClient`` pattern used elsewhere in sipx.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from ._rtp import RTPSession

if TYPE_CHECKING:
    from sipx._client import Client
    from sipx.models._body import SDPBody
    from sipx.models._message import Response
    from sipx.media._codecs import Codec


# ============================================================================
# Async DTMF Helper
# ============================================================================


class AsyncDTMFHelper:
    """Async DTMF send/collect wrapping sync helpers via ``asyncio.to_thread``."""

    def __init__(self, async_rtp: AsyncRTPSession) -> None:
        self._rtp = async_rtp

    async def send(self, digits: str, duration_ms: int = 160) -> None:
        """Send one or more DTMF digits via RFC 4733.

        Args:
            digits: String of digits to send (e.g. ``"123#"``).
            duration_ms: Per-digit tone duration in milliseconds.
        """
        from ._dtmf import DTMFSender

        sender = DTMFSender(self._rtp._sync)
        for d in digits:
            await asyncio.to_thread(sender.send_digit, d, duration_ms)
            await asyncio.sleep(0.05)

    async def collect(self, max_digits: int = 1, timeout: float = 10.0) -> str:
        """Collect DTMF digits from the remote party.

        Args:
            max_digits: Maximum digits to collect (``0`` = unlimited).
            timeout: Collection timeout in seconds.

        Returns:
            String of collected digits.
        """
        from ._dtmf import DTMFCollector

        effective = max_digits if max_digits > 0 else 9999
        collector = DTMFCollector(
            self._rtp._sync, max_digits=effective, timeout=timeout
        )
        return await asyncio.to_thread(collector.collect)


# ============================================================================
# Async RTP Session
# ============================================================================


class AsyncRTPSession:
    """Async wrapper for ``RTPSession`` via ``asyncio.to_thread``."""

    def __init__(
        self,
        local_ip: str,
        local_port: int,
        remote_ip: str,
        remote_port: int,
        payload_type: int = 0,
        clock_rate: int = 8000,
        codec: "Codec | None" = None,
    ) -> None:
        self._sync = RTPSession(
            local_ip=local_ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            payload_type=payload_type,
            clock_rate=clock_rate,
            codec=codec,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Bind the UDP socket and start the receive thread."""
        await asyncio.to_thread(self._sync.start)

    async def stop(self) -> None:
        """Stop threads and close the socket."""
        await asyncio.to_thread(self._sync.stop)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send_audio(self, pcm_data: bytes) -> None:
        """Encode PCM data and send as RTP packets at 20 ms intervals.

        Args:
            pcm_data: 16-bit signed little-endian PCM audio.
        """
        await asyncio.to_thread(self._sync.send_audio, pcm_data)

    async def send_packet(self, packet: object) -> None:
        """Send a raw RTP packet to the remote endpoint."""
        await asyncio.to_thread(self._sync.send_packet, packet)

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    async def recv_audio(self, timeout: float = 1.0) -> Optional[bytes]:
        """Receive an RTP packet, decode, and return PCM audio."""
        return await asyncio.to_thread(self._sync.recv_audio, timeout)

    async def recv_packet(self, timeout: float = 1.0):
        """Receive a single RTP packet (blocking with timeout)."""
        return await asyncio.to_thread(self._sync.recv_packet, timeout)

    # ------------------------------------------------------------------
    # DTMF convenience
    # ------------------------------------------------------------------

    @property
    def dtmf(self) -> AsyncDTMFHelper:
        """Auto-created ``AsyncDTMFHelper`` for send/collect."""
        if not hasattr(self, "_dtmf_helper") or self._dtmf_helper is None:
            self._dtmf_helper = AsyncDTMFHelper(self)
        return self._dtmf_helper

    # ------------------------------------------------------------------
    # Proxy properties
    # ------------------------------------------------------------------

    @property
    def local_ip(self) -> str:
        return self._sync.local_ip

    @property
    def local_port(self) -> int:
        return self._sync.local_port

    @property
    def remote_ip(self) -> str:
        return self._sync.remote_ip

    @property
    def remote_port(self) -> int:
        return self._sync.remote_port

    @property
    def clock_rate(self) -> int:
        return self._sync.clock_rate

    @property
    def payload_type(self) -> int:
        return self._sync.payload_type

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_sdp(
        cls,
        sdp_body: SDPBody,
        local_ip: str,
        local_port: int,
    ) -> AsyncRTPSession:
        """Create an ``AsyncRTPSession`` from an SDP body.

        Args:
            sdp_body: Parsed ``SDPBody`` (typically from a 200 OK).
            local_ip: Local IP address to bind.
            local_port: Local UDP port to bind.

        Returns:
            Configured (but not started) ``AsyncRTPSession``.
        """
        sync = RTPSession.from_sdp(sdp_body, local_ip, local_port)
        obj = cls.__new__(cls)
        obj._sync = sync
        return obj

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncRTPSession:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()


# ============================================================================
# Async Call Session
# ============================================================================


class AsyncCallSession:
    """Async call session wrapping RTP + DTMF via ``asyncio.to_thread``."""

    def __init__(self, client: Client, response: Response, rtp_port: int) -> None:
        from ._session import CallSession

        self._sync = CallSession(client, response, rtp_port)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rtp(self):
        """The underlying ``RTPSession``, or ``None`` if SDP was absent."""
        return self._sync.rtp

    @property
    def dtmf(self) -> AsyncDTMFHelper | None:
        """Async DTMF helper, or ``None`` if no RTP session."""
        if self._sync.rtp is None:
            return None
        if not hasattr(self, "_async_rtp") or self._async_rtp is None:
            self._async_rtp = AsyncRTPSession.__new__(AsyncRTPSession)
            self._async_rtp._sync = self._sync.rtp
        if not hasattr(self, "_async_dtmf") or self._async_dtmf is None:
            self._async_dtmf = AsyncDTMFHelper(self._async_rtp)
        return self._async_dtmf

    # ------------------------------------------------------------------
    # Media helpers
    # ------------------------------------------------------------------

    async def play(self, audio: bytes) -> None:
        """Send raw PCM audio over RTP.

        Args:
            audio: 16-bit signed little-endian PCM bytes.
        """
        await asyncio.to_thread(self._sync.play, audio)

    async def play_tone(self, freq: int = 440, duration_ms: int = 500) -> None:
        """Generate and play a sine-wave tone.

        Args:
            freq: Tone frequency in Hz.
            duration_ms: Tone duration in milliseconds.
        """
        await asyncio.to_thread(self._sync.play_tone, freq, duration_ms)

    async def send_dtmf(self, digits: str, duration_ms: int = 160) -> None:
        """Send DTMF digits via RFC 4733.

        Args:
            digits: Digits to send (e.g. ``"123#"``).
            duration_ms: Per-digit tone duration in milliseconds.
        """
        await asyncio.to_thread(self._sync.send_dtmf, digits, duration_ms)

    async def collect_dtmf(self, max_digits: int = 1, timeout: float = 10.0) -> str:
        """Collect DTMF digits from the remote party.

        Args:
            max_digits: Maximum digits to collect (``0`` = unlimited).
            timeout: Timeout in seconds.

        Returns:
            String of collected digits (may be empty on timeout).
        """
        return await asyncio.to_thread(self._sync.collect_dtmf, max_digits, timeout)

    async def record(self, duration: float) -> bytes:
        """Record incoming audio for a given duration.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Concatenated raw PCM bytes received.
        """
        return await asyncio.to_thread(self._sync.record, duration)

    async def hangup(self) -> None:
        """Send a BYE to terminate the call."""
        self._sync.hangup()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncCallSession:
        if self._sync.rtp is not None:
            self._sync.rtp.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._sync.rtp is not None:
            self._sync.rtp.stop()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "AsyncRTPSession",
    "AsyncCallSession",
    "AsyncDTMFHelper",
]
