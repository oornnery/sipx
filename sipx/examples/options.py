"""OPTIONS example: query a SIP peer's capabilities using AsyncClient.

OPTIONS lets a user agent ask another user agent (or proxy) which methods,
body types, and extensions it supports, without creating a dialog. The peer
reports its capabilities in the Allow, Accept, Supported, and Allow-Events
header fields of the 2xx response.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_TARGET=sip:bob@example.com
    python -m sipx.examples.options

Environment variables:
    SIPX_AOR          Address of Record used in the From header
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)
    SIPX_TARGET       SIP URI to query (default: account AOR)
    SIPX_DEBUG        Set to 1 to print SIP request/response debug output

References:
    RFC 3261 §11 - Querying for Capabilities (OPTIONS)
"""

from __future__ import annotations

import asyncio
import os
import sys

from sipx import AsyncClient
from sipx.config import ClientConfig
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
from sipx.protocol.auth import AuthFlow


async def options(target: str, debug: bool) -> None:
    """Send a SIP OPTIONS request and report the peer's capabilities.

    Args:
        target: SIP URI to query for capabilities.
        debug: Enable wire-level debug output.
    """
    s = account_settings()

    config = ClientConfig(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )
    auth = AuthFlow(username=s["username"], password=s["credential"])

    event_hooks = {}
    if debug:
        event_hooks["request"] = [debug_request]
        event_hooks["response"] = [debug_response]

    async with AsyncClient(
        transport="udp",
        config=config,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        try:
            response = await client.options(target)
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

        # Capabilities are advertised in these response headers (RFC 3261 §11).
        capabilities = {
            field: response.headers.get(field)
            for field in ("Allow", "Accept", "Supported", "Allow-Events")
            if response.headers.get(field) is not None
        }
        print_json(
            {
                "state": "ok" if 200 <= response.status_code < 300 else "non_2xx",
                "status_code": response.status_code,
                "reason": response.reason,
                "target": target,
                "capabilities": capabilities,
            }
        )


def main() -> None:
    """Entry point for the options example."""
    s = account_settings()
    debug = os.getenv("SIPX_DEBUG", "0") not in ("", "0", "false")
    try:
        asyncio.run(options(target=s["target"], debug=debug))
    except KeyboardInterrupt:
        print("\nOPTIONS cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
