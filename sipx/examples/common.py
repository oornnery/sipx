"""Shared helpers for the runnable SIP examples.

Provides wire-level debug printers for requests/responses, a default demo
account resolved from ``SIPX_*`` environment variables, and small JSON
output utilities. Imported by the example scripts; not part of the client
runtime.

References:
    RFC 3261 §7 - SIP Messages (printed verbatim for inspection)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

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
