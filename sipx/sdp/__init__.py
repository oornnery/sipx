"""SDP (Session Description Protocol) modeling and offer/answer.

Aggregates the SDP data model, a text parser, and RFC 3264 offer/answer
helpers for negotiating audio media (G.711 plus optional telephone-event)
carried in SIP message bodies.

References:
    RFC 4566 - SDP: Session Description Protocol
    RFC 3264 - An Offer/Answer Model with the Session Description Protocol
"""

from sipx.sdp.model import AudioMedia, SdpCodec, SdpDirection, SessionDescription
from sipx.sdp.offer_answer import (
    SdpNegotiationError,
    create_audio_offer,
    create_audio_answer,
)
from sipx.sdp.parser import parse_sdp

__all__ = [
    "AudioMedia",
    "SdpCodec",
    "SdpDirection",
    "SdpNegotiationError",
    "SessionDescription",
    "create_audio_answer",
    "create_audio_offer",
    "parse_sdp",
]
