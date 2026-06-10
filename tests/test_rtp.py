import asyncio

import pytest

from sipx import (
    RtpAudioSession,
    RtpAudioSessionConfig,
    RtpJitterBuffer,
    RtpMetrics,
    RtpPacket,
    RtpParseError,
    RtpSequenceStats,
    decode_pcma,
    decode_pcmu,
    decode_dtmf_event,
    encode_pcma,
    encode_pcmu,
    encode_dtmf_event,
)
from sipx.rtp import G711Error


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
    assert snapshot.loss_percent == 25.0


def test_rtp_sequence_stats_tracks_duplicates_and_jitter() -> None:
    stats = RtpSequenceStats()
    stats.update(
        RtpPacket(payload_type=0, sequence_number=1, timestamp=0, ssrc=9, payload=b"a"),
        arrival_time=0.000,
    )
    stats.update(
        RtpPacket(
            payload_type=0,
            sequence_number=2,
            timestamp=160,
            ssrc=9,
            payload=b"b",
        ),
        arrival_time=0.025,
    )
    snapshot = stats.update(
        RtpPacket(
            payload_type=0,
            sequence_number=2,
            timestamp=160,
            ssrc=9,
            payload=b"b",
        ),
        arrival_time=0.026,
    )

    assert snapshot.received == 3
    assert snapshot.bytes == 2
    assert snapshot.duplicates == 1
    assert snapshot.jitter_ms > 0


def test_rtp_metrics_tracks_tx_and_rx() -> None:
    metrics = RtpMetrics()
    packet = RtpPacket(
        payload_type=0, sequence_number=1, timestamp=1, ssrc=7, payload=b"abc"
    )

    metrics.record_tx(packet)
    snapshot = metrics.record_rx(packet, arrival_time=0.0)

    assert snapshot.tx_packets == 1
    assert snapshot.tx_bytes == 3
    assert snapshot.rx.received == 1
    assert snapshot.rx.bytes == 3


def test_g711_pcmu_and_pcma_round_trip_close_to_pcm16() -> None:
    samples = (-12000, -1000, 0, 1000, 12000)
    pcm = b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)

    pcmu = decode_pcmu(encode_pcmu(pcm))
    pcma = decode_pcma(encode_pcma(pcm))

    for original, decoded in zip(samples, _pcm16_samples(pcmu), strict=True):
        assert abs(original - decoded) < 900
    for original, decoded in zip(samples, _pcm16_samples(pcma), strict=True):
        assert abs(original - decoded) < 900


def test_g711_rejects_odd_pcm_length() -> None:
    with pytest.raises(G711Error, match="even"):
        encode_pcmu(b"x")


def test_rtp_jitter_buffer_reorders_packets_and_conceals_loss() -> None:
    buffer = RtpJitterBuffer(
        ptime_ms=20,
        target_ms=60,
        max_ms=100,
        concealment_payload=b"silence",
    )
    packet_1 = RtpPacket(
        payload_type=0, sequence_number=1, timestamp=160, ssrc=9, payload=b"1"
    )
    packet_2 = RtpPacket(
        payload_type=0, sequence_number=2, timestamp=320, ssrc=9, payload=b"2"
    )
    packet_3 = RtpPacket(
        payload_type=0, sequence_number=3, timestamp=480, ssrc=9, payload=b"3"
    )

    assert buffer.push(packet_1)
    assert buffer.push(packet_3)
    assert buffer.push(packet_2)

    assert buffer.pop().payload == b"1"
    assert buffer.pop().payload == b"2"
    assert buffer.pop().payload == b"3"
    concealed = buffer.pop()
    snapshot = buffer.snapshot()

    assert concealed.concealed
    assert concealed.payload == b"silence"
    assert snapshot.concealment_frames == 1
    assert snapshot.underruns == 1


def test_rtp_jitter_buffer_drops_duplicate_late_and_overflow_packets() -> None:
    buffer = RtpJitterBuffer(ptime_ms=20, target_ms=20, max_ms=40)
    assert buffer.push(
        RtpPacket(payload_type=0, sequence_number=10, timestamp=10, ssrc=9)
    )
    assert not buffer.push(
        RtpPacket(payload_type=0, sequence_number=10, timestamp=10, ssrc=9)
    )
    assert buffer.pop().packet is not None
    assert not buffer.push(
        RtpPacket(payload_type=0, sequence_number=10, timestamp=10, ssrc=9)
    )
    assert buffer.push(
        RtpPacket(payload_type=0, sequence_number=11, timestamp=11, ssrc=9)
    )
    assert buffer.push(
        RtpPacket(payload_type=0, sequence_number=12, timestamp=12, ssrc=9)
    )
    assert buffer.push(
        RtpPacket(payload_type=0, sequence_number=13, timestamp=13, ssrc=9)
    )
    snapshot = buffer.snapshot()

    assert snapshot.duplicate_drops == 1
    assert snapshot.late_drops == 1
    assert snapshot.overruns == 1


def test_rtp_audio_session_sends_synthetic_noise_over_udp() -> None:
    asyncio.run(_rtp_audio_session_sends_synthetic_noise_over_udp())


async def _rtp_audio_session_sends_synthetic_noise_over_udp() -> None:
    receiver = await RtpAudioSession.open(
        RtpAudioSessionConfig(jitter_buffer_ms=0, max_jitter_buffer_ms=40)
    )
    sender = await RtpAudioSession.open(
        RtpAudioSessionConfig(
            remote=receiver.local_address,
            jitter_buffer_ms=0,
            max_jitter_buffer_ms=40,
        )
    )
    try:
        packets = await sender.send_synthetic(mode="noise", frames=1, seed=7)
        frame = await receiver.receive_frame(timeout=1.0)
        sender_snapshot = sender.snapshot()
        receiver_snapshot = receiver.snapshot()

        assert len(packets) == 1
        assert frame.sample_rate == 8000
        assert frame.channels == 1
        assert frame.duration_ms == 20
        assert frame.byte_length == 320
        assert frame.source == "rtp"
        assert frame.pcm.tobytes() != bytes(320)
        assert sender_snapshot.metrics.tx_packets == 1
        assert sender_snapshot.metrics.tx_bytes == 160
        assert receiver_snapshot.metrics.rx.received == 1
        assert receiver_snapshot.metrics.rx.bytes == 160
        assert receiver_snapshot.codec == "PCMU"
    finally:
        await sender.close()
        await receiver.close()


def test_rtp_audio_session_sends_synthetic_silence_over_udp() -> None:
    asyncio.run(_rtp_audio_session_sends_synthetic_silence_over_udp())


async def _rtp_audio_session_sends_synthetic_silence_over_udp() -> None:
    receiver = await RtpAudioSession.open(
        RtpAudioSessionConfig(codec="PCMA", payload_type=8, jitter_buffer_ms=0)
    )
    sender = await RtpAudioSession.open(
        RtpAudioSessionConfig(
            remote=receiver.local_address,
            codec="PCMA",
            payload_type=8,
            jitter_buffer_ms=0,
        )
    )
    try:
        await sender.send_synthetic(mode="silence", frames=1)
        frame = await receiver.receive_frame(timeout=1.0)

        assert max(abs(sample) for sample in _pcm16_samples(frame.pcm.tobytes())) <= 8
        assert sender.metrics.tx_packets == 1
        assert receiver.metrics.rx.received == 1
    finally:
        await sender.close()
        await receiver.close()


def test_rtp_audio_session_records_parse_errors() -> None:
    asyncio.run(_rtp_audio_session_records_parse_errors())


async def _rtp_audio_session_records_parse_errors() -> None:
    receiver = await RtpAudioSession.open(RtpAudioSessionConfig())
    transport, _protocol = await asyncio.get_running_loop().create_datagram_endpoint(
        asyncio.DatagramProtocol,
        local_addr=("127.0.0.1", 0),
    )
    try:
        transport.sendto(b"bad", receiver.local_address)
        with pytest.raises(RtpParseError):
            await receiver.receive_packet(timeout=1.0)
        assert receiver.metrics.rx.parse_errors == 1
    finally:
        transport.close()
        await receiver.close()


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


def _pcm16_samples(data: bytes) -> list[int]:
    return [
        int.from_bytes(data[offset : offset + 2], "little", signed=True)
        for offset in range(0, len(data), 2)
    ]
