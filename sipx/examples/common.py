from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

from sipx import RtpWireDirection, RtpWireEvent, SipWireDirection, SipWireEvent
from sipx.models import Request, Response


def debug_request(request: Request) -> None:
    call_id = request.headers.get("Call-ID", "unknown")
    header = f"REQUEST (Call-ID: {call_id}) Local ===> {request.uri}"
    raw_text = request.to_bytes().decode("utf-8", errors="replace").rstrip()
    border = "=" * len(header)
    print(f"\n{border}\n{header}\n{border}\n{raw_text}\n{border}\n", file=sys.stderr)


def debug_response(response: Response) -> None:
    call_id = response.headers.get("Call-ID", "unknown")
    origin = response.request.uri if response.request else "remote"
    header = f"RESPONSE (Call-ID: {call_id}) {origin} <=== Local"
    raw_text = response.to_bytes().decode("utf-8", errors="replace").rstrip()
    border = "=" * len(header)
    print(f"\n{border}\n{header}\n{border}\n{raw_text}\n{border}\n", file=sys.stderr)


def debug_wire(event: SipWireEvent) -> None:
    call_id = "unknown"
    is_request = True

    if event.message:
        is_request = type(event.message).__name__ == "SipRequest"
        call_id = event.message.headers.get("Call-ID", "unknown")
    else:
        raw_text = event.raw.decode("utf-8", errors="replace")
        is_request = not raw_text.startswith("SIP/")
        for line in raw_text.split("\r\n"):
            if line.lower().startswith("call-id:"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    call_id = parts[1].strip()
                break

    msg_type = "REQUEST" if is_request else "RESPONSE"
    remote_str = f"{event.remote[0]}:{event.remote[1]}"

    if event.direction is SipWireDirection.TX:
        header = f"{msg_type} (Call-ID: {call_id}) Local ===> {remote_str}"
    else:
        header = f"{msg_type} (Call-ID: {call_id}) {remote_str} <=== Local"

    raw_text = event.raw.decode("utf-8", errors="replace").rstrip()
    border = "=" * len(header)
    print(f"\n{border}\n{header}\n{border}\n{raw_text}\n{border}\n", file=sys.stderr)


PUBLIC_MIZU_AOR = "sip:1111@demo.mizu-voip.com:37075"
PUBLIC_MIZU_REGISTRAR = "sip:demo.mizu-voip.com:37075"
PUBLIC_MIZU_USERNAME = "1111"
PUBLIC_MIZU_PASSWORD = "1111xxx"
PUBLIC_MIZU_REMOTE = ("demo.mizu-voip.com", 37075)


def account_settings() -> dict[str, Any]:
    return {
        "aor": os.getenv("SIPX_AOR", PUBLIC_MIZU_AOR),
        "registrar": os.getenv("SIPX_REGISTRAR", PUBLIC_MIZU_REGISTRAR),
        "username": os.getenv("SIPX_USERNAME", PUBLIC_MIZU_USERNAME),
        "credential": os.getenv("SIPX_PASSWORD", PUBLIC_MIZU_PASSWORD),
        "contact_user": os.getenv("SIPX_CONTACT_USER", PUBLIC_MIZU_USERNAME),
        "remote_host": os.getenv("SIPX_REMOTE_HOST", PUBLIC_MIZU_REMOTE[0]),
        "remote_port": int(os.getenv("SIPX_REMOTE_PORT", str(PUBLIC_MIZU_REMOTE[1]))),
        "local_host": os.getenv("SIPX_LOCAL_HOST", "0.0.0.0"),
        "local_port": int(os.getenv("SIPX_LOCAL_PORT", "0")),
        "timeout": float(os.getenv("SIPX_TIMEOUT", "10")),
        "target": os.getenv("SIPX_TARGET") or os.getenv("SIPX_AOR", PUBLIC_MIZU_AOR),
        "audio": os.getenv("SIPX_AUDIO", "silence"),
        "run_call": os.getenv("SIPX_RUN_CALL", "0"),
    }


def debug_wire_rtp(event: RtpWireEvent) -> None:
    ssrc = event.packet.ssrc if event.packet else 0
    seq = event.packet.sequence_number if event.packet else 0
    ts = event.packet.timestamp if event.packet else 0
    pt = event.packet.payload_type if event.packet else 0
    payload_len = len(event.packet.payload) if event.packet else len(event.raw)
    marker = " M" if event.packet and event.packet.marker else ""

    remote_str = f"{event.remote[0]}:{event.remote[1]}"
    if event.direction is RtpWireDirection.TX:
        header = f"RTP (SSRC: {ssrc:08x}) Local ===> {remote_str}"
    else:
        header = f"RTP (SSRC: {ssrc:08x}) {remote_str} <=== Local"

    detail = f"seq={seq:5d}  ts={ts:10d}  pt={pt:3d}{marker}  payload={payload_len}B"
    border = "=" * max(len(header), len(detail))
    print(f"\n{border}\n{header}\n{border}\n{detail}\n{border}\n", file=sys.stderr)


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
