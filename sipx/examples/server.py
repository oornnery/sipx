"""UAS example: register request handlers and dispatch with handle_request.

A user agent server (UAS) answers incoming requests. The AsyncClient exposes
``on_options``/``on_message``/``on_invite``/``on_subscribe`` to register async
handlers, and ``handle_request`` to run the matching handler, drive a server
transaction, and return the response.

The AsyncClient receive loop currently dispatches *responses* to in-flight
client requests; it does not yet route inbound *requests* to these handlers
automatically. This example therefore feeds two synthetic requests through
``handle_request`` to show how handlers shape responses. The handler wiring is
exactly what a future inbound-request router would call.

Usage:
    python -m sipx.examples.server

Environment variables:
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_SERVER_AOR   AOR this UAS answers for (default: account AOR)

References:
    RFC 3261 §8.2 - General User Agent Server Behavior
    RFC 3261 §11 - OPTIONS (capability query)
    RFC 3428 - The SIP MESSAGE Method
"""

from __future__ import annotations

import asyncio
import os
import sys

from sipx import AsyncClient
from sipx.config import Settings
from sipx.examples.common import account_settings, print_json
from sipx.models import Request, Response

ALLOWED_METHODS = "INVITE, ACK, BYE, CANCEL, OPTIONS, MESSAGE"


def _echo_dialog_headers(request: Request) -> dict[str, str | list[str]]:
    """Copy the headers a UAS must echo back into its response."""
    headers: dict[str, str | list[str]] = {}
    for name in ("Via", "From", "To", "Call-ID", "CSeq"):
        value = request.headers.get(name)
        if value is not None:
            headers[name] = value
    return headers


def _sample_request(method: str, server_aor: str, body: bytes | None = None) -> Request:
    """Build a synthetic inbound request for demonstration."""
    headers: dict[str, str | list[str]] = {
        "Via": "SIP/2.0/UDP 198.51.100.10:5060;branch=z9hG4bKdemo",
        "From": "<sip:caller@example.com>;tag=remote-1",
        "To": f"<{server_aor}>",
        "Call-ID": f"demo-{method.lower()}@example.com",
        "CSeq": f"1 {method}",
        "Max-Forwards": "70",
    }
    if body is not None:
        headers["Content-Type"] = "text/plain"
        headers["Content-Length"] = str(len(body))
    return Request(method=method, uri=server_aor, headers=headers, body=body)


async def serve(server_aor: str) -> None:
    """Register UAS handlers and dispatch two synthetic requests.

    Args:
        server_aor: The address-of-record this UAS answers for.
    """
    s = account_settings()
    settings = Settings(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        user_agent="sipx/2.0",
    )

    async with AsyncClient(transport="udp", settings=settings) as client:

        @client.on_options
        async def handle_options(request: Request) -> Response:
            # Advertise supported methods per RFC 3261 §11.
            headers = _echo_dialog_headers(request)
            headers["Allow"] = ALLOWED_METHODS
            return Response.from_request(request, 200, "OK", headers=headers)

        @client.on_message
        async def handle_message(request: Request) -> Response:
            # Accept the instant message per RFC 3428.
            text = (
                request.body.decode("utf-8", errors="replace") if request.body else ""
            )
            print(f"received MESSAGE: {text!r}", file=sys.stderr)
            return Response.from_request(
                request, 200, "OK", headers=_echo_dialog_headers(request)
            )

        options_response = await client.handle_request(
            _sample_request("OPTIONS", server_aor)
        )
        message_response = await client.handle_request(
            _sample_request("MESSAGE", server_aor, body=b"ping")
        )

        print_json(
            {
                "server_aor": server_aor,
                "options": {
                    "status_code": options_response.status_code,
                    "allow": options_response.headers.get("Allow"),
                },
                "message": {
                    "status_code": message_response.status_code,
                    "reason": message_response.reason,
                },
            }
        )


def main() -> None:
    """Entry point for the UAS server example."""
    s = account_settings()
    server_aor = os.getenv("SIPX_SERVER_AOR", s["aor"])
    try:
        asyncio.run(serve(server_aor=server_aor))
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
