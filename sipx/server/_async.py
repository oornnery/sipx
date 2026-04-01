"""Async SIP server using asyncio DatagramProtocol."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict

from .._utils import logger
from ..models._message import MessageParser, Request
from .._types import TransportAddress, TransactionType, TransactionState
from ..fsm import StateManager, AsyncTimerManager
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
        self._state_manager = StateManager()
        self._rseq_counter: int = 0  # RFC 3262: monotonically increasing RSeq
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

        # ACK: no response — confirm original INVITE transaction (cancels Timer G/H)
        if message.method == "ACK":
            logger.info("Received ACK from %s:%s", addr[0], addr[1])
            invite_txn = self._state_manager.find_transaction(
                call_id=message.headers.get("Call-ID"),
                method="INVITE",
            )
            if invite_txn:
                invite_txn.transition_to(TransactionState.CONFIRMED)
            return

        # Create server transaction for tracking
        txn_type = (
            TransactionType.INVITE_SERVER
            if message.method == "INVITE"
            else TransactionType.NON_INVITE_SERVER
        )
        txn = self._state_manager.create_transaction(message, transaction_type=txn_type)

        # Auto 100 Trying for INVITE (RFC 3261 §8.2.6.1)
        if message.method == "INVITE" and transport:
            trying = message.trying()
            transport.sendto(trying.to_bytes(), addr)
            logger.debug(">>> AUTO 100 Trying to %s:%s", addr[0], addr[1])

        handler = self._handlers.get(message.method)
        if handler:
            try:
                import asyncio as _asyncio

                if _asyncio.iscoroutinefunction(handler):
                    response = await handler(message, source)
                else:
                    response = resolve_handler(handler, message, source)
            except Exception as e:
                logger.error("Handler error: %s", e)
                response = message.error(500)

            # Add RSeq for reliable provisional responses (RFC 3262)
            if (
                message.method == "INVITE"
                and 100 < response.status_code < 200
                and "100rel" in message.headers.get("Require", "")
            ):
                self._rseq_counter += 1
                response.headers["RSeq"] = str(self._rseq_counter)
                response.headers["Require"] = "100rel"
        else:
            response = message.error(501)

        if transport:
            response_data = response.to_bytes()
            transport.sendto(response_data, addr)

            # Wire async Timer G retransmit for INVITE on UDP
            if message.method == "INVITE":
                timer_manager = AsyncTimerManager()
                txn.timer_manager = timer_manager
                txn._retransmit_fn = lambda d=response_data, a=addr: (
                    transport.sendto(d, a) if transport else None
                )
                txn._on_state_change(txn.state, txn.state)

            self._state_manager.update_transaction(txn.id, response)

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
