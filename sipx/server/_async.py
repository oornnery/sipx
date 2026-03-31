"""Async SIP server using asyncio DatagramProtocol."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict

from .._utils import logger
from ..models._message import MessageParser, Request
from .._types import TransportAddress
from .._depends import resolve_handler
from ._base import SIPServerHandlerMixin


class _SIPServerProtocol(asyncio.DatagramProtocol):
    """asyncio DatagramProtocol for native async SIP server."""

    def __init__(self, server: AsyncSIPServer) -> None:
        self.server = server
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        asyncio.ensure_future(self.server._handle_datagram(data, addr, self.transport))


class AsyncSIPServer(SIPServerHandlerMixin):
    """Native async SIP server using asyncio.DatagramProtocol.

    No threading -- runs entirely in the asyncio event loop.
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

    # ------------------------------------------------------------------
    # Datagram handler
    # ------------------------------------------------------------------

    async def _handle_datagram(
        self,
        data: bytes,
        addr: tuple[str, int],
        transport: asyncio.DatagramTransport | None,
    ) -> None:
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

        # Auto 100 Trying for INVITE (RFC 3261 §8.2.6.1)
        if message.method == "INVITE" and transport:
            trying = message.trying()
            transport.sendto(trying.to_bytes(), addr)
            logger.debug(">>> AUTO 100 Trying to %s:%s", addr[0], addr[1])

        handler = self._handlers.get(message.method)
        if handler:
            try:
                response = resolve_handler(handler, message, source)
            except Exception as e:
                logger.error("Handler error: %s", e)
                response = message.error(500)
        else:
            response = message.error(501)

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
