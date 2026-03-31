#!/usr/bin/env python3
"""
sipx — Events & Handlers Demo

Shows all event handler patterns: global hooks, method filters,
status filters, multi-method, range filters.

Usage:
    uv run python examples/events_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sipx import Client, Events, on, SDPBody
from sipx._utils import console


class MyEvents(Events):
    """Demonstrates every event handler pattern."""

    # --- Global hooks (called for ALL requests/responses) ---

    def on_request(self, request, context):
        console.print(f"  [dim]>> {request.method} {request.uri}[/dim]")
        return request

    def on_response(self, response, context):
        console.print(
            f"  [dim]<< {response.status_code} {response.reason_phrase}[/dim]"
        )
        return response

    # --- Single method + single status ---

    @on("REGISTER", status=200)
    def on_registered(self, request, response, context):
        console.print("  [green]Registered![/green]")

    @on("INVITE", status=200)
    def on_call_accepted(self, request, response, context):
        console.print("  [green]Call accepted![/green]")

    # --- Single method + multiple statuses ---

    @on("INVITE", status=(180, 183))
    def on_ringing(self, request, response, context):
        console.print(f"  [cyan]Ringing... ({response.status_code})[/cyan]")

    # --- Any method + specific status ---

    @on(status=(401, 407))
    def on_auth_required(self, request, response, context):
        console.print("  [yellow]Auth challenge received[/yellow]")

    # --- Multiple methods + single status ---

    @on(("REGISTER", "INVITE", "MESSAGE"), status=200)
    def on_any_success(self, request, response, context):
        console.print(f"  [bold green]{request.method} succeeded[/bold green]")

    # --- Method only (any status) ---

    @on("BYE")
    def on_bye(self, request, response, context):
        if response and response.status_code == 200:
            console.print("  [green]Call terminated cleanly[/green]")


def main():
    console.print("\n[bold]sipx — Events Demo[/bold]")
    console.print("Requires: cd docker/asterisk && docker-compose up -d\n")

    events = MyEvents()

    with Client(local_port=5061) as client:
        client.events = events
        client.auth = ("1111", "1111xxx")

        # Register (triggers: on_request, on_auth_required, on_registered, on_any_success)
        console.rule("REGISTER")
        client.register("sip:1111@127.0.0.1")

        # Invite (triggers: on_request, on_ringing, on_call_accepted, on_any_success)
        console.rule("INVITE + ACK + BYE")
        sdp = SDPBody.audio(ip=client.local_address.host, port=8000)
        r = client.invite(
            to_uri="sip:100@127.0.0.1",
            body=sdp.to_string(),
            headers={
                "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
            },
        )
        if r.status_code == 200:
            client.ack(response=r)
            import time

            time.sleep(1)
            client.bye(response=r)

        # Unregister
        console.rule("UNREGISTER")
        client.unregister("sip:1111@127.0.0.1")


if __name__ == "__main__":
    main()
