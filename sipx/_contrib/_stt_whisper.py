"""
OpenAI Whisper STT adapter (stub).

This module provides the adapter interface but does **not** include the
Whisper library.  Install it separately::

    pip install openai-whisper
"""

from __future__ import annotations

from sipx._media._stt import BaseSTT


class WhisperSTT(BaseSTT):
    """
    OpenAI Whisper STT adapter (stub).

    Args:
        model: Whisper model size (default ``"base"``).
    """

    def __init__(self, model: str = "base") -> None:
        self._model = model

    def transcribe(self, audio: bytes) -> str:
        """Raise ``ImportError`` — the Whisper library is not installed."""
        raise ImportError(
            "pip install openai-whisper"
        )
