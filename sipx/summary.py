"""Human-readable summaries of SIP messages and SDP bodies.

Converts ``Request``/``Response`` objects and parsed SDP into flat,
JSON-serializable dataclasses for logging, debugging, and example output.
A presentation helper only; it does not alter protocol behavior.

References:
    RFC 3261 §7 - SIP Messages (summarized structure)
    RFC 4566 - SDP: Session Description Protocol (summarized media)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sipx.sdp import SessionDescription


@dataclass(frozen=True, slots=True)
class SipSdpSummary:
    connection_address: str | None
    audio_port: int
    direction: str
    codecs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SipRequestSummary:
    method: str
    uri: str
    headers: dict[str, str]
    body: str


@dataclass(frozen=True, slots=True)
class SipResponseSummary:
    status_code: int
    reason: str
    headers: dict[str, str]
    body: str


def sdp_summary(sdp: SessionDescription | None) -> SipSdpSummary | None:
    if sdp is None or sdp.audio is None:
        return None
    audio = sdp.audio
    return SipSdpSummary(
        connection_address=sdp.connection_address,
        audio_port=audio.port,
        direction=audio.direction,
        codecs=tuple(
            audio.codecs[payload].name
            for payload in audio.payload_types
            if payload in audio.codecs
        ),
    )


def response_summary(response: Any) -> SipResponseSummary:
    return SipResponseSummary(
        status_code=response.status_code,
        reason=response.reason,
        headers=dict(response.headers.items()),
        body=response.body.decode("utf-8", errors="replace"),
    )


def request_summary(request: Any) -> SipRequestSummary:
    return SipRequestSummary(
        method=request.method,
        uri=str(request.uri),
        headers=dict(request.headers.items()),
        body=request.body.decode("utf-8", errors="replace"),
    )
