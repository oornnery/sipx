from __future__ import annotations

from dataclasses import dataclass

from sipx.rtp.packet import RtpPacket


@dataclass(frozen=True, slots=True)
class RtpPlayoutFrame:
    packet: RtpPacket | None
    payload: bytes
    concealed: bool = False


@dataclass(frozen=True, slots=True)
class RtpJitterBufferSnapshot:
    target_ms: int
    max_ms: int
    depth_ms: int
    depth_frames: int
    min_depth_ms: int
    max_depth_ms: int
    underruns: int
    overruns: int
    late_drops: int
    duplicate_drops: int
    concealment_frames: int
    resyncs: int


class RtpJitterBuffer:
    def __init__(
        self,
        *,
        ptime_ms: int = 20,
        target_ms: int = 60,
        max_ms: int = 200,
        concealment_payload: bytes = b"",
    ) -> None:
        if ptime_ms <= 0:
            raise ValueError("ptime_ms must be positive")
        if target_ms < 0:
            raise ValueError("target_ms must be non-negative")
        if max_ms < target_ms:
            raise ValueError("max_ms must be greater than or equal to target_ms")
        self.ptime_ms = ptime_ms
        self.target_ms = target_ms
        self.max_ms = max_ms
        self.concealment_payload = concealment_payload
        self._target_frames = target_ms // ptime_ms
        self._max_frames = max(1, max_ms // ptime_ms)
        self._packets: dict[int, RtpPacket] = {}
        self._base_sequence: int | None = None
        self._expected_sequence: int | None = None
        self.underruns = 0
        self.overruns = 0
        self.late_drops = 0
        self.duplicate_drops = 0
        self.concealment_frames = 0
        self.resyncs = 0
        self._min_depth_frames = 0
        self._max_depth_frames = 0

    def push(self, packet: RtpPacket) -> bool:
        sequence = packet.sequence_number
        if self._expected_sequence is not None and _sequence_before(
            sequence, self._expected_sequence
        ):
            self.late_drops += 1
            return False
        if sequence in self._packets:
            self.duplicate_drops += 1
            return False
        if self._base_sequence is None:
            self._base_sequence = sequence
        self._packets[sequence] = packet
        self._trim_overflow()
        self._record_depth()
        return True

    def pop(self) -> RtpPlayoutFrame:
        if self._expected_sequence is None:
            if self._base_sequence is None or len(self._packets) < self._target_frames:
                return self._conceal(underrun=True)
            self._expected_sequence = self._base_sequence

        packet = self._packets.pop(self._expected_sequence, None)
        if packet is not None:
            self._expected_sequence = (self._expected_sequence + 1) & 0xFFFF
            self._record_depth()
            return RtpPlayoutFrame(packet=packet, payload=packet.payload)

        return self._conceal(underrun=not self._packets)

    def snapshot(self) -> RtpJitterBufferSnapshot:
        depth_frames = len(self._packets)
        return RtpJitterBufferSnapshot(
            target_ms=self.target_ms,
            max_ms=self.max_ms,
            depth_ms=depth_frames * self.ptime_ms,
            depth_frames=depth_frames,
            min_depth_ms=self._min_depth_frames * self.ptime_ms,
            max_depth_ms=self._max_depth_frames * self.ptime_ms,
            underruns=self.underruns,
            overruns=self.overruns,
            late_drops=self.late_drops,
            duplicate_drops=self.duplicate_drops,
            concealment_frames=self.concealment_frames,
            resyncs=self.resyncs,
        )

    def _conceal(self, *, underrun: bool) -> RtpPlayoutFrame:
        if underrun:
            self.underruns += 1
        self.concealment_frames += 1
        if self._expected_sequence is not None:
            self._expected_sequence = (self._expected_sequence + 1) & 0xFFFF
        self._record_depth()
        return RtpPlayoutFrame(
            packet=None,
            payload=self.concealment_payload,
            concealed=True,
        )

    def _trim_overflow(self) -> None:
        while len(self._packets) > self._max_frames:
            sequence = min(
                self._packets, key=lambda item: _sequence_distance(self._base(), item)
            )
            self._packets.pop(sequence, None)
            self.overruns += 1

    def _record_depth(self) -> None:
        depth = len(self._packets)
        if self._min_depth_frames == 0 or depth < self._min_depth_frames:
            self._min_depth_frames = depth
        if depth > self._max_depth_frames:
            self._max_depth_frames = depth

    def _base(self) -> int:
        return 0 if self._base_sequence is None else self._base_sequence


def _sequence_before(sequence: int, reference: int) -> bool:
    return 0 < ((reference - sequence) & 0xFFFF) < 0x8000


def _sequence_distance(base: int, sequence: int) -> int:
    return (sequence - base) & 0xFFFF
