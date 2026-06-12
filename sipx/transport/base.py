from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TransportConfig:
    """Common configuration for SIP transports."""

    local_host: str = "0.0.0.0"
    local_port: int = 0
    timeout: float = 30.0
    max_message_size: int = 65535


class Transport(abc.ABC):
    """Abstract base class for SIP transports (UDP, TCP, TLS)."""

    def __init__(self, config: TransportConfig | None = None) -> None:
        self._config = config or TransportConfig()

    @abc.abstractmethod
    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        """Send raw bytes to the remote address."""

    @abc.abstractmethod
    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        """Yield incoming datagrams as (data, remote_address) pairs."""
        yield b"", ("", 0)  # pragma: no cover

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the transport and release resources."""

    @property
    @abc.abstractmethod
    def local_address(self) -> tuple[str, int]:
        """Return the bound local address as (host, port)."""

    @property
    @abc.abstractmethod
    def transport_type(self) -> Literal["udp", "tcp", "tls"]:
        """Return the transport protocol identifier."""
