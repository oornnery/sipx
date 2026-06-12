"""SUBSCRIBE/NOTIFY example for presence using the new httpx-like AsyncClient API.

This example demonstrates how to subscribe to SIP event notifications using
the AsyncClient. It shows:

1. Creating an AsyncClient with configuration
2. Sending a SUBSCRIBE request for presence events
3. Handling the subscription response
4. Understanding the NOTIFY flow (documented in comments)
5. Proper error handling for common failures

Usage:
    # Using default Mizu demo account:
    export SIPX_LOCAL_HOST=<your-local-ip>
    python -m sipx.examples.subscribe sip:2222@demo.mizu-voip.com:37075

    # Using custom SIP account:
    export SIPX_AOR=sip:1001@example.com
    export SIPX_USERNAME=1001
    export SIPX_PASSWORD=secret
    python -m sipx.examples.subscribe sip:alice@pbx.example.com --event presence

    # Show help:
    python -m sipx.examples.subscribe --help
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sipx import AsyncClient
from sipx.config import ClientConfig
from sipx.exceptions import (
    AuthError,
    ProtocolError,
    TimeoutError as SipTimeoutError,
)
from sipx.examples.common import account_settings, debug_wire, print_json
from sipx.protocol.auth import AuthFlow


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="SIP SUBSCRIBE example using AsyncClient",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  SIPX_AOR          Address of Record (e.g., sip:1001@example.com)
  SIPX_USERNAME     Authentication username
  SIPX_PASSWORD     Authentication password
  SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
  SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
  SIPX_TIMEOUT      Request timeout in seconds (default: 30)

Examples:
  # Subscribe to presence events
  export SIPX_LOCAL_HOST=192.168.1.100
  python -m sipx.examples.subscribe sip:2222@demo.mizu-voip.com:37075

  # Subscribe with custom event package
  python -m sipx.examples.subscribe sip:alice@pbx.example.com --event message-summary

  # Subscribe with custom expiration
  python -m sipx.examples.subscribe sip:alice@pbx.example.com --expires 1800

Notes:
  This example demonstrates sending SUBSCRIBE requests. Receiving NOTIFY
  requests requires extending the AsyncClient with a NOTIFY handler or
  using the full SipUserAgent runtime for complete subscription management.
        """,
    )
    parser.add_argument(
        "target",
        help="Target SIP URI to subscribe to (e.g., sip:alice@example.com)",
    )
    parser.add_argument(
        "--event",
        default="presence",
        help="Event package to subscribe to (default: presence)",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=3600,
        help="Subscription expiration in seconds (default: 3600)",
    )
    parser.add_argument(
        "--accept",
        default="application/pidf+xml",
        help="Accept header for NOTIFY body format (default: application/pidf+xml)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable SIP wire-level debug output",
    )
    return parser.parse_args()


async def subscribe(
    target: str,
    event: str,
    expires: int,
    accept: str,
    debug: bool,
) -> None:
    """Send SIP SUBSCRIBE using AsyncClient.

    This function demonstrates the subscription flow:
    1. Load account settings from environment variables
    2. Create a ClientConfig with local bind address and timeout
    3. Create an AuthFlow for automatic digest authentication
    4. Create an AsyncClient with the config and auth
    5. Send a SUBSCRIBE request for the specified event
    6. Handle the subscription response

    The SUBSCRIBE/NOTIFY flow per RFC 6665:
    - SUBSCRIBE establishes a subscription to an event package
    - The server responds with 200 OK if subscription is accepted
    - The server sends NOTIFY requests when the event state changes
    - NOTIFY requests contain the current state in the body
    - The subscription expires after the Expires period
    - Refresh by sending another SUBSCRIBE before expiration
    - Unsubscribe by sending SUBSCRIBE with Expires: 0

    Args:
        target: Target SIP URI to subscribe to.
        event: Event package name (e.g., "presence", "message-summary").
        expires: Subscription duration in seconds.
        accept: Accept header for NOTIFY body format.
        debug: Enable wire-level debug output.
    """
    # Load account settings from environment variables
    s = account_settings()

    # Step 1: Create ClientConfig
    # For SUBSCRIBE, we need from_uri and contact_uri for proper
    # dialog establishment. SUBSCRIBE creates a dialog per RFC 6665.
    config = ClientConfig(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )

    # Step 2: Create AuthFlow for automatic digest authentication
    # SUBSCRIBE requests often require authentication, especially for
    # presence subscriptions through a proxy.
    auth = AuthFlow(
        username=s["username"],
        password=s["credential"],
    )

    # Step 3: Set up event hooks (optional)
    event_hooks = {}
    if debug:
        event_hooks["wire"] = [debug_wire]

    # Step 4: Create and use the AsyncClient
    async with AsyncClient(
        transport="udp",
        config=config,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        # Step 5: Send SUBSCRIBE request
        # The subscribe() method:
        # - Builds a SUBSCRIBE request with proper dialog headers
        # - Sets the Event header to the specified event package
        # - Sets the Expires header for subscription duration
        # - Sends it to the target (extracted from URI)
        # - Handles auth challenges automatically via AuthFlow
        # - Returns the Response
        #
        # Required headers for SUBSCRIBE:
        # - Event: The event package (e.g., "presence")
        # - Expires: Subscription duration in seconds
        # - Accept: Expected NOTIFY body format
        try:
            response = await client.subscribe(
                target,
                event=event,
                Expires=str(expires),
                Accept=accept,
            )
        except SipTimeoutError as exc:
            # Timeout waiting for response
            print_json({
                "state": "failed",
                "error": {
                    "type": "timeout",
                    "message": str(exc),
                    "rfc_ref": exc.rfc_ref,
                },
            })
            return
        except AuthError as exc:
            # Authentication failed
            print_json({
                "state": "failed",
                "error": {
                    "type": "auth",
                    "message": str(exc),
                    "rfc_ref": exc.rfc_ref,
                },
            })
            return
        except ProtocolError as exc:
            # Protocol violation
            print_json({
                "state": "failed",
                "error": {
                    "type": "protocol",
                    "message": str(exc),
                    "rfc_ref": exc.rfc_ref,
                },
            })
            return

        # Step 6: Process the response
        # 200 OK means subscription was accepted
        # 202 Accepted means subscription is pending
        # 4xx/5xx means subscription failed
        if response.status_code == 200:
            # Subscription accepted
            call_id = response.headers.get("Call-ID", "unknown")
            from_header = response.headers.get("From", "")
            to_header = response.headers.get("To", "")
            expires_header = response.headers.get("Expires", str(expires))

            print_json({
                "state": "subscribed",
                "status_code": response.status_code,
                "event": event,
                "expires": expires_header,
                "call_id": call_id,
                "from": from_header,
                "to": to_header,
                "note": "Subscription active. NOTIFY requests will be sent by the server.",
            })

        elif response.status_code == 202:
            # Subscription pending (rare, but valid per RFC 6665)
            print_json({
                "state": "pending",
                "status_code": response.status_code,
                "event": event,
                "note": "Subscription pending approval. NOTIFY will indicate final state.",
            })

        elif 400 <= response.status_code < 500:
            # Client error - subscription rejected
            # Common codes:
            # - 403 Forbidden: Not authorized to subscribe
            # - 404 Not Found: Target user not found
            # - 481 Call/Transaction Does Not Exist: Dialog issue
            # - 489 Bad Event: Unsupported event package
            print_json({
                "state": "rejected",
                "status_code": response.status_code,
                "reason": response.reason,
                "event": event,
            })

        elif 500 <= response.status_code < 600:
            # Server error - temporary failure
            print_json({
                "state": "server_error",
                "status_code": response.status_code,
                "reason": response.reason,
                "event": event,
            })

        else:
            # Other failure
            print_json({
                "state": "failed",
                "status_code": response.status_code,
                "reason": response.reason,
                "event": event,
            })


def main() -> None:
    """Entry point for the subscribe example."""
    args = parse_args()
    try:
        asyncio.run(
            subscribe(
                target=args.target,
                event=args.event,
                expires=args.expires,
                accept=args.accept,
                debug=args.debug,
            )
        )
    except KeyboardInterrupt:
        print("\nSubscription cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
