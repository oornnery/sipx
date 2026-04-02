"""Shared handler registration and dispatch logic for SIP servers."""

from __future__ import annotations

from typing import Callable, Dict

from .._utils import logger
from ..models._message import Request, Response
from .._types import TransportAddress, TransactionType, TransactionState
from ..fsm import StateManager
from .._depends import resolve_handler


class SIPServerBase:
    """Abstract base class with shared SIP server logic.

    Provides handler registration, decorator methods, default handlers,
    and request-dispatch logic used by both SIPServer and AsyncSIPServer.
    """

    _handlers: Dict[str, Callable]
    _state_manager: StateManager
    _rseq_counter: int

    # ------------------------------------------------------------------
    # Default handlers
    # ------------------------------------------------------------------

    def _register_default_handlers(self) -> None:
        """Register default handlers for common SIP methods."""

        def handle_bye(request: Request, source: TransportAddress) -> Response:
            """Handle BYE request - respond with 200 OK."""
            return request.ok()

        def handle_cancel(request: Request, source: TransportAddress) -> Response:
            """Handle CANCEL request - respond with 200 OK."""
            return request.ok()

        def handle_options(request: Request, source: TransportAddress) -> Response:
            """Handle OPTIONS request - respond with 200 OK."""
            resp = request.ok()
            resp.headers["Allow"] = "INVITE,ACK,BYE,CANCEL,OPTIONS,MESSAGE,REGISTER"
            resp.headers["Accept"] = "application/sdp"
            return resp

        self.register_handler("BYE", handle_bye)
        self.register_handler("CANCEL", handle_cancel)
        self.register_handler("OPTIONS", handle_options)

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

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

    def handle(self, method: str, **options):
        """Decorator factory to register a handler for a SIP method.

        Args:
            method: SIP method name.
            **options: Reserved for future options (e.g., auth, middleware).

        Usage::

            @server.handle("INVITE")
            def on_invite(request, source):
                return request.ok()
        """

        def decorator(fn):
            self.register_handler(method, fn)
            return fn

        return decorator

    # ------------------------------------------------------------------
    # Convenience decorator methods (call with parentheses)
    # ------------------------------------------------------------------

    def invite(self, **options):
        """Decorator to register an INVITE handler.

        Usage::

            @server.invite()
            def on_invite(request, source):
                return request.ok()
        """
        return self.handle("INVITE", **options)

    def register(self, **options):
        """Decorator to register a REGISTER handler."""
        return self.handle("REGISTER", **options)

    def options(self, **options):
        """Decorator to register an OPTIONS handler."""
        return self.handle("OPTIONS", **options)

    def bye(self, **options):
        """Decorator to register a BYE handler."""
        return self.handle("BYE", **options)

    def cancel(self, **options):
        """Decorator to register a CANCEL handler."""
        return self.handle("CANCEL", **options)

    def message(self, **options):
        """Decorator to register a MESSAGE handler."""
        return self.handle("MESSAGE", **options)

    def subscribe(self, **options):
        """Decorator to register a SUBSCRIBE handler."""
        return self.handle("SUBSCRIBE", **options)

    def notify(self, **options):
        """Decorator to register a NOTIFY handler."""
        return self.handle("NOTIFY", **options)

    def refer(self, **options):
        """Decorator to register a REFER handler."""
        return self.handle("REFER", **options)

    def info(self, **options):
        """Decorator to register an INFO handler."""
        return self.handle("INFO", **options)

    def update(self, **options):
        """Decorator to register an UPDATE handler."""
        return self.handle("UPDATE", **options)

    def prack(self, **options):
        """Decorator to register a PRACK handler."""
        return self.handle("PRACK", **options)

    def publish(self, **options):
        """Decorator to register a PUBLISH handler."""
        return self.handle("PUBLISH", **options)

    # ------------------------------------------------------------------
    # Shared dispatch logic
    # ------------------------------------------------------------------

    def _create_server_transaction(self, request: Request, transport_name: str = "UDP"):
        """Create a server-side transaction for an incoming request.

        Uses INVITE_SERVER for INVITE requests, NON_INVITE_SERVER for others.
        """
        if request.method == "INVITE":
            txn_type = TransactionType.INVITE_SERVER
        else:
            txn_type = TransactionType.NON_INVITE_SERVER

        txn = self._state_manager.create_transaction(request, transaction_type=txn_type)
        txn.transport = transport_name
        return txn

    def _handle_ack(self, request: Request, source: TransportAddress) -> None:
        """Handle ACK: confirm original INVITE transaction (no response)."""
        logger.debug("<<< RECEIVED ACK from %s:%s", source.host, source.port)
        invite_txn = self._state_manager.find_transaction(
            call_id=request.headers.get("Call-ID"),
            method="INVITE",
        )
        if invite_txn:
            invite_txn.transition_to(TransactionState.CONFIRMED)

    def _resolve_handler_sync(
        self, handler: Callable, request: Request, source: TransportAddress
    ) -> Response:
        """Resolve DI and call handler synchronously."""
        return resolve_handler(handler, request, source)

    def _apply_rseq(self, request: Request, response: Response) -> None:
        """Apply RSeq for reliable provisional responses (RFC 3262)."""
        if (
            request.method == "INVITE"
            and 100 < response.status_code < 200
            and "100rel" in request.headers.get("Require", "")
        ):
            self._rseq_counter += 1
            response.headers["RSeq"] = str(self._rseq_counter)
            response.headers["Require"] = "100rel"

    def _resolve_response_sync(
        self, request: Request, source: TransportAddress
    ) -> Response:
        """Look up handler, call it (with DI), return response or 501."""
        handler = self._handlers.get(request.method)
        if handler:
            try:
                response = self._resolve_handler_sync(handler, request, source)
            except Exception as err:
                logger.error("Handler error: %s", err, exc_info=True)
                response = request.error(500)
            self._apply_rseq(request, response)
        else:
            logger.warning(
                "<<< RECEIVED %s from %s:%s (no handler)",
                request.method,
                source.host,
                source.port,
            )
            logger.debug(request.to_string())
            response = request.error(501)
        return response

    async def _resolve_response_async(
        self, request: Request, source: TransportAddress
    ) -> Response:
        """Look up handler, call it async (with DI), return response or 501."""
        from .._depends import async_resolve_handler

        handler = self._handlers.get(request.method)
        if handler:
            try:
                response = await async_resolve_handler(handler, request, source)
            except Exception as err:
                logger.error("Handler error: %s", err, exc_info=True)
                response = request.error(500)
            self._apply_rseq(request, response)
        else:
            logger.warning(
                "<<< RECEIVED %s from %s:%s (no handler)",
                request.method,
                source.host,
                source.port,
            )
            logger.debug(request.to_string())
            response = request.error(501)
        return response

    def _log_request(self, request: Request, source: TransportAddress) -> None:
        """Log an incoming SIP request."""
        logger.debug(
            "<<< RECEIVED %s from %s:%s",
            request.method,
            source.host,
            source.port,
        )
        logger.debug(request.to_string())

    def _log_response(self, response: Response, source: TransportAddress) -> None:
        """Log an outgoing SIP response."""
        logger.debug(
            ">>> SENDING %s %s to %s:%s",
            response.status_code,
            response.reason_phrase,
            source.host,
            source.port,
        )
        logger.debug(response.to_string())
