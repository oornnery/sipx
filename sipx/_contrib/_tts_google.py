"""
Google Cloud Text-to-Speech adapter (stub).

This module provides the adapter interface but does **not** include the
Google Cloud SDK.  Install it separately::

    pip install google-cloud-texttospeech
"""

from __future__ import annotations

from sipx._media._tts import BaseTTS


class GoogleTTS(BaseTTS):
    """
    Google Cloud TTS adapter (stub).

    Args:
        language: BCP-47 language code (default ``"en-US"``).
        credentials_path: Optional path to a service-account JSON file.
    """

    def __init__(
        self,
        language: str = "en-US",
        credentials_path: str | None = None,
    ) -> None:
        self._language = language
        self._credentials_path = credentials_path

    @property
    def language(self) -> str:
        return self._language

    def synthesize(self, text: str) -> bytes:
        """Raise ``ImportError`` — the Google Cloud SDK is not installed."""
        raise ImportError("pip install google-cloud-texttospeech")
