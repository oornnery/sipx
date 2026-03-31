"""Native async IVR controller using AsyncRTPSession."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from sipx.media._tts import BaseTTS

from ._models import Menu, Prompt

if TYPE_CHECKING:
    from sipx.media._async import AsyncRTPSession

logger = logging.getLogger(__name__)


class AsyncIVR:
    """Async IVR controller using AsyncRTPSession + TTS + DTMF.

    All I/O is non-blocking — uses ``await rtp.send_audio()``
    and ``await rtp.dtmf.collect()`` natively.
    """

    def __init__(
        self,
        rtp_session: AsyncRTPSession,
        tts: Optional[BaseTTS] = None,
    ) -> None:
        self.rtp_session = rtp_session
        self.tts = tts
        self._on_call_start: list[Callable] = []
        self._on_call_end: list[Callable] = []

    def on_call_start(self, callback: Callable) -> None:
        self._on_call_start.append(callback)

    def on_call_end(self, callback: Callable) -> None:
        self._on_call_end.append(callback)

    async def play_prompt(self, prompt: Prompt) -> None:
        """Play prompt via TTS or audio file (async)."""
        if prompt.audio_file:
            import wave
            with wave.open(prompt.audio_file, "rb") as wf:
                pcm = wf.readframes(wf.getnframes())
            await self.rtp_session.send_audio(pcm)
        elif prompt.text and self.tts is not None:
            pcm = self.tts.synthesize(prompt.text)
            if pcm:
                await self.rtp_session.send_audio(pcm)

    async def collect_digit(self, timeout: float = 5.0) -> str:
        """Collect single DTMF digit (async)."""
        return await self.rtp_session.dtmf.collect(max_digits=1, timeout=timeout)

    async def run_menu(self, menu: Menu) -> None:
        """Run IVR menu loop (async)."""
        for cb in self._on_call_start:
            cb()
        try:
            await self._run_menu_loop(menu)
        finally:
            for cb in self._on_call_end:
                cb()

    async def _run_menu_loop(self, menu: Menu) -> None:
        retries = 0
        while retries <= menu.max_retries:
            await self.play_prompt(menu.greeting)
            digit = await self.collect_digit(timeout=menu.greeting.timeout)
            if not digit:
                retries += 1
                continue
            item = menu._item_map.get(digit)
            if item is None:
                await self.play_prompt(menu.invalid_prompt)
                retries += 1
                continue
            await self.play_prompt(item.prompt)
            if item.handler is not None:
                item.handler()
            if item.submenu is not None:
                await self._run_menu_loop(item.submenu)
            return
