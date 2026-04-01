"""Synchronous SIP server using threading."""

from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from .._utils import logger
from ..models._message import MessageParser, Request, Response
from ..transports._udp import UDPTransport
from .._types import TransportConfig, TransactionType, TransactionState
from ..fsm import StateManager, TimerManager
from .._depends import resolve_handler
from ._base import SIPServerHandlerMixin


class SIPServer(SIPServerHandlerMixin):
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
        self._rseq_counter: int = 0  # RFC 3262: monotonically increasing RSeq

        # Register default handlers
        self._register_default_handlers()

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

                # ACK doesn't get a response — confirm original INVITE transaction
                if request.method == "ACK":
                    logger.debug(
                        "<<< RECEIVED ACK from %s:%s", source.host, source.port
                    )
                    logger.debug(request.to_string())
                    # Find the original INVITE IST and confirm it (cancels Timer G/H)
                    invite_txn = self._state_manager.find_transaction(
                        call_id=request.headers.get("Call-ID"),
                        method="INVITE",
                    )
                    if invite_txn:
                        invite_txn.transition_to(TransactionState.CONFIRMED)
                    else:
                        txn.transition_to(TransactionState.CONFIRMED)
                    continue

                # Auto 100 Trying for INVITE (RFC 3261 §8.2.6.1)
                if request.method == "INVITE":
                    trying = request.trying()
                    self._transport.send(trying.to_bytes(), source)
                    logger.debug(
                        ">>> AUTO 100 Trying to %s:%s", source.host, source.port
                    )

                # Find handler for this method
                handler = self._handlers.get(request.method)

                if handler:
                    # Call handler with DI resolution
                    try:
                        response = resolve_handler(handler, request, source)
                    except Exception as handler_err:
                        logger.error("Handler error: %s", handler_err)
                        response = request.error(500)

                    # Add RSeq for reliable provisional responses (RFC 3262)
                    if (
                        request.method == "INVITE"
                        and 100 < response.status_code < 200
                        and "100rel" in request.headers.get("Require", "")
                    ):
                        self._rseq_counter += 1
                        response.headers["RSeq"] = str(self._rseq_counter)
                        response.headers["Require"] = "100rel"

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

                    # Wire Timer G retransmit for INVITE (IST) on UDP
                    if request.method == "INVITE" and self.transport == "UDP":
                        timer_manager = TimerManager()
                        txn.timer_manager = timer_manager
                        txn._retransmit_fn = (
                            lambda d=response_data, s=source: self._transport.send(d, s)
                        )
                        txn._on_state_change(txn.state, txn.state)

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

                    response = request.error(501)

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
