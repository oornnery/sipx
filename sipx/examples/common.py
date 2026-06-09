# RFC 3261 SIP examples. Defaults target the public Mizu demo server.
# SDP examples use RFC 3264/RFC 8866 offer-answer; RTP examples use RFC 3550/3551.
# Packets are built by `sipx`: Via/From/To/Call-ID/CSeq/Contact plus optional SDP.

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Coroutine
from dataclasses import asdict, is_dataclass
from typing import Any, Literal

from sipx import (
    SessionDescription,
    SipCall,
    SipHooks,
    SipResponse,
    SipUac,
    SipUri,
    SipUserAgent,
    call_summary as sip_call_summary,
    new_branch,
    new_call_id,
    new_tag,
    response_summary as sip_response_summary,
    sdp_summary as sip_sdp_summary,
)

PUBLIC_MIZU_AOR = "sip:1111@demo.mizu-voip.com:37075"
PUBLIC_MIZU_REGISTRAR = "sip:demo.mizu-voip.com:37075"
PUBLIC_MIZU_USERNAME = "1111"
PUBLIC_MIZU_PASSWORD = "1111xxx"
PUBLIC_MIZU_REMOTE = ("demo.mizu-voip.com", 37075)
MizuAudioMode = Literal["none", "silence", "noise", "pyaudio"]


class ExampleConfigError(ValueError):
    pass


class ExampleCallTimeout(TimeoutError):
    pass


def account_settings() -> dict[str, str]:
    return {
        "aor": os.getenv("SIPX_AOR", PUBLIC_MIZU_AOR),
        "registrar": os.getenv("SIPX_REGISTRAR", PUBLIC_MIZU_REGISTRAR),
        "username": os.getenv("SIPX_USERNAME", PUBLIC_MIZU_USERNAME),
        "credential": os.getenv("SIPX_PASSWORD", PUBLIC_MIZU_PASSWORD),
        "contact_user": os.getenv("SIPX_CONTACT_USER", PUBLIC_MIZU_USERNAME),
    }


def local_host() -> str:
    return os.getenv("SIPX_LOCAL_HOST", "0.0.0.0")


def local_port() -> int:
    return int(os.getenv("SIPX_LOCAL_PORT", "0"))


def timeout() -> float:
    return float(os.getenv("SIPX_TIMEOUT", "10"))


def call_duration(default: float = 3.0) -> float:
    return float(os.getenv("SIPX_CALL_DURATION", str(default)))


def remote_address() -> tuple[str, int]:
    host = os.getenv("SIPX_REMOTE_HOST", PUBLIC_MIZU_REMOTE[0])
    port = int(os.getenv("SIPX_REMOTE_PORT", str(PUBLIC_MIZU_REMOTE[1])))
    return host, port


def target() -> str:
    return os.getenv("SIPX_TARGET", PUBLIC_MIZU_AOR)


def call_target() -> str:
    value = os.getenv("SIPX_TARGET")
    if value is None or value == "":
        raise ExampleConfigError(
            "SIPX_TARGET must be set for call examples, "
            "for example sip:<target>@demo.mizu-voip.com:37075"
        )
    return value


def rtp_bind_host() -> str | None:
    return os.getenv("SIPX_RTP_BIND_HOST")


def rtp_advertise_host() -> str | None:
    return os.getenv("SIPX_RTP_ADVERTISE_HOST")


def jitter_buffer_ms() -> int:
    return int(os.getenv("SIPX_JITTER_BUFFER_MS", "60"))


def audio_mode(default: MizuAudioMode = "none") -> MizuAudioMode:
    value = os.getenv("SIPX_AUDIO", default)
    if value == "none":
        return "none"
    if value == "silence":
        return "silence"
    if value == "noise":
        return "noise"
    if value == "pyaudio":
        return "pyaudio"
    raise ValueError("SIPX_AUDIO must be none, silence, noise, or pyaudio")


def mizu_uac(*, mode: str = "strict", lab_hooks: SipHooks | None = None) -> SipUac:
    settings = account_settings()
    return SipUac(
        aor=settings["aor"],
        registrar=settings["registrar"],
        remote=remote_address(),
        username=settings["username"],
        password=settings["credential"],
        contact_user=settings["contact_user"],
        local_host=local_host(),
        local_port=local_port(),
        timeout=timeout(),
        mode=mode,
        lab_hooks=lab_hooks,
        rtp_bind_host=rtp_bind_host(),
        rtp_advertise_host=rtp_advertise_host(),
        jitter_buffer_ms=jitter_buffer_ms(),
        codecs=("PCMU", "PCMA"),
    )


def contact_uri(aor: SipUri, local_address: tuple[str, int]) -> SipUri:
    return SipUri(
        scheme="sip",
        user=account_settings()["contact_user"] or aor.user or "sipx",
        host=local_address[0],
        port=local_address[1],
    )


def new_id(prefix: str) -> str:
    return new_call_id(prefix)


def branch(prefix: str) -> str:
    return new_branch(prefix)


def tag(prefix: str) -> str:
    return new_tag(prefix)


def print_json(data: object) -> None:
    print(json.dumps(_jsonable(data), indent=2, sort_keys=True))


def _jsonable(data: object) -> object:
    if is_dataclass(data) and not isinstance(data, type):
        return asdict(data)
    if isinstance(data, dict):
        return {key: _jsonable(value) for key, value in data.items()}
    if isinstance(data, tuple | list):
        return [_jsonable(value) for value in data]
    return data


def error_summary(error: Exception) -> dict[str, object]:
    return {
        "state": "failed",
        "error": {"type": type(error).__name__, "message": str(error)},
    }


async def await_call(call: Awaitable[SipCall]) -> SipCall:
    limit = timeout()
    try:
        return await asyncio.wait_for(call, timeout=limit)
    except TimeoutError as exc:
        raise ExampleCallTimeout(
            f"call did not complete within SIPX_TIMEOUT={limit:g} seconds"
        ) from exc


def run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def call_summary(call: SipCall, *, started: float | None = None):
    return sip_call_summary(call, started=started)


def sdp_summary(sdp: SessionDescription | None):
    return sip_sdp_summary(sdp)


def rtp_summary(uac: SipUac, call: SipCall) -> dict[str, object] | None:
    session = uac.rtp_session(call)
    if session is None:
        return None
    return asdict(session.snapshot())


def response_summary(response: SipResponse):
    return sip_response_summary(response)


async def send_stateless_request(method: str) -> SipResponse:
    settings = account_settings()
    aor = SipUri.parse(settings["aor"])
    request_uri = SipUri.parse(target())
    async with SipUserAgent(local_host=local_host(), local_port=local_port()) as ua:
        return await ua.request(
            method.upper(),
            request_uri,
            remote=remote_address(),
            caller=aor,
            contact=contact_uri(aor, ua.local_address),
            timeout=timeout(),
            username=settings["username"],
            password=settings["credential"],
            cnonce="sipx-example",
        )
