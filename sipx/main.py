"""
sipx CLI powered by typer.

Provides command-line access to core SIP operations:
  - register: Register with a SIP server
  - options:  Send OPTIONS to query capabilities
  - call:     Make a call (INVITE + ACK, wait, BYE)
  - message:  Send a SIP MESSAGE
  - listen:   Start a SIP server listener
"""

from __future__ import annotations

import sys
import time


def _import_typer():
    """Lazy import typer."""
    try:
        import typer

        return typer
    except ImportError:
        print(
            "The sipx CLI requires 'typer'. Install it with: pip install typer",
            file=sys.stderr,
        )
        sys.exit(1)


def _get_app():
    """Build and return the typer application."""
    typer = _import_typer()
    from rich.console import Console

    from .client import SIPClient
    from .models._auth import Auth
    from .server import SIPServer

    console = Console()
    app = typer.Typer(
        name="sipx",
        help="sipx -- SIP Swiss-army knife CLI",
        add_completion=False,
    )

    # ------------------------------------------------------------------
    # register
    # ------------------------------------------------------------------
    @app.command()
    def register(
        aor: str = typer.Argument(
            ..., help="Address of Record (e.g. sip:alice@example.com)"
        ),
        user: str = typer.Option("", "--user", "-u", help="Auth username"),
        password: str = typer.Option("", "--password", "-p", help="Auth password"),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="SIP proxy host"),
        port: int = typer.Option(5060, "--port", help="SIP proxy port"),
        transport: str = typer.Option(
            "UDP", "--transport", "-t", help="Transport protocol"
        ),
    ):
        """Register with a SIP server."""
        auth = None
        if user and password:
            auth = Auth.Digest(username=user, password=password)

        with SIPClient(
            local_host="0.0.0.0", local_port=0, transport=transport, auth=auth
        ) as client:
            console.print(
                f"[bold]Registering [cyan]{aor}[/cyan] via {host}:{port}...[/bold]"
            )
            response = client.register(aor=aor, registrar=f"sip:{host}:{port}")
            if response is None:
                console.print("[red]No response (timeout)[/red]")
                raise typer.Exit(1)
            console.print(
                f"[green]{response.status_code} {response.reason_phrase}[/green]"
            )
            for name, value in response.headers:
                console.print(f"  {name}: {value}")

    # ------------------------------------------------------------------
    # options
    # ------------------------------------------------------------------
    @app.command()
    def options(
        uri: str = typer.Argument(..., help="Target SIP URI"),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="SIP proxy host"),
        port: int = typer.Option(5060, "--port", help="SIP proxy port"),
        transport: str = typer.Option(
            "UDP", "--transport", "-t", help="Transport protocol"
        ),
    ):
        """Send OPTIONS to query server capabilities."""
        with SIPClient(
            local_host="0.0.0.0", local_port=0, transport=transport
        ) as client:
            console.print(
                f"[bold]OPTIONS [cyan]{uri}[/cyan] via {host}:{port}...[/bold]"
            )
            response = client.options(uri=uri)
            if response is None:
                console.print("[red]No response (timeout)[/red]")
                raise typer.Exit(1)
            console.print(
                f"[green]{response.status_code} {response.reason_phrase}[/green]"
            )
            for name, value in response.headers:
                console.print(f"  {name}: {value}")

    # ------------------------------------------------------------------
    # call
    # ------------------------------------------------------------------
    @app.command()
    def call(
        uri: str = typer.Argument(..., help="Target SIP URI to call"),
        user: str = typer.Option("", "--user", "-u", help="Auth username"),
        password: str = typer.Option("", "--password", "-p", help="Auth password"),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="SIP proxy host"),
        port: int = typer.Option(5060, "--port", help="SIP proxy port"),
        duration: int = typer.Option(
            5, "--duration", "-d", help="Call hold time in seconds"
        ),
        transport: str = typer.Option(
            "UDP", "--transport", "-t", help="Transport protocol"
        ),
    ):
        """Make a call: INVITE + ACK, hold, BYE."""
        auth = None
        if user and password:
            auth = Auth.Digest(username=user, password=password)

        with SIPClient(
            local_host="0.0.0.0", local_port=0, transport=transport, auth=auth
        ) as client:
            console.print(f"[bold]INVITE [cyan]{uri}[/cyan]...[/bold]")
            response = client.invite(to_uri=uri)
            if response is None:
                console.print("[red]No response (timeout)[/red]")
                raise typer.Exit(1)
            console.print(
                f"[green]{response.status_code} {response.reason_phrase}[/green]"
            )

            if response.is_success:
                # Send ACK
                console.print("[bold]Sending ACK...[/bold]")
                client.ack(to_uri=uri)

                # Hold the call
                console.print(f"[dim]Holding call for {duration}s...[/dim]")
                time.sleep(duration)

                # Send BYE
                console.print("[bold]Sending BYE...[/bold]")
                bye_resp = client.bye(to_uri=uri)
                if bye_resp:
                    console.print(
                        f"[green]{bye_resp.status_code} {bye_resp.reason_phrase}[/green]"
                    )
            else:
                console.print(
                    f"[red]Call failed: {response.status_code} {response.reason_phrase}[/red]"
                )

    # ------------------------------------------------------------------
    # message
    # ------------------------------------------------------------------
    @app.command()
    def message(
        uri: str = typer.Argument(..., help="Target SIP URI"),
        text: str = typer.Argument(..., help="Message text to send"),
        user: str = typer.Option("", "--user", "-u", help="Auth username"),
        password: str = typer.Option("", "--password", "-p", help="Auth password"),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="SIP proxy host"),
        port: int = typer.Option(5060, "--port", help="SIP proxy port"),
        transport: str = typer.Option(
            "UDP", "--transport", "-t", help="Transport protocol"
        ),
    ):
        """Send a SIP MESSAGE."""
        auth = None
        if user and password:
            auth = Auth.Digest(username=user, password=password)

        with SIPClient(
            local_host="0.0.0.0", local_port=0, transport=transport, auth=auth
        ) as client:
            console.print(f"[bold]MESSAGE [cyan]{uri}[/cyan]: {text}[/bold]")
            response = client.message(to_uri=uri, content=text)
            if response is None:
                console.print("[red]No response (timeout)[/red]")
                raise typer.Exit(1)
            console.print(
                f"[green]{response.status_code} {response.reason_phrase}[/green]"
            )

    # ------------------------------------------------------------------
    # listen
    # ------------------------------------------------------------------
    @app.command()
    def listen(
        host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind address"),
        port: int = typer.Option(5060, "--port", "-p", help="Bind port"),
        transport: str = typer.Option(
            "UDP", "--transport", "-t", help="Transport protocol"
        ),
    ):
        """Start a SIP server listener."""
        console.print(
            f"[bold green]Starting SIP listener on {host}:{port} ({transport})...[/bold green]"
        )
        console.print("[dim]Press Ctrl+C to stop.[/dim]")

        server = SIPServer(local_host=host, local_port=port, transport=transport)
        try:
            with server:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold red]Stopped.[/bold red]")

    # ------------------------------------------------------------------
    # tui
    # ------------------------------------------------------------------
    @app.command()
    def tui(
        host: str = typer.Option("0.0.0.0", "--host", "-h", help="Listen address"),
        port: int = typer.Option(5060, "--port", "-p", help="Listen port"),
        listen: bool = typer.Option(
            False, "--listen", "-l", help="Start passive listener on launch"
        ),
    ):
        """Launch interactive SIP workbench (TUI)."""
        try:
            from .tui import SipxApp
        except ImportError:
            console.print(
                "[red]TUI requires textual. Install with:[/red]\n"
                "  pip install sipx[tui]"
            )
            raise typer.Exit(1)

        tui_app = SipxApp()
        if listen:
            # Schedule listener start after mount

            original_on_mount = tui_app.on_mount

            def _patched_on_mount() -> None:
                original_on_mount()
                tui_app.start_listener(host=host, port=port)

            tui_app.on_mount = _patched_on_mount  # type: ignore[method-assign]

        tui_app.run()

    return app


def main():
    """Entry point for the sipx CLI."""
    app = _get_app()
    app()


if __name__ == "__main__":
    main()
