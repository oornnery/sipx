from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict
from typing import Literal
from uuid import uuid4

from sipx import (
    HeaderMap,
    SipCall,
    SipHooks,
    SipRequest,
    SipResponse,
    SessionDescription,
    SipUac,
    SipUri,
    SipUserAgent,
    build_digest_authorization,
    parse_digest_challenge,
)


PUBLIC_MIZU_AOR = "sip:1111@demo.mizu-voip.com:37075"
PUBLIC_MIZU_REGISTRAR = "sip:demo.mizu-voip.com:37075"
PUBLIC_MIZU_USERNAME = "1111"
PUBLIC_MIZU_PASSWORD = "1111xxx"
PUBLIC_MIZU_REMOTE = ("demo.mizu-voip.com", 37075)
MizuAudioMode = Literal["none", "silence", "noise", "pyaudio"]


def account_settings() -> dict[str, str]:
    return {
        "aor": os.getenv("SIPX_MIZU_AOR", PUBLIC_MIZU_AOR),
        "registrar": os.getenv("SIPX_MIZU_REGISTRAR", PUBLIC_MIZU_REGISTRAR),
        "username": os.getenv("SIPX_MIZU_USERNAME", PUBLIC_MIZU_USERNAME),
        "credential": os.getenv("SIPX_MIZU_PASSWORD", PUBLIC_MIZU_PASSWORD),
        "contact_user": os.getenv("SIPX_MIZU_CONTACT_USER", PUBLIC_MIZU_USERNAME),
    }


def remote_address() -> tuple[str, int]:
    host = os.getenv("SIPX_MIZU_REMOTE_HOST", PUBLIC_MIZU_REMOTE[0])
    port = int(os.getenv("SIPX_MIZU_REMOTE_PORT", str(PUBLIC_MIZU_REMOTE[1])))
    return host, port


def default_target() -> str:
    return os.getenv("SIPX_MIZU_TARGET", PUBLIC_MIZU_AOR)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--local-host", default=os.getenv("SIPX_LOCAL_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--local-port", type=int, default=int(os.getenv("SIPX_LOCAL_PORT", "0"))
    )
    parser.add_argument(
        "--timeout", type=float, default=float(os.getenv("SIPX_TIMEOUT", "10"))
    )


def add_call_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=default_target())
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument(
        "--audio", choices=("none", "silence", "noise", "pyaudio"), default="none"
    )
    parser.add_argument("--rtp-bind", default=os.getenv("SIPX_RTP_BIND_HOST"))
    parser.add_argument("--rtp-advertise", default=os.getenv("SIPX_RTP_ADVERTISE_HOST"))
    parser.add_argument("--jitter-buffer-ms", type=int, default=60)


def mizu_uac(
    *,
    local_host: str,
    local_port: int = 0,
    timeout: float = 10.0,
    mode: str = "strict",
    lab_hooks: SipHooks | None = None,
    rtp_bind_host: str | None = None,
    rtp_advertise_host: str | None = None,
    jitter_buffer_ms: int = 60,
) -> SipUac:
    settings = account_settings()
    return SipUac(
        aor=settings["aor"],
        registrar=settings["registrar"],
        remote=remote_address(),
        username=settings["username"],
        password=settings["credential"],
        contact_user=settings["contact_user"],
        local_host=local_host,
        local_port=local_port,
        timeout=timeout,
        mode=mode,
        lab_hooks=lab_hooks,
        rtp_bind_host=rtp_bind_host,
        rtp_advertise_host=rtp_advertise_host,
        jitter_buffer_ms=jitter_buffer_ms,
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
    return f"{prefix}-{uuid4().hex}"


def branch(prefix: str) -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def tag(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def audio_mode(value: str) -> MizuAudioMode:
    if value == "none":
        return "none"
    if value == "silence":
        return "silence"
    if value == "noise":
        return "noise"
    if value == "pyaudio":
        return "pyaudio"
    raise ValueError("audio must be none, silence, noise, or pyaudio")


def call_summary(call: SipCall, *, started: float | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "call_id": call.call_id,
        "state": call.state.value,
        "remote": {"host": call.remote[0], "port": call.remote[1]},
        "local_sdp": sdp_summary(call.local_sdp),
        "remote_sdp": sdp_summary(call.remote_sdp),
    }
    if started is not None:
        data["duration_seconds"] = time.monotonic() - started
    return data


def sdp_summary(sdp: SessionDescription | None) -> dict[str, object] | None:
    if sdp is None or sdp.audio is None:
        return None
    audio = sdp.audio
    return {
        "connection_address": sdp.connection_address,
        "audio_port": audio.port,
        "direction": audio.direction,
        "codecs": [
            audio.codecs[payload].name
            for payload in audio.payload_types
            if payload in audio.codecs
        ],
    }


def rtp_summary(uac: SipUac, call: SipCall) -> dict[str, object] | None:
    session = uac.rtp_session(call)
    if session is None:
        return None
    return asdict(session.snapshot())


def build_stateless_request(
    *,
    method: str,
    target: SipUri,
    aor: SipUri,
    contact: SipUri,
    call_id: str,
    from_tag: str,
    cseq: int = 1,
    body: bytes = b"",
    content_type: str | None = None,
    auth_header: tuple[str, str] | None = None,
) -> SipRequest:
    headers = HeaderMap()
    headers.add(
        "Via",
        f"SIP/2.0/UDP {contact.host}:{contact.port};branch={branch(method.lower())}",
    )
    headers.add("From", f"<{aor}>;tag={from_tag}")
    headers.add("To", f"<{target}>")
    headers.add("Call-ID", call_id)
    headers.add("CSeq", f"{cseq} {method}")
    headers.add("Contact", f"<{contact}>")
    headers.add("Max-Forwards", "70")
    if content_type is not None:
        headers.add("Content-Type", content_type)
    if auth_header is not None:
        headers.add(auth_header[0], auth_header[1])
    return SipRequest(method=method, uri=target, headers=headers, body=body)


async def send_stateless_request(
    *,
    method: str,
    target: str,
    local_host: str,
    local_port: int,
    timeout: float,
    body: bytes = b"",
    content_type: str | None = None,
) -> SipResponse:
    settings = account_settings()
    aor = SipUri.parse(settings["aor"])
    target_uri = SipUri.parse(target)
    async with SipUserAgent(local_host=local_host, local_port=local_port) as user_agent:
        contact = contact_uri(aor, user_agent.local_address)
        call_id = new_id(method.lower())
        from_tag = tag("from")
        request = build_stateless_request(
            method=method,
            target=target_uri,
            aor=aor,
            contact=contact,
            call_id=call_id,
            from_tag=from_tag,
            body=body,
            content_type=content_type,
        )
        await user_agent.send_request(request, remote_address())
        response = await receive_response(
            user_agent,
            call_id=call_id,
            method=method,
            cseq=1,
            timeout=timeout,
        )
        challenge = digest_challenge(response)
        if challenge is None:
            return response
        header_name, header_value = challenge
        request = build_stateless_request(
            method=method,
            target=target_uri,
            aor=aor,
            contact=contact,
            call_id=call_id,
            from_tag=from_tag,
            cseq=2,
            body=body,
            content_type=content_type,
            auth_header=(
                header_name,
                build_digest_authorization(
                    username=settings["username"],
                    password=settings["credential"],
                    method=method,
                    uri=str(target_uri),
                    challenge=parse_digest_challenge(header_value),
                ),
            ),
        )
        await user_agent.send_request(request, remote_address())
        return await receive_response(
            user_agent,
            call_id=call_id,
            method=method,
            cseq=2,
            timeout=timeout,
        )


async def receive_response(
    user_agent: SipUserAgent,
    *,
    call_id: str,
    method: str,
    cseq: int,
    timeout: float,
) -> SipResponse:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for SIP response")
        event = await user_agent.receive_event(timeout=remaining)
        message = event.message
        if not isinstance(message, SipResponse):
            continue
        if message.headers.get("Call-ID") != call_id:
            continue
        if message.headers.get("CSeq") != f"{cseq} {method}":
            continue
        return message


def response_summary(response: SipResponse) -> dict[str, object]:
    return {
        "status_code": response.status_code,
        "reason": response.reason,
        "headers": {name: value for name, value in response.headers.items()},
        "body_bytes": len(response.body),
    }


def digest_challenge(response: SipResponse) -> tuple[str, str] | None:
    if response.status_code == 401:
        value = response.headers.get("WWW-Authenticate")
        return ("Authorization", value) if value is not None else None
    if response.status_code == 407:
        value = response.headers.get("Proxy-Authenticate")
        return ("Proxy-Authorization", value) if value is not None else None
    return None


def run(coro):
    return asyncio.run(coro)
