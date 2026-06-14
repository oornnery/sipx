"""DTMF-over-INFO example using the AsyncClient request() escape hatch.

Some networks signal DTMF digits with SIP INFO requests carrying an
``application/dtmf-relay`` body (the legacy alternative to RFC 4733 in-band
telephone-event packets). There is no dedicated ``info()`` method, so this
uses ``client.request("INFO", ...)`` to send each digit.

INFO is normally sent inside an established INVITE dialog. This example shows
the message shape with the generic ``request`` helper; in a real call you
would send these within the dialog created by ``invite()``.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_TARGET=sip:2222@demo.mizu-voip.com:37075
    export SIPX_DTMF=1234
    python -m sipx.examples.info_dtmf

Environment variables:
    SIPX_AOR          Address of Record used in the From header
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)
    SIPX_TARGET       Target SIP URI (default: account AOR)
    SIPX_DTMF         Digits to send (default: "1234")
    SIPX_DTMF_DURATION DTMF duration in ms (default: 160)
    SIPX_DEBUG        Set to 1 to print SIP request/response debug output

References:
    RFC 6086 - SIP INFO Method and Package Framework
    RFC 4733 - RTP Payload for DTMF Digits (the in-band alternative)
"""

from __future__ import annotations

import asyncio
import os
import sys

from sipx import AsyncClient
from sipx.config import Settings
from sipx.exceptions import (
    AuthError,
    ProtocolError,
    TimeoutError as SipTimeoutError,
)
from sipx.examples.common import (
    account_settings,
    debug_request,
    debug_response,
    print_json,
)
from sipx.protocol.auth import AuthDigest


def _dtmf_relay_body(digit: str, duration: int) -> bytes:
    """Build an application/dtmf-relay body for a single digit."""
    return f"Signal={digit}\r\nDuration={duration}\r\n".encode("utf-8")


async def send_dtmf(target: str, digits: str, duration: int, debug: bool) -> None:
    """Send each digit in *digits* as a separate INFO request.

    Args:
        target: Target SIP URI.
        digits: String of DTMF digits to send in order.
        duration: DTMF tone duration in milliseconds.
        debug: Enable wire-level debug output.
    """
    s = account_settings()

    settings = Settings(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )
    auth = AuthDigest(username=s["username"], password=s["credential"])

    event_hooks = {}
    if debug:
        event_hooks["request"] = [debug_request]
        event_hooks["response"] = [debug_response]

    results = []
    async with AsyncClient(
        transport="udp",
        settings=settings,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        for digit in digits:
            body = _dtmf_relay_body(digit, duration)
            try:
                response = await client.request(
                    "INFO",
                    target,
                    body=body,
                    headers={
                        "Content-Type": "application/dtmf-relay",
                        "Content-Length": str(len(body)),
                    },
                )
            except (SipTimeoutError, AuthError, ProtocolError) as exc:
                results.append({"digit": digit, "state": "failed", "error": str(exc)})
                continue
            results.append(
                {
                    "digit": digit,
                    "status_code": response.status_code,
                    "reason": response.reason,
                }
            )

    print_json({"target": target, "digits": digits, "results": results})


def main() -> None:
    """Entry point for the DTMF INFO example."""
    s = account_settings()
    digits = os.getenv("SIPX_DTMF", "1234")
    duration = int(os.getenv("SIPX_DTMF_DURATION", "160"))
    debug = os.getenv("SIPX_DEBUG", "0") not in ("", "0", "false")
    try:
        asyncio.run(
            send_dtmf(target=s["target"], digits=digits, duration=duration, debug=debug)
        )
    except KeyboardInterrupt:
        print("\nDTMF send cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
