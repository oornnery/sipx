"""RTP reception statistics: loss, ordering, duplicates, and jitter.

Tracks received/lost/out-of-order/duplicate counts and computes interarrival
jitter using the smoothing estimator from RFC 3550, exposing immutable
snapshots for reporting.

References:
    RFC 3550 §6.4.1 - Interarrival jitter calculation
    RFC 3550 §A.8 - Estimating the Interarrival Jitter
"""

from __future__ import annotations

from dataclasses import dataclass

from sipx.rtp.packet import RtpPacket


@dataclass(frozen=True, slots=True)
class RtpStatsSnapshot:
    received: int
    lost: int
    out_of_order: int
    highest_sequence: int | None
    ssrc: int | None
    bytes: int = 0
    duplicates: int = 0
    parse_errors: int = 0
    decode_errors: int = 0
    late_drops: int = 0
    jitter: float = 0.0
    jitter_ms: float = 0.0
    jitter_min_ms: float = 0.0
    jitter_max_ms: float = 0.0
    loss_percent: float = 0.0


@dataclass(frozen=True, slots=True)
class RtpMetricsSnapshot:
    tx_packets: int
    tx_bytes: int
    rx: RtpStatsSnapshot


class RtpSequenceStats:
    def __init__(self) -> None:
        self.received = 0
        self.lost = 0
        self.out_of_order = 0
        self.duplicates = 0
        self.bytes = 0
        self.parse_errors = 0
        self.decode_errors = 0
        self.late_drops = 0
        self.highest_sequence: int | None = None
        self.ssrc: int | None = None
        self._seen_sequences: set[int] = set()
        self._previous_transit: float | None = None
        self._jitter = 0.0
        self._jitter_min_ms: float | None = None
        self._jitter_max_ms = 0.0
        self._clock_rate = 8000

    def update(
        self,
        packet: RtpPacket,
        *,
        arrival_time: float | None = None,
        clock_rate: int = 8000,
    ) -> RtpStatsSnapshot:
        self.received += 1
        if self.ssrc is None:
            self.ssrc = packet.ssrc
        if packet.sequence_number in self._seen_sequences:
            self.duplicates += 1
            return self.snapshot()
        self._seen_sequences.add(packet.sequence_number)
        self.bytes += len(packet.payload)
        if self.highest_sequence is None:
            self.highest_sequence = packet.sequence_number
            self._update_jitter(
                packet, arrival_time=arrival_time, clock_rate=clock_rate
            )
            return self.snapshot()

        expected = (self.highest_sequence + 1) & 0xFFFF
        if packet.sequence_number == expected:
            self.highest_sequence = packet.sequence_number
        elif _sequence_after(packet.sequence_number, self.highest_sequence):
            gap = (packet.sequence_number - expected) & 0xFFFF
            self.lost += gap
            self.highest_sequence = packet.sequence_number
        else:
            self.out_of_order += 1
        self._update_jitter(packet, arrival_time=arrival_time, clock_rate=clock_rate)
        return self.snapshot()

    def record_parse_error(self) -> RtpStatsSnapshot:
        self.parse_errors += 1
        return self.snapshot()

    def record_decode_error(self) -> RtpStatsSnapshot:
        self.decode_errors += 1
        return self.snapshot()

    def record_late_drop(self) -> RtpStatsSnapshot:
        self.late_drops += 1
        return self.snapshot()

    def snapshot(self) -> RtpStatsSnapshot:
        jitter_ms = self._jitter * 1000 / self._clock_rate
        return RtpStatsSnapshot(
            received=self.received,
            lost=self.lost,
            out_of_order=self.out_of_order,
            highest_sequence=self.highest_sequence,
            ssrc=self.ssrc,
            bytes=self.bytes,
            duplicates=self.duplicates,
            parse_errors=self.parse_errors,
            decode_errors=self.decode_errors,
            late_drops=self.late_drops,
            jitter=self._jitter,
            jitter_ms=jitter_ms,
            jitter_min_ms=0.0 if self._jitter_min_ms is None else self._jitter_min_ms,
            jitter_max_ms=self._jitter_max_ms,
            loss_percent=_loss_percent(self.lost, self.received),
        )

    def _update_jitter(
        self,
        packet: RtpPacket,
        *,
        arrival_time: float | None,
        clock_rate: int,
    ) -> None:
        if arrival_time is None:
            return
        if clock_rate <= 0:
            raise ValueError("clock_rate must be positive")
        self._clock_rate = clock_rate
        arrival = arrival_time * clock_rate
        transit = arrival - packet.timestamp
        if self._previous_transit is None:
            self._previous_transit = transit
            return
        delta = abs(transit - self._previous_transit)
        self._previous_transit = transit
        self._jitter += (delta - self._jitter) / 16
        jitter_ms = self._jitter * 1000 / clock_rate
        if self._jitter_min_ms is None or jitter_ms < self._jitter_min_ms:
            self._jitter_min_ms = jitter_ms
        if jitter_ms > self._jitter_max_ms:
            self._jitter_max_ms = jitter_ms


class RtpMetrics:
    def __init__(self) -> None:
        self.tx_packets = 0
        self.tx_bytes = 0
        self.rx = RtpSequenceStats()

    def record_tx(self, packet: RtpPacket) -> RtpMetricsSnapshot:
        self.tx_packets += 1
        self.tx_bytes += len(packet.payload)
        return self.snapshot()

    def record_rx(
        self,
        packet: RtpPacket,
        *,
        arrival_time: float | None = None,
        clock_rate: int = 8000,
    ) -> RtpMetricsSnapshot:
        self.rx.update(packet, arrival_time=arrival_time, clock_rate=clock_rate)
        return self.snapshot()

    def snapshot(self) -> RtpMetricsSnapshot:
        return RtpMetricsSnapshot(
            tx_packets=self.tx_packets,
            tx_bytes=self.tx_bytes,
            rx=self.rx.snapshot(),
        )


def _sequence_after(sequence: int, previous: int) -> bool:
    return 0 < ((sequence - previous) & 0xFFFF) < 0x8000


def _loss_percent(lost: int, received: int) -> float:
    total = lost + received
    if total == 0:
        return 0.0
    return lost * 100 / total
