"""PCM audio frame model for the media plane.

``AudioFrame`` wraps a buffer of linear 16-bit PCM samples with its sample
rate, channel count, duration, capture timestamp, and origin. It is the unit
exchanged between audio sources, codecs, and RTP sessions before G.711
encoding.

References:
    RFC 3550 §5.1 - RTP fixed header (timestamp carried per frame)
    ITU-T G.711 - PCM of voice frequencies (target encoding for frames)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AudioSource = Literal[
    "rtp", "generated", "file", "tone", "silence", "noise", "pyaudio", "websocket"
]


@dataclass(init=False, slots=True)
class AudioFrame:
    pcm: memoryview
    sample_rate: int
    channels: int
    duration_ms: int
    timestamp_ns: int
    source: AudioSource

    def __init__(
        self,
        *,
        pcm: bytes | bytearray | memoryview,
        sample_rate: int,
        channels: int,
        duration_ms: int,
        timestamp_ns: int,
        source: AudioSource,
    ) -> None:
        self.pcm = memoryview(pcm)
        self.sample_rate = sample_rate
        self.channels = channels
        self.duration_ms = duration_ms
        self.timestamp_ns = timestamp_ns
        self.source = source
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")

    @property
    def byte_length(self) -> int:
        return self.pcm.nbytes

    def to_dict(self) -> dict[str, int | str]:
        return {
            "byte_length": self.byte_length,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_ms": self.duration_ms,
            "timestamp_ns": self.timestamp_ns,
            "source": self.source,
        }
