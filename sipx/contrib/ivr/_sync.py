"""Synchronous IVR controller."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from sipx.media._audio import AudioPlayer
from sipx.media._dtmf import DTMFCollector
from sipx.media._tts import BaseTTS

from ._models import Menu, Prompt

if TYPE_CHECKING:
    from sipx.media._rtp import RTPSession

logger = logging.getLogger(__name__)


class IVR:
    """Sync IVR controller using RTPSession + TTS + DTMF."""

    def __init__(self, rtp_session: RTPSession, tts: Optional[BaseTTS] = None, dtmf_collector: Optional[DTMFCollector] = None) -> None:
        self.rtp_session = rtp_session
        self.tts = tts
        self._player = AudioPlayer(rtp_session)
        self._dtmf_collector = dtmf_collector or DTMFCollector(rtp_session, max_digits=1)
        self._on_call_start: list[Callable] = []
        self._on_call_end: list[Callable] = []

    def on_call_start(self, callback: Callable) -> None:
        self._on_call_start.append(callback)

    def on_call_end(self, callback: Callable) -> None:
        self._on_call_end.append(callback)

    def play_prompt(self, prompt: Prompt) -> None:
        if prompt.audio_file:
            self._player.play_file(prompt.audio_file)
        elif prompt.text and self.tts is not None:
            pcm = self.tts.synthesize(prompt.text)
            if pcm:
                self._player.play_pcm(pcm)

    def collect_digit(self, timeout: float = 5.0) -> str:
        collector = DTMFCollector(self.rtp_session, max_digits=1, timeout=timeout)
        return collector.collect()

    def run_menu(self, menu: Menu) -> None:
        for cb in self._on_call_start:
            cb()
        try:
            self._run_menu_loop(menu)
        finally:
            for cb in self._on_call_end:
                cb()

    def _run_menu_loop(self, menu: Menu) -> None:
        retries = 0
        while retries <= menu.max_retries:
            self.play_prompt(menu.greeting)
            digit = self.collect_digit(timeout=menu.greeting.timeout)
            if not digit:
                retries += 1
                continue
            item = menu._item_map.get(digit)
            if item is None:
                self.play_prompt(menu.invalid_prompt)
                retries += 1
                continue
            self.play_prompt(item.prompt)
            if item.handler is not None:
                item.handler()
            if item.submenu is not None:
                self._run_menu_loop(item.submenu)
            return
