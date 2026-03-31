#!/usr/bin/env python3
"""
sipx — Async IVR Demo with REAL RTP + DTMF (no Asterisk)

Full async event loop. SIP client ops run in thread pool via asyncio.to_thread.
IVR handler runs as async coroutine.

    sngrep port 15070                    # SIP
    sudo tcpdump -i lo udp port 19000   # RTP

Usage:
    uv run python examples/ivr.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Annotated

from rich import box
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import (
    Client,
    SIPServer,
    Request,
    Response,
    SDPBody,
    FromHeader,
    AutoRTP,
    on,
    Events,
)
from sipx._utils import console
from sipx.media import RTPSession, ToneGenerator, CallSession

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
SIP_PORT = 15080
CLIENT_PORT = 15081
RTP_SERVER = 19010
RTP_CLIENT = 19012

# ---------------------------------------------------------------------------
# IVR Server
# ---------------------------------------------------------------------------

server = SIPServer(local_host=HOST, local_port=SIP_PORT)
tone = ToneGenerator(440)
ivr_state = {"dtmf": None, "rtp_packets": 0}
loop: asyncio.AbstractEventLoop | None = None


@server.invite
def on_invite(
    request: Request,
    caller: Annotated[str, FromHeader],
    rtp: Annotated[RTPSession, AutoRTP(port=RTP_SERVER)],
) -> Response:
    console.print(f"\n  [bold green]IVR: call from {caller}[/bold green]")
    if loop:
        asyncio.run_coroutine_threadsafe(_async_ivr(rtp), loop)

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


async def _async_ivr(rtp: RTPSession):
    """Async IVR: greeting → collect DTMF → response. Blocking I/O in thread pool."""
    await asyncio.sleep(0.5)
    rtp.start()

    console.print("\n  [bold yellow]--- IVR Started (async) ---[/bold yellow]")
    try:
        # Play greeting (blocking → thread pool)
        console.print('  [cyan]TTS: "Press 1 for sales, 2 for support"[/cyan]')
        pcm = tone.generate(500)
        await asyncio.to_thread(rtp.send_audio, pcm)
        ivr_state["rtp_packets"] = len(pcm) // 320

        # Collect DTMF (blocking → thread pool)
        console.print("  [dim]Listening for DTMF...[/dim]")
        digits = await asyncio.to_thread(rtp.dtmf.collect, 3, 5.0)

        if digits:
            ivr_state["dtmf"] = digits
            console.print(f"  [yellow]DTMF received: '{digits}'[/yellow]")
        else:
            console.print("  [dim]No DTMF (timeout)[/dim]")

        # Play response
        console.print(f'  [cyan]TTS: "You entered {digits or "nothing"}"[/cyan]')
        pcm2 = tone.generate(300)
        await asyncio.to_thread(rtp.send_audio, pcm2)
        ivr_state["rtp_packets"] += len(pcm2) // 320

    finally:
        rtp.stop()
        console.print("  [bold yellow]--- IVR Ended (async) ---[/bold yellow]")


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
# Async Client (sync Client in thread pool)
# ---------------------------------------------------------------------------


async def run_client() -> CallerEvents:
    events = CallerEvents()
    sdp = SDPBody.audio(ip=HOST, port=RTP_CLIENT)

    def _sip_flow():
        """Sync SIP flow running in thread pool."""
        with Client(local_host=HOST, local_port=CLIENT_PORT) as client:
            client.events = events

            # INVITE
            r = client.invite(
                to_uri=f"sip:ivr@{HOST}:{SIP_PORT}",
                from_uri=f"sip:caller@{HOST}",
                body=sdp.to_string(),
                headers={"Contact": f"<sip:caller@{HOST}:{CLIENT_PORT}>"},
                host=HOST,
                port=SIP_PORT,
            )
            if r.status_code != 200:
                return

            # ACK
            client.ack(response=r, host=HOST, port=SIP_PORT)

            # DTMF via real RTP
            with CallSession(client, r, rtp_port=RTP_CLIENT) as call:
                import time
                time.sleep(2)
                call.send_dtmf("123")
                time.sleep(2)

            # BYE
            client.bye(response=r, host=HOST, port=SIP_PORT)

    await asyncio.to_thread(_sip_flow)
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    global loop
    loop = asyncio.get_running_loop()

    console.print("\n[bold]sipx — Async IVR Demo (real RTP + DTMF)[/bold]")
    console.print(f"SIP: {HOST}:{SIP_PORT}  RTP: {RTP_SERVER}/{RTP_CLIENT}\n")

    server.start()
    await asyncio.sleep(0.5)

    try:
        # Client runs in parallel with IVR coroutines
        console.rule("Running async IVR")
        events = await run_client()

        await asyncio.sleep(0.5)  # let IVR finish

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
        table.add_row("Async", p(sip_ok, "asyncio + to_thread"))
        console.print(table)

    except Exception as e:
        console.print(f"\n[red]{e}[/red]")
        raise
    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())
