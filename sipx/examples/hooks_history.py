"""Event hooks and response.history example using AsyncClient.

Two complementary observability features are shown here:

* event_hooks - httpx-style callbacks fired on "request", "response", and
  "provisional" events while a request is in flight.
* response.history - on the final response, the list of intermediate
  responses (provisional 1xx plus 401/407 auth challenges) in arrival order,
  each carrying its own ``request`` so the whole exchange is reconstructable.

A REGISTER against an authenticating registrar usually produces a 401
challenge first, so ``response.history`` will contain that challenge and the
final 200 OK is returned directly.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_REGISTRAR=sip:pbx.example.com:5060
    python -m sipx.examples.hooks_history

Environment variables:
    SIPX_AOR          Address of Record used in the From header
    SIPX_REGISTRAR    Registrar URI (default: account registrar)
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)

References:
    RFC 3261 §8.1.3 - Processing Responses
    RFC 3261 §22 - Usage of HTTP Authentication (401/407 challenges)
"""

from __future__ import annotations

import asyncio
import sys

from sipx import AsyncClient
from sipx.config import ClientConfig
from sipx.exceptions import SipError
from sipx.examples.common import account_settings, print_json
from sipx.models import Request, Response
from sipx.protocol.auth import AuthFlow


async def show_hooks_and_history() -> None:
    """Send a REGISTER while recording hook events and response history."""
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

    seen: list[str] = []

    def on_request(request: Request) -> None:
        seen.append(f"request {request.method}")

    def on_response(response: Response) -> None:
        seen.append(f"response {response.status_code}")

    def on_provisional(response: Response) -> None:
        seen.append(f"provisional {response.status_code}")

    event_hooks = {
        "request": [on_request],
        "response": [on_response],
        "provisional": [on_provisional],
    }

    async with AsyncClient(
        transport="udp",
        config=config,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        try:
            response = await client.register(s["registrar"], Expires="3600")
        except SipError as exc:
            print_json({"state": "failed", "error": str(exc), "hook_events": seen})
            return

        history = [
            {"status_code": item.status_code, "reason": item.reason}
            for item in response.history
        ]
        print_json(
            {
                "final": {
                    "status_code": response.status_code,
                    "reason": response.reason,
                },
                "history": history,
                "hook_events": seen,
            }
        )


def main() -> None:
    """Entry point for the hooks/history example."""
    try:
        asyncio.run(show_hooks_and_history())
    except KeyboardInterrupt:
        print("\nCancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
