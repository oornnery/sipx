"""
PyAudio integration — microphone capture and speaker playback.

Optional dependency: pip install pyaudio

Bridges hardware audio I/O with RTP sessions for softphone mode.

Usage::

    from sipx.media import MicrophoneSource, SpeakerSink

    # Capture mic and send via RTP
    mic = MicrophoneSource(rtp_session)
    mic.start()
    # ... call active ...
    mic.stop()

    # Receive RTP and play through speakers
    speaker = SpeakerSink(rtp_session)
    speaker.start()
    # ... call active ...
    speaker.stop()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._rtp import RTPSession


def _import_pyaudio():
    try:
        import pyaudio

        return pyaudio
    except ImportError:
        raise ImportError(
            "PyAudio integration requires 'pyaudio'. Install with: pip install pyaudio"
        )


class MicrophoneSource:
    """Captures audio from microphone and sends via RTP.

    Args:
        rtp_session: RTP session to send audio through.
        sample_rate: Audio sample rate (default: 8000 for G.711).
        channels: Number of channels (default: 1 mono).
        chunk_size: Samples per read (default: 160 = 20ms at 8kHz).
    """

    def __init__(
        self,
        rtp_session: RTPSession,
        sample_rate: int = 8000,
        channels: int = 1,
        chunk_size: int = 160,
    ):
        self.rtp_session = rtp_session
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._stream = None
        self._pa = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start capturing from microphone and sending via RTP."""
        if self._running:
            return

        pyaudio = _import_pyaudio()
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop microphone capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def _capture_loop(self):
        """Read from mic, send as RTP."""
        while self._running and self._stream:
            try:
                pcm = self._stream.read(self.chunk_size, exception_on_overflow=False)
                self.rtp_session.send_audio(pcm)
            except Exception:
                break

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


class SpeakerSink:
    """Receives RTP audio and plays through speakers.

    Args:
        rtp_session: RTP session to receive audio from.
        sample_rate: Audio sample rate (default: 8000).
        channels: Number of channels (default: 1 mono).
        chunk_size: Samples per write (default: 160 = 20ms at 8kHz).
    """

    def __init__(
        self,
        rtp_session: RTPSession,
        sample_rate: int = 8000,
        channels: int = 1,
        chunk_size: int = 160,
    ):
        self.rtp_session = rtp_session
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._stream = None
        self._pa = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start receiving RTP and playing through speakers."""
        if self._running:
            return

        pyaudio = _import_pyaudio()
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
        )

        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop speaker playback."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def _playback_loop(self):
        """Receive RTP, decode, play."""
        while self._running and self._stream:
            try:
                pcm = self.rtp_session.recv_audio(timeout=0.5)
                if pcm:
                    self._stream.write(pcm)
            except Exception:
                continue

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


__all__ = ["MicrophoneSource", "SpeakerSink"]
