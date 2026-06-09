from __future__ import annotations

import time
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


@dataclass(frozen=True, slots=True)
class SipCallSummary:
    call_id: str
    state: str
    remote: dict[str, object]
    local_sdp: SipSdpSummary | None
    remote_sdp: SipSdpSummary | None
    duration_seconds: float | None = None


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


def call_summary(call: Any, *, started: float | None = None) -> SipCallSummary:
    duration = None if started is None else time.monotonic() - started
    return SipCallSummary(
        call_id=call.call_id,
        state=call.state.value,
        remote={"host": call.remote[0], "port": call.remote[1]},
        local_sdp=sdp_summary(call.local_sdp),
        remote_sdp=sdp_summary(call.remote_sdp),
        duration_seconds=duration,
    )
