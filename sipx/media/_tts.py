"""
Text-to-Speech adapter interfaces.

Provides a base class for TTS engines and a file-based reference implementation
that maps text keys to pre-recorded WAV files.
"""

from __future__ import annotations

import wave
from abc import ABC, abstractmethod


class BaseTTS(ABC):
    """Abstract base class for text-to-speech adapters."""

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Convert text to PCM audio.

        Args:
            text: Text string (or lookup key) to synthesize.

        Returns:
            Raw 16-bit signed little-endian PCM audio bytes at
            ``sample_rate`` Hz, mono.
        """

    @property
    def language(self) -> str:
        """Language code for this TTS engine (e.g. 'en-US')."""
        return "en-US"

    @property
    def sample_rate(self) -> int:
        """Sample rate in Hz (default 8000 for telephony)."""
        return 8000


class FileTTS(BaseTTS):
    """
    File-based TTS that maps text keys to pre-recorded WAV files.

    This is a reference implementation useful for IVR systems that use
    a fixed set of prompts recorded as WAV files.

    Args:
        prompts: Mapping of text keys to WAV file paths.
                 Each WAV file must be 8 kHz, 16-bit, mono.
    """

    def __init__(self, prompts: dict[str, str]) -> None:
        self._prompts = dict(prompts)

    def synthesize(self, text: str) -> bytes:
        """
        Look up the WAV file for *text* and return its PCM data.

        Args:
            text: Key into the prompts dictionary.

        Returns:
            Raw PCM bytes from the WAV file, or empty bytes if
            the key is not found.
        """
        path = self._prompts.get(text)
        if path is None:
            return b""

        with wave.open(path, "rb") as wf:
            return wf.readframes(wf.getnframes())
