"""
Audio I/O helpers using the stdlib ``wave`` module.

Provides simple WAV playback and recording over an RTPSession.
"""

from __future__ import annotations

import time
import wave
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._rtp import RTPSession


class AudioPlayer:
    """Play audio files or raw PCM through an RTP session."""

    def __init__(self, rtp_session: "RTPSession") -> None:
        self.rtp_session = rtp_session

    def play_file(self, path: str) -> None:
        """
        Read a WAV file and send its audio via RTP.

        The WAV file **must** be 8 kHz, 16-bit, mono (the standard
        telephony format).  A ``ValueError`` is raised otherwise.

        Args:
            path: Path to the WAV file.
        """
        with wave.open(path, "rb") as wf:
            if wf.getnchannels() != 1:
                raise ValueError(
                    f"WAV must be mono, got {wf.getnchannels()} channels"
                )
            if wf.getsampwidth() != 2:
                raise ValueError(
                    f"WAV must be 16-bit, got {wf.getsampwidth() * 8}-bit"
                )
            if wf.getframerate() != 8000:
                raise ValueError(
                    f"WAV must be 8000 Hz, got {wf.getframerate()} Hz"
                )

            pcm_data = wf.readframes(wf.getnframes())

        self.play_pcm(pcm_data, sample_rate=8000)

    def play_pcm(self, pcm_data: bytes, sample_rate: int = 8000) -> None:
        """
        Send raw 16-bit signed LE PCM data via RTP.

        Audio is packetized at 20 ms intervals by the underlying
        ``RTPSession.send_audio`` method.

        Args:
            pcm_data: Raw PCM audio bytes (16-bit signed LE).
            sample_rate: Sample rate in Hz (default 8000).
        """
        self.rtp_session.send_audio(pcm_data)


class AudioRecorder:
    """Record audio received from an RTP session."""

    def __init__(self, rtp_session: "RTPSession") -> None:
        self.rtp_session = rtp_session

    def record(self, duration: float) -> bytes:
        """
        Record RTP audio for *duration* seconds and return raw PCM.

        Args:
            duration: Recording length in seconds.

        Returns:
            16-bit signed LE PCM bytes.
        """
        chunks: list[bytes] = []
        deadline = time.monotonic() + duration

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            timeout = min(remaining, 0.5)
            pcm = self.rtp_session.recv_audio(timeout=timeout)
            if pcm is not None:
                chunks.append(pcm)

        return b"".join(chunks)

    def record_to_file(self, path: str, duration: float) -> None:
        """
        Record RTP audio and save as a WAV file (8 kHz, 16-bit, mono).

        Args:
            path: Output WAV file path.
            duration: Recording length in seconds.
        """
        pcm_data = self.record(duration)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(pcm_data)
