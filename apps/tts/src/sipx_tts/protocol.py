from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from sipx import AudioFrame


class TtsEngine(Protocol):
    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        sample_rate: int,
    ) -> AsyncIterator[AudioFrame]: ...
