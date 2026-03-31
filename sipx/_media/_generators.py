"""
Audio generators for testing, tone signaling, and media placeholders.

Provides an ``AudioGenerator`` ABC and concrete implementations for
sine tones, silence, white noise, and DTMF dual-tone audio.
"""

from __future__ import annotations

import math
import random
import struct
from abc import ABC, abstractmethod


# ============================================================================
# Base Class
# ============================================================================


class AudioGenerator(ABC):
    """Abstract base class for PCM audio generators.

    All generators produce 16-bit signed little-endian PCM samples.
    """

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Sample rate in Hz."""
        ...

    @abstractmethod
    def generate(self, duration_ms: int) -> bytes:
        """Generate PCM audio for the given duration.

        Args:
            duration_ms: Duration in milliseconds.

        Returns:
            Raw 16-bit signed little-endian PCM bytes.
        """
        ...


# ============================================================================
# Tone Generator
# ============================================================================


class ToneGenerator(AudioGenerator):
    """Generate a pure sine-wave tone.

    Args:
        freq: Frequency in Hz (default 440).
        sample_rate: Sample rate in Hz (default 8000).
        amplitude: Amplitude factor 0.0-1.0 (default 0.5).
    """

    def __init__(
        self,
        freq: int = 440,
        sample_rate: int = 8000,
        amplitude: float = 0.5,
    ) -> None:
        self._freq = freq
        self._sample_rate = sample_rate
        self._amplitude = amplitude

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(self, duration_ms: int) -> bytes:
        samples = int(self._sample_rate * duration_ms / 1000)
        max_val = int(32767 * self._amplitude)
        pcm = bytearray()
        for i in range(samples):
            val = int(
                max_val * math.sin(2 * math.pi * self._freq * i / self._sample_rate)
            )
            pcm.extend(struct.pack("<h", val))
        return bytes(pcm)


# ============================================================================
# Silence Generator
# ============================================================================


class SilenceGenerator(AudioGenerator):
    """Generate digital silence (all-zero PCM samples).

    Args:
        sample_rate: Sample rate in Hz (default 8000).
    """

    def __init__(self, sample_rate: int = 8000) -> None:
        self._sample_rate = sample_rate

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(self, duration_ms: int) -> bytes:
        return b"\x00\x00" * int(self._sample_rate * duration_ms / 1000)


# ============================================================================
# Noise Generator
# ============================================================================


class NoiseGenerator(AudioGenerator):
    """Generate white noise.

    Args:
        sample_rate: Sample rate in Hz (default 8000).
        amplitude: Amplitude factor 0.0-1.0 (default 0.3).
    """

    def __init__(self, sample_rate: int = 8000, amplitude: float = 0.3) -> None:
        self._sample_rate = sample_rate
        self._amplitude = amplitude

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(self, duration_ms: int) -> bytes:
        samples = int(self._sample_rate * duration_ms / 1000)
        max_val = int(32767 * self._amplitude)
        pcm = bytearray()
        for _ in range(samples):
            pcm.extend(struct.pack("<h", random.randint(-max_val, max_val)))
        return bytes(pcm)


# ============================================================================
# DTMF Tone Generator
# ============================================================================


class DTMFToneGenerator(AudioGenerator):
    """Generate DTMF dual-tone audio (not RFC 4733 events).

    Produces the actual analog dual-frequency tones used in telephone
    signaling.  For in-band RTP DTMF events, use ``DTMFSender`` instead.

    Args:
        sample_rate: Sample rate in Hz (default 8000).
        amplitude: Amplitude factor 0.0-1.0 (default 0.4).
    """

    FREQS: dict[str, tuple[int, int]] = {
        "1": (697, 1209),
        "2": (697, 1336),
        "3": (697, 1477),
        "A": (697, 1633),
        "4": (770, 1209),
        "5": (770, 1336),
        "6": (770, 1477),
        "B": (770, 1633),
        "7": (852, 1209),
        "8": (852, 1336),
        "9": (852, 1477),
        "C": (852, 1633),
        "*": (941, 1209),
        "0": (941, 1336),
        "#": (941, 1477),
        "D": (941, 1633),
    }

    def __init__(self, sample_rate: int = 8000, amplitude: float = 0.4) -> None:
        self._sample_rate = sample_rate
        self._amplitude = amplitude

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def generate(self, duration_ms: int = 160) -> bytes:
        """Generate DTMF tone for digit ``'0'`` (default)."""
        return self.generate_digit("0", duration_ms)

    def generate_digit(self, digit: str, duration_ms: int = 160) -> bytes:
        """Generate a DTMF dual-tone for a specific digit.

        Args:
            digit: DTMF digit ('0'-'9', '*', '#', 'A'-'D').
            duration_ms: Tone duration in milliseconds (default 160).

        Returns:
            Raw 16-bit signed little-endian PCM bytes.
        """
        freqs = self.FREQS.get(digit.upper(), (697, 1209))
        samples = int(self._sample_rate * duration_ms / 1000)
        max_val = int(32767 * self._amplitude)
        pcm = bytearray()
        for i in range(samples):
            t = i / self._sample_rate
            val = int(
                max_val
                * (
                    math.sin(2 * math.pi * freqs[0] * t)
                    + math.sin(2 * math.pi * freqs[1] * t)
                )
                / 2
            )
            val = max(-32767, min(32767, val))
            pcm.extend(struct.pack("<h", val))
        return bytes(pcm)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "AudioGenerator",
    "ToneGenerator",
    "SilenceGenerator",
    "NoiseGenerator",
    "DTMFToneGenerator",
]
