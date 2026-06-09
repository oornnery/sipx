from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sipx.sip.message import (
    DEFAULT_MAX_MESSAGE_SIZE,
    SipMessage,
    SipParseError,
    SipRequest,
    SipResponse,
    parse_sip_message,
)


UdpAddress = tuple[str, int]


class SipUdpError(RuntimeError):
    pass


class SipWireDirection(StrEnum):
    RX = "rx"
    TX = "tx"


@dataclass(frozen=True, slots=True)
class SipWireEvent:
    direction: SipWireDirection
    remote: UdpAddress
    raw: bytes
    message: SipMessage | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


class SipUdpEndpoint:
    def __init__(
        self,
        *,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        compact_headers: bool = False,
    ) -> None:
        if not local_host:
            raise SipUdpError("local_host is required")
        if not 0 <= local_port < 65536:
            raise SipUdpError("local_port must be between 0 and 65535")
        if max_message_size <= 0:
            raise SipUdpError("max_message_size must be positive")
        self.local_host = local_host
        self.local_port = local_port
        self.max_message_size = max_message_size
        self.compact_headers = compact_headers
        self._events: asyncio.Queue[SipWireEvent] = asyncio.Queue()
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _SipDatagramProtocol | None = None

    @property
    def is_started(self) -> bool:
        return self._transport is not None

    @property
    def local_address(self) -> UdpAddress:
        transport = self._require_transport()
        return _normalize_address(transport.get_extra_info("sockname"))

    async def start(self) -> SipUdpEndpoint:
        if self._transport is not None:
            return self
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _SipDatagramProtocol(
                events=self._events,
                max_message_size=self.max_message_size,
            ),
            local_addr=(self.local_host, self.local_port),
        )
        self._transport = transport  # type: ignore[assignment]
        self._protocol = protocol  # type: ignore[assignment]
        return self

    async def close(self) -> None:
        transport = self._transport
        protocol = self._protocol
        self._transport = None
        self._protocol = None
        if transport is None:
            return
        transport.close()
        if protocol is not None:
            try:
                await asyncio.wait_for(protocol.wait_closed(), timeout=1.0)
            except TimeoutError:
                pass

    async def __aenter__(self) -> SipUdpEndpoint:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        await self.close()

    def send_message(self, message: SipMessage, remote: UdpAddress) -> SipWireEvent:
        raw = message.to_bytes(compact_headers=self.compact_headers)
        self.send_raw(raw, remote)
        return SipWireEvent(
            direction=SipWireDirection.TX,
            remote=_normalize_address(remote),
            raw=raw,
            message=message,
        )

    def send_raw(self, raw: bytes, remote: UdpAddress) -> SipWireEvent:
        if len(raw) > self.max_message_size:
            raise SipUdpError("SIP datagram exceeds maximum size")
        transport = self._require_transport()
        address = _normalize_address(remote)
        transport.sendto(raw, address)
        return SipWireEvent(direction=SipWireDirection.TX, remote=address, raw=raw)

    async def receive_event(self, *, timeout: float | None = None) -> SipWireEvent:
        if timeout is None:
            return await self._events.get()
        try:
            return await asyncio.wait_for(self._events.get(), timeout=timeout)
        except TimeoutError as exc:
            raise SipUdpError("timed out waiting for SIP datagram") from exc

    def _require_transport(self) -> asyncio.DatagramTransport:
        if self._transport is None:
            raise SipUdpError("SIP UDP endpoint is not started")
        return self._transport


class _SipDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        *,
        events: asyncio.Queue[SipWireEvent],
        max_message_size: int,
    ) -> None:
        self._events = events
        self._max_message_size = max_message_size
        self._closed = asyncio.Event()

    def datagram_received(self, data: bytes, addr: Any) -> None:
        remote = _normalize_address(addr)
        try:
            message = parse_sip_message(data, max_size=self._max_message_size)
        except (SipParseError, ValueError) as exc:
            self._events.put_nowait(
                SipWireEvent(
                    direction=SipWireDirection.RX,
                    remote=remote,
                    raw=data,
                    error=str(exc),
                )
            )
            return
        self._events.put_nowait(
            SipWireEvent(
                direction=SipWireDirection.RX,
                remote=remote,
                raw=data,
                message=message,
            )
        )

    def error_received(self, exc: Exception) -> None:
        self._events.put_nowait(
            SipWireEvent(
                direction=SipWireDirection.RX,
                remote=("0.0.0.0", 0),
                raw=b"",
                error=f"UDP error: {exc}",
            )
        )

    def connection_lost(self, exc: Exception | None) -> None:
        self._closed.set()

    async def wait_closed(self) -> None:
        await self._closed.wait()


def _normalize_address(addr: object) -> UdpAddress:
    if not isinstance(addr, tuple) or len(addr) < 2:
        raise SipUdpError(f"invalid UDP address: {addr!r}")
    host, port = addr[:2]
    return str(host), int(port)


def sip_wire_event_name(event: SipWireEvent) -> str:
    if event.is_error:
        return "parse_error" if event.raw else "transport_error"
    if isinstance(event.message, SipRequest):
        return (
            "request_received"
            if event.direction is SipWireDirection.RX
            else "request_sent"
        )
    if isinstance(event.message, SipResponse):
        return (
            "response_received"
            if event.direction is SipWireDirection.RX
            else "response_sent"
        )
    return "raw_received" if event.direction is SipWireDirection.RX else "raw_sent"
