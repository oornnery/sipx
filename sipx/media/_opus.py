"""
Opus codec (RFC 6716) — wideband audio.

Optional dependency: pip install opuslib

Opus supports:
  - 8kHz to 48kHz sample rates
  - 6 kbit/s to 510 kbit/s bitrate
  - Payload type 111 (dynamic, negotiated via SDP)
"""

from __future__ import annotations

from ._codecs import Codec


class Opus(Codec):
    """Opus codec wrapper. Requires `opuslib` package.

    Usage::

        from sipx.media import Opus
        codec = Opus(sample_rate=48000, channels=1)
        encoded = codec.encode(pcm_data)
        decoded = codec.decode(encoded)
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        channels: int = 1,
        bitrate: int = 64000,
        payload_type_value: int = 111,
    ):
        self._sample_rate = sample_rate
        self._channels = channels
        self._bitrate = bitrate
        self._payload_type_value = payload_type_value
        self._encoder = None
        self._decoder = None

    def _ensure_encoder(self):
        if self._encoder is None:
            try:
                import opuslib
            except ImportError:
                raise ImportError(
                    "Opus codec requires 'opuslib'. Install with: pip install opuslib"
                )
            self._encoder = opuslib.Encoder(
                self._sample_rate, self._channels, opuslib.APPLICATION_VOIP
            )
            self._encoder.bitrate = self._bitrate

    def _ensure_decoder(self):
        if self._decoder is None:
            try:
                import opuslib
            except ImportError:
                raise ImportError(
                    "Opus codec requires 'opuslib'. Install with: pip install opuslib"
                )
            self._decoder = opuslib.Decoder(self._sample_rate, self._channels)

    @property
    def name(self) -> str:
        return "opus"

    @property
    def payload_type(self) -> int:
        return self._payload_type_value

    @property
    def clock_rate(self) -> int:
        return self._sample_rate

    @property
    def sample_size(self) -> int:
        return 2  # 16-bit PCM input

    def encode(self, pcm: bytes) -> bytes:
        """Encode 16-bit PCM to Opus.

        Args:
            pcm: 16-bit signed little-endian PCM audio.
                 Must be a valid Opus frame size (2.5, 5, 10, 20, 40, 60 ms).

        Returns:
            Opus encoded bytes.
        """
        self._ensure_encoder()
        # Calculate frame size in samples
        frame_size = len(pcm) // (2 * self._channels)
        return self._encoder.encode(pcm, frame_size)

    def decode(self, data: bytes) -> bytes:
        """Decode Opus to 16-bit PCM.

        Args:
            data: Opus encoded frame.

        Returns:
            16-bit signed little-endian PCM audio.
        """
        self._ensure_decoder()
        # Default frame size: 20ms
        frame_size = self._sample_rate // 50  # 960 samples for 48kHz
        return self._decoder.decode(data, frame_size)


__all__ = ["Opus"]
