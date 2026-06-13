"""RTP media plane: packets, codecs, jitter buffering, and statistics.

Aggregates the RTP packet model, G.711 (PCMU/PCMA) codecs, RFC 4733 DTMF
events, an async G.711 audio session, a playout jitter buffer, and reception
statistics (loss/jitter). The media plane only; SIP signaling is elsewhere.

References:
    RFC 3550 - RTP: A Transport Protocol for Real-Time Applications
    RFC 3551 - RTP Profile for Audio and Video Conferences (PCMU=0, PCMA=8)
    RFC 4733 - RTP Payload for DTMF Digits, Telephony Tones, and Signals
    ITU-T G.711 - PCM of voice frequencies
"""

from sipx.rtp.buffer import RtpJitterBuffer, RtpJitterBufferSnapshot, RtpPlayoutFrame
from sipx.rtp.audio import (
    RtpAudioMode,
    RtpAudioSession,
    RtpAudioSessionConfig,
    RtpAudioSessionSnapshot,
    RtpWireDirection,
    RtpWireEvent,
)
from sipx.rtp.dtmf import DtmfEvent, decode_dtmf_event, encode_dtmf_event
from sipx.rtp.g711 import (
    G711_CHANNELS,
    G711_SAMPLE_RATE,
    G711Error,
    decode_g711,
    decode_pcma,
    decode_pcmu,
    encode_g711,
    encode_pcma,
    encode_pcmu,
)
from sipx.rtp.packet import RtpPacket, RtpParseError
from sipx.rtp.stats import (
    RtpMetrics,
    RtpMetricsSnapshot,
    RtpSequenceStats,
    RtpStatsSnapshot,
)

__all__ = [
    "DtmfEvent",
    "G711_CHANNELS",
    "G711_SAMPLE_RATE",
    "G711Error",
    "RtpJitterBuffer",
    "RtpJitterBufferSnapshot",
    "RtpAudioMode",
    "RtpAudioSession",
    "RtpAudioSessionConfig",
    "RtpAudioSessionSnapshot",
    "RtpMetrics",
    "RtpMetricsSnapshot",
    "RtpPacket",
    "RtpParseError",
    "RtpPlayoutFrame",
    "RtpSequenceStats",
    "RtpStatsSnapshot",
    "RtpWireDirection",
    "RtpWireEvent",
    "decode_g711",
    "decode_dtmf_event",
    "decode_pcma",
    "decode_pcmu",
    "encode_g711",
    "encode_dtmf_event",
    "encode_pcma",
    "encode_pcmu",
]
