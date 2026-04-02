#!/usr/bin/env python3
"""
sipx — IVR: Bidirectional RTP + 3 DTMF Methods (100% async API)


    sngrep port 15080
    sudo tcpdump -i lo udp port 19010

Usage:
    uv run python examples/ivr.py
"""

import asyncio
from typing import Annotated

from rich import box
from rich.table import Table
from sipx import (
    AsyncSIPClient,
    AsyncSIPServer,
    Request,
    SDPBody,
    FromHeader,
    AutoRTP,
    Source,
    on,
    Events,
)
from rich.console import Console
from sipx.media import (
    RTPSession,
    AsyncRTPSession,
    ToneGenerator,
    DTMFToneGenerator,
)

console = Console()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
SIP_PORT = 15080
CLIENT_PORT = 15081
RTP_SERVER = 19010
RTP_CLIENT = 19012

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

server = AsyncSIPServer(local_host=HOST, local_port=SIP_PORT)
tone = ToneGenerator(440)
tone_low = ToneGenerator(330)

results: dict[str, object] = {
    "dtmf_rfc4733": None,
    "dtmf_info": None,
    "dtmf_inband": False,
    "rtp_sent": 0,
}
_loop: asyncio.AbstractEventLoop | None = None

# ---------------------------------------------------------------------------
# Server handlers
# ---------------------------------------------------------------------------


@server.invite()
def on_invite(
    request: Request,
    caller: Annotated[str, FromHeader],
    rtp: Annotated[RTPSession, AutoRTP(port=RTP_SERVER)],
):
    console.print(f"\n  [bold green]IVR: call from {caller}[/bold green]")

    # Create native async RTP from sync RTP's parameters
    async_rtp = AsyncRTPSession(
        local_ip=rtp.local_ip,
        local_port=rtp.local_port,
        remote_ip=rtp.remote_ip,
        remote_port=rtp.remote_port,
        payload_type=rtp.payload_type,
        clock_rate=rtp.clock_rate,
    )
    if _loop:
        _loop.call_soon_threadsafe(asyncio.ensure_future, _ivr_flow(async_rtp))

    answer = SDPBody.audio(ip=HOST, port=RTP_SERVER)
    return request.ok(
        headers={
            "To": (request.to_header or "") + ";tag=ivr-tag",
            "Contact": f"<sip:ivr@{HOST}:{SIP_PORT}>",
            "Content-Type": "application/sdp",
        },
        content=answer.to_string(),
    )


@server.handle("INFO")
def on_info(request: Request, source: Annotated[object, Source]):
    body = request.content.decode("utf-8", errors="ignore") if request.content else ""
    if "Signal=" in body:
        digit = body.split("Signal=")[1].split("\r")[0].split("\n")[0].strip()
        results["dtmf_info"] = digit
        console.print(f"  [yellow]IVR: DTMF '{digit}' via SIP INFO[/yellow]")
    return request.ok()


async def _ivr_flow(rtp: AsyncRTPSession):
    """Async IVR: play greeting -> collect DTMF -> play response."""
    await asyncio.sleep(0.5)
    await rtp.start()

    console.print("\n  [bold yellow]--- IVR Started ---[/bold yellow]")
    try:
        # Play greeting
        console.print("  [cyan]Server -> Client: 440Hz greeting[/cyan]")
        pcm = tone.generate(500)
        await rtp.send_audio(pcm)
        results["rtp_sent"] = len(pcm) // 320

        # Collect DTMF
        console.print("  [dim]Listening for DTMF...[/dim]")
        digits = await rtp.dtmf.collect(max_digits=3, timeout=8.0)
        if digits:
            results["dtmf_rfc4733"] = digits
            console.print(f"  [yellow]DTMF RFC 4733: '{digits}'[/yellow]")

        # Play response
        console.print("  [cyan]Server -> Client: response tone[/cyan]")
        pcm2 = tone_low.generate(300)
        await rtp.send_audio(pcm2)
        results["rtp_sent"] = int(results["rtp_sent"] or 0) + len(pcm2) // 320
    finally:
        await rtp.stop()
        console.print("  [bold yellow]--- IVR Ended ---[/bold yellow]")


# ---------------------------------------------------------------------------
# Client events
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


async def main():
    global _loop
    _loop = asyncio.get_running_loop()

    console.print("\n[bold]sipx — IVR: Bidirectional RTP + 3 DTMF (async API)[/bold]")
    console.print(f"SIP: {HOST}:{SIP_PORT}  RTP: {RTP_SERVER}/{RTP_CLIENT}\n")

    await server.start()
    await asyncio.sleep(0.5)

    try:
        events = CallerEvents()
        dtmf_gen = DTMFToneGenerator()
        sdp = SDPBody.audio(ip=HOST, port=RTP_CLIENT)

        async with AsyncSIPClient(local_host=HOST, local_port=CLIENT_PORT) as client:
            client.events = events

            # INVITE
            console.rule("1. INVITE")
            r = await client.invite(
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
            console.rule("2. ACK")
            await client.ack(host=HOST, port=SIP_PORT)

            # DTMF (3 methods)
            console.rule("3. DTMF (3 methods)")
            call = AsyncRTPSession(
                local_ip=HOST,
                local_port=RTP_CLIENT,
                remote_ip=HOST,
                remote_port=RTP_SERVER,
            )
            async with call:
                await asyncio.sleep(2)

                # Method 1: RFC 4733
                console.print("  [bold]RFC 4733 (RTP telephone-event)[/bold]")
                await call.dtmf.send("123")
                console.print("  [green]Sent '123' (15 RTP packets)[/green]")
                await asyncio.sleep(1)

                # Method 2: SIP INFO
                console.print("  [bold]SIP INFO (out-of-band)[/bold]")
                await client.info(
                    uri=f"sip:ivr@{HOST}:{SIP_PORT}",
                    content="Signal=5\r\nDuration=160\r\n",
                    content_type="application/dtmf-relay",
                    host=HOST,
                    port=SIP_PORT,
                )
                console.print("  [green]Sent '5' via SIP INFO[/green]")
                await asyncio.sleep(1)

                # Method 3: Inband
                console.print("  [bold]Inband (dual-tone audio)[/bold]")
                await call.send_audio(dtmf_gen.generate_digit("9", duration_ms=200))
                results["dtmf_inband"] = True
                console.print("  [green]Sent '9' as 697+1477Hz tone[/green]")
                await asyncio.sleep(1)

                # Bidirectional audio
                console.print("  [bold]Bidirectional audio[/bold]")
                await call.send_audio(ToneGenerator(880).generate(500))
                console.print("  [green]Client -> Server: 880Hz tone[/green]")
                await asyncio.sleep(1)

            # BYE
            console.rule("4. BYE")
            await client.bye(host=HOST, port=SIP_PORT)

        # Summary
        await asyncio.sleep(0.5)
        console.rule("Summary")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Test", style="bold", width=20)
        table.add_column("Result", width=45)

        def p(ok, msg):
            return f"[green]PASS[/green] — {msg}" if ok else f"[red]FAIL[/red] — {msg}"

        sip_ok = events.connected
        rtp_ok = (results.get("rtp_sent") or 0) != 0
        dtmf_4733 = results.get("dtmf_rfc4733") == "123"
        dtmf_info = results.get("dtmf_info") == "5"
        dtmf_inband = results.get("dtmf_inband") is True

        table.add_row("SIP", p(sip_ok, "INVITE->200->ACK->BYE"))
        table.add_row("RTP", p(rtp_ok, f"{results['rtp_sent']} packets"))
        table.add_row("DTMF RFC 4733", p(dtmf_4733, f"'{results['dtmf_rfc4733']}'"))
        table.add_row("DTMF SIP INFO", p(dtmf_info, f"'{results['dtmf_info']}'"))
        table.add_row("DTMF Inband", p(dtmf_inband, "'9' as 697+1477Hz"))
        console.print(table)

        if all([sip_ok, rtp_ok, dtmf_4733, dtmf_info, dtmf_inband]):
            console.print("\n[bold green]All tests passed![/bold green]\n")

    except Exception as e:
        console.print(f"\n[red]{e}[/red]")
        raise
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
