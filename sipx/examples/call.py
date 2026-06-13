"""Full call example: INVITE -> ACK -> BYE using AsyncClient dialogs.

This drives a complete UAC call leg:

1. Build an SDP audio offer.
2. Send INVITE and wait for the final 2xx (provisional 1xx responses such as
   100 Trying and 180 Ringing are collected on ``response.history``).
3. ACK the 2xx to confirm the dialog (RFC 3261 §13.2.2.4).
4. After a short hold, send BYE to terminate the dialog (RFC 3261 §15).

The client tracks the dialog by Call-ID, so ``ack``/``bye`` only need that id.

Usage (all configuration via SIPX_* environment variables):
    export SIPX_TARGET=sip:2222@demo.mizu-voip.com:37075
    python -m sipx.examples.call

Environment variables:
    SIPX_AOR          Address of Record used in the From header
    SIPX_USERNAME     Authentication username
    SIPX_PASSWORD     Authentication password
    SIPX_LOCAL_HOST   Local bind address (default: 0.0.0.0)
    SIPX_LOCAL_PORT   Local bind port (default: 0 for ephemeral)
    SIPX_TIMEOUT      Request timeout in seconds (default: 10)
    SIPX_TARGET       Target SIP URI to call (default: account AOR)
    SIPX_CODECS       Space-separated codecs to offer (default: "PCMU PCMA")
    SIPX_RTP_PORT     Local RTP port advertised in SDP (default: 10000)
    SIPX_HOLD         Seconds to stay on the call before BYE (default: 1)
    SIPX_DEBUG        Set to 1 to print SIP request/response debug output

References:
    RFC 3261 §13 - Initiating a Session (INVITE)
    RFC 3261 §13.2.2.4 - The ACK for a 2xx
    RFC 3261 §15 - Terminating a Session (BYE)
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
from sipx.sdp import create_audio_offer


def _history_summary(response: object) -> list[dict[str, object]]:
    """Flatten ``response.history`` into status/reason pairs for display."""
    history = getattr(response, "history", [])
    return [
        {"status_code": item.status_code, "reason": item.reason} for item in history
    ]


async def call(
    target: str,
    codecs: list[str],
    rtp_port: int,
    hold: float,
    debug: bool,
) -> None:
    """Place a call to *target*, confirm it, hold briefly, then hang up.

    Args:
        target: Target SIP URI to call.
        codecs: Audio codec names to offer.
        rtp_port: Local RTP port advertised in the SDP offer.
        hold: Seconds to remain on the call before sending BYE.
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

    # SDP needs a routable address; 0.0.0.0 is not valid in a c= line.
    sdp_host = s["local_host"] if s["local_host"] != "0.0.0.0" else "127.0.0.1"
    offer = create_audio_offer(
        connection_address=sdp_host,
        port=rtp_port,
        codecs=tuple(codecs),
        telephone_event=True,
    )
    sdp_body = offer.to_sdp().encode("utf-8")

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
            response = await client.invite(
                target,
                body=sdp_body,
                headers={
                    "Content-Type": "application/sdp",
                    "Content-Length": str(len(sdp_body)),
                },
            )
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

        if not 200 <= response.status_code < 300:
            print_json(
                {
                    "state": "not_answered",
                    "status_code": response.status_code,
                    "reason": response.reason,
                    "provisional_history": _history_summary(response),
                }
            )
            return

        call_id = response.headers.get("Call-ID")
        call_id = call_id if isinstance(call_id, str) else ""
        dialog = client.dialog(call_id) if call_id else None
        if dialog is None:
            # No Contact in the 2xx means no in-dialog target to ACK/BYE.
            print_json(
                {
                    "state": "answered_no_dialog",
                    "status_code": response.status_code,
                    "provisional_history": _history_summary(response),
                }
            )
            return

        # Confirm the dialog, stay on the call, then terminate it.
        await client.ack(call_id)
        await asyncio.sleep(hold)
        try:
            bye_response = await client.bye(call_id)
            bye_status = bye_response.status_code
        except (SipTimeoutError, ProtocolError) as exc:
            bye_status = None
            print(f"BYE failed: {exc}", file=sys.stderr)

        print_json(
            {
                "state": "completed",
                "status_code": response.status_code,
                "call_id": call_id,
                "dialog_state": dialog.state,
                "provisional_history": _history_summary(response),
                "bye_status": bye_status,
            }
        )


def main() -> None:
    """Entry point for the call example."""
    s = account_settings()
    codecs = os.getenv("SIPX_CODECS", "PCMU PCMA").split()
    rtp_port = int(os.getenv("SIPX_RTP_PORT", "10000"))
    hold = float(os.getenv("SIPX_HOLD", "1"))
    debug = os.getenv("SIPX_DEBUG", "0") not in ("", "0", "false")
    try:
        asyncio.run(
            call(
                target=s["target"],
                codecs=codecs,
                rtp_port=rtp_port,
                hold=hold,
                debug=debug,
            )
        )
    except KeyboardInterrupt:
        print("\nCall cancelled by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
