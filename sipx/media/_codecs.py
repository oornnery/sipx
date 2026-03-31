"""
G.711 Codec implementations (PCMU / PCMA).

Pure Python mu-law and A-law codecs per ITU-T G.711.
No external dependencies — lookup tables are used for fast encode/decode.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, List


class Codec(ABC):
    """Abstract base class for audio codecs."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Codec name (e.g. 'PCMU')."""
        ...

    @property
    @abstractmethod
    def payload_type(self) -> int:
        """RTP payload type number."""
        ...

    @property
    @abstractmethod
    def clock_rate(self) -> int:
        """Clock rate in Hz."""
        ...

    @property
    @abstractmethod
    def sample_size(self) -> int:
        """Encoded bytes per sample."""
        ...

    @abstractmethod
    def encode(self, pcm: bytes) -> bytes:
        """Encode 16-bit signed linear PCM to codec format."""
        ...

    @abstractmethod
    def decode(self, data: bytes) -> bytes:
        """Decode codec format to 16-bit signed linear PCM."""
        ...


# ---------------------------------------------------------------------------
# Mu-law (G.711 mu-law, PCMU) — ITU-T G.711 Section 2
# ---------------------------------------------------------------------------

_MULAW_BIAS = 33
_MULAW_CLIP = 32635


def _build_mulaw_encode_table() -> List[int]:
    """Build a 65536-entry table mapping signed 16-bit PCM → 8-bit mu-law."""
    table: List[int] = [0] * 65536

    for i in range(65536):
        # Interpret as signed 16-bit
        sample = i if i < 32768 else i - 65536

        sign = 0
        if sample < 0:
            sign = 0x80
            sample = -sample

        sample = min(sample, _MULAW_CLIP)
        sample += _MULAW_BIAS

        # Find segment (exponent)
        exponent = 7
        mask = 0x4000
        while exponent > 0 and not (sample & mask):
            exponent -= 1
            mask >>= 1

        mantissa = (sample >> (exponent + 3)) & 0x0F
        mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
        table[i] = mulaw_byte

    return table


def _build_mulaw_decode_table() -> List[int]:
    """Build a 256-entry table mapping 8-bit mu-law → signed 16-bit PCM."""
    table: List[int] = [0] * 256

    for i in range(256):
        complement = ~i & 0xFF
        sign = complement & 0x80
        exponent = (complement >> 4) & 0x07
        mantissa = complement & 0x0F

        magnitude = ((mantissa << 1) + 1 + 32) << (exponent + 2)
        magnitude -= _MULAW_BIAS

        sample = -magnitude if sign else magnitude
        # Clamp to 16-bit range
        sample = max(-32768, min(32767, sample))
        table[i] = sample

    return table


class PCMU(Codec):
    """G.711 mu-law codec (payload type 0)."""

    _encode_table: ClassVar[List[int]] = _build_mulaw_encode_table()
    _decode_table: ClassVar[List[int]] = _build_mulaw_decode_table()

    @property
    def name(self) -> str:
        return "PCMU"

    @property
    def payload_type(self) -> int:
        return 0

    @property
    def clock_rate(self) -> int:
        return 8000

    @property
    def sample_size(self) -> int:
        return 1

    def encode(self, pcm: bytes) -> bytes:
        """Encode 16-bit signed LE PCM to 8-bit mu-law."""
        table = self._encode_table
        n_samples = len(pcm) // 2
        out = bytearray(n_samples)
        for i in range(n_samples):
            # Read little-endian signed 16-bit
            lo = pcm[2 * i]
            hi = pcm[2 * i + 1]
            idx = lo | (hi << 8)  # unsigned 16-bit index
            out[i] = table[idx]
        return bytes(out)

    def decode(self, data: bytes) -> bytes:
        """Decode 8-bit mu-law to 16-bit signed LE PCM."""
        table = self._decode_table
        out = bytearray(len(data) * 2)
        for i, byte in enumerate(data):
            sample = table[byte]
            out[2 * i] = sample & 0xFF
            out[2 * i + 1] = (sample >> 8) & 0xFF
        return bytes(out)


# ---------------------------------------------------------------------------
# A-law (G.711 A-law, PCMA) — ITU-T G.711 Section 3
# ---------------------------------------------------------------------------


def _build_alaw_encode_table() -> List[int]:
    """Build a 65536-entry table mapping signed 16-bit PCM → 8-bit A-law."""
    table: List[int] = [0] * 65536

    for i in range(65536):
        sample = i if i < 32768 else i - 65536

        sign = 0
        if sample < 0:
            sign = 0x80
            sample = -sample

        if sample > 32767:
            sample = 32767

        if sample >= 256:
            exponent = 7
            mask = 0x4000
            while exponent > 1 and not (sample & mask):
                exponent -= 1
                mask >>= 1
            mantissa = (sample >> (exponent + 3)) & 0x0F
            alaw_byte = (exponent << 4) | mantissa
        else:
            alaw_byte = sample >> 4

        alaw_byte = (sign | alaw_byte) ^ 0x55
        table[i] = alaw_byte

    return table


def _build_alaw_decode_table() -> List[int]:
    """Build a 256-entry table mapping 8-bit A-law → signed 16-bit PCM."""
    table: List[int] = [0] * 256

    for i in range(256):
        value = i ^ 0x55
        sign = value & 0x80
        exponent = (value >> 4) & 0x07
        mantissa = value & 0x0F

        if exponent == 0:
            magnitude = (mantissa << 4) + 8
        else:
            magnitude = ((mantissa << 1) + 1 + 32) << (exponent + 2)

        sample = -magnitude if sign else magnitude
        sample = max(-32768, min(32767, sample))
        table[i] = sample

    return table


class PCMA(Codec):
    """G.711 A-law codec (payload type 8)."""

    _encode_table: ClassVar[List[int]] = _build_alaw_encode_table()
    _decode_table: ClassVar[List[int]] = _build_alaw_decode_table()

    @property
    def name(self) -> str:
        return "PCMA"

    @property
    def payload_type(self) -> int:
        return 8

    @property
    def clock_rate(self) -> int:
        return 8000

    @property
    def sample_size(self) -> int:
        return 1

    def encode(self, pcm: bytes) -> bytes:
        """Encode 16-bit signed LE PCM to 8-bit A-law."""
        table = self._encode_table
        n_samples = len(pcm) // 2
        out = bytearray(n_samples)
        for i in range(n_samples):
            lo = pcm[2 * i]
            hi = pcm[2 * i + 1]
            idx = lo | (hi << 8)
            out[i] = table[idx]
        return bytes(out)

    def decode(self, data: bytes) -> bytes:
        """Decode 8-bit A-law to 16-bit signed LE PCM."""
        table = self._decode_table
        out = bytearray(len(data) * 2)
        for i, byte in enumerate(data):
            sample = table[byte]
            out[2 * i] = sample & 0xFF
            out[2 * i + 1] = (sample >> 8) & 0xFF
        return bytes(out)
