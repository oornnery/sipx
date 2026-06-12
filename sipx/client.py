"""AsyncClient - httpx-like async SIP client.

Provides a high-level async interface for SIP operations with support
for multiple transports, event hooks, and authentication flows.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Awaitable, Callable

from sipx.config import ClientConfig
from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.protocol.auth import AuthFlow
from sipx.protocol.dialog import Dialog
from sipx.protocol.hooks import EventHooks
from sipx.protocol.transaction import ServerTransaction
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
        self._uas_handlers: dict[str, Callable[[Request], Awaitable[Response]]] = {}
        self._dialogs: dict[str, Dialog] = {}

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

    def on_invite(
        self, handler: Callable[[Request], Awaitable[Response]]
    ) -> Callable[[Request], Awaitable[Response]]:
        """Register an INVITE request handler.

        The handler receives incoming INVITE requests and must return a Response.
        Use this for UAS behavior per RFC 3261 §13.

        Args:
            handler: Async callable taking a Request, returning a Response.

        Returns:
            The handler (for use as a decorator).
        """
        self._uas_handlers["INVITE"] = handler
        return handler

    def on_message(
        self, handler: Callable[[Request], Awaitable[Response]]
    ) -> Callable[[Request], Awaitable[Response]]:
        """Register a MESSAGE request handler.

        The handler receives incoming MESSAGE requests and must return a Response.
        Use this for UAS behavior per RFC 3428.

        Args:
            handler: Async callable taking a Request, returning a Response.

        Returns:
            The handler (for use as a decorator).
        """
        self._uas_handlers["MESSAGE"] = handler
        return handler

    def on_options(
        self, handler: Callable[[Request], Awaitable[Response]]
    ) -> Callable[[Request], Awaitable[Response]]:
        """Register an OPTIONS request handler.

        The handler receives incoming OPTIONS requests and must return a Response.
        Use this for UAS behavior per RFC 3261 §11.

        Args:
            handler: Async callable taking a Request, returning a Response.

        Returns:
            The handler (for use as a decorator).
        """
        self._uas_handlers["OPTIONS"] = handler
        return handler

    def on_subscribe(
        self, handler: Callable[[Request], Awaitable[Response]]
    ) -> Callable[[Request], Awaitable[Response]]:
        """Register a SUBSCRIBE request handler.

        The handler receives incoming SUBSCRIBE requests and must return a Response.
        Use this for UAS behavior per RFC 6665.

        Args:
            handler: Async callable taking a Request, returning a Response.

        Returns:
            The handler (for use as a decorator).
        """
        self._uas_handlers["SUBSCRIBE"] = handler
        return handler

    async def handle_request(self, request: Request) -> Response:
        """Dispatch an incoming request to the registered handler.

        Creates a ServerTransaction for state management and manages Dialog
        state for INVITE requests per RFC 3261 §13.

        Args:
            request: The incoming SIP request.

        Returns:
            The Response from the handler.

        Raises:
            ProtocolError: If no handler is registered for the request method,
                or if the handler returns an invalid response.
        """
        method = request.method
        handler = self._uas_handlers.get(method)
        if handler is None:
            raise ProtocolError(
                f"no handler registered for {method} requests",
                rfc_ref="RFC 3261 §8.2",
            )

        transaction = ServerTransaction(request)

        try:
            response = await handler(request)
        except Exception as e:
            raise ProtocolError(
                f"handler for {method} raised an exception: {e}",
                rfc_ref="RFC 3261 §8.2",
            ) from e

        if not isinstance(response, Response):
            raise ProtocolError(
                f"handler for {method} must return a Response, got {type(response).__name__}",
                rfc_ref="RFC 3261 §8.2",
            )

        transaction.send_response(
            status_code=response.status_code,
            reason=response.reason,
            headers=response.headers,
            body=response.body,
        )

        if method == "INVITE" and 100 <= response.status_code < 300:
            call_id = request.headers.get("Call-ID")
            if call_id:
                if call_id not in self._dialogs:
                    local_tag = f"uas-{call_id}"
                    dialog = Dialog.from_request(request, local_tag=local_tag)
                    self._dialogs[call_id] = dialog
                self._dialogs[call_id].update(response)

        response.request = request

        return response

    def merged_config(
        self,
        *,
        transport: str | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: AuthFlow | None = None,
        **extra: Any,
    ) -> tuple[ClientConfig, AuthFlow | None]:
        """Merge per-request overrides into client defaults.

        Returns a new ClientConfig and an optional AuthFlow.  The caller
        should use the returned config/auth for the individual request.

        Args:
            transport: Override transport type.
            timeout: Override timeout.
            headers: Extra headers merged with client defaults.
            params: Extra query params merged with client defaults.
            cookies: Extra cookies merged with client defaults.
            auth: Override auth flow (falls back to client auth if None).
            **extra: Additional config fields forwarded to ClientConfig.merge().

        Returns:
            (merged_config, effective_auth)
        """
        overrides: dict[str, Any] = {}
        if transport is not None:
            overrides["transport"] = transport
        if timeout is not None:
            overrides["timeout"] = timeout
        if headers is not None:
            overrides["headers"] = headers
        if params is not None:
            overrides["params"] = params
        if cookies is not None:
            overrides["cookies"] = cookies
        overrides.update(extra)

        merged = self._config.merge(overrides)
        effective_auth = auth if auth is not None else self._auth
        return merged, effective_auth
