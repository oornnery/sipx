"""
SIP Server/Listener for handling incoming requests.

Provides a simple server that listens for incoming SIP requests
and automatically responds with appropriate status codes.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from ._utils import console, logger
from ._models._message import MessageParser, Request, Response
from ._transports._udp import UDPTransport
from ._types import TransportConfig, TransportAddress


class SIPServer:
    """
    Simple SIP server that listens for incoming requests.

    Automatically handles:
    - BYE: Responds with 200 OK
    - CANCEL: Responds with 200 OK
    - ACK: No response (ACK doesn't get a response)
    - OPTIONS: Responds with 200 OK

    Custom handlers can be registered for specific methods.
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        config: Optional[TransportConfig] = None,
    ):
        """
        Initialize SIP server.

        Args:
            local_host: Local IP to bind to
            local_port: Local port to bind to
            config: Transport configuration
        """
        self.config = config or TransportConfig(
            local_host=local_host,
            local_port=local_port,
        )

        self._transport = UDPTransport(self.config)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, Callable[[Request, tuple], Response]] = {}

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default handlers for common SIP methods."""

        def handle_bye(request: Request, source: TransportAddress) -> Response:
            """Handle BYE request - respond with 200 OK."""
            console.print(
                f"\n[bold yellow]<<< RECEIVED BYE from {source.host}:{source.port}[/bold yellow]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

            response = Response(
                status_code=200,
                reason_phrase="OK",
                headers={
                    "Via": request.via or "",
                    "From": request.from_header or "",
                    "To": request.to_header or "",
                    "Call-ID": request.call_id or "",
                    "CSeq": request.cseq or "",
                    "Content-Length": "0",
                },
            )
            return response

        def handle_cancel(request: Request, source: TransportAddress) -> Response:
            """Handle CANCEL request - respond with 200 OK."""
            console.print(
                f"\n[bold yellow]<<< RECEIVED CANCEL from {source.host}:{source.port}[/bold yellow]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

            response = Response(
                status_code=200,
                reason_phrase="OK",
                headers={
                    "Via": request.via or "",
                    "From": request.from_header or "",
                    "To": request.to_header or "",
                    "Call-ID": request.call_id or "",
                    "CSeq": request.cseq or "",
                    "Content-Length": "0",
                },
            )
            return response

        def handle_options(request: Request, source: TransportAddress) -> Response:
            """Handle OPTIONS request - respond with 200 OK."""
            console.print(
                f"\n[bold cyan]<<< RECEIVED OPTIONS from {source.host}:{source.port}[/bold cyan]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

            response = Response(
                status_code=200,
                reason_phrase="OK",
                headers={
                    "Via": request.via or "",
                    "From": request.from_header or "",
                    "To": request.to_header or "",
                    "Call-ID": request.call_id or "",
                    "CSeq": request.cseq or "",
                    "Allow": "INVITE,ACK,BYE,CANCEL,OPTIONS,MESSAGE,REGISTER",
                    "Accept": "application/sdp",
                    "Content-Length": "0",
                },
            )
            return response

        # Register handlers
        self.register_handler("BYE", handle_bye)
        self.register_handler("CANCEL", handle_cancel)
        self.register_handler("OPTIONS", handle_options)

    def register_handler(
        self,
        method: str,
        handler: Callable[[Request, TransportAddress], Response],
    ) -> None:
        """
        Register a custom handler for a SIP method.

        Args:
            method: SIP method (e.g., "INVITE", "BYE", "REGISTER")
            handler: Callable that takes (request, source) and returns Response
        """
        self._handlers[method.upper()] = handler

    def start(self) -> None:
        """Start the server in a background thread."""
        if self._running:
            logger.warning("Server already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            f"SIP Server started on {self.config.local_host}:{self.config.local_port}"
        )
        console.print(
            f"\n[bold green][SERVER] Started on {self.config.local_host}:{self.config.local_port}[/bold green]"
        )

    def stop(self) -> None:
        """Stop the server."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

        self._transport.close()
        logger.info("SIP Server stopped")
        console.print("\n[bold red][SERVER] Stopped[/bold red]")

    def _run(self) -> None:
        """Main server loop - runs in background thread."""
        parser = MessageParser()

        while self._running:
            try:
                # Receive incoming message with timeout
                data, source = self._transport.receive(timeout=1.0)

                if not data:
                    continue

                # Parse message
                message = parser.parse(data)

                # Only handle requests (not responses)
                if not isinstance(message, Request):
                    continue

                request = message

                # ACK doesn't get a response
                if request.method == "ACK":
                    console.print(
                        f"\n[bold magenta]<<< RECEIVED ACK from {source.host}:{source.port}[/bold magenta]"
                    )
                    console.print(request.to_string())
                    console.print("=" * 80)
                    logger.info(f"Received ACK from {source.host}:{source.port}")
                    continue

                # Find handler for this method
                handler = self._handlers.get(request.method)

                if handler:
                    # Call handler and send response
                    response = handler(request, source)

                    console.print(
                        f"\n[bold green]>>> SENDING {response.status_code} {response.reason_phrase} to {source.host}:{source.port}[/bold green]"
                    )
                    console.print(response.to_string())
                    console.print("=" * 80)

                    response_data = response.to_bytes()
                    self._transport.send(response_data, source)
                else:
                    # No handler - send 501 Not Implemented
                    console.print(
                        f"\n[bold red]<<< RECEIVED {request.method} from {source.host}:{source.port} (no handler)[/bold red]"
                    )
                    console.print(request.to_string())
                    console.print("=" * 80)

                    response = Response(
                        status_code=501,
                        reason_phrase="Not Implemented",
                        headers={
                            "Via": request.via or "",
                            "From": request.from_header or "",
                            "To": request.to_header or "",
                            "Call-ID": request.call_id or "",
                            "CSeq": request.cseq or "",
                            "Content-Length": "0",
                        },
                    )

                    console.print(
                        f"\n[bold red]>>> SENDING 501 Not Implemented to {source.host}:{source.port}[/bold red]"
                    )
                    console.print(response.to_string())
                    console.print("=" * 80)

                    response_data = response.to_bytes()
                    self._transport.send(response_data, source)

            except Exception as e:
                # Timeout or other errors - continue
                if self._running and "timeout" not in str(e).lower():
                    logger.debug(f"Server loop error: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


class AsyncSIPServer:
    """
    Async SIP server (placeholder for future async implementation).

    For now, uses the sync SIPServer internally.
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        config: Optional[TransportConfig] = None,
    ):
        self._server = SIPServer(local_host, local_port, config)

    async def start(self) -> None:
        """Start the async server."""
        self._server.start()

    async def stop(self) -> None:
        """Stop the async server."""
        self._server.stop()

    def register_handler(
        self,
        method: str,
        handler: Callable[[Request, TransportAddress], Response],
    ) -> None:
        """Register a handler (sync for now)."""
        self._server.register_handler(method, handler)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False
