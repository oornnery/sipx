"""
Base transport abstractions for SIP protocol.

This module defines abstract base classes for SIP transports, inspired by HTTPX's
transport architecture but adapted for SIP's unique requirements (UDP, TCP, TLS).
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional, Tuple

# Import types from centralized _types module
from .._types import TransportAddress, TransportConfig

if TYPE_CHECKING:
    from .._models._message import Request, Response


class BaseTransport(abc.ABC):
    """
    Abstract base class for synchronous SIP transports.

    This follows the pattern from HTTPX but adapted for SIP protocol requirements.
    All transports must implement send/receive methods and context manager protocol.
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize transport with configuration.

        Args:
            config: Transport configuration. If None, uses defaults.
        """
        self.config = config or TransportConfig()
        self._closed = False

    @abc.abstractmethod
    def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send a request and return the response.

        This is the main method that clients call. It handles:
        - Serializing the request
        - Sending over the network
        - Receiving the response
        - Parsing the response

        Args:
            request: The SIP request to send
            destination: Where to send the request

        Returns:
            The parsed SIP response

        Raises:
            TransportError: On network or protocol errors
            TimeoutError: If operation times out
        """
        ...

    @abc.abstractmethod
    def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes to destination.

        Args:
            data: Raw bytes to send
            destination: Where to send

        Raises:
            TransportError: On send failure
        """
        ...

    @abc.abstractmethod
    def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes from transport.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (data, source_address)

        Raises:
            TimeoutError: If timeout expires
            TransportError: On receive failure
        """
        ...

    @abc.abstractmethod
    def close(self) -> None:
        """Close the transport and release resources."""
        ...

    def __enter__(self) -> BaseTransport:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close transport."""
        self.close()

    @property
    def is_closed(self) -> bool:
        """Check if transport is closed."""
        return self._closed

    @property
    def local_address(self) -> TransportAddress:
        """Get local bound address."""
        return TransportAddress(
            host=self.config.local_host,
            port=self.config.local_port,
            protocol=self._get_protocol_name(),
        )

    @abc.abstractmethod
    def _get_protocol_name(self) -> str:
        """Return protocol name (UDP, TCP, or TLS)."""
        ...


class AsyncBaseTransport(abc.ABC):
    """
    Abstract base class for asynchronous SIP transports.

    Async version of BaseTransport using asyncio.
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        """
        Initialize async transport with configuration.

        Args:
            config: Transport configuration. If None, uses defaults.
        """
        self.config = config or TransportConfig()
        self._closed = False

    @abc.abstractmethod
    async def handle_request(
        self,
        request: Request,
        destination: TransportAddress,
    ) -> Response:
        """
        Send a request and return the response (async).

        Args:
            request: The SIP request to send
            destination: Where to send the request

        Returns:
            The parsed SIP response

        Raises:
            TransportError: On network or protocol errors
            TimeoutError: If operation times out
        """
        ...

    @abc.abstractmethod
    async def send(self, data: bytes, destination: TransportAddress) -> None:
        """
        Send raw bytes to destination (async).

        Args:
            data: Raw bytes to send
            destination: Where to send

        Raises:
            TransportError: On send failure
        """
        ...

    @abc.abstractmethod
    async def receive(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, TransportAddress]:
        """
        Receive raw bytes from transport (async).

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (data, source_address)

        Raises:
            TimeoutError: If timeout expires
            TransportError: On receive failure
        """
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the transport and release resources (async)."""
        ...

    async def __aenter__(self) -> AsyncBaseTransport:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and close transport."""
        await self.close()

    @property
    def is_closed(self) -> bool:
        """Check if transport is closed."""
        return self._closed

    @property
    def local_address(self) -> TransportAddress:
        """Get local bound address."""
        return TransportAddress(
            host=self.config.local_host,
            port=self.config.local_port,
            protocol=self._get_protocol_name(),
        )

    @abc.abstractmethod
    def _get_protocol_name(self) -> str:
        """Return protocol name (UDP, TCP, or TLS)."""
        ...
