"""Synchronous SIP server using threading."""

from __future__ import annotations

import socket
import threading
from typing import Callable, Dict, Optional

from .._types import SIPTimeoutError
from .._utils import logger
from ..models._message import MessageParser, Request, Response
from ..transports._udp import UDPTransport
from ..transports._tcp import TCPTransport
from ..transports._tls import TLSTransport
from .._types import TransportConfig
from ..fsm import StateManager, TimerManager
from ._base import SIPServerBase


def _create_server_transport(protocol: str, config: TransportConfig):
    """Create a sync transport for the server based on protocol name."""
    if protocol == "UDP":
        return UDPTransport(config)
    elif protocol == "TCP":
        return TCPTransport(config)
    elif protocol == "TLS":
        return TLSTransport(config)
    raise ValueError(f"Unsupported server transport: {protocol}")


class SIPServer(SIPServerBase):
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
        self._transport = _create_server_transport(self.transport, self.config)
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
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                logger.warning(
                    "Event handler error for '%s': %s", event, e, exc_info=True
                )

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

    def _run(self) -> None:
        """Main server loop - runs in background thread."""
        parser = MessageParser()

        while not self._stop_event.is_set():
            try:
                data, source = self._transport.receive(timeout=1.0)

                if not data:
                    continue

                message = parser.parse(data)

                if not isinstance(message, Request):
                    continue

                request = message
                self._log_request(request, source)

                txn = self._create_server_transaction(request, self.transport)
                self._emit("transaction_created", txn)

                if request.method == "ACK":
                    self._handle_ack(request, source)
                    continue

                # Auto 100 Trying for INVITE (RFC 3261 Section 8.2.6.1)
                if request.method == "INVITE":
                    trying = request.trying()
                    self._transport.send(trying.to_bytes(), source)
                    logger.debug(
                        ">>> AUTO 100 Trying to %s:%s", source.host, source.port
                    )

                response = self._resolve_response_sync(request, source)

                self._log_response(response, source)
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

                self._state_manager.update_transaction(txn.id, response)
                self._emit("response_sent", txn, response)

            except (socket.timeout, SIPTimeoutError):
                pass
            except OSError as e:
                if not self._stop_event.is_set():
                    logger.debug("Server loop OS error: %s", e)
            except Exception as e:
                logger.warning("Unexpected server loop error: %s", e, exc_info=True)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
