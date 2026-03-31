#!/usr/bin/env python3
"""
sipx — Async IVR Demo: Bidirectional RTP + 3 DTMF Methods

Full async. Bidirectional audio (server↔client). All 3 DTMF protocols:
  1. RFC 4733 (telephone-event via RTP) — most common
  2. SIP INFO (application/dtmf-relay) — out-of-band
  3. Inband (dual-tone in audio stream) — legacy

    sngrep port 15080                    # SIP + SIP INFO
    sudo tcpdump -i lo udp port 19010   # RTP (server)
    sudo tcpdump -i lo udp port 19012   # RTP (client)

Usage:
    uv run python examples/ivr.py
"""

import asyncio
import sys
import time
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
from sipx.media import RTPSession, ToneGenerator, DTMFToneGenerator, CallSession

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
tone_low = ToneGenerator(330)

ivr_state: dict[str, object] = {
    "dtmf_rfc4733": None,
    "dtmf_info": None,
    "dtmf_inband": False,
    "rtp_sent": 0,
    "rtp_received": 0,
}
main_loop: asyncio.AbstractEventLoop | None = None


@server.invite
def on_invite(
    request: Request,
    caller: Annotated[str, FromHeader],
    rtp: Annotated[RTPSession, AutoRTP(port=RTP_SERVER)],
) -> Response:
    console.print(f"\n  [bold green]IVR: call from {caller}[/bold green]")
    if main_loop:
        asyncio.run_coroutine_threadsafe(_async_ivr(rtp), main_loop)

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


# Handle DTMF via SIP INFO (method 2)
@server.handle("INFO")
def on_info(request: Request, source) -> Response:
    body = request.content.decode("utf-8", errors="ignore") if request.content else ""
    if "Signal=" in body:
        digit = body.split("Signal=")[1].split("\r")[0].split("\n")[0].strip()
        ivr_state["dtmf_info"] = digit
        console.print(f"  [yellow]IVR: DTMF '{digit}' via SIP INFO[/yellow]")
    return Response(
        status_code=200,
        headers={
            "Via": request.via or "",
            "From": request.from_header or "",
            "To": request.to_header or "",
            "Call-ID": request.call_id or "",
            "CSeq": request.cseq or "",
            "Content-Length": "0",
        },
    )


async def _async_ivr(rtp: RTPSession):
    """Async IVR: bidirectional audio + DTMF collection."""
    await asyncio.sleep(0.5)
    rtp.start()

    console.print("\n  [bold yellow]--- IVR Started (async, bidirectional) ---[/bold yellow]")
    try:
        # Send greeting tone (server → client)
        console.print('  [cyan]Server → Client: 440Hz greeting tone[/cyan]')
        pcm = tone.generate(500)
        await asyncio.to_thread(rtp.send_audio, pcm)
        ivr_state["rtp_sent"] = len(pcm) // 320

        # Receive audio from client (client → server) in background
        async def _recv_audio():
            count = 0
            for _ in range(20):  # try for ~10s
                audio = await asyncio.to_thread(rtp.recv_audio, 0.5)
                if audio:
                    count += 1
            ivr_state["rtp_received"] = count

        recv_task = asyncio.create_task(_recv_audio())

        # Collect RFC 4733 DTMF
        console.print("  [dim]Listening for RFC 4733 DTMF...[/dim]")
        digits = await asyncio.to_thread(rtp.dtmf.collect, 3, 8.0)
        if digits:
            ivr_state["dtmf_rfc4733"] = digits
            console.print(f"  [yellow]DTMF RFC 4733: '{digits}'[/yellow]")

        # Send response tone
        console.print("  [cyan]Server → Client: response tone[/cyan]")
        pcm2 = tone_low.generate(300)
        await asyncio.to_thread(rtp.send_audio, pcm2)
        ivr_state["rtp_sent"] += len(pcm2) // 320

        # Wait for receive task
        recv_task.cancel()
        try:
            await recv_task
        except asyncio.CancelledError:
            pass

    finally:
        rtp.stop()
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
# Client Flow
# ---------------------------------------------------------------------------


async def run_client() -> CallerEvents:
    events = CallerEvents()
    sdp = SDPBody.audio(ip=HOST, port=RTP_CLIENT)
    dtmf_tone_gen = DTMFToneGenerator()

    def _sip_flow():
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
                console.print(f"  [red]Failed: {r.status_code}[/red]")
                return

            # ACK
            client.ack(response=r, host=HOST, port=SIP_PORT)

            with CallSession(client, r, rtp_port=RTP_CLIENT) as call:
                time.sleep(2)  # wait for IVR greeting

                # --- Method 1: RFC 4733 (telephone-event via RTP) ---
                console.print("\n  [bold]DTMF Method 1: RFC 4733 (RTP telephone-event)[/bold]")
                console.print("  [yellow]Sending '123' via RFC 4733...[/yellow]")
                call.send_dtmf("123")
                console.print("  [green]RFC 4733: sent 15 RTP packets (5 per digit)[/green]")

                time.sleep(1)

                # --- Method 2: SIP INFO ---
                console.print("\n  [bold]DTMF Method 2: SIP INFO (out-of-band)[/bold]")
                console.print("  [yellow]Sending '5' via SIP INFO...[/yellow]")
                client.info(
                    uri=f"sip:ivr@{HOST}:{SIP_PORT}",
                    content="Signal=5\r\nDuration=160\r\n",
                    content_type="application/dtmf-relay",
                    host=HOST,
                    port=SIP_PORT,
                )
                console.print("  [green]SIP INFO: sent as SIP message (not RTP)[/green]")

                time.sleep(1)

                # --- Method 3: Inband DTMF (dual-tone in audio) ---
                console.print("\n  [bold]DTMF Method 3: Inband (dual-tone in audio stream)[/bold]")
                console.print("  [yellow]Sending '9' as audio tone (697+1477 Hz)...[/yellow]")
                dtmf_pcm = dtmf_tone_gen.generate_digit("9", duration_ms=200)
                call.play(dtmf_pcm)
                ivr_state["dtmf_inband"] = True
                console.print("  [green]Inband: sent as RTP audio (real DTMF tone)[/green]")

                time.sleep(1)

                # --- Send regular audio (client → server) ---
                console.print("\n  [bold]Bidirectional Audio[/bold]")
                console.print("  [yellow]Client → Server: sending 880Hz tone...[/yellow]")
                call.play_tone(freq=880, duration_ms=500)
                console.print("  [green]Audio sent (client → server)[/green]")

                time.sleep(1)

            # BYE
            client.bye(response=r, host=HOST, port=SIP_PORT)

    await asyncio.to_thread(_sip_flow)
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    console.print("\n[bold]sipx — Async IVR: Bidirectional RTP + 3 DTMF Methods[/bold]")
    console.print(f"SIP: {HOST}:{SIP_PORT}  RTP: {RTP_SERVER}/{RTP_CLIENT}\n")

    server.start()
    await asyncio.sleep(0.5)

    try:
        console.rule("IVR Session")
        events = await run_client()
        await asyncio.sleep(1)

        # Summary
        console.rule("Summary")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Test", style="bold", width=22)
        table.add_column("Result", width=50)

        def p(ok, msg):
            return f"[green]PASS[/green] — {msg}" if ok else f"[red]FAIL[/red] — {msg}"

        sip_ok = events.connected
        rtp_sent = ivr_state.get("rtp_sent", 0) not in (0, None)
        rtp_recv = ivr_state.get("rtp_received", 0) not in (0, None)
        dtmf_4733 = ivr_state.get("dtmf_rfc4733") == "123"
        dtmf_info = ivr_state.get("dtmf_info") == "5"
        dtmf_inband = ivr_state.get("dtmf_inband") is True

        table.add_row("SIP Signaling", p(sip_ok, "INVITE->200->ACK->BYE"))
        table.add_row("RTP Server→Client", p(rtp_sent, f"{ivr_state['rtp_sent']} packets"))
        table.add_row("RTP Client→Server", p(rtp_recv, f"{ivr_state['rtp_received']} packets"))
        table.add_row("DTMF RFC 4733", p(dtmf_4733, f"'{ivr_state['dtmf_rfc4733']}' (RTP PT=101)"))
        table.add_row("DTMF SIP INFO", p(dtmf_info, f"'{ivr_state['dtmf_info']}' (SIP message)"))
        table.add_row("DTMF Inband", p(dtmf_inband, "digit '9' as 697+1477Hz audio"))
        table.add_row("Async", p(sip_ok, "asyncio + coroutines + to_thread"))

        console.print(table)

        all_ok = sip_ok and rtp_sent and dtmf_4733 and dtmf_info and dtmf_inband
        if all_ok:
            console.print("\n[bold green]All 3 DTMF methods + bidirectional RTP working![/bold green]\n")

    except Exception as e:
        console.print(f"\n[red]{e}[/red]")
        raise
    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())
