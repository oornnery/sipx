#!/usr/bin/env python3
"""
sipx — SIP Server Demo with Decorators and DI

Shows how to build a SIP server with Flask/FastAPI-style decorators
and Annotated dependency injection.

Usage:
    uv run python examples/server_demo.py

Test with:
    # In another terminal:
    uv run python -c "import sipx; print(sipx.options('sip:127.0.0.1:15090').status_code)"
    uv run python -c "import sipx; print(sipx.register('sip:test@127.0.0.1:15090').status_code)"
    uv run python -c "import sipx; print(sipx.send('sip:test@127.0.0.1:15090', 'Hello!').status_code)"
"""

import time
from typing import Annotated
from sipx import (
    SIPServer,
    Request,
    FromHeader,
    CallID,
    Header,
    Source,
    Extractor,
)
from sipx._utils import console
from sipx._types import TransportAddress


# ---------------------------------------------------------------------------
# Custom Extractor (user-defined)
# ---------------------------------------------------------------------------
class UserAgent(Extractor):
    """Extract User-Agent header — shows how to create custom extractors."""

    def extract(self, request: Request, source: TransportAddress):
        return request.headers.get("User-Agent", "unknown")


# ---------------------------------------------------------------------------
# Server with decorator handlers
# ---------------------------------------------------------------------------

server = SIPServer(local_host="127.0.0.1", local_port=15090)


@server.options
def on_options(request: Request):
    """Simple handler — just request, no DI."""
    console.print("  [green]OPTIONS received[/green]")
    return request.ok({"Allow": "INVITE,ACK,BYE,CANCEL,OPTIONS,MESSAGE,REGISTER"})


@server.register
def on_register(
    request: Request,
    caller: Annotated[str, FromHeader],
    call_id: Annotated[str, CallID],
    source: Annotated[TransportAddress, Source],
):
    """DI handler — headers auto-extracted."""
    console.print(f"  [green]REGISTER from {caller}[/green]")
    console.print(f"  [dim]Call-ID: {call_id}, Source: {source}[/dim]")
    return request.ok()


@server.message
def on_message(
    request: Request,
    caller: Annotated[str, FromHeader],
    ua: Annotated[str, UserAgent()],
    content_type: Annotated[str, Header("Content-Type")],
):
    """DI with custom extractor."""
    body = request.content.decode("utf-8", errors="ignore") if request.content else ""
    console.print(f"  [green]MESSAGE from {caller}[/green]")
    console.print(f"  [dim]UA: {ua}, Content-Type: {content_type}[/dim]")
    console.print(f"  [cyan]Body: {body}[/cyan]")
    return request.ok()


@server.handle("SUBSCRIBE")
def on_subscribe(
    request: Request,
    caller: Annotated[str, FromHeader],
    event: Annotated[str, Header("Event")],
):
    """Generic handler via @server.handle()."""
    console.print(f"  [green]SUBSCRIBE from {caller}, event={event}[/green]")
    return request.ok()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    console.print("\n[bold]sipx — SIP Server Demo (decorators + DI)[/bold]")
    console.print("Listening on 127.0.0.1:15090")
    console.print("[dim]Press Ctrl+C to stop\n")
    console.print("Test commands:")
    console.print(
        "  uv run python -c \"import sipx; print(sipx.options('sip:127.0.0.1:15090').status_code)\""
    )
    console.print(
        "  uv run python -c \"import sipx; print(sipx.send('sip:test@127.0.0.1:15090', 'Hello!').status_code)\""
    )
    console.print()

    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
