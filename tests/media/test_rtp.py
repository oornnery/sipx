"""Tests for RTP packet serialization/deserialization."""

from __future__ import annotations

import pytest

from sipx._media._rtp import RTPPacket


class TestRTPPacketRoundtrip:
    """RTPPacket to_bytes/from_bytes roundtrip tests."""

    def test_roundtrip_basic(self):
        pkt = RTPPacket(
            version=2,
            marker=True,
            payload_type=0,
            sequence_number=1234,
            timestamp=56789,
            ssrc=99999,
            payload=b"\x80\x81\x82\x83",
        )
        data = pkt.to_bytes()
        parsed = RTPPacket.from_bytes(data)
        assert parsed.version == 2
        assert parsed.marker is True
        assert parsed.payload_type == 0
        assert parsed.sequence_number == 1234
        assert parsed.timestamp == 56789
        assert parsed.ssrc == 99999
        assert parsed.payload == b"\x80\x81\x82\x83"

    def test_roundtrip_no_marker(self):
        pkt = RTPPacket(
            marker=False,
            payload_type=8,
            sequence_number=65535,
            timestamp=0xFFFFFFFF,
            ssrc=0,
            payload=b"\x00\x01",
        )
        parsed = RTPPacket.from_bytes(pkt.to_bytes())
        assert parsed.marker is False
        assert parsed.payload_type == 8
        assert parsed.sequence_number == 65535
        assert parsed.timestamp == 0xFFFFFFFF
        assert parsed.ssrc == 0

    def test_empty_payload(self):
        pkt = RTPPacket(payload=b"")
        parsed = RTPPacket.from_bytes(pkt.to_bytes())
        assert parsed.payload == b""

    def test_large_payload(self):
        payload = bytes(range(256)) * 4  # 1024 bytes
        pkt = RTPPacket(payload=payload[:1000])
        parsed = RTPPacket.from_bytes(pkt.to_bytes())
        assert len(parsed.payload) == 1000
        assert parsed.payload == payload[:1000]

    def test_fields_preserved(self):
        pkt = RTPPacket(
            version=2,
            marker=True,
            payload_type=101,
            sequence_number=42,
            timestamp=160,
            ssrc=0xDEADBEEF,
            payload=b"\xff",
        )
        parsed = RTPPacket.from_bytes(pkt.to_bytes())
        assert parsed.version == 2
        assert parsed.marker is True
        assert parsed.payload_type == 101
        assert parsed.sequence_number == 42
        assert parsed.timestamp == 160
        assert parsed.ssrc == 0xDEADBEEF

    def test_from_bytes_too_short_raises(self):
        with pytest.raises(ValueError, match="too short"):
            RTPPacket.from_bytes(b"\x00" * 11)

    def test_from_bytes_exactly_12_bytes(self):
        pkt = RTPPacket(payload=b"")
        data = pkt.to_bytes()
        assert len(data) == 12
        parsed = RTPPacket.from_bytes(data)
        assert parsed.payload == b""
