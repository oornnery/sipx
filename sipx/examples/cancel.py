"""CANCEL example: abort a pending INVITE using AsyncClient (RFC 3261 §9).

CANCEL stops an INVITE that has not yet received a final response (for example
while the callee is still ringing). Because ``invite()`` blocks until the final
response, the INVITE runs in one task while a second task waits briefly and then
calls ``cancel(call_id)``. The pending INVITE then completes with ``487 Request
Terminated`` and the CANCEL itself is answered with ``200 OK``.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_TARGET=sip:2222@demo.mizu-voip.com:37075
    python -m sipx.examples.cancel

Environment variables:
    SIPX_AOR          Address of Record used in the From header
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)
    SIPX_TARGET       Target SIP URI to call (default: account AOR)
    SIPX_CANCEL_AFTER Seconds to wait before sending CANCEL (default: 1)
    SIPX_DEBUG        Set to 1 to print SIP request/response debug output

References:
    RFC 3261 §9 - Canceling a Request (CANCEL)
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


async def cancel_call(target: str, cancel_after: float, debug: bool) -> None:
    """Start an INVITE to *target*, then CANCEL it after a short delay.

    Args:
        target: Target SIP URI to call and then cancel.
        cancel_after: Seconds to wait before sending CANCEL.
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

    call_id = ""

    event_hooks = {}
    if debug:
        event_hooks["request"] = [debug_request]
        event_hooks["response"] = [debug_response]

    async with AsyncClient(
        transport="udp",
        settings=settings,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        invite_task = asyncio.create_task(client.invite(target))

        # Wait until the INVITE is in flight, then send CANCEL from this task.
        deadline = asyncio.get_event_loop().time() + s["timeout"]
        while not client._pending_invites:
            if asyncio.get_event_loop().time() > deadline:
                break
            await asyncio.sleep(0.01)
        call_id = next(iter(client._pending_invites), "")
        await asyncio.sleep(cancel_after)

        cancel_status = None
        try:
            if call_id:
                cancel_response = await client.cancel(call_id)
                cancel_status = cancel_response.status_code
        except (SipTimeoutError, ProtocolError) as exc:
            print(f"CANCEL failed: {exc}", file=sys.stderr)

        try:
            invite_response = await invite_task
        except SipTimeoutError as exc:
            print_json(
                {"state": "failed", "error": {"type": "timeout", "message": str(exc)}}
            )
            return
        except AuthError as exc:
            print_json(
                {"state": "failed", "error": {"type": "auth", "message": str(exc)}}
            )
            return
        except ProtocolError as exc:
            print_json(
                {"state": "failed", "error": {"type": "protocol", "message": str(exc)}}
            )
            return

        print_json(
            {
                "state": "cancelled"
                if invite_response.status_code == 487
                else "completed",
                "invite_status": invite_response.status_code,
                "invite_reason": invite_response.reason,
                "cancel_status": cancel_status,
                "call_id": call_id,
            }
        )


def main() -> None:
    """Entry point for the cancel example."""
    s = account_settings()
    cancel_after = float(os.getenv("SIPX_CANCEL_AFTER", "1"))
    debug = os.getenv("SIPX_DEBUG", "0") not in ("", "0", "false")
    try:
        asyncio.run(
            cancel_call(target=s["target"], cancel_after=cancel_after, debug=debug)
        )
    except KeyboardInterrupt:
        print("\nCancel example interrupted by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
