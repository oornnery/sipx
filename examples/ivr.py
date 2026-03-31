#!/usr/bin/env python3
"""
sipx — IVR Demo with REAL RTP + DTMF (no Asterisk)

sipx as both server (IVR) and client. Real RTP audio and DTMF RFC 4733.

    sngrep port 15070                    # SIP
    sudo tcpdump -i lo udp port 19000   # RTP

Usage:
    uv run python examples/ivr.py
"""

import sys
import threading
import time
from pathlib import Path
from typing import Annotated

from rich import box
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import (
    SIPServer,
    Request,
    Response,
    SDPBody,
    FromHeader,
    AutoRTP,
    console,
    on,
    Client,
    Events,
)
from sipx.media import (
    RTPSession,
    ToneGenerator,
    CallSession,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
SIP_PORT = 15070
CLIENT_PORT = 15071
RTP_SERVER = 19000
RTP_CLIENT = 19002

# ---------------------------------------------------------------------------
# IVR Server
# ---------------------------------------------------------------------------

server = SIPServer(local_host=HOST, local_port=SIP_PORT)
tone = ToneGenerator(440)

# Shared state for results
ivr_state = {
    "dtmf": None,
    "rtp_packets": 0,
    "active": False,
}


@server.invite
def on_invite(
    request: Request,
    caller: Annotated[str, FromHeader],
    rtp: Annotated[RTPSession, AutoRTP(port=RTP_SERVER)],
) -> Response:
    """Handle incoming INVITE — answer and run IVR."""
    console.print(f"\n  [bold green]IVR: call from {caller}[/bold green]")

    ivr_state["active"] = True

    # Start IVR in background (after response is sent)
    threading.Thread(target=_run_ivr, args=(rtp,), daemon=True).start()

    answer = SDPBody.audio(ip=HOST, port=RTP_SERVER)
    return Response(
        status_code=200,
        headers={
            "Via": request.via or "",
            "From": request.from_header or "",
            "To": (request.to_header or "") + ";tag=ivr-tag",
            "Call-ID": request.call_id or "",
            "CSeq": request.cseq or "",
            "Contact": f"<sip:ivr@{HOST}:{SIP_PORT}>",
            "Content-Type": "application/sdp",
        },
        content=answer.to_string(),
    )


def _run_ivr(rtp: RTPSession):
    """IVR flow: play greeting, collect DTMF, play response."""
    time.sleep(0.5)
    rtp.start()

    console.print("\n  [bold yellow]--- IVR Started ---[/bold yellow]")
    try:
        # Play greeting tone
        console.print('  [cyan]TTS: "Press 1 for sales, 2 for support"[/cyan]')
        pcm = tone.generate(500)
        rtp.send_audio(pcm)
        ivr_state["rtp_packets"] = len(pcm) // 320

        # Collect DTMF (real RFC 4733)
        console.print("  [dim]Listening for DTMF...[/dim]")
        digits = rtp.dtmf.collect(max_digits=3, timeout=5.0)

        if digits:
            ivr_state["dtmf"] = digits
            console.print(f"  [yellow]DTMF received: '{digits}'[/yellow]")
        else:
            console.print("  [dim]No DTMF (timeout)[/dim]")

        # Play response tone
        console.print(f'  [cyan]TTS: "You entered {digits or "nothing"}"[/cyan]')
        pcm2 = tone.generate(300)
        rtp.send_audio(pcm2)
        ivr_state["rtp_packets"] += len(pcm2) // 320

    finally:
        rtp.stop()
        ivr_state["active"] = False
        console.print("  [bold yellow]--- IVR Ended ---[/bold yellow]")


# ---------------------------------------------------------------------------
# Client Events
# ---------------------------------------------------------------------------


class CallerEvents(Events):
    def __init__(self):
        super().__init__()
        self.connected = False

    @on("INVITE", status=200)
    def on_ok(self, request, response, context):
        self.connected = True
        console.print("  [green]Call accepted[/green]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    console.print("\n[bold]sipx — IVR Demo (real RTP + DTMF)[/bold]")
    console.print(f"SIP: {HOST}:{SIP_PORT}  RTP: {RTP_SERVER}/{RTP_CLIENT}\n")

    server.start()
    time.sleep(0.5)

    try:
        events = CallerEvents()
        sdp = SDPBody.audio(ip=HOST, port=RTP_CLIENT)

        with Client(local_host=HOST, local_port=CLIENT_PORT) as client:
            client.events = events

            # 1. INVITE
            console.rule("1. INVITE")
            r = client.invite(
                to_uri=f"sip:ivr@{HOST}:{SIP_PORT}",
                from_uri=f"sip:caller@{HOST}",
                body=sdp.to_string(),
                headers={"Contact": f"<sip:caller@{HOST}:{CLIENT_PORT}>"},
                host=HOST,
                port=SIP_PORT,
            )
            if r.status_code != 200:
                console.print(f"  [red]Failed: {r.status_code}[/red]")
                return

            # 2. ACK
            console.rule("2. ACK")
            client.ack(response=r, host=HOST, port=SIP_PORT)

            # 3. Send DTMF via real RTP
            console.rule("3. DTMF")
            with CallSession(client, r, rtp_port=RTP_CLIENT) as call:
                time.sleep(2)  # wait for IVR greeting
                console.print("  [yellow]Sending DTMF '123'...[/yellow]")
                call.send_dtmf("123")
                console.print("  [green]DTMF sent (15 RTP packets)[/green]")
                time.sleep(2)  # wait for IVR to process

            # 4. BYE
            console.rule("4. BYE")
            bye_r = client.bye(response=r, host=HOST, port=SIP_PORT)
            console.print(f"  BYE -> {bye_r.status_code}")

        # Summary
        console.rule("Summary")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Test", style="bold", width=16)
        table.add_column("Result", width=45)

        def p(ok, msg):
            return f"[green]PASS[/green] — {msg}" if ok else f"[red]FAIL[/red] — {msg}"

        sip_ok = events.connected
        rtp_ok = (ivr_state.get("rtp_packets") or 0) > 0
        dtmf_ok = ivr_state.get("dtmf") == "123"

        table.add_row("SIP", p(sip_ok, "INVITE->200->ACK->BYE->200"))
        table.add_row("RTP", p(rtp_ok, f"{ivr_state['rtp_packets']} packets"))
        table.add_row("DTMF", p(dtmf_ok, f"'{ivr_state['dtmf']}' via RFC 4733"))
        table.add_row("B2BUA", p(sip_ok, "sipx as UAC + UAS"))
        console.print(table)

    except Exception as e:
        console.print(f"\n[red]{e}[/red]")
        raise
    finally:
        server.stop()


if __name__ == "__main__":
    main()
