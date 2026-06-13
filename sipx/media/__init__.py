"""Audio media primitives for the RTP media plane.

Aggregates PCM frame types and audio sources (synthetic silence/noise and
optional PyAudio capture) plus the ``MediaPort`` protocol and barge-in
policy. These feed encoded audio into RTP sessions (see ``sipx.rtp``).

References:
    RFC 3550 - RTP: A Transport Protocol for Real-Time Applications
"""

from sipx.media.barge import BargeInPolicy, BargeInSignal
from sipx.media.frame import AudioFrame, AudioSource
from sipx.media.ports import MediaPort
from sipx.media.pyaudio import (
    PyAudioError,
    PyAudioInputSource,
    ensure_pyaudio_available,
)
from sipx.media.synthetic import SyntheticAudioMode, SyntheticAudioSource

__all__ = [
    "AudioFrame",
    "AudioSource",
    "BargeInPolicy",
    "BargeInSignal",
    "MediaPort",
    "PyAudioError",
    "PyAudioInputSource",
    "SyntheticAudioMode",
    "SyntheticAudioSource",
    "ensure_pyaudio_available",
]
