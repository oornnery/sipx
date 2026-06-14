"""Unregister example: remove a binding by sending REGISTER with Expires: 0.

De-registration is an ordinary REGISTER request whose Expires value is 0,
which tells the registrar to drop the binding for the address-of-record. The
same Digest authentication challenge handling applies as for registration.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_AOR=sip:1001@example.com
    export SIPX_REGISTRAR=sip:pbx.example.com:5060
    export SIPX_USERNAME=1001
    export SIPX_PASSWORD=secret
    python -m sipx.examples.unregister

Environment variables:
    SIPX_AOR          Address of Record (e.g., sip:1001@example.com)
    SIPX_REGISTRAR    Registrar URI (e.g., sip:pbx.example.com:5060)
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)
    SIPX_DEBUG        Set to 1 to print SIP request/response debug output

References:
    RFC 3261 §10.2.2 - Removing Bindings (Expires: 0)
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


async def unregister(debug: bool) -> None:
    """Remove the registrar binding for the configured address-of-record.

    Args:
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

    async with AsyncClient(
        transport="udp",
        settings=settings,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        try:
            # Expires: 0 removes the binding instead of refreshing it.
            response = await client.register(s["registrar"], Expires="0")
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

        if response.status_code == 200:
            print_json(
                {
                    "state": "unregistered",
                    "status_code": response.status_code,
                    "contact": response.headers.get("Contact", "removed"),
                }
            )
        else:
            print_json(
                {
                    "state": "failed",
                    "status_code": response.status_code,
                    "reason": response.reason,
                }
            )


def main() -> None:
    """Entry point for the unregister example."""
    debug = os.getenv("SIPX_DEBUG", "0") not in ("", "0", "false")
    try:
        asyncio.run(unregister(debug=debug))
    except KeyboardInterrupt:
        print("\nUnregister cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
