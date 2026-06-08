import pytest

from sipx import (
    RtpPacket,
    RtpParseError,
    RtpSequenceStats,
    decode_dtmf_event,
    encode_dtmf_event,
)


def test_rtp_packet_round_trip() -> None:
    packet = RtpPacket(
        payload_type=0,
        sequence_number=42,
        timestamp=160,
        ssrc=1234,
        payload=b"abc",
        marker=True,
    )

    parsed = RtpPacket.parse(packet.to_bytes())

    assert parsed == packet


def test_rtp_parse_rejects_short_packet() -> None:
    with pytest.raises(RtpParseError):
        RtpPacket.parse(b"short")


def test_rtp_parse_rejects_wrong_version() -> None:
    data = bytearray(
        RtpPacket(payload_type=0, sequence_number=1, timestamp=1, ssrc=1).to_bytes()
    )
    data[0] = 0

    with pytest.raises(RtpParseError):
        RtpPacket.parse(bytes(data))


def test_rtp_sequence_stats_tracks_gap_and_out_of_order() -> None:
    stats = RtpSequenceStats()
    stats.update(RtpPacket(payload_type=0, sequence_number=1, timestamp=1, ssrc=9))
    stats.update(RtpPacket(payload_type=0, sequence_number=3, timestamp=3, ssrc=9))
    snapshot = stats.update(
        RtpPacket(payload_type=0, sequence_number=2, timestamp=2, ssrc=9)
    )

    assert snapshot.received == 3
    assert snapshot.lost == 1
    assert snapshot.out_of_order == 1
    assert snapshot.highest_sequence == 3
    assert snapshot.ssrc == 9


def test_dtmf_rfc4733_encode_decode() -> None:
    payload = encode_dtmf_event("#", end=True, volume=7, duration=320)
    event = decode_dtmf_event(payload)

    assert payload == bytes([11, 0x87, 1, 64])
    assert event.digit == "#"
    assert event.event == 11
    assert event.end
    assert event.volume == 7
    assert event.duration == 320


def test_dtmf_rejects_invalid_payload_size() -> None:
    with pytest.raises(ValueError):
        decode_dtmf_event(b"abc")
