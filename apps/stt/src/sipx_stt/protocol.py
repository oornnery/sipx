from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from sipx import AudioFrame


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    text: str
    is_final: bool
    timestamp_ns: int
    confidence: float | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def kind(self) -> Literal["partial", "final"]:
        return "final" if self.is_final else "partial"


class SttStream(Protocol):
    async def push_audio(self, frame: AudioFrame) -> None: ...

    def events(self) -> AsyncIterator[TranscriptEvent]: ...

    async def close(self) -> None: ...


class SttEngine(Protocol):
    async def start(self, *, sample_rate: int, language: str) -> SttStream: ...
