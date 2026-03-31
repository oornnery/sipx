"""Shared handler registration mixin for SIP servers."""

from __future__ import annotations

from typing import Callable, Dict

from ..models._message import Request, Response
from .._types import TransportAddress


class SIPServerHandlerMixin:
    """Shared handler registration and decorator properties."""

    _handlers: Dict[str, Callable]

    def _register_default_handlers(self) -> None:
        """Register default handlers for common SIP methods."""

        def handle_bye(request: Request, source: TransportAddress) -> Response:
            """Handle BYE request - respond with 200 OK."""
            return Response(
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

        def handle_cancel(request: Request, source: TransportAddress) -> Response:
            """Handle CANCEL request - respond with 200 OK."""
            return Response(
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

        def handle_options(request: Request, source: TransportAddress) -> Response:
            """Handle OPTIONS request - respond with 200 OK."""
            return Response(
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
