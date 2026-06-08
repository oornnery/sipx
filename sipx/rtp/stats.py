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


class RtpSequenceStats:
    def __init__(self) -> None:
        self.received = 0
        self.lost = 0
        self.out_of_order = 0
        self.highest_sequence: int | None = None
        self.ssrc: int | None = None

    def update(self, packet: RtpPacket) -> RtpStatsSnapshot:
        self.received += 1
        if self.ssrc is None:
            self.ssrc = packet.ssrc
        if self.highest_sequence is None:
            self.highest_sequence = packet.sequence_number
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
        return self.snapshot()

    def snapshot(self) -> RtpStatsSnapshot:
        return RtpStatsSnapshot(
            received=self.received,
            lost=self.lost,
            out_of_order=self.out_of_order,
            highest_sequence=self.highest_sequence,
            ssrc=self.ssrc,
        )


def _sequence_after(sequence: int, previous: int) -> bool:
    return 0 < ((sequence - previous) & 0xFFFF) < 0x8000
