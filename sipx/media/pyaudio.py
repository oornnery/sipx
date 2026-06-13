"""Optional microphone capture source backed by PyAudio.

Wraps the optional ``pyaudio`` dependency to read linear 16-bit PCM
``AudioFrame`` chunks from a local input device for transmission over RTP.
Raises ``PyAudioError`` when the dependency is missing so callers can fall
back to synthetic audio.

References:
    RFC 3550 - RTP (captured PCM is encoded and sent as RTP)
    ITU-T G.711 - PCM of voice frequencies (sample format)
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from sipx.media.frame import AudioFrame


class PyAudioError(RuntimeError):
    pass


class PyAudioInputSource:
    def __init__(
        self,
        *,
        sample_rate: int = 8000,
        channels: int = 1,
        frame_duration_ms: int = 20,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if channels <= 0:
            raise ValueError("channels must be positive")
        if frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration_ms = frame_duration_ms
        self._pyaudio: Any | None = None
        self._stream: Any | None = None

    def start(self) -> PyAudioInputSource:
        module = _pyaudio_module()
        self._pyaudio = module.PyAudio()
        self._stream = self._pyaudio.open(
            format=module.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.samples_per_frame,
        )
        return self

    @property
    def samples_per_frame(self) -> int:
        return self.sample_rate * self.frame_duration_ms // 1000

    def next_frame(self) -> AudioFrame:
        if self._stream is None:
            raise PyAudioError("PyAudio input source is not started")
        pcm = self._stream.read(
            self.samples_per_frame,
            exception_on_overflow=False,
        )
        return AudioFrame(
            pcm=pcm,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration_ms=self.frame_duration_ms,
            timestamp_ns=time.monotonic_ns(),
            source="pyaudio",
        )

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio is not None:
            self._pyaudio.terminate()
            self._pyaudio = None

    def __enter__(self) -> PyAudioInputSource:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        self.close()


def ensure_pyaudio_available() -> None:
    _pyaudio_module()


def _pyaudio_module() -> Any:
    try:
        return importlib.import_module("pyaudio")
    except ImportError as exc:
        raise PyAudioError(
            "PyAudio audio mode requires optional dependency 'pyaudio'"
        ) from exc
