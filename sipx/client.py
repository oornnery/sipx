"""AsyncClient - httpx-like async SIP client.

Provides a high-level async interface for SIP operations with support
for multiple transports, event hooks, and authentication flows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sipx.config import ClientConfig
from sipx.protocol.auth import AuthFlow
from sipx.protocol.hooks import EventHooks
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.registry import TransportRegistry

if TYPE_CHECKING:
    pass


class AsyncClient:
    """Async SIP client with httpx-like interface.

    Supports multiple transports (UDP, TCP, TLS), event hooks for
    request/response interception, and automatic authentication flows.

    Usage:
        async with AsyncClient(transport="udp") as client:
            # Use client for SIP operations
            pass

        # Or without context manager:
        client = AsyncClient()
        try:
            # Use client
            pass
        finally:
            await client.aclose()
    """

    def __init__(
        self,
        transport: str = "udp",
        config: ClientConfig | None = None,
        event_hooks: EventHooks | None = None,
        auth: AuthFlow | None = None,
    ) -> None:
        """Initialize AsyncClient.

        Args:
            transport: Transport type ("udp", "tcp", or "tls").
            config: Client configuration. Uses defaults if None.
            event_hooks: Dict mapping event names to lists of callables.
            auth: Authentication flow for automatic challenge handling.

        Raises:
            ValueError: If transport type is not supported.
        """
        self._config = config or ClientConfig()
        self._event_hooks: EventHooks = dict(event_hooks) if event_hooks else {}
        self._auth = auth
        self._closed = False

        # Create transport using registry
        registry = TransportRegistry()
        transport_config = TransportConfig(
            local_host=self._config.local_host,
            local_port=self._config.local_port,
            timeout=self._config.timeout,
            max_message_size=self._config.max_message_size,
        )
        self._transport = registry.create(transport, transport_config)

    async def __aenter__(self) -> AsyncClient:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and close client."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the client and release resources.

        Closes the underlying transport. Safe to call multiple times.
        """
        if not self._closed:
            await self._transport.close()
            self._closed = True

    @property
    def is_closed(self) -> bool:
        """Return True if the client is closed."""
        return self._closed

    @property
    def transport(self) -> Transport:
        """Return the underlying transport instance."""
        return self._transport

    @property
    def config(self) -> ClientConfig:
        """Return the client configuration."""
        return self._config

    @property
    def event_hooks(self) -> EventHooks:
        """Return the registered event hooks."""
        return self._event_hooks

    @property
    def auth(self) -> AuthFlow | None:
        """Return the authentication flow, if configured."""
        return self._auth
