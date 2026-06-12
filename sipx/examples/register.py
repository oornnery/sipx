"""Simple REGISTER example using the new httpx-like AsyncClient API.

This example demonstrates how to register a SIP user agent with a registrar
server using the AsyncClient. It shows:

1. Creating an AsyncClient with configuration
2. Setting up automatic digest authentication with AuthFlow
3. Sending a REGISTER request
4. Handling the response and extracting registration state
5. Proper error handling for common failures

Usage:
    # Using default Mizu demo account:
    export SIPX_LOCAL_HOST=<your-local-ip>
    python -m sipx.examples.register

    # Using custom SIP account:
    export SIPX_AOR=sip:1001@example.com
    export SIPX_REGISTRAR=sip:pbx.example.com:5060
    export SIPX_USERNAME=1001
    export SIPX_PASSWORD=secret
    python -m sipx.examples.register

    # Show help:
    python -m sipx.examples.register --help
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sipx import AsyncClient
from sipx.config import ClientConfig
from sipx.exceptions import AuthError, ProtocolError, TimeoutError as SipTimeoutError
from sipx.examples.common import account_settings, debug_wire, print_json
from sipx.protocol.auth import AuthFlow


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="SIP REGISTER example using AsyncClient",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  SIPX_AOR          Address of Record (e.g., sip:1001@example.com)
  SIPX_REGISTRAR    Registrar URI (e.g., sip:pbx.example.com:5060)
  SIPX_USERNAME     Authentication username
  SIPX_PASSWORD     Authentication password
  SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
  SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
  SIPX_TIMEOUT      Request timeout in seconds (default: 10)

Examples:
  # Register with default Mizu demo account
  export SIPX_LOCAL_HOST=192.168.1.100
  python -m sipx.examples.register

  # Register with custom account
  export SIPX_AOR=sip:alice@pbx.example.com
  export SIPX_REGISTRAR=sip:pbx.example.com:5060
  export SIPX_USERNAME=alice
  export SIPX_PASSWORD=secret123
  python -m sipx.examples.register --expires 3600
        """,
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=3600,
        help="Registration expiration in seconds (default: 3600)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable SIP wire-level debug output",
    )
    return parser.parse_args()


async def register(expires: int, debug: bool) -> None:
    """Perform SIP REGISTER using AsyncClient.

    This function demonstrates the complete registration flow:
    1. Load account settings from environment variables
    2. Create a ClientConfig with local bind address and timeout
    3. Create an AuthFlow for automatic digest authentication
    4. Create an AsyncClient with the config and auth
    5. Send a REGISTER request to the registrar
    6. Handle the response and extract registration state

    Args:
        expires: Registration expiration in seconds.
        debug: Enable wire-level debug output.
    """
    # Load account settings from environment variables
    # These defaults to the public Mizu demo account for easy testing
    s = account_settings()

    # Step 1: Create ClientConfig
    # ClientConfig holds transport and identity settings for the client.
    # - local_host/local_port: Where to bind the UDP socket
    # - timeout: How long to wait for responses
    # - from_uri: The From header URI (usually the AOR)
    # - contact_uri: The Contact header URI (where to receive requests)
    # - user_agent: The User-Agent header value
    config = ClientConfig(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )

    # Step 2: Create AuthFlow for automatic digest authentication
    # AuthFlow handles 401/407 challenges automatically:
    # - First request is sent without auth
    # - If server responds with 401/407, AuthFlow extracts the challenge
    # - Second request is sent with proper Authorization header
    # This follows the httpx-style generator-based auth pattern.
    auth = AuthFlow(
        username=s["username"],
        password=s["credential"],
    )

    # Step 3: Set up event hooks (optional)
    # Event hooks allow intercepting requests and responses for debugging.
    # The "wire" hook fires for every SIP message sent/received.
    event_hooks = {}
    if debug:
        event_hooks["wire"] = [debug_wire]

    # Step 4: Create and use the AsyncClient
    # The async context manager ensures proper cleanup:
    # - Starts the transport (binds UDP socket)
    # - Starts the receive loop for incoming messages
    # - Closes everything on exit
    async with AsyncClient(
        transport="udp",
        config=config,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        # Step 5: Send REGISTER request
        # The register() method:
        # - Builds a REGISTER request with proper headers
        # - Sends it to the registrar (extracted from URI)
        # - Handles auth challenges automatically via AuthFlow
        # - Returns the final Response
        #
        # The Expires header controls registration duration.
        # Use 0 to unregister (remove binding).
        try:
            response = await client.register(
                s["registrar"],
                Expires=str(expires),
            )
        except SipTimeoutError as exc:
            # Timeout waiting for response - network issue or server down
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
            # Authentication failed - wrong credentials
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
            # Protocol violation - malformed response
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
        # A 200 OK means registration succeeded.
        # The Contact header shows the registered binding.
        # The Expires header shows the actual expiration.
        if response.status_code == 200:
            contact = response.headers.get("Contact", "unknown")
            expires_header = response.headers.get("Expires", str(expires))
            print_json({
                "state": "registered",
                "status_code": response.status_code,
                "contact": contact,
                "expires": expires_header,
                "local_address": {
                    "host": client.transport.local_address[0],
                    "port": client.transport.local_address[1],
                },
            })
        else:
            # Non-200 response - registration failed
            print_json({
                "state": "failed",
                "status_code": response.status_code,
                "reason": response.reason,
                "headers": dict(response.headers.items()),
            })


def main() -> None:
    """Entry point for the register example."""
    args = parse_args()
    try:
        asyncio.run(register(expires=args.expires, debug=args.debug))
    except KeyboardInterrupt:
        print("\nRegistration cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
