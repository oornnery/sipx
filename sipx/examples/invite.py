"""INVITE example with SDP offer/answer using the new httpx-like AsyncClient API.

This example demonstrates how to initiate a SIP session (call) using the
AsyncClient. It shows:

1. Creating an AsyncClient with configuration
2. Building an SDP offer for audio negotiation
3. Sending an INVITE request with the SDP body
4. Handling the response and extracting SDP answer
5. Proper error handling for common failures

Usage:
    # Using default Mizu demo account:
    export SIPX_LOCAL_HOST=<your-local-ip>
    python -m sipx.examples.invite sip:2222@demo.mizu-voip.com:37075

    # Using custom SIP account:
    export SIPX_AOR=sip:1001@example.com
    export SIPX_USERNAME=1001
    export SIPX_PASSWORD=secret
    python -m sipx.examples.invite sip:alice@pbx.example.com

    # Show help:
    python -m sipx.examples.invite --help
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
from sipx.sdp import create_audio_offer, parse_sdp


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="SIP INVITE example with SDP using AsyncClient",
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
  # Call the Mizu demo echo service
  export SIPX_LOCAL_HOST=192.168.1.100
  python -m sipx.examples.invite sip:2222@demo.mizu-voip.com:37075

  # Call with custom codecs
  python -m sipx.examples.invite sip:alice@pbx.example.com --codecs PCMU PCMA

  # Call with specific RTP port
  python -m sipx.examples.invite sip:alice@pbx.example.com --rtp-port 10000
        """,
    )
    parser.add_argument(
        "target",
        help="Target SIP URI to call (e.g., sip:alice@example.com)",
    )
    parser.add_argument(
        "--codecs",
        nargs="+",
        default=["PCMU", "PCMA"],
        help="Audio codecs to offer (default: PCMU PCMA)",
    )
    parser.add_argument(
        "--rtp-port",
        type=int,
        default=10000,
        help="Local RTP port to advertise in SDP (default: 10000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable SIP wire-level debug output",
    )
    return parser.parse_args()


async def invite(
    target: str,
    codecs: list[str],
    rtp_port: int,
    debug: bool,
) -> None:
    """Perform SIP INVITE with SDP using AsyncClient.

    This function demonstrates the complete call setup flow:
    1. Load account settings from environment variables
    2. Create a ClientConfig with local bind address and timeout
    3. Create an AuthFlow for automatic digest authentication
    4. Build an SDP offer with audio codecs
    5. Create an AsyncClient with the config and auth
    6. Send an INVITE request with the SDP body
    7. Handle the response and extract SDP answer

    Args:
        target: Target SIP URI to call.
        codecs: List of audio codec names to offer.
        rtp_port: Local RTP port to advertise in SDP.
        debug: Enable wire-level debug output.
    """
    # Load account settings from environment variables
    s = account_settings()

    # Step 1: Create ClientConfig
    # For INVITE, we need to set from_uri and contact_uri for proper
    # dialog establishment per RFC 3261 §13.
    config = ClientConfig(
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        from_uri=s["aor"],
        contact_uri=s["aor"],
        user_agent="sipx/2.0",
    )

    # Step 2: Create AuthFlow for automatic digest authentication
    # INVITE requests often require authentication, especially for
    # outbound calls through a PBX or proxy.
    auth = AuthFlow(
        username=s["username"],
        password=s["credential"],
    )

    # Step 3: Build SDP offer
    # The SDP offer describes our media capabilities:
    # - connection_address: IP address for RTP media
    # - port: UDP port for RTP media
    # - codecs: Audio codecs we support (PCMU=0, PCMA=8)
    # - telephone_event: Enable DTMF via RFC 4733
    #
    # Note: In a real application, you would bind an actual RTP socket
    # and use its bound address/port. Here we use the configured values
    # for demonstration purposes.
    local_host = s["local_host"]
    if local_host == "0.0.0.0":
        # For SDP, we need a real IP address, not 0.0.0.0
        # In production, you'd detect the local IP or use STUN
        local_host = "127.0.0.1"

    offer = create_audio_offer(
        connection_address=local_host,
        port=rtp_port,
        codecs=tuple(codecs),
        telephone_event=True,
    )
    sdp_body = offer.to_sdp().encode("utf-8")

    # Step 4: Set up event hooks (optional)
    event_hooks = {}
    if debug:
        event_hooks["wire"] = [debug_wire]

    # Step 5: Create and use the AsyncClient
    async with AsyncClient(
        transport="udp",
        config=config,
        auth=auth,
        event_hooks=event_hooks,
    ) as client:
        # Step 6: Send INVITE request
        # The invite() method:
        # - Builds an INVITE request with proper dialog headers
        # - Includes the SDP offer in the body
        # - Sends it to the target (extracted from URI)
        # - Handles auth challenges automatically via AuthFlow
        # - Waits for provisional (1xx) and final (2xx/3xx-6xx) responses
        # - Returns the final Response
        #
        # Required headers for INVITE:
        # - Content-Type: application/sdp (for SDP body)
        # - Content-Length: length of SDP body
        try:
            response = await client.invite(
                target,
                body=sdp_body,
                headers={
                    "Content-Type": "application/sdp",
                    "Content-Length": str(len(sdp_body)),
                },
            )
        except SipTimeoutError as exc:
            # Timeout waiting for response - callee didn't answer
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

        # Step 7: Process the response
        # A 2xx response means the call was accepted.
        # The response body contains the SDP answer from the callee.
        if 200 <= response.status_code < 300:
            # Parse SDP answer from response body
            answer_sdp = None
            if response.body:
                try:
                    answer_sdp = parse_sdp(response.body.decode("utf-8"))
                except Exception as e:
                    print(f"Warning: Failed to parse SDP answer: {e}", file=sys.stderr)

            # Extract dialog identifiers for future in-dialog requests
            call_id = response.headers.get("Call-ID", "unknown")
            from_header = response.headers.get("From", "")
            to_header = response.headers.get("To", "")

            result = {
                "state": "established",
                "status_code": response.status_code,
                "call_id": call_id,
                "from": from_header,
                "to": to_header,
                "offer": {
                    "codecs": codecs,
                    "rtp_port": rtp_port,
                },
            }

            if answer_sdp and answer_sdp.audio:
                # Extract negotiated codecs from answer
                answer_codecs = [
                    answer_sdp.audio.codecs[pt].name
                    for pt in answer_sdp.audio.payload_types
                    if pt in answer_sdp.audio.codecs
                ]
                result["answer"] = {
                    "codecs": answer_codecs,
                    "rtp_port": answer_sdp.audio.port,
                    "direction": answer_sdp.audio.direction,
                }

            print_json(result)

        elif 300 <= response.status_code < 400:
            # Redirect - callee is at a different address
            contact = response.headers.get("Contact", "unknown")
            print_json({
                "state": "redirected",
                "status_code": response.status_code,
                "contact": contact,
            })

        elif 400 <= response.status_code < 500:
            # Client error - request was rejected
            print_json({
                "state": "rejected",
                "status_code": response.status_code,
                "reason": response.reason,
            })

        elif 500 <= response.status_code < 600:
            # Server error - temporary failure
            print_json({
                "state": "server_error",
                "status_code": response.status_code,
                "reason": response.reason,
            })

        else:
            # Global failure
            print_json({
                "state": "failed",
                "status_code": response.status_code,
                "reason": response.reason,
            })


def main() -> None:
    """Entry point for the invite example."""
    args = parse_args()
    try:
        asyncio.run(
            invite(
                target=args.target,
                codecs=args.codecs,
                rtp_port=args.rtp_port,
                debug=args.debug,
            )
        )
    except KeyboardInterrupt:
        print("\nCall cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
