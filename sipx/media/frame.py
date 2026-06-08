from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AudioSource = Literal["rtp", "tts", "file", "tone", "silence", "websocket"]


@dataclass(slots=True)
class AudioFrame:
    pcm: memoryview
    sample_rate: int
    channels: int
    duration_ms: int
    timestamp_ns: int
    source: AudioSource

    def __post_init__(self) -> None:
        self.pcm = memoryview(self.pcm)
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
