"""RTP packet parsing and serialization.

``RtpPacket`` models the RTP fixed header (version, payload type, sequence
number, timestamp, SSRC, CSRC list, marker) plus payload, with validation and
round-trip ``parse``/``to_bytes``. Header extensions are not supported.

References:
    RFC 3550 §5.1 - RTP Fixed Header Fields
    RFC 3550 §5.3 - Profile-Specific Modifications to the RTP Header
"""

from __future__ import annotations

from dataclasses import dataclass, field


class RtpParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RtpPacket:
    payload_type: int
    sequence_number: int
    timestamp: int
    ssrc: int
    payload: bytes = b""
    marker: bool = False
    csrc: tuple[int, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0 <= self.payload_type <= 127:
            raise ValueError("payload_type must be between 0 and 127")
        if not 0 <= self.sequence_number <= 65535:
            raise ValueError("sequence_number must be between 0 and 65535")
        if not 0 <= self.timestamp <= 0xFFFFFFFF:
            raise ValueError("timestamp must be a uint32")
        if not 0 <= self.ssrc <= 0xFFFFFFFF:
            raise ValueError("ssrc must be a uint32")
        if len(self.csrc) > 15:
            raise ValueError("RTP supports at most 15 CSRC values")

    @classmethod
    def parse(cls, data: bytes) -> RtpPacket:
        if len(data) < 12:
            raise RtpParseError("RTP packet is too short")
        first = data[0]
        version = first >> 6
        if version != 2:
            raise RtpParseError(f"unsupported RTP version: {version}")
        padding = bool(first & 0x20)
        extension = bool(first & 0x10)
        csrc_count = first & 0x0F
        if extension:
            raise RtpParseError("RTP header extensions are not supported yet")
        header_length = 12 + csrc_count * 4
        if len(data) < header_length:
            raise RtpParseError("RTP packet is shorter than CSRC header length")

        marker = bool(data[1] & 0x80)
        payload_type = data[1] & 0x7F
        sequence_number = int.from_bytes(data[2:4], "big")
        timestamp = int.from_bytes(data[4:8], "big")
        ssrc = int.from_bytes(data[8:12], "big")
        csrc = tuple(
            int.from_bytes(data[offset : offset + 4], "big")
            for offset in range(12, header_length, 4)
        )
        payload = data[header_length:]
        if padding:
            if not payload:
                raise RtpParseError("RTP padding flag set with empty payload")
            padding_length = payload[-1]
            if padding_length == 0 or padding_length > len(payload):
                raise RtpParseError("invalid RTP padding length")
            payload = payload[:-padding_length]

        return cls(
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            payload=payload,
            marker=marker,
            csrc=csrc,
        )

    def to_bytes(self) -> bytes:
        first = 0x80 | len(self.csrc)
        second = (0x80 if self.marker else 0) | self.payload_type
        header = bytes([first, second])
        header += self.sequence_number.to_bytes(2, "big")
        header += self.timestamp.to_bytes(4, "big")
        header += self.ssrc.to_bytes(4, "big")
        for item in self.csrc:
            header += item.to_bytes(4, "big")
        return header + self.payload
