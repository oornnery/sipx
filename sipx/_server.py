"""
SIP Server/Listener for handling incoming requests.

Provides a simple server that listens for incoming SIP requests
and automatically responds with appropriate status codes.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Dict, Optional

from ._utils import console, logger
from ._models._message import MessageParser, Request, Response
from ._transports._udp import UDPTransport
from ._types import TransportConfig, TransportAddress, TransactionType, TransactionState
from ._fsm import StateManager
from ._depends import resolve_handler


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
        transport: str = "UDP",
        events: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialize SIP server.

        Args:
            local_host: Local IP to bind to
            local_port: Local port to bind to
            config: Transport configuration
            transport: Transport protocol ("UDP", "TCP", "TLS")
            events: Optional dict of event name to callback
        """
        self.config = config or TransportConfig(
            local_host=local_host,
            local_port=local_port,
        )

        self.transport = transport.upper()
        self._transport = UDPTransport(self.config)
        self._stop_event = threading.Event()
        self._stop_event.set()  # Start in stopped state
        self._thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, Callable[[Request, tuple], Response]] = {}
        self._state_manager = StateManager()
        self._events: Dict[str, Callable] = events or {}

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

    def handle(self, method: str):
        """Decorator to register a handler for a SIP method."""

        def decorator(fn):
            self.register_handler(method, fn)
            return fn

        return decorator

    @property
    def invite(self):
        """Decorator to register an INVITE handler."""
        return self.handle("INVITE")

    @property
    def register(self):
        """Decorator to register a REGISTER handler."""
        return self.handle("REGISTER")

    @property
    def options(self):
        """Decorator to register an OPTIONS handler."""
        return self.handle("OPTIONS")

    @property
    def bye(self):
        """Decorator to register a BYE handler."""
        return self.handle("BYE")

    @property
    def cancel(self):
        """Decorator to register a CANCEL handler."""
        return self.handle("CANCEL")

    @property
    def message(self):
        """Decorator to register a MESSAGE handler."""
        return self.handle("MESSAGE")

    @property
    def subscribe(self):
        """Decorator to register a SUBSCRIBE handler."""
        return self.handle("SUBSCRIBE")

    @property
    def notify(self):
        """Decorator to register a NOTIFY handler."""
        return self.handle("NOTIFY")

    @property
    def refer(self):
        """Decorator to register a REFER handler."""
        return self.handle("REFER")

    @property
    def info(self):
        """Decorator to register an INFO handler."""
        return self.handle("INFO")

    @property
    def update(self):
        """Decorator to register an UPDATE handler."""
        return self.handle("UPDATE")

    @property
    def prack(self):
        """Decorator to register a PRACK handler."""
        return self.handle("PRACK")

    @property
    def publish(self):
        """Decorator to register a PUBLISH handler."""
        return self.handle("PUBLISH")

    @property
    def _running(self) -> bool:
        """Check if the server is running (thread-safe)."""
        return not self._stop_event.is_set()

    @property
    def state_manager(self) -> StateManager:
        """Access the server's state manager."""
        return self._state_manager

    def _emit(self, event: str, *args) -> None:
        """Emit an event to registered callbacks."""
        callback = self._events.get(event)
        if callback is not None:
            try:
                callback(*args)
            except Exception:
                logger.debug(f"Event handler error for '{event}'")

    def start(self) -> None:
        """Start the server in a background thread."""
        if not self._stop_event.is_set() and self._thread is not None:
            logger.warning("Server already running")
            return

        self._stop_event.clear()
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
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

        self._transport.close()
        logger.info("SIP Server stopped")
        console.print("\n[bold red][SERVER] Stopped[/bold red]")

    def _create_server_transaction(self, request: Request) -> None:
        """
        Create a server-side transaction for an incoming request.

        Uses INVITE_SERVER for INVITE requests, NON_INVITE_SERVER for others.

        Args:
            request: The incoming SIP request
        """
        if request.method == "INVITE":
            txn_type = TransactionType.INVITE_SERVER
        else:
            txn_type = TransactionType.NON_INVITE_SERVER

        txn = self._state_manager.create_transaction(request, transaction_type=txn_type)
        txn.transport = self.transport
        self._emit("transaction_created", txn)
        return txn

    def _run(self) -> None:
        """Main server loop - runs in background thread."""
        parser = MessageParser()

        while not self._stop_event.is_set():
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

                # Create a server transaction for tracking
                txn = self._create_server_transaction(request)

                # ACK doesn't get a response
                if request.method == "ACK":
                    console.print(
                        f"\n[bold magenta]<<< RECEIVED ACK from {source.host}:{source.port}[/bold magenta]"
                    )
                    console.print(request.to_string())
                    console.print("=" * 80)
                    logger.info(f"Received ACK from {source.host}:{source.port}")
                    txn.transition_to(TransactionState.CONFIRMED)
                    continue

                # Find handler for this method
                handler = self._handlers.get(request.method)

                if handler:
                    # Call handler with DI resolution
                    try:
                        response = resolve_handler(handler, request, source)
                    except Exception as handler_err:
                        logger.error(f"Handler error: {handler_err}")
                        response = Response(
                            status_code=500,
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
                        f"\n[bold green]>>> SENDING {response.status_code} {response.reason_phrase} to {source.host}:{source.port}[/bold green]"
                    )
                    console.print(response.to_string())
                    console.print("=" * 80)

                    response_data = response.to_bytes()
                    self._transport.send(response_data, source)

                    # Track response in the transaction
                    self._state_manager.update_transaction(txn.id, response)
                    self._emit("response_sent", txn, response)
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

                    self._state_manager.update_transaction(txn.id, response)

            except Exception as e:
                # Timeout or other errors - continue
                if not self._stop_event.is_set() and "timeout" not in str(e).lower():
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
    """Async SIP server wrapping sync ``SIPServer`` via ``asyncio.to_thread``."""

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        config: Optional[TransportConfig] = None,
        transport: str = "UDP",
        events: Optional[Dict[str, Callable]] = None,
    ) -> None:
        self._sync = SIPServer(
            local_host=local_host,
            local_port=local_port,
            config=config,
            transport=transport,
            events=events,
        )

    # ------------------------------------------------------------------
    # Decorators (delegate to sync server)
    # ------------------------------------------------------------------

    def handle(self, method: str):
        """Decorator to register a handler for a SIP method."""
        return self._sync.handle(method)

    @property
    def invite(self):
        """Decorator to register an INVITE handler."""
        return self._sync.invite

    @property
    def register(self):
        """Decorator to register a REGISTER handler."""
        return self._sync.register

    @property
    def options(self):
        """Decorator to register an OPTIONS handler."""
        return self._sync.options

    @property
    def bye(self):
        """Decorator to register a BYE handler."""
        return self._sync.bye

    @property
    def cancel(self):
        """Decorator to register a CANCEL handler."""
        return self._sync.cancel

    @property
    def message(self):
        """Decorator to register a MESSAGE handler."""
        return self._sync.message

    @property
    def subscribe(self):
        """Decorator to register a SUBSCRIBE handler."""
        return self._sync.subscribe

    @property
    def notify(self):
        """Decorator to register a NOTIFY handler."""
        return self._sync.notify

    @property
    def refer(self):
        """Decorator to register a REFER handler."""
        return self._sync.refer

    @property
    def info(self):
        """Decorator to register an INFO handler."""
        return self._sync.info

    @property
    def update(self):
        """Decorator to register an UPDATE handler."""
        return self._sync.update

    @property
    def prack(self):
        """Decorator to register a PRACK handler."""
        return self._sync.prack

    @property
    def publish(self):
        """Decorator to register a PUBLISH handler."""
        return self._sync.publish

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state_manager(self) -> StateManager:
        """Access the server's state manager."""
        return self._sync.state_manager

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_handler(
        self,
        method: str,
        handler: Callable[[Request, TransportAddress], Response],
    ) -> None:
        """Register a custom handler for a SIP method."""
        self._sync.register_handler(method, handler)

    # ------------------------------------------------------------------
    # Lifecycle (async via to_thread)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the server in a background thread."""
        await asyncio.to_thread(self._sync.start)

    async def stop(self) -> None:
        """Stop the server."""
        await asyncio.to_thread(self._sync.stop)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *_) -> bool:
        """Async context manager exit."""
        await self.stop()
        return False
