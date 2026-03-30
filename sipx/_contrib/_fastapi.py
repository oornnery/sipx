"""
FastAPI integration for sipx.

Provides a SIPRouter that wraps a SIPServer and exposes decorator-based
handler registration for common SIP methods, with FastAPI lifespan support.

Requires the optional ``fastapi`` package.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def _import_fastapi():
    """Lazy import FastAPI."""
    try:
        import fastapi

        return fastapi
    except ImportError:
        raise ImportError(
            "FastAPI integration requires 'fastapi'. "
            "Install it with: pip install fastapi"
        ) from None


class SIPRouter:
    """
    SIP router for FastAPI applications.

    Wraps a :class:`SIPServer` and provides decorator-based registration
    of handlers for INVITE, REGISTER, and MESSAGE methods.  Integrates
    with FastAPI's lifespan protocol so the SIP server starts and stops
    together with the ASGI application.

    Example::

        from fastapi import FastAPI
        from sipx._contrib._fastapi import SIPRouter

        sip = SIPRouter(host="0.0.0.0", port=5060)

        @sip.on_invite
        def handle_invite(request, source):
            ...

        app = FastAPI(lifespan=sip.lifespan)
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5060,
        transport: str = "UDP",
    ) -> None:
        self._host = host
        self._port = port
        self._transport = transport
        self._server = None
        self._handlers: dict[str, Callable] = {}

    def _get_server(self):
        """Lazily create the SIPServer instance."""
        if self._server is None:
            from .._server import SIPServer

            self._server = SIPServer(
                local_host=self._host,
                local_port=self._port,
                transport=self._transport,
            )
            # Register any handlers that were added before server creation
            for method, handler in self._handlers.items():
                self._server.register_handler(method, handler)
        return self._server

    # ------------------------------------------------------------------
    # Decorator-based handler registration
    # ------------------------------------------------------------------

    def on_invite(self, handler: Callable) -> Callable:
        """
        Decorator to register a handler for INVITE requests.

        The handler receives ``(request, source)`` and should return a
        :class:`Response`.

        Example::

            @sip.on_invite
            def handle_invite(request, source):
                return Response(status_code=200, reason_phrase="OK", ...)
        """
        self._handlers["INVITE"] = handler
        if self._server is not None:
            self._server.register_handler("INVITE", handler)
        return handler

    def on_register(self, handler: Callable) -> Callable:
        """
        Decorator to register a handler for REGISTER requests.

        The handler receives ``(request, source)`` and should return a
        :class:`Response`.
        """
        self._handlers["REGISTER"] = handler
        if self._server is not None:
            self._server.register_handler("REGISTER", handler)
        return handler

    def on_message(self, handler: Callable) -> Callable:
        """
        Decorator to register a handler for MESSAGE requests.

        The handler receives ``(request, source)`` and should return a
        :class:`Response`.
        """
        self._handlers["MESSAGE"] = handler
        if self._server is not None:
            self._server.register_handler("MESSAGE", handler)
        return handler

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the underlying SIP server."""
        server = self._get_server()
        server.start()

    def stop(self) -> None:
        """Stop the underlying SIP server."""
        if self._server is not None:
            self._server.stop()

    # ------------------------------------------------------------------
    # FastAPI lifespan integration
    # ------------------------------------------------------------------

    @property
    def lifespan(self) -> Callable[["FastAPI"], AsyncIterator[None]]:
        """
        Return a FastAPI lifespan context manager.

        Usage::

            app = FastAPI(lifespan=sip.lifespan)
        """
        router = self

        @contextlib.asynccontextmanager
        async def _lifespan(app: "FastAPI") -> AsyncIterator[None]:
            router.start()
            try:
                yield
            finally:
                router.stop()

        return _lifespan


__all__ = ["SIPRouter"]
