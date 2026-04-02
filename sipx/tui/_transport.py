"""Intercepting transport wrapper — captures every SIP packet at the wire level."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple

from ..transports._base import AsyncBaseTransport
from .._types import TransportAddress, TransportConfig

_log = logging.getLogger(__name__)


class InterceptingTransport(AsyncBaseTransport):
    """Wraps a real AsyncBaseTransport and taps every send/receive.

    Every packet that goes through send() or receive() is forwarded
    to the on_send / on_recv callbacks before/after the real operation.
    This gives the TUI full visibility — like sngrep's pcap tap.
    """

    def __init__(
        self,
        inner: AsyncBaseTransport,
        on_send: Callable[[bytes, TransportAddress], Any] | None = None,
        on_recv: Callable[[bytes, TransportAddress], Any] | None = None,
    ) -> None:
        # Don't call super().__init__ — we delegate everything to inner
        self._inner = inner
        self._on_send = on_send
        self._on_recv = on_recv

    # ── Delegated properties ────────────────────────────────────────

    @property
    def config(self) -> TransportConfig:
        return self._inner.config

    @config.setter
    def config(self, value: TransportConfig) -> None:
        self._inner.config = value

    @property
    def is_closed(self) -> bool:
        return self._inner.is_closed

    @property
    def local_address(self) -> TransportAddress:
        return self._inner.local_address

    def _get_protocol_name(self) -> str:
        return self._inner._get_protocol_name()

    # ── Intercepted methods ─────────────────────────────────────────

    async def send(self, data: bytes, destination: TransportAddress) -> None:
        """Send data and notify the tap callback."""
        if self._on_send:
            try:
                self._on_send(data, destination)
            except Exception:
                _log.debug("capture on_send callback failed", exc_info=True)
        await self._inner.send(data, destination)

    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, TransportAddress]:
        """Receive data and notify the tap callback."""
        data, source = await self._inner.receive(timeout=timeout)
        if self._on_recv:
            try:
                self._on_recv(data, source)
            except Exception:
                _log.debug("capture on_recv callback failed", exc_info=True)
        return data, source

    async def handle_request(self, request: Any, destination: TransportAddress) -> Any:
        """Delegate to inner — send/receive inside will be intercepted."""
        return await self._inner.handle_request(request, destination)

    async def close(self) -> None:
        await self._inner.close()

    async def __aenter__(self) -> InterceptingTransport:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._inner.__aexit__(exc_type, exc_val, exc_tb)

    # ── Passthrough for any internal attributes the transport needs ──

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes to the inner transport."""
        return getattr(self._inner, name)
