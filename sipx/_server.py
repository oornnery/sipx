"""
SIP Server/Listener for handling incoming requests.

Provides a simple server that listens for incoming SIP requests
and automatically responds with appropriate status codes.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Dict, Optional

from ._utils import logger
from .models._message import MessageParser, Request, Response
from .transports._udp import UDPTransport
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
            logger.debug("<<< RECEIVED BYE from %s:%s", source.host, source.port)
            logger.debug(request.to_string())

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
            logger.debug("<<< RECEIVED CANCEL from %s:%s", source.host, source.port)
            logger.debug(request.to_string())

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
            logger.debug("<<< RECEIVED OPTIONS from %s:%s", source.host, source.port)
            logger.debug(request.to_string())

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
            "SIP Server started on %s:%s",
            self.config.local_host,
            self.config.local_port,
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
                    logger.debug(
                        "<<< RECEIVED ACK from %s:%s", source.host, source.port
                    )
                    logger.debug(request.to_string())
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

                    logger.debug(
                        ">>> SENDING %s %s to %s:%s",
                        response.status_code,
                        response.reason_phrase,
                        source.host,
                        source.port,
                    )
                    logger.debug(response.to_string())

                    response_data = response.to_bytes()
                    self._transport.send(response_data, source)

                    # Track response in the transaction
                    self._state_manager.update_transaction(txn.id, response)
                    self._emit("response_sent", txn, response)
                else:
                    # No handler - send 501 Not Implemented
                    logger.warning(
                        "<<< RECEIVED %s from %s:%s (no handler)",
                        request.method,
                        source.host,
                        source.port,
                    )
                    logger.debug(request.to_string())

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

                    logger.debug(
                        ">>> SENDING 501 Not Implemented to %s:%s",
                        source.host,
                        source.port,
                    )
                    logger.debug(response.to_string())

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


class _SIPServerProtocol(asyncio.DatagramProtocol):
    """asyncio DatagramProtocol for native async SIP server."""

    def __init__(self, server: AsyncSIPServer) -> None:
        self.server = server
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        asyncio.ensure_future(self.server._handle_datagram(data, addr, self.transport))


class AsyncSIPServer:
    """Native async SIP server using asyncio.DatagramProtocol.

    No threading — runs entirely in the asyncio event loop.
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        **kwargs: object,
    ) -> None:
        self._host = local_host
        self._port = local_port
        self._handlers: Dict[str, Callable] = {}
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _SIPServerProtocol | None = None
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        def _bye(request: Request, source: TransportAddress) -> Response:
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

        def _cancel(request: Request, source: TransportAddress) -> Response:
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

        def _options(request: Request, source: TransportAddress) -> Response:
            return Response(
                status_code=200,
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

        self._handlers["BYE"] = _bye
        self._handlers["CANCEL"] = _cancel
        self._handlers["OPTIONS"] = _options

    # ------------------------------------------------------------------
    # Decorators
    # ------------------------------------------------------------------

    def handle(self, method: str):
        def decorator(fn: Callable) -> Callable:
            self._handlers[method.upper()] = fn
            return fn

        return decorator

    def register_handler(self, method: str, handler: Callable) -> None:
        self._handlers[method.upper()] = handler

    @property
    def invite(self):
        return self.handle("INVITE")

    @property
    def register(self):
        return self.handle("REGISTER")

    @property
    def options(self):
        return self.handle("OPTIONS")

    @property
    def bye(self):
        return self.handle("BYE")

    @property
    def cancel(self):
        return self.handle("CANCEL")

    @property
    def message(self):
        return self.handle("MESSAGE")

    @property
    def subscribe(self):
        return self.handle("SUBSCRIBE")

    @property
    def notify(self):
        return self.handle("NOTIFY")

    @property
    def refer(self):
        return self.handle("REFER")

    @property
    def info(self):
        return self.handle("INFO")

    @property
    def update(self):
        return self.handle("UPDATE")

    @property
    def prack(self):
        return self.handle("PRACK")

    @property
    def publish(self):
        return self.handle("PUBLISH")

    # ------------------------------------------------------------------
    # Datagram handler
    # ------------------------------------------------------------------

    async def _handle_datagram(
        self,
        data: bytes,
        addr: tuple[str, int],
        transport: asyncio.DatagramTransport | None,
    ) -> None:
        from .models._message import MessageParser

        try:
            message = MessageParser.parse(data)
        except Exception:
            return

        if not isinstance(message, Request):
            return

        source = TransportAddress(host=addr[0], port=addr[1])

        # ACK: no response
        if message.method == "ACK":
            logger.info("Received ACK from %s:%s", addr[0], addr[1])
            return

        handler = self._handlers.get(message.method)
        if handler:
            try:
                response = resolve_handler(handler, message, source)
            except Exception as e:
                logger.error("Handler error: %s", e)
                response = Response(
                    status_code=500,
                    headers={
                        "Via": message.via or "",
                        "From": message.from_header or "",
                        "To": message.to_header or "",
                        "Call-ID": message.call_id or "",
                        "CSeq": message.cseq or "",
                        "Content-Length": "0",
                    },
                )
        else:
            response = Response(
                status_code=501,
                headers={
                    "Via": message.via or "",
                    "From": message.from_header or "",
                    "To": message.to_header or "",
                    "Call-ID": message.call_id or "",
                    "CSeq": message.cseq or "",
                    "Content-Length": "0",
                },
            )

        if transport:
            transport.sendto(response.to_bytes(), addr)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: _SIPServerProtocol(self),
            local_addr=(self._host, self._port),
        )
        logger.info("AsyncSIPServer started on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
        logger.info("AsyncSIPServer stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_) -> bool:
        await self.stop()
        return False
