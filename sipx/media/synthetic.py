"""Synthetic audio source generating silence or low-level noise.

Produces deterministic linear 16-bit PCM ``AudioFrame`` chunks without any
capture hardware, useful for tests and for keeping an RTP stream alive when
no real audio is available.

References:
    RFC 3550 - RTP (generated PCM is encoded and sent as RTP)
    ITU-T G.711 - PCM of voice frequencies (sample format)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Literal

from sipx.media.frame import AudioFrame


SyntheticAudioMode = Literal["silence", "noise"]


@dataclass(slots=True)
class SyntheticAudioSource:
    mode: SyntheticAudioMode = "silence"
    sample_rate: int = 8000
    channels: int = 1
    frame_duration_ms: int = 20
    noise_level: float = 0.03
    seed: int | None = 1
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in {"silence", "noise"}:
            raise ValueError("synthetic audio mode must be silence or noise")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        if not 0 <= self.noise_level <= 1:
            raise ValueError("noise_level must be between 0 and 1")
        self._random = random.Random(self.seed)

    @property
    def samples_per_frame(self) -> int:
        return self.sample_rate * self.frame_duration_ms // 1000

    @property
    def bytes_per_frame(self) -> int:
        return self.samples_per_frame * self.channels * 2

    def next_frame(self, *, timestamp_ns: int | None = None) -> AudioFrame:
        pcm = self._silence() if self.mode == "silence" else self._noise()
        return AudioFrame(
            pcm=pcm,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration_ms=self.frame_duration_ms,
            timestamp_ns=time.monotonic_ns() if timestamp_ns is None else timestamp_ns,
            source=self.mode,
        )

    def _silence(self) -> bytes:
        return bytes(self.bytes_per_frame)

    def _noise(self) -> bytes:
        amplitude = int(32767 * self.noise_level)
        output = bytearray()
        for _ in range(self.samples_per_frame * self.channels):
            sample = self._random.randint(-amplitude, amplitude) if amplitude else 0
            output.extend(sample.to_bytes(2, "little", signed=True))
        return bytes(output)
