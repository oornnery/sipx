from __future__ import annotations

from typing import Protocol

from sipx.media.frame import AudioFrame


class MediaPort(Protocol):
    async def recv_frame(self) -> AudioFrame: ...

    async def send_frame(self, frame: AudioFrame) -> None: ...

    async def close(self) -> None: ...
