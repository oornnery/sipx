#!/usr/bin/env python3
"""
sipx — IVR Demo with REAL RTP and DTMF (no Asterisk required)

sipx acts as both SIP server (IVR) and client in the same process.
After SIP signaling, real RTP packets and DTMF (RFC 4733) flow over
UDP between the two endpoints. Visible in sngrep/tcpdump.

    sngrep port 15070                    # SIP signaling
    sudo tcpdump -i lo udp port 19000   # RTP server side
    sudo tcpdump -i lo udp port 19002   # RTP client side

Usage:
    uv run python examples/ivr.py
"""

import sys
import struct
import threading
import time
from pathlib import Path

from rich import box
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import (
    Client,
    Events,
    Request,
    Response,
    SDPBody,
    console,
    on,
)
from sipx._media._dtmf import DTMFCollector, DTMFSender
from sipx._media._rtp import RTPSession
from sipx._media._tts import BaseTTS
from sipx._server import SIPServer
from sipx._types import TransportAddress

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 15070
CLIENT_PORT = 15071
RTP_PORT_SERVER = 19000
RTP_PORT_CLIENT = 19002


# ---------------------------------------------------------------------------
# TTS — generates real PCM audio (sine wave tone)
# ---------------------------------------------------------------------------


class ToneTTS(BaseTTS):
    """TTS that generates a short tone as PCM audio and sends it via RTP."""

    @property
    def language(self) -> str:
        return "pt-BR"

    @property
    def sample_rate(self) -> int:
        return 8000

    def synthesize(self, text: str) -> bytes:
        """Generate 0.5s of 440Hz tone as 16-bit PCM (real audio)."""
        console.print(f'  [cyan]TTS: "{text}"[/cyan]')
        import math

        duration = 0.5
        freq = 440  # Hz
        samples = int(self.sample_rate * duration)
        pcm = bytearray()
        for i in range(samples):
            val = int(16000 * math.sin(2 * math.pi * freq * i / self.sample_rate))
            pcm.extend(struct.pack("<h", max(-32768, min(32767, val))))
        return bytes(pcm)


# ---------------------------------------------------------------------------
# IVR Server — answers calls, plays RTP audio, collects real DTMF
# ---------------------------------------------------------------------------


class IVRCallHandler:
    """Handles incoming INVITE: answers, sends RTP, collects DTMF."""

    def __init__(self):
        self.tts = ToneTTS()
        self.call_active = False
        self.ivr_result: str | None = None
        self.rtp_session: RTPSession | None = None
        self.rtp_packets_sent = 0
        self.dtmf_received: str | None = None

    def handle_invite(self, request: Request, source: TransportAddress) -> Response:
        """Answer INVITE with SDP and start IVR with real RTP."""
        console.print(f"\n  [bold green]IVR: incoming call from {source}[/bold green]")

        # Parse caller SDP to know their RTP port
        caller_rtp_port = RTP_PORT_CLIENT
        if request.content:
            from sipx._models._body import BodyParser

            try:
                caller_sdp = BodyParser.parse_sdp(request.content)
                ports = caller_sdp.get_media_ports()
                caller_rtp_port = ports.get("audio", RTP_PORT_CLIENT)
                console.print(
                    f"  [dim]Caller RTP: {source.host}:{caller_rtp_port}[/dim]"
                )
            except Exception:
                pass

        # Build answer SDP
        answer_sdp = SDPBody.create_offer(
            session_name="sipx-IVR",
            origin_username="ivr",
            origin_address=SERVER_HOST,
            connection_address=SERVER_HOST,
            media_specs=[
                {
                    "media": "audio",
                    "port": RTP_PORT_SERVER,
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {
                            "payload": "101",
                            "name": "telephone-event",
                            "rate": "8000",
                        },
                    ],
                }
            ],
        )

        # Create RTP session (server side: listens on RTP_PORT_SERVER, sends to caller's RTP port)
        self.rtp_session = RTPSession(
            local_ip=SERVER_HOST,
            local_port=RTP_PORT_SERVER,
            remote_ip=SERVER_HOST,
            remote_port=caller_rtp_port,
            payload_type=0,
            clock_rate=8000,
        )

        response = Response(
            status_code=200,
            reason_phrase="OK",
            headers={
                "Via": request.via or "",
                "From": request.from_header or "",
                "To": (request.to_header or "") + ";tag=ivr-server-tag",
                "Call-ID": request.call_id or "",
                "CSeq": request.cseq or "",
                "Contact": f"<sip:ivr@{SERVER_HOST}:{SERVER_PORT}>",
                "Content-Type": "application/sdp",
            },
            content=answer_sdp.to_string(),
        )

        self.call_active = True

        # Start IVR with real RTP in background
        threading.Thread(target=self._run_ivr, daemon=True).start()

        return response

    def _run_ivr(self):
        """Run IVR with real RTP audio and DTMF collection."""
        time.sleep(0.5)  # wait for ACK

        assert self.rtp_session is not None
        self.rtp_session.start()

        console.print(
            "\n  [bold yellow]--- IVR Session Started (real RTP) ---[/bold yellow]"
        )

        try:
            # Step 1: Play greeting via RTP (real audio packets)
            greeting = "Welcome to sipx IVR. Press 1 for sales, 2 for support."
            pcm_data = self.tts.synthesize(greeting)
            console.print(
                f"  [dim]Sending {len(pcm_data)} bytes PCM as RTP "
                f"({len(pcm_data) // 320} packets)...[/dim]"
            )
            self.rtp_session.send_audio(pcm_data)
            self.rtp_packets_sent = len(pcm_data) // 320

            # Step 2: Collect DTMF via RFC 4733 (real RTP telephone-event)
            console.print("  [dim]IVR: listening for DTMF on RTP...[/dim]")
            collector = DTMFCollector(self.rtp_session, max_digits=1, timeout=5.0)
            digit = collector.collect()

            if digit:
                self.dtmf_received = digit
                console.print(
                    f"  [yellow]IVR: received DTMF '{digit}' via RFC 4733[/yellow]"
                )
            else:
                self.dtmf_received = None
                console.print("  [dim]IVR: no DTMF received (timeout)[/dim]")

            # Step 3: Play response based on choice
            menu_map = {"1": "sales", "2": "support", "0": "operator"}
            self.ivr_result = menu_map.get(digit or "", "unknown")

            response_text = f"You selected {self.ivr_result}."
            pcm_resp = self.tts.synthesize(response_text)
            self.rtp_session.send_audio(pcm_resp)
            self.rtp_packets_sent += len(pcm_resp) // 320

        finally:
            self.rtp_session.stop()
            console.print("  [bold yellow]--- IVR Session Ended ---[/bold yellow]")
            self.call_active = False


# ---------------------------------------------------------------------------
# Client Events
# ---------------------------------------------------------------------------


class CallerEvents(Events):
    """Client-side event handlers."""

    def __init__(self):
        super().__init__()
        self.got_200 = False

    @on("INVITE", status=200)
    def on_call_accepted(self, request, response, context):
        self.got_200 = True
        if response.body:
            console.print("  [green]Caller: call accepted, SDP received[/green]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    console.print("\n[bold]sipx — IVR Demo with REAL RTP + DTMF[/bold]")
    console.print(f"SIP Server: {SERVER_HOST}:{SERVER_PORT}")
    console.print(f"SIP Client: {SERVER_HOST}:{CLIENT_PORT}")
    console.print(f"RTP Server: {SERVER_HOST}:{RTP_PORT_SERVER}")
    console.print(f"RTP Client: {SERVER_HOST}:{RTP_PORT_CLIENT}\n")
    console.print(
        "[dim]Capture RTP: sudo tcpdump -i lo udp port 19000 or port 19002[/dim]\n"
    )

    ivr_handler = IVRCallHandler()
    server = SIPServer(local_host=SERVER_HOST, local_port=SERVER_PORT)
    server.register_handler("INVITE", ivr_handler.handle_invite)

    # --- Start server ---
    console.rule("Starting IVR Server")
    server.start()
    time.sleep(0.5)

    try:
        console.rule("Client Calling IVR")
        events = CallerEvents()

        with Client(local_host=SERVER_HOST, local_port=CLIENT_PORT) as client:
            client.events = events

            sdp = SDPBody.create_offer(
                session_name="Caller",
                origin_username="caller",
                origin_address=SERVER_HOST,
                connection_address=SERVER_HOST,
                media_specs=[
                    {
                        "media": "audio",
                        "port": RTP_PORT_CLIENT,
                        "codecs": [
                            {"payload": "0", "name": "PCMU", "rate": "8000"},
                            {
                                "payload": "101",
                                "name": "telephone-event",
                                "rate": "8000",
                            },
                        ],
                    }
                ],
            )

            # 1. INVITE
            console.print("\n[bold]1. INVITE[/bold]")
            response = client.invite(
                to_uri=f"sip:ivr@{SERVER_HOST}:{SERVER_PORT}",
                from_uri=f"sip:caller@{SERVER_HOST}",
                body=sdp.to_string(),
                headers={
                    "Contact": f"<sip:caller@{SERVER_HOST}:{CLIENT_PORT}>",
                },
                host=SERVER_HOST,
                port=SERVER_PORT,
            )

            if response.status_code != 200:
                console.print(f"  [red]Call failed: {response.status_code}[/red]")
                return

            console.print("  [green]Call established (200 OK)[/green]")

            # 2. ACK
            console.print("\n[bold]2. ACK[/bold]")
            client.ack(response=response, host=SERVER_HOST, port=SERVER_PORT)
            console.print("  [green]ACK sent[/green]")

            # 3. Open client-side RTP to send DTMF
            console.print("\n[bold]3. RTP + DTMF[/bold]")
            client_rtp = RTPSession(
                local_ip=SERVER_HOST,
                local_port=RTP_PORT_CLIENT,
                remote_ip=SERVER_HOST,
                remote_port=RTP_PORT_SERVER,
                payload_type=0,
                clock_rate=8000,
            )
            client_rtp.start()

            try:
                # Wait for server to finish playing greeting
                console.print("  [dim]Waiting for IVR greeting...[/dim]")
                time.sleep(1.5)

                # Send DTMF digit '1' via RFC 4733
                console.print(
                    "  [yellow]Sending DTMF '1' via RFC 4733 (real RTP)...[/yellow]"
                )
                dtmf_sender = DTMFSender(client_rtp)
                dtmf_sender.send_digit("1", duration_ms=160)
                console.print("  [green]DTMF '1' sent (5 RTP packets)[/green]")

                # Wait for IVR to process
                time.sleep(2)

            finally:
                client_rtp.stop()

            # 4. Results
            console.print("\n[bold]4. IVR Result[/bold]")
            console.print(
                f"  DTMF received by server: [bold cyan]{ivr_handler.dtmf_received}[/bold cyan]"
            )
            console.print(
                f"  IVR choice: [bold cyan]{ivr_handler.ivr_result}[/bold cyan]"
            )
            console.print(
                f"  RTP packets sent by server: [bold]{ivr_handler.rtp_packets_sent}[/bold]"
            )

            # 5. BYE
            console.print("\n[bold]5. BYE[/bold]")
            bye_r = client.bye(response=response, host=SERVER_HOST, port=SERVER_PORT)
            console.print(f"  [green]BYE -> {bye_r.status_code}[/green]")

        # --- Summary ---
        console.rule("Summary")

        table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Component", style="bold", width=18)
        table.add_column("Result", width=50)

        sip_ok = events.got_200
        rtp_ok = ivr_handler.rtp_packets_sent > 0
        dtmf_ok = ivr_handler.dtmf_received == "1"
        ivr_ok = ivr_handler.ivr_result == "sales"

        def r(ok: bool, msg: str) -> str:
            return f"[green]PASS[/green] — {msg}" if ok else f"[red]FAIL[/red] — {msg}"

        table.add_row("SIP Signaling", r(sip_ok, "INVITE -> 200 -> ACK -> BYE -> 200"))
        table.add_row(
            "RTP Audio",
            r(
                rtp_ok,
                f"{ivr_handler.rtp_packets_sent} packets sent via UDP:{RTP_PORT_SERVER}",
            ),
        )
        table.add_row(
            "DTMF RFC 4733", r(dtmf_ok, f"digit '{ivr_handler.dtmf_received}' via RTP")
        )
        table.add_row("IVR Menu", r(ivr_ok, f"choice='{ivr_handler.ivr_result}'"))
        table.add_row("TTS", r(rtp_ok, "440Hz tone PCM -> PCMU -> RTP"))
        table.add_row("B2BUA", r(sip_ok, "sipx as UAC + UAS in same process"))

        console.print(table)

        all_ok = sip_ok and rtp_ok and dtmf_ok and ivr_ok
        if all_ok:
            console.print(
                "\n[bold green]All components working with real RTP/DTMF![/bold green]\n"
            )
        else:
            console.print(
                "\n[bold yellow]Some components need attention.[/bold yellow]\n"
            )

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise
    finally:
        server.stop()


if __name__ == "__main__":
    main()
