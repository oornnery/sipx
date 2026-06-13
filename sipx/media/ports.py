"""Media port protocol for bidirectional audio frame exchange.

Defines ``MediaPort``, a structural interface for objects that send and
receive ``AudioFrame`` instances and can be closed. Abstracts the RTP media
plane from higher-level audio logic.

References:
    RFC 3550 - RTP: A Transport Protocol for Real-Time Applications
"""

from __future__ import annotations

from typing import Protocol

from sipx.media.frame import AudioFrame


class MediaPort(Protocol):
    async def recv_frame(self) -> AudioFrame: ...

    async def send_frame(self, frame: AudioFrame) -> None: ...

    async def close(self) -> None: ...
