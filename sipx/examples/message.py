"""MESSAGE example for instant messaging using the new httpx-like AsyncClient API.

This example demonstrates how to send SIP instant messages using the
AsyncClient. It shows:

1. Creating an AsyncClient with configuration
2. Sending a MESSAGE request with text body
3. Handling the response and delivery confirmation
4. Proper error handling for common failures

Usage:
    # Using default Mizu demo account:
    export SIPX_LOCAL_HOST=<your-local-ip>
    python -m sipx.examples.message sip:2222@demo.mizu-voip.com:37075 "Hello from sipx!"

    # Using custom SIP account:
    export SIPX_AOR=sip:1001@example.com
    export SIPX_USERNAME=1001
    export SIPX_PASSWORD=secret
    python -m sipx.examples.message sip:alice@pbx.example.com "Meeting at 3pm"

    # Show help:
    python -m sipx.examples.message --help
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
        description="SIP MESSAGE example using AsyncClient",
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
  # Send a simple text message
  export SIPX_LOCAL_HOST=192.168.1.100
  python -m sipx.examples.message sip:2222@demo.mizu-voip.com:37075 "Hello!"

  # Send with custom content type
  python -m sipx.examples.message sip:alice@pbx.example.com "<msg>Hi</msg>" --content-type application/xml

  # Send multiple messages
  python -m sipx.examples.message sip:alice@pbx.example.com "Message 1" "Message 2" "Message 3"
        """,
    )
    parser.add_argument(
        "target",
        help="Target SIP URI to message (e.g., sip:alice@example.com)",
    )
    parser.add_argument(
        "messages",
        nargs="+",
        help="Message text(s) to send",
    )
    parser.add_argument(
        "--content-type",
        default="text/plain",
        help="Content-Type for message body (default: text/plain)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable SIP wire-level debug output",
    )
    return parser.parse_args()


async def message(
    target: str,
    messages: list[str],
    content_type: str,
    debug: bool,
) -> None:
    """Send SIP MESSAGE using AsyncClient.

    This function demonstrates the complete messaging flow:
    1. Load account settings from environment variables
    2. Create a ClientConfig with local bind address and timeout
    3. Create an AuthFlow for automatic digest authentication
    4. Create an AsyncClient with the config and auth
    5. Send one or more MESSAGE requests
    6. Handle responses and delivery confirmations

    Args:
        target: Target SIP URI to message.
        messages: List of message texts to send.
        content_type: MIME type for message body.
        debug: Enable wire-level debug output.
    """
    # Load account settings from environment variables
    s = account_settings()

    # Step 1: Create ClientConfig
    # For MESSAGE, we need from_uri for the From header.
    # MESSAGE is a standalone transaction (no dialog), so contact_uri
    # is optional but included for completeness.
    config = ClientConfig(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )

    # Step 2: Create AuthFlow for automatic digest authentication
    # MESSAGE requests often require authentication when sent through
    # a proxy or to external domains.
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
        # Step 5: Send each message
        # The message() method:
        # - Builds a MESSAGE request with proper headers
        # - Includes the text body with Content-Type
        # - Sends it to the target (extracted from URI)
        # - Handles auth challenges automatically via AuthFlow
        # - Returns the Response (2xx = delivered, 4xx/5xx = failed)
        #
        # MESSAGE is a standalone transaction per RFC 3428:
        # - No dialog is established
        # - Each message is independent
        # - 200 OK means the message was accepted by the recipient's server
        results = []

        for msg_text in messages:
            # Encode message body
            body = msg_text.encode("utf-8")

            try:
                response = await client.message(
                    target,
                    body=body,
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(len(body)),
                    },
                )
            except SipTimeoutError as exc:
                # Timeout waiting for response
                results.append({
                    "message": msg_text,
                    "state": "failed",
                    "error": {
                        "type": "timeout",
                        "message": str(exc),
                        "rfc_ref": exc.rfc_ref,
                    },
                })
                continue
            except AuthError as exc:
                # Authentication failed
                results.append({
                    "message": msg_text,
                    "state": "failed",
                    "error": {
                        "type": "auth",
                        "message": str(exc),
                        "rfc_ref": exc.rfc_ref,
                    },
                })
                continue
            except ProtocolError as exc:
                # Protocol violation
                results.append({
                    "message": msg_text,
                    "state": "failed",
                    "error": {
                        "type": "protocol",
                        "message": str(exc),
                        "rfc_ref": exc.rfc_ref,
                    },
                })
                continue

            # Step 6: Process the response
            # 200 OK means the message was delivered to the recipient's server
            # 4xx/5xx means delivery failed
            if 200 <= response.status_code < 300:
                results.append({
                    "message": msg_text,
                    "state": "delivered",
                    "status_code": response.status_code,
                })
            elif 400 <= response.status_code < 500:
                # Client error - message rejected
                results.append({
                    "message": msg_text,
                    "state": "rejected",
                    "status_code": response.status_code,
                    "reason": response.reason,
                })
            elif 500 <= response.status_code < 600:
                # Server error - temporary failure
                results.append({
                    "message": msg_text,
                    "state": "server_error",
                    "status_code": response.status_code,
                    "reason": response.reason,
                })
            else:
                # Other failure
                results.append({
                    "message": msg_text,
                    "state": "failed",
                    "status_code": response.status_code,
                    "reason": response.reason,
                })

        # Print summary
        print_json({
            "target": target,
            "messages_sent": len(messages),
            "results": results,
        })


def main() -> None:
    """Entry point for the message example."""
    args = parse_args()
    try:
        asyncio.run(
            message(
                target=args.target,
                messages=args.messages,
                content_type=args.content_type,
                debug=args.debug,
            )
        )
    except KeyboardInterrupt:
        print("\nMessaging cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
