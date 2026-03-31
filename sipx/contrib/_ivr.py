"""
IVR (Interactive Voice Response) builder.

Provides a callback-driven IVR system with nested menu support,
built on top of sipx RTP sessions, TTS adapters, and DTMF collection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from sipx.media._audio import AudioPlayer
from sipx.media._dtmf import DTMFCollector
from sipx.media._tts import BaseTTS

if TYPE_CHECKING:
    from sipx.media._rtp import RTPSession

logger = logging.getLogger(__name__)


# ============================================================================
# Data structures
# ============================================================================


@dataclass
class Prompt:
    """
    A prompt to play to the caller.

    Either ``text`` is synthesized via TTS, or ``audio_file`` is played
    directly.  If both are provided, ``audio_file`` takes precedence.

    Args:
        text: Text to speak (or TTS lookup key).
        audio_file: Optional path to a pre-recorded WAV file.
        timeout: Seconds to wait for input after the prompt finishes.
    """

    text: str = ""
    audio_file: Optional[str] = None
    timeout: float = 5.0


@dataclass
class MenuItem:
    """
    A single option in an IVR menu, activated by a DTMF digit.

    Args:
        digit: DTMF digit that selects this item ('0'-'9', '*', '#').
        prompt: What to say when this item is selected.
        handler: Optional callback invoked when the item is selected.
        submenu: Optional nested ``Menu`` to enter after selection.
    """

    digit: str = ""
    prompt: Prompt = field(default_factory=Prompt)
    handler: Optional[Callable[[], None]] = None
    submenu: Optional[Menu] = None


class Menu:
    """
    An IVR menu with a greeting, selectable items, and retry logic.

    Args:
        greeting: Prompt played when the menu starts.
        items: List of ``MenuItem`` options.
        invalid_prompt: Prompt played when an unrecognized digit is pressed.
        max_retries: Maximum number of times to replay after invalid input.
    """

    def __init__(
        self,
        greeting: Prompt,
        items: Optional[list[MenuItem]] = None,
        invalid_prompt: Optional[Prompt] = None,
        max_retries: int = 3,
    ) -> None:
        self.greeting = greeting
        self.items: list[MenuItem] = list(items) if items else []
        self.invalid_prompt = invalid_prompt or Prompt(
            text="Invalid selection. Please try again."
        )
        self.max_retries = max_retries
        self._item_map: dict[str, MenuItem] = {item.digit: item for item in self.items}

    def add_item(
        self,
        digit: str,
        prompt: Prompt,
        handler: Optional[Callable[[], None]] = None,
        submenu: Optional[Menu] = None,
    ) -> None:
        """
        Add a menu item.

        Args:
            digit: DTMF digit ('0'-'9', '*', '#').
            prompt: Prompt to play when this item is selected.
            handler: Optional callback function.
            submenu: Optional nested menu.
        """
        item = MenuItem(digit=digit, prompt=prompt, handler=handler, submenu=submenu)
        self.items.append(item)
        self._item_map[digit] = item


# ============================================================================
# IVR controller
# ============================================================================


class IVR:
    """
    IVR controller that drives menus over an RTP session.

    Combines TTS synthesis, audio playback, and DTMF collection to run
    interactive voice menus.

    Args:
        rtp_session: Active ``RTPSession`` for media I/O.
        tts: Optional TTS adapter for synthesizing prompts.
        dtmf_collector: Optional pre-configured ``DTMFCollector``.
            If *None*, one is created from *rtp_session* with
            ``max_digits=1``.
    """

    def __init__(
        self,
        rtp_session: RTPSession,
        tts: Optional[BaseTTS] = None,
        dtmf_collector: Optional[DTMFCollector] = None,
    ) -> None:
        self.rtp_session = rtp_session
        self.tts = tts
        self._player = AudioPlayer(rtp_session)
        self._dtmf_collector = dtmf_collector or DTMFCollector(
            rtp_session, max_digits=1
        )
        self._on_call_start: list[Callable[[], None]] = []
        self._on_call_end: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------

    def on_call_start(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when the IVR session starts."""
        self._on_call_start.append(callback)

    def on_call_end(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when the IVR session ends."""
        self._on_call_end.append(callback)

    # ------------------------------------------------------------------
    # Prompt / digit helpers
    # ------------------------------------------------------------------

    def play_prompt(self, prompt: Prompt) -> None:
        """
        Play a prompt to the caller.

        If ``prompt.audio_file`` is set, the WAV file is played directly.
        Otherwise ``prompt.text`` is synthesized via the configured TTS
        adapter and the resulting PCM is sent over RTP.

        Args:
            prompt: The ``Prompt`` to play.
        """
        if prompt.audio_file:
            self._player.play_file(prompt.audio_file)
        elif prompt.text and self.tts is not None:
            pcm = self.tts.synthesize(prompt.text)
            if pcm:
                self._player.play_pcm(pcm)
        else:
            logger.warning(
                "Cannot play prompt: no audio_file and no TTS adapter configured"
            )

    def collect_digit(self, timeout: float = 5.0) -> str:
        """
        Collect a single DTMF digit from the caller.

        Args:
            timeout: Seconds to wait for a digit.

        Returns:
            The digit string (e.g. ``"1"``), or empty string on timeout.
        """
        collector = DTMFCollector(self.rtp_session, max_digits=1, timeout=timeout)
        return collector.collect()

    # ------------------------------------------------------------------
    # Menu runner
    # ------------------------------------------------------------------

    def run_menu(self, menu: Menu) -> None:
        """
        Run an IVR menu loop.

        Plays the greeting, collects a digit, and dispatches to the
        matching ``MenuItem``.  If the item has a handler, it is called.
        If the item has a submenu, ``run_menu`` recurses into it.
        On invalid input the ``invalid_prompt`` is played and the menu
        retries up to ``max_retries`` times.

        Args:
            menu: The ``Menu`` to run.
        """
        for callback in self._on_call_start:
            callback()

        try:
            self._run_menu_loop(menu)
        finally:
            for callback in self._on_call_end:
                callback()

    def _run_menu_loop(self, menu: Menu) -> None:
        """Internal menu loop (no lifecycle callbacks)."""
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

            # Valid selection
            self.play_prompt(item.prompt)

            if item.handler is not None:
                item.handler()

            if item.submenu is not None:
                self._run_menu_loop(item.submenu)

            return

        logger.info("IVR menu exhausted max retries (%d)", menu.max_retries)
