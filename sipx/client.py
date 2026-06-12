"""AsyncClient - httpx-like async SIP client.

Provides a high-level async interface for SIP operations with support
for multiple transports, event hooks, and authentication flows.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, TYPE_CHECKING, Awaitable, Callable

from sipx.config import ClientConfig
from sipx.exceptions import ProtocolError, TimeoutError as SipTimeoutError
from sipx.models import Request, Response
from sipx.protocol.auth import AuthFlow
from sipx.protocol.dialog import Dialog
from sipx.protocol.hooks import EventHooks, run_hooks
from sipx.protocol.transaction import ClientTransaction, ServerTransaction
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.registry import TransportRegistry

if TYPE_CHECKING:
    pass


def _new_call_id() -> str:
    return str(uuid.uuid4())


def _new_tag() -> str:
    return uuid.uuid4().hex[:8]


def _new_branch() -> str:
    return f"z9hG4bK{uuid.uuid4().hex[:12]}"


def _parse_response(data: bytes, request: Request) -> Response:
    """Parse raw SIP response bytes into a Response object."""
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\r\n")

    if not lines:
        raise ValueError("Empty response")

    status_line = lines[0]
    parts = status_line.split(" ", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid SIP status line: {status_line}")

    try:
        status_code = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid status code: {parts[1]}") from exc

    reason = parts[2]

    headers: dict[str, str | list[str]] = {}
    body_start = 0
    for i, line in enumerate(lines[1:], start=1):
        if not line:
            body_start = i + 1
            break
        if ":" in line:
            name, _, value = line.partition(":")
            name = name.strip()
            value = value.strip()
            if name in headers:
                existing = headers[name]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    headers[name] = [existing, value]
            else:
                headers[name] = value

    body = None
    if body_start > 0 and body_start < len(lines):
        body_text = "\r\n".join(lines[body_start:])
        if body_text:
            body = body_text.encode("utf-8")

    return Response(
        status_code=status_code,
        reason=reason,
        headers=headers,
        body=body,
        request=request,
    )


def _parse_remote(uri: str) -> tuple[str, int]:
    """Parse a SIP URI to extract host and port."""
    if uri.startswith("sips:"):
        uri = uri[5:]
    elif uri.startswith("sip:"):
        uri = uri[4:]

    if "@" in uri:
        uri = uri.split("@", 1)[1]

    if ";" in uri:
        uri = uri.split(";", 1)[0]

    if "?" in uri:
        uri = uri.split("?", 1)[0]

    if ":" in uri:
        host, port_str = uri.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 5060
    else:
        host = uri
        port = 5060

    return (host, port)


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
        self._closed = True
        self._receive_task: asyncio.Task | None = None
        self._uas_handlers: dict[str, Callable[[Request], Awaitable[Response]]] = {}
        self._dialogs: dict[str, Dialog] = {}
        self._pending_responses: dict[str, asyncio.Future[Response]] = {}

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
        """Enter async context manager.

        Starts the underlying transport and the receive loop.
        """
        if not self._closed:
            return self

        try:
            # Start transport if it has an async start method
            start = getattr(self._transport, "start", None)
            if start is not None:
                await start()

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._closed = False
        except Exception:
            # Clean up on failure so the client remains in a closed state
            await self._cleanup()
            raise

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

        Closes the underlying transport and cancels the receive loop.
        Safe to call multiple times.
        """
        if self._closed:
            return

        await self._cleanup()

    async def _cleanup(self) -> None:
        """Internal cleanup: cancel receive task and close transport."""
        # Cancel receive task
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        # Close transport
        if self._transport is not None:
            try:
                await self._transport.close()
            except Exception:
                pass

        self._closed = True

    async def _receive_loop(self) -> None:
        """Background receive loop that dispatches responses to UAC methods."""
        try:
            async for data, _remote in self._transport.receive():
                try:
                    self._dispatch_response(data)
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def _dispatch_response(self, data: bytes) -> None:
        """Parse a response and dispatch to waiting UAC method."""
        text = data.decode("utf-8", errors="replace")
        lines = text.split("\r\n")
        if not lines:
            return

        status_line = lines[0]
        parts = status_line.split(" ", 2)
        if len(parts) < 3 or not parts[0].startswith("SIP/"):
            return

        headers: dict[str, str | list[str]] = {}
        for line in lines[1:]:
            if not line:
                break
            if ":" in line:
                name, _, value = line.partition(":")
                name = name.strip()
                value = value.strip()
                if name in headers:
                    existing = headers[name]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        headers[name] = [existing, value]
                else:
                    headers[name] = value

        call_id = headers.get("Call-ID")
        cseq = headers.get("CSeq")
        if not isinstance(call_id, str) or not isinstance(cseq, str):
            return
        if not call_id or not cseq:
            return

        cseq_parts = cseq.split(" ", 1)
        if len(cseq_parts) < 2:
            return

        key = f"{call_id}:{cseq_parts[0]}"
        future = self._pending_responses.get(key)
        if future and not future.done():
            future.set_result(data)

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
            if isinstance(call_id, str) and call_id:
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

    def _build_request(
        self,
        method: str,
        uri: str,
        *,
        body: bytes | None = None,
        **extra_headers: Any,
    ) -> Request:
        """Build a SIP request with required headers."""
        call_id = extra_headers.pop("Call-ID", _new_call_id())
        from_uri = extra_headers.pop(
            "From", self._config.from_uri or f"sip:user@{self._config.local_host}"
        )
        from_tag = _new_tag()
        to_uri = extra_headers.pop("To", uri)
        cseq = extra_headers.pop("CSeq", 1)
        branch = _new_branch()

        transport_type = self._transport.transport_type.upper()
        local_host = self._config.local_host
        local_port = self._config.local_port
        via = f"SIP/2.0/{transport_type} {local_host}:{local_port};branch={branch}"

        headers: dict[str, str | list[str]] = {
            "Via": via,
            "From": f"<{from_uri}>;tag={from_tag}",
            "To": f"<{to_uri}>",
            "Call-ID": call_id,
            "CSeq": f"{cseq} {method}",
            "Max-Forwards": "70",
            "User-Agent": self._config.user_agent,
        }

        if method in ("INVITE", "REGISTER", "SUBSCRIBE"):
            contact_uri = self._config.contact_uri or from_uri
            headers["Contact"] = f"<{contact_uri}>"

        headers.update(extra_headers)

        return Request(
            method=method,
            uri=uri,
            headers=headers,
            body=body,
            transport=self._transport,
        )

    async def _send_request(
        self,
        request: Request,
        remote: tuple[str, int],
    ) -> Response:
        """Send a SIP request and wait for a response with auth handling."""
        transaction = ClientTransaction(request)
        await run_hooks(self._event_hooks, "request", request)

        if self._auth:
            flow = self._auth.auth_flow(request)
            current_request = next(flow)

            while True:
                response = await self._send_and_receive(
                    current_request, remote, transaction
                )
                await run_hooks(self._event_hooks, "response", response)

                if response.status_code in (401, 407):
                    try:
                        current_request = flow.send(response)
                        transaction = ClientTransaction(current_request)
                    except StopIteration:
                        return response
                else:
                    return response
        else:
            response = await self._send_and_receive(request, remote, transaction)
            await run_hooks(self._event_hooks, "response", response)
            return response

    async def _send_and_receive(
        self,
        request: Request,
        remote: tuple[str, int],
        transaction: ClientTransaction,
    ) -> Response:
        """Send request and wait for final response."""
        call_id = request.headers.get("Call-ID", "")
        cseq_header = request.headers.get("CSeq", "")
        cseq_num = (
            cseq_header.split(" ", 1)[0]
            if isinstance(cseq_header, str) and cseq_header
            else "1"
        )
        key = f"{call_id}:{cseq_num}"

        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        self._pending_responses[key] = future

        try:
            await self._transport.send(request.to_bytes(), remote)

            timeout = self._config.timeout
            try:
                data = await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError:
                raise SipTimeoutError(
                    f"Timeout waiting for response to {request.method}",
                    rfc_ref="RFC 3261 §17",
                )

            response = _parse_response(data, request)

            transaction.receive_response(
                status_code=response.status_code,
                reason=response.reason,
                headers=response.headers,
                body=response.body,
            )

            if 100 <= response.status_code < 200:
                await run_hooks(self._event_hooks, "provisional", response)
                future2: asyncio.Future[Response] = (
                    asyncio.get_event_loop().create_future()
                )
                self._pending_responses[key] = future2
                try:
                    data2 = await asyncio.wait_for(future2, timeout)
                    response = _parse_response(data2, request)
                    transaction.receive_response(
                        status_code=response.status_code,
                        reason=response.reason,
                        headers=response.headers,
                        body=response.body,
                    )
                except asyncio.TimeoutError:
                    raise SipTimeoutError(
                        f"Timeout waiting for final response to {request.method}",
                        rfc_ref="RFC 3261 §17",
                    )

            return response
        finally:
            self._pending_responses.pop(key, None)

    async def invite(self, uri: str, **kwargs: Any) -> Response:
        """Send an INVITE request to initiate a session (RFC 3261 §13).

        Args:
            uri: Target SIP URI for the invitation.
            **kwargs: Extra headers merged into the request.

        Returns:
            The SIP response, typically 100 Trying, 180 Ringing, or 200 OK.

        Raises:
            ProtocolError: If the response indicates a protocol-level failure.
            TimeoutError: If no response is received within the configured timeout.

        Examples:
            >>> response = await client.invite("sip:bob@example.com")
            >>> print(response.status_code)
            200
        """
        request = self._build_request("INVITE", uri, **kwargs)
        remote = _parse_remote(uri)
        response = await self._send_request(request, remote)

        if 100 <= response.status_code < 300:
            call_id = request.headers.get("Call-ID")
            if isinstance(call_id, str) and call_id:
                try:
                    dialog = Dialog.from_invite(request, response)
                    self._dialogs[call_id] = dialog
                except Exception:
                    pass

        return response

    async def register(self, uri: str, **kwargs: Any) -> Response:
        """Send a REGISTER request (RFC 3261 §10).

        Args:
            uri: SIP URI of the registrar (e.g. ``sip:registrar.example.com``).
            **kwargs: Extra headers merged into the request.

        Returns:
            The SIP response, typically 200 OK on success.

        Raises:
            ProtocolError: If the response indicates a registration failure.
            TimeoutError: If no response is received within the configured timeout.

        Examples:
            >>> response = await client.register("sip:registrar.example.com")
            >>> print(response.status_code)
            200
        """
        request = self._build_request("REGISTER", uri, **kwargs)
        remote = _parse_remote(uri)
        return await self._send_request(request, remote)

    async def message(self, uri: str, body: str | bytes, **kwargs: Any) -> Response:
        """Send a MESSAGE request (RFC 3428).

        Args:
            uri: Target SIP URI.
            body: Message body as str or bytes.
            **kwargs: Extra headers merged into the request.

        Returns:
            The SIP response.

        Raises:
            ProtocolError: If the response is a 4xx or 5xx error.
        """
        if isinstance(body, str):
            body = body.encode("utf-8")
            kwargs.setdefault("Content-Type", "text/plain")
        elif isinstance(body, bytes):
            kwargs.setdefault("Content-Type", "application/octet-stream")

        kwargs["Content-Length"] = str(len(body))

        request = self._build_request("MESSAGE", uri, body=body, **kwargs)
        remote = _parse_remote(uri)
        response = await self._send_request(request, remote)

        if 400 <= response.status_code < 600:
            raise ProtocolError(
                f"MESSAGE failed: {response.status_code} {response.reason}",
                rfc_ref="RFC 3428",
                details={
                    "status_code": response.status_code,
                    "reason": response.reason,
                },
            )

        return response

    async def options(self, uri: str, **kwargs: Any) -> Response:
        """Send an OPTIONS request (RFC 3261 §11).

        Args:
            uri: Target SIP URI to query for capabilities.
            **kwargs: Extra headers merged into the request.

        Returns:
            The SIP response, typically 200 OK with supported methods
            and capabilities in the header fields.

        Raises:
            ProtocolError: If the response indicates a protocol-level failure.
            TimeoutError: If no response is received within the configured timeout.

        Examples:
            >>> response = await client.options("sip:bob@example.com")
            >>> print(response.status_code)
            200
        """
        request = self._build_request("OPTIONS", uri, **kwargs)
        remote = _parse_remote(uri)
        return await self._send_request(request, remote)

    async def subscribe(self, uri: str, event: str, **kwargs: Any) -> Response:
        """Send a SUBSCRIBE request (RFC 6665).

        Args:
            uri: Target SIP URI for the subscription.
            event: Event package name (e.g. ``presence``, ``dialog``).
            **kwargs: Extra headers merged into the request.

        Returns:
            The SIP response, typically 200 OK or 202 Accepted.

        Raises:
            ProtocolError: If the response indicates a protocol-level failure.
            TimeoutError: If no response is received within the configured timeout.

        Examples:
            >>> response = await client.subscribe(
            ...     "sip:bob@example.com", event="presence"
            ... )
            >>> print(response.status_code)
            200
        """
        kwargs["Event"] = event
        kwargs.setdefault("Expires", "3600")
        request = self._build_request("SUBSCRIBE", uri, **kwargs)
        remote = _parse_remote(uri)
        return await self._send_request(request, remote)
