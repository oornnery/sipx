"""
Speech-to-Text adapter interfaces.

Provides a base class for STT engines and a dummy reference implementation
useful for testing IVR flows without a real STT service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSTT(ABC):
    """Abstract base class for speech-to-text adapters."""

    @abstractmethod
    def transcribe(self, audio: bytes) -> str:
        """
        Convert PCM audio to text.

        Args:
            audio: Raw 16-bit signed little-endian PCM audio bytes
                   (8 kHz, mono).

        Returns:
            Transcribed text string.
        """


class DummySTT(BaseSTT):
    """
    Dummy STT adapter that always returns ``"hello"``.

    Useful for testing IVR flows without a real speech-to-text service.
    """

    def transcribe(self, audio: bytes) -> str:
        """Return ``"hello"`` regardless of input audio."""
        return "hello"
