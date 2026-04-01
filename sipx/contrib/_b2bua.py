"""Back-to-Back User Agent (B2BUA) for sipx.

Provides :class:`B2BUA` (sync) and :class:`AsyncB2BUA` (async) which bridge
an incoming A-leg (server side) to an outgoing B-leg (client side).

The bridge is minimal: SDP is relayed verbatim, BYE/CANCEL from either side
terminates both legs.  The caller keeps full control over the underlying
:class:`~sipx.server.SIPServer` / :class:`~sipx.server.AsyncSIPServer` and
:class:`~sipx.client.Client` / :class:`~sipx.client.AsyncClient` instances.

Example (sync)::

    from sipx import SIPServer, Client
    from sipx.contrib import B2BUA

    server = SIPServer(local_port=5060)
    client = Client()

    b2b = B2BUA(server, client, target="sip:pbx@192.168.1.1")

    with b2b:
        input("Press Enter to stop…")

Example (async)::

    from sipx import AsyncSIPServer, AsyncClient
    from sipx.contrib import AsyncB2BUA

    async def main():
        server = AsyncSIPServer(local_port=5060)
        client = AsyncClient()
        b2b = AsyncB2BUA(server, client, target="sip:pbx@192.168.1.1")
        async with b2b:
            await asyncio.sleep(3600)
"""

from __future__ import annotations

from typing import Callable, Optional

from .._utils import logger
from ..models._message import Request, Response
from .._types import TransportAddress

_log = logger.getChild("b2bua")


class B2BUA:
    """Synchronous Back-to-Back User Agent.

    Accepts calls arriving on *server* and forwards them to *target* via
    *client*.  BYE from either leg terminates both.

    Args:
        server: A :class:`~sipx.server.SIPServer` instance (not yet started).
        client: A :class:`~sipx.client.Client` instance.
        target: B-leg destination URI (e.g. ``"sip:pbx@192.168.1.1"``).
        on_bridge: Optional callback ``(a_request, b_response)`` fired when
            both legs are connected.
        on_terminate: Optional callback ``(call_id: str)`` fired when a call
            is torn down.
    """

    def __init__(
        self,
        server,
        client,
        target: str,
        on_bridge: Optional[Callable[[Request, Response], None]] = None,
        on_terminate: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.server = server
        self.client = client
        self.target = target
        self.on_bridge = on_bridge
        self.on_terminate = on_terminate
        self._calls: dict[str, Response] = {}  # A-leg Call-ID → B-leg 200 OK
        self._register_handlers()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        b2b = self

        def on_invite(request: Request, source: TransportAddress) -> Response:
            call_id = request.headers.get("Call-ID", "")
            body = request.content_text if request.content else None
            _log.info("B2BUA INVITE %s → %s", call_id[:8], b2b.target)

            b_resp = b2b.client.invite(b2b.target, body=body)

            if b_resp and b_resp.status_code == 200:
                try:
                    b2b.client.ack(response=b_resp)
                except Exception as e:
                    _log.warning("ACK failed: %s", e)

                b2b._calls[call_id] = b_resp
                _log.info("B2BUA bridge established: %s", call_id[:8])

                if b2b.on_bridge:
                    try:
                        b2b.on_bridge(request, b_resp)
                    except Exception as e:
                        _log.warning("on_bridge callback error: %s", e)

                return request.ok(
                    content=b_resp.content_text if b_resp.content else None
                )

            code = b_resp.status_code if b_resp else 503
            _log.info("B2BUA B-leg rejected: %s", code)
            return request.error(code)

        def on_bye(request: Request, source: TransportAddress) -> Response:
            call_id = request.headers.get("Call-ID", "")
            if call_id in b2b._calls:
                _log.info("B2BUA BYE A-leg %s — terminating B-leg", call_id[:8])
                try:
                    b2b.client.bye(response=b2b._calls[call_id])
                except Exception as e:
                    _log.warning("B-leg BYE error: %s", e)
                del b2b._calls[call_id]
                if b2b.on_terminate:
                    try:
                        b2b.on_terminate(call_id)
                    except Exception as e:
                        _log.warning("on_terminate callback error: %s", e)
            return request.ok()

        def on_cancel(request: Request, source: TransportAddress) -> Response:
            return request.ok()

        self.server.register_handler("INVITE", on_invite)
        self.server.register_handler("BYE", on_bye)
        self.server.register_handler("CANCEL", on_cancel)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the underlying SIP server."""
        self.server.start()

    def stop(self) -> None:
        """Stop the underlying SIP server."""
        self.server.stop()

    def __enter__(self) -> B2BUA:
        self.start()
        return self

    def __exit__(self, *_) -> bool:
        self.stop()
        return False

    @property
    def active_calls(self) -> int:
        """Number of currently bridged calls."""
        return len(self._calls)

    def __repr__(self) -> str:
        return f"<B2BUA(target={self.target!r}, active={self.active_calls})>"


class AsyncB2BUA:
    """Asynchronous Back-to-Back User Agent.

    Drop-in async replacement for :class:`B2BUA`.  Requires an
    :class:`~sipx.server.AsyncSIPServer` and :class:`~sipx.client.AsyncClient`.

    Args:
        server: An :class:`~sipx.server.AsyncSIPServer` (not yet started).
        client: An :class:`~sipx.client.AsyncClient`.
        target: B-leg destination URI.
        on_bridge: Optional async or sync callback ``(a_request, b_response)``.
        on_terminate: Optional async or sync callback ``(call_id: str)``.
    """

    def __init__(
        self,
        server,
        client,
        target: str,
        on_bridge: Optional[Callable] = None,
        on_terminate: Optional[Callable] = None,
    ) -> None:
        self.server = server
        self.client = client
        self.target = target
        self.on_bridge = on_bridge
        self.on_terminate = on_terminate
        self._calls: dict[str, Response] = {}
        self._register_handlers()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        import asyncio

        b2b = self

        async def on_invite(request: Request, source: TransportAddress) -> Response:
            call_id = request.headers.get("Call-ID", "")
            body = request.content_text if request.content else None
            _log.info("AsyncB2BUA INVITE %s → %s", call_id[:8], b2b.target)

            b_resp = await b2b.client.invite(b2b.target, body=body)

            if b_resp and b_resp.status_code == 200:
                try:
                    await b2b.client.ack(response=b_resp)
                except Exception as e:
                    _log.warning("ACK failed: %s", e)

                b2b._calls[call_id] = b_resp
                _log.info("AsyncB2BUA bridge established: %s", call_id[:8])

                if b2b.on_bridge:
                    try:
                        cb = b2b.on_bridge(request, b_resp)
                        if asyncio.iscoroutine(cb):
                            await cb
                    except Exception as e:
                        _log.warning("on_bridge callback error: %s", e)

                return request.ok(
                    content=b_resp.content_text if b_resp.content else None
                )

            code = b_resp.status_code if b_resp else 503
            _log.info("AsyncB2BUA B-leg rejected: %s", code)
            return request.error(code)

        async def on_bye(request: Request, source: TransportAddress) -> Response:
            call_id = request.headers.get("Call-ID", "")
            if call_id in b2b._calls:
                _log.info("AsyncB2BUA BYE %s — terminating B-leg", call_id[:8])
                try:
                    await b2b.client.bye(response=b2b._calls[call_id])
                except Exception as e:
                    _log.warning("B-leg BYE error: %s", e)
                del b2b._calls[call_id]
                if b2b.on_terminate:
                    try:
                        cb = b2b.on_terminate(call_id)
                        if asyncio.iscoroutine(cb):
                            await cb
                    except Exception as e:
                        _log.warning("on_terminate callback error: %s", e)
            return request.ok()

        async def on_cancel(request: Request, source: TransportAddress) -> Response:
            return request.ok()

        self.server.register_handler("INVITE", on_invite)
        self.server.register_handler("BYE", on_bye)
        self.server.register_handler("CANCEL", on_cancel)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the underlying async SIP server."""
        await self.server.start()

    async def stop(self) -> None:
        """Stop the underlying async SIP server."""
        await self.server.stop()

    async def __aenter__(self) -> AsyncB2BUA:
        await self.start()
        return self

    async def __aexit__(self, *_) -> bool:
        await self.stop()
        return False

    @property
    def active_calls(self) -> int:
        """Number of currently bridged calls."""
        return len(self._calls)

    def __repr__(self) -> str:
        return f"<AsyncB2BUA(target={self.target!r}, active={self.active_calls})>"
