"""
DTMF signaling over RTP (RFC 4733) and SIP INFO.

RFC 4733 telephone-event payload format:
  - 4 bytes: event(8) | E(1) | R(1) | volume(6) | duration(16)
  - Payload type 101 (negotiated via SDP)
  - 3 packets per digit: start (M=1), continuation, end (E=1)
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._utils import logger

_log = logger.getChild("dtmf")

if TYPE_CHECKING:
    from ._rtp import RTPSession

# DTMF event codes per RFC 4733
DTMF_EVENTS: dict[str, int] = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "*": 10,
    "#": 11,
    "A": 12,
    "B": 13,
    "C": 14,
    "D": 15,
}

DTMF_PAYLOAD_TYPE = 101


@dataclass
class DTMFEvent:
    """RFC 4733 telephone-event payload (4 bytes)."""

    event: int = 0
    end: bool = False
    volume: int = 10
    duration: int = 0

    def to_bytes(self) -> bytes:
        """Encode to 4-byte RFC 4733 payload."""
        byte1 = self.event & 0xFF
        byte2 = ((1 if self.end else 0) << 7) | (self.volume & 0x3F)
        return struct.pack("!BBH", byte1, byte2, self.duration & 0xFFFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> DTMFEvent:
        """Decode from 4-byte RFC 4733 payload."""
        if len(data) < 4:
            return cls()
        byte1, byte2, duration = struct.unpack("!BBH", data[:4])
        return cls(
            event=byte1,
            end=bool(byte2 & 0x80),
            volume=byte2 & 0x3F,
            duration=duration,
        )

    @property
    def digit(self) -> str | None:
        """Convert event code to DTMF digit character."""
        for d, code in DTMF_EVENTS.items():
            if code == self.event:
                return d
        return None

    @classmethod
    def from_digit(cls, digit: str, **kwargs) -> DTMFEvent:
        """Create from digit character ('0'-'9', '*', '#', 'A'-'D')."""
        code = DTMF_EVENTS.get(digit.upper())
        if code is None:
            raise ValueError(f"Invalid DTMF digit: {digit}")
        return cls(event=code, **kwargs)


class DTMFSender:
    """Send DTMF digits as RFC 4733 named telephone events."""

    def __init__(self, rtp_session: RTPSession) -> None:
        self.rtp_session = rtp_session

    def send_digit(self, digit: str, duration_ms: int = 160, volume: int = 10) -> None:
        """
        Send a single DTMF digit via RTP (RFC 4733).

        Sends 3 packets: start (marker=1), continuation, end (E=1).

        Args:
            digit: DTMF digit ('0'-'9', '*', '#', 'A'-'D')
            duration_ms: Tone duration in milliseconds (default 160)
            volume: Power level 0-63 (default 10, ~= -10 dBm0)
        """
        from ._rtp import RTPPacket

        _log.debug("DTMF send: digit=%s", digit)
        event_code = DTMF_EVENTS.get(digit.upper())
        if event_code is None:
            raise ValueError(f"Invalid DTMF digit: {digit}")

        ts = self.rtp_session._timestamp
        samples_per_ms = self.rtp_session.clock_rate // 1000
        total_duration = duration_ms * samples_per_ms

        # Packet 1: start (marker bit set)
        payload = DTMFEvent(
            event=event_code, end=False, volume=volume, duration=0
        ).to_bytes()
        pkt = RTPPacket(
            marker=True,
            payload_type=DTMF_PAYLOAD_TYPE,
            sequence_number=self.rtp_session._sequence_number,
            timestamp=ts,
            ssrc=self.rtp_session._ssrc,
            payload=payload,
        )
        self.rtp_session.send_packet(pkt)
        self.rtp_session._sequence_number = (
            self.rtp_session._sequence_number + 1
        ) & 0xFFFF

        # Wait half duration
        time.sleep(duration_ms / 2000.0)

        # Packet 2: continuation
        mid_duration = total_duration // 2
        payload = DTMFEvent(
            event=event_code, end=False, volume=volume, duration=mid_duration
        ).to_bytes()
        pkt = RTPPacket(
            marker=False,
            payload_type=DTMF_PAYLOAD_TYPE,
            sequence_number=self.rtp_session._sequence_number,
            timestamp=ts,
            ssrc=self.rtp_session._ssrc,
            payload=payload,
        )
        self.rtp_session.send_packet(pkt)
        self.rtp_session._sequence_number = (
            self.rtp_session._sequence_number + 1
        ) & 0xFFFF

        # Wait remaining duration
        time.sleep(duration_ms / 2000.0)

        # Packet 3: end (E bit set, send 3 times per RFC 4733)
        payload = DTMFEvent(
            event=event_code, end=True, volume=volume, duration=total_duration
        ).to_bytes()
        for _ in range(3):
            pkt = RTPPacket(
                marker=False,
                payload_type=DTMF_PAYLOAD_TYPE,
                sequence_number=self.rtp_session._sequence_number,
                timestamp=ts,
                ssrc=self.rtp_session._ssrc,
                payload=payload,
            )
            self.rtp_session.send_packet(pkt)
            self.rtp_session._sequence_number = (
                self.rtp_session._sequence_number + 1
            ) & 0xFFFF

        # Advance timestamp past this digit so next digit has a different ts
        self.rtp_session._timestamp = (
            self.rtp_session._timestamp + total_duration
        ) & 0xFFFFFFFF


class DTMFCollector:
    """Collect DTMF digits received from an RTP stream."""

    def __init__(
        self,
        rtp_session: RTPSession,
        max_digits: int = 1,
        timeout: float = 10.0,
    ) -> None:
        self.rtp_session = rtp_session
        self.max_digits = max_digits
        self.timeout = timeout

    def collect(self) -> str:
        """
        Collect up to max_digits DTMF digits within timeout seconds.

        Listens for RFC 4733 telephone-event packets and detects digit
        boundaries via the E (end) bit.

        Returns:
            String of collected digits (e.g. "123#")
        """
        digits: list[str] = []
        last_end_ts: int | None = None  # deduplicate repeated end-packets
        deadline = time.time() + self.timeout

        while len(digits) < self.max_digits:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            try:
                pkt = self.rtp_session.recv_packet(timeout=min(remaining, 0.5))
            except Exception:
                continue

            if pkt is None:
                continue
            if pkt.payload_type != DTMF_PAYLOAD_TYPE:
                continue
            if len(pkt.payload) < 4:
                continue

            evt = DTMFEvent.from_bytes(pkt.payload)
            if evt.end:
                # RFC 4733: end-packet is sent 3 times with same timestamp.
                # Only count the first one per timestamp.
                if pkt.timestamp == last_end_ts:
                    continue
                last_end_ts = pkt.timestamp
                if evt.digit is not None:
                    _log.debug("DTMF recv: digit=%s", evt.digit)
                    digits.append(evt.digit)

        collected = "".join(digits)
        _log.debug("DTMF collected: %s", collected)
        return collected
