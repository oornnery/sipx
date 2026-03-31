"""
Async wrappers for RTP, DTMF, and CallSession.

Thin async layer that delegates blocking I/O to ``asyncio.to_thread``,
matching the ``AsyncClient`` pattern used elsewhere in sipx.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from ._rtp import RTPPacket

if TYPE_CHECKING:
    from sipx.client import Client
    from sipx.models._body import SDPBody
    from sipx.models._message import Response
    from sipx.media._codecs import Codec


# ============================================================================
# Async DTMF Helper
# ============================================================================


class AsyncDTMFHelper:
    """Native async DTMF send/collect using AsyncRTPSession directly."""

    def __init__(self, async_rtp: AsyncRTPSession) -> None:
        self._rtp = async_rtp

    async def send(self, digits: str, duration_ms: int = 160, volume: int = 10) -> None:
        """Send DTMF digits via RFC 4733 (native async)."""
        from ._dtmf import DTMF_EVENTS, DTMF_PAYLOAD_TYPE, DTMFEvent
        from ._rtp import RTPPacket

        for digit in digits:
            event_code = DTMF_EVENTS.get(digit.upper())
            if event_code is None:
                continue

            ts = self._rtp._timestamp
            samples_per_ms = self._rtp.clock_rate // 1000
            total_duration = duration_ms * samples_per_ms

            # Start packet (marker=True)
            payload = DTMFEvent(
                event=event_code, end=False, volume=volume, duration=0
            ).to_bytes()
            await self._rtp.send_packet(
                RTPPacket(
                    marker=True,
                    payload_type=DTMF_PAYLOAD_TYPE,
                    sequence_number=self._rtp._sequence_number & 0xFFFF,
                    timestamp=ts,
                    ssrc=self._rtp._ssrc,
                    payload=payload,
                )
            )
            self._rtp._sequence_number += 1
            await asyncio.sleep(duration_ms / 2000.0)

            # Continuation
            mid = total_duration // 2
            payload = DTMFEvent(
                event=event_code, end=False, volume=volume, duration=mid
            ).to_bytes()
            await self._rtp.send_packet(
                RTPPacket(
                    payload_type=DTMF_PAYLOAD_TYPE,
                    sequence_number=self._rtp._sequence_number & 0xFFFF,
                    timestamp=ts,
                    ssrc=self._rtp._ssrc,
                    payload=payload,
                )
            )
            self._rtp._sequence_number += 1
            await asyncio.sleep(duration_ms / 2000.0)

            # End (3x per RFC 4733)
            payload = DTMFEvent(
                event=event_code, end=True, volume=volume, duration=total_duration
            ).to_bytes()
            for _ in range(3):
                await self._rtp.send_packet(
                    RTPPacket(
                        payload_type=DTMF_PAYLOAD_TYPE,
                        sequence_number=self._rtp._sequence_number & 0xFFFF,
                        timestamp=ts,
                        ssrc=self._rtp._ssrc,
                        payload=payload,
                    )
                )
                self._rtp._sequence_number += 1

            self._rtp._timestamp = (self._rtp._timestamp + total_duration) & 0xFFFFFFFF
            await asyncio.sleep(0.05)

    async def collect(self, max_digits: int = 1, timeout: float = 10.0) -> str:
        """Collect DTMF digits via RFC 4733 (native async)."""
        import time
        from ._dtmf import DTMF_PAYLOAD_TYPE, DTMFEvent

        effective = max_digits if max_digits > 0 else 9999
        digits: list[str] = []
        last_end_ts: int | None = None
        deadline = time.monotonic() + timeout

        while len(digits) < effective:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            pkt = await self._rtp.recv_packet(timeout=min(remaining, 0.5))
            if (
                pkt is None
                or pkt.payload_type != DTMF_PAYLOAD_TYPE
                or len(pkt.payload) < 4
            ):
                continue
            evt = DTMFEvent.from_bytes(pkt.payload)
            if evt.end:
                if pkt.timestamp == last_end_ts:
                    continue
                last_end_ts = pkt.timestamp
                if evt.digit is not None:
                    digits.append(evt.digit)

        return "".join(digits)


# ============================================================================
# Async RTP Session
# ============================================================================


class _RTPProtocol(asyncio.DatagramProtocol):
    """asyncio DatagramProtocol for native async RTP."""

    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self._queue: asyncio.Queue[RTPPacket] = asyncio.Queue()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) >= 12:
            try:
                packet = RTPPacket.from_bytes(data)
                self._queue.put_nowait(packet)
            except Exception:
                pass


class AsyncRTPSession:
    """Native async RTP session using asyncio.DatagramProtocol.

    No threading — runs entirely in the asyncio event loop.
    """

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
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.payload_type = payload_type
        self.clock_rate = clock_rate

        # Resolve codec
        from ._codecs import PCMA, PCMU

        _registry: dict[int, type] = {0: PCMU, 8: PCMA}
        if codec is not None:
            self.codec = codec
        elif payload_type in _registry:
            self.codec = _registry[payload_type]()
        else:
            self.codec = PCMU()

        # RTP state
        import random

        self._ssrc = random.randint(0, 0xFFFFFFFF)
        self._sequence_number = random.randint(0, 0xFFFF)
        self._timestamp = random.randint(0, 0xFFFFFFFF)
        self._samples_per_packet = clock_rate // 50  # 20ms

        # asyncio transport
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _RTPProtocol | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            _RTPProtocol,
            local_addr=(self.local_ip, self.local_port),
        )

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None

    async def send_packet(self, packet: RTPPacket) -> None:
        if self._transport:
            self._transport.sendto(
                packet.to_bytes(), (self.remote_ip, self.remote_port)
            )

    async def recv_packet(self, timeout: float = 1.0) -> Optional[RTPPacket]:
        if not self._protocol:
            return None
        try:
            return await asyncio.wait_for(self._protocol._queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

    async def send_audio(self, pcm_data: bytes) -> None:
        bytes_per_packet = self._samples_per_packet * 2
        offset = 0
        while offset < len(pcm_data):
            chunk = pcm_data[offset : offset + bytes_per_packet]
            if not chunk:
                break
            encoded = self.codec.encode(chunk)
            packet = RTPPacket(
                payload_type=self.payload_type,
                sequence_number=self._sequence_number & 0xFFFF,
                timestamp=self._timestamp & 0xFFFFFFFF,
                ssrc=self._ssrc,
                payload=encoded,
            )
            await self.send_packet(packet)
            self._sequence_number += 1
            self._timestamp += self._samples_per_packet
            offset += bytes_per_packet
            await asyncio.sleep(0.020)

    async def recv_audio(self, timeout: float = 1.0) -> Optional[bytes]:
        packet = await self.recv_packet(timeout)
        if packet is None:
            return None
        return self.codec.decode(packet.payload)

    @property
    def dtmf(self) -> AsyncDTMFHelper:
        if not hasattr(self, "_dtmf_helper") or self._dtmf_helper is None:
            self._dtmf_helper = AsyncDTMFHelper(self)
        return self._dtmf_helper

    @classmethod
    def from_sdp(
        cls, sdp_body: SDPBody, local_ip: str, local_port: int
    ) -> AsyncRTPSession:
        params = sdp_body.get_rtp_params()
        if params:
            return cls(
                local_ip=local_ip,
                local_port=local_port,
                remote_ip=params["ip"] or "127.0.0.1",
                remote_port=params["port"],
                payload_type=params["payload_type"],
                clock_rate=params["clock_rate"],
            )
        return cls(
            local_ip=local_ip,
            local_port=local_port,
            remote_ip="127.0.0.1",
            remote_port=0,
        )

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
