"""AsyncClient - httpx-like async SIP client.

Provides a high-level async interface for SIP operations with support
for multiple transports, event hooks, and authentication flows.
"""

from __future__ import annotations

import asyncio
import ipaddress
import uuid
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING, Awaitable, Callable

from sipx.config import ClientConfig
from sipx.exceptions import ProtocolError, TimeoutError as SipTimeoutError
from sipx.models import Request, Response
from sipx.protocol.auth import AuthFlow
from sipx.protocol.dialog import Dialog
from sipx.protocol.hooks import EventHooks, run_hooks
from sipx.protocol.transaction import (
    ClientTransaction,
    ServerTransaction,
    T1,
    T2,
)
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.registry import TransportRegistry
from sipx.wire import (
    extract_cseq_parts,
    extract_top_via_branch,
    sanitize_sip_token,
)

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class _PendingMatch:
    """In-flight UAC response waiter with strict correlation fields."""

    future: asyncio.Future[bytes]
    branch: str | None
    remote: tuple[str, int]
    cseq_method: str


@dataclass(slots=True)
class _PendingInvite:
    """An INVITE awaiting its final response, so CANCEL can target it."""

    request: Request
    remote: tuple[str, int]


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


def _contact_uri(contact: str) -> str:
    """Extract the bare URI from a Contact header value like ``<sip:a@b>;p=1``."""
    value = contact.strip()
    if "<" in value and ">" in value:
        value = value[value.index("<") + 1 : value.index(">")]
    else:
        value = value.split(";", 1)[0].strip()
    return value


def _is_ip_literal(host: str) -> bool:
    """Return True if *host* is a literal IPv4/IPv6 address (not a hostname)."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _remote_matches(source: tuple[str, int], expected: tuple[str, int]) -> bool:
    """Check a response source against the request destination (RFC 3261 §18).

    Exact ``(host, port)`` match passes. When the request targeted a hostname,
    the datagram arrives from the resolved IP, so the host cannot be compared
    directly; a matching port is accepted (Call-ID/CSeq/branch still bind the
    response). When the request targeted an IP literal, the host must match.
    """
    if source == expected:
        return True
    if source[1] != expected[1]:
        return False
    return not _is_ip_literal(expected[0])


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
        self._pending_responses: dict[str, _PendingMatch] = {}
        self._pending_invites: dict[str, _PendingInvite] = {}
        self._learned_address: tuple[str, int] | None = None

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
            async for data, remote in self._transport.receive():
                try:
                    self._dispatch_response(data, remote)
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def _dispatch_response(self, data: bytes, remote: tuple[str, int]) -> None:
        """Parse a response and dispatch to a waiting UAC transaction.

        Matches Call-ID, CSeq number/method, top Via branch, and source
        address per RFC 3261 §17.1.3. Unmatched datagrams are dropped.
        """
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

        cseq_parts = extract_cseq_parts(cseq)
        if cseq_parts is None:
            return
        cseq_num, cseq_method = cseq_parts

        key = f"{call_id}:{cseq_num}:{cseq_method.upper()}"
        pending = self._pending_responses.get(key)
        if pending is None or pending.future.done():
            return

        response_branch = extract_top_via_branch(headers)
        if pending.branch and response_branch != pending.branch:
            return

        if not _remote_matches(remote, pending.remote):
            return

        self._learn_via_address(headers)
        pending.future.set_result(data)

    def _learn_via_address(self, headers: dict[str, str | list[str]]) -> None:
        """Record our public address from the top Via ``received``/``rport`` (RFC 3581)."""
        via = headers.get("Via")
        if isinstance(via, list):
            via = via[0] if via else ""
        if not isinstance(via, str) or not via:
            return
        host: str | None = None
        port: int | None = None
        for param in via.split(";")[1:]:
            name, _, val = param.strip().partition("=")
            lname = name.lower()
            if lname == "received" and val:
                host = val.strip()
            elif lname == "rport" and val.strip().isdigit():
                port = int(val.strip())
        if host is None and port is None:
            return
        prev = self._learned_address
        final_host = host if host is not None else (prev[0] if prev else None)
        final_port = port if port is not None else (prev[1] if prev else None)
        if final_host is not None and final_port is not None:
            self._learned_address = (final_host, final_port)

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

    @property
    def learned_address(self) -> tuple[str, int] | None:
        """Public ``(host, port)`` learned from Via ``received``/``rport`` (RFC 3581).

        Populated from the topmost Via of received responses when the server
        echoes our request Via with ``received`` and/or ``rport`` filled in.
        Returns ``None`` until such a response is seen.
        """
        return self._learned_address

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
        method = sanitize_sip_token(method.upper(), field="method")
        uri = sanitize_sip_token(uri, field="URI")

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
        if self._config.rport and transport_type == "UDP":
            via += ";rport"

        headers: dict[str, str | list[str]] = {
            "Via": via,
            "From": f"<{sanitize_sip_token(str(from_uri), field='From URI')}>;tag={from_tag}",
            "To": f"<{sanitize_sip_token(str(to_uri), field='To URI')}>",
            "Call-ID": sanitize_sip_token(str(call_id), field="Call-ID"),
            "CSeq": f"{cseq} {method}",
            "Max-Forwards": "70",
            "User-Agent": sanitize_sip_token(
                self._config.user_agent, field="User-Agent"
            ),
        }

        if method in ("INVITE", "REGISTER", "SUBSCRIBE"):
            contact_uri = self._config.contact_uri or str(from_uri)
            headers["Contact"] = (
                f"<{sanitize_sip_token(str(contact_uri), field='Contact URI')}>"
            )

        for name, value in extra_headers.items():
            safe_name = sanitize_sip_token(str(name), field="header name")
            if isinstance(value, list):
                headers[safe_name] = [
                    sanitize_sip_token(str(v), field=f"header {safe_name}")
                    for v in value
                ]
            else:
                headers[safe_name] = sanitize_sip_token(
                    str(value), field=f"header {safe_name}"
                )

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
            history: list[Response] = []

            while True:
                response = await self._send_and_receive(
                    current_request, remote, transaction
                )
                # Provisional responses for this attempt become history.
                history.extend(response.history)
                response.history = []
                await run_hooks(self._event_hooks, "response", response)

                if response.status_code in (401, 407):
                    try:
                        current_request = flow.send(response)
                    except StopIteration:
                        response.history = history
                        return response
                    # The challenge response is part of the exchange history.
                    history.append(response)
                    transaction = ClientTransaction(current_request)
                else:
                    response.history = history
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
        """Send a request and wait for the final response.

        Provisional (1xx) responses are collected on the returned response's
        ``history`` in arrival order; the returned response is the first
        final (>= 200) response.
        """
        call_id = request.headers.get("Call-ID", "")
        cseq_header = request.headers.get("CSeq", "")
        cseq_parts = (
            extract_cseq_parts(cseq_header)
            if isinstance(cseq_header, str) and cseq_header
            else None
        )
        cseq_num = cseq_parts[0] if cseq_parts else "1"
        cseq_method = cseq_parts[1] if cseq_parts else request.method
        key = f"{call_id}:{cseq_num}:{cseq_method.upper()}"
        provisionals: list[Response] = []
        branch = extract_top_via_branch(request.headers)
        is_invite = request.method == "INVITE"
        reliable = self._transport.transport_type in ("tcp", "tls")
        retransmit = self._config.retransmit and not reliable
        got_provisional = False
        try:
            prack_cseq = int(cseq_num)
        except ValueError:
            prack_cseq = 1

        loop = asyncio.get_event_loop()
        deadline = loop.time() + self._config.timeout
        future: asyncio.Future[bytes] = loop.create_future()
        self._pending_responses[key] = _PendingMatch(
            future=future,
            branch=branch,
            remote=remote,
            cseq_method=cseq_method,
        )

        try:
            await self._transport.send(request.to_bytes(), remote)

            while True:
                # INVITE stops retransmitting once a provisional arrives
                # (Timer A cancelled in Proceeding); non-INVITE keeps Timer E
                # up to T2 (RFC 3261 §17.1.1.2 / §17.1.2.2).
                allow_retransmit = retransmit and not (is_invite and got_provisional)
                data = await self._await_response(
                    future,
                    request,
                    remote,
                    deadline=deadline,
                    retransmit=allow_retransmit,
                    invite=is_invite,
                )

                response = _parse_response(data, request)
                transaction.receive_response(
                    status_code=response.status_code,
                    reason=response.reason,
                    headers=response.headers,
                    body=response.body,
                )

                if 100 <= response.status_code < 200:
                    provisionals.append(response)
                    got_provisional = True
                    future = loop.create_future()
                    self._pending_responses[key] = _PendingMatch(
                        future=future,
                        branch=branch,
                        remote=remote,
                        cseq_method=cseq_method,
                    )
                    await run_hooks(self._event_hooks, "provisional", response)
                    if is_invite and await self._maybe_send_prack(
                        request, response, prack_cseq + 1
                    ):
                        prack_cseq += 1
                    continue

                response.history = provisionals
                return response
        finally:
            self._pending_responses.pop(key, None)

    async def _await_response(
        self,
        future: asyncio.Future[bytes],
        request: Request,
        remote: tuple[str, int],
        *,
        deadline: float,
        retransmit: bool,
        invite: bool,
    ) -> bytes:
        """Wait for *future*, retransmitting on unreliable transports.

        Implements RFC 3261 §17 client retransmission: on UDP the request is
        resent at intervals starting at T1 and doubling (capped at T2 for
        non-INVITE) until a response arrives or the overall timeout
        (``deadline``) elapses, which raises ``SipTimeoutError``. On reliable
        transports or when ``retransmit`` is False, it waits once.
        """
        loop = asyncio.get_event_loop()
        interval = T1
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise SipTimeoutError(
                    f"Timeout waiting for response to {request.method}",
                    rfc_ref="RFC 3261 §17",
                )
            wait = min(interval, remaining) if retransmit else remaining
            try:
                return await asyncio.wait_for(asyncio.shield(future), wait)
            except asyncio.TimeoutError:
                if future.done():
                    return future.result()
                if not retransmit or (deadline - loop.time()) <= 0:
                    raise SipTimeoutError(
                        f"Timeout waiting for response to {request.method}",
                        rfc_ref="RFC 3261 §17",
                    )
                await self._transport.send(request.to_bytes(), remote)
                interval = interval * 2 if invite else min(interval * 2, T2)

    async def _maybe_send_prack(
        self,
        invite: Request,
        provisional: Response,
        prack_cseq: int,
    ) -> bool:
        """Send PRACK for a reliable provisional response (RFC 3262).

        Triggers only when the provisional carries an ``RSeq`` and advertises
        ``100rel`` in ``Require``/``Supported``. The PRACK is sent in the early
        dialog to the provisional's Contact, with a ``RAck`` header tying it to
        the provisional's RSeq and the INVITE CSeq.

        Returns:
            True if a PRACK was sent, False otherwise.
        """
        rseq = provisional.headers.get("RSeq")
        if isinstance(rseq, list):
            rseq = rseq[0] if rseq else None
        if not isinstance(rseq, str) or not rseq.strip():
            return False

        tokens: list[str] = []
        for header in ("Require", "Supported"):
            value = provisional.headers.get(header)
            if isinstance(value, list):
                tokens.extend(value)
            elif isinstance(value, str):
                tokens.append(value)
        if not any("100rel" in token.lower() for token in tokens):
            return False

        from_hdr = invite.headers.get("From")
        call_id = invite.headers.get("Call-ID")
        inv_cseq = invite.headers.get("CSeq")
        if not (
            isinstance(from_hdr, str)
            and isinstance(call_id, str)
            and isinstance(inv_cseq, str)
        ):
            return False
        to_hdr = provisional.headers.get("To") or invite.headers.get("To")
        if isinstance(to_hdr, list):
            to_hdr = to_hdr[0] if to_hdr else ""
        if not isinstance(to_hdr, str):
            return False

        inv_parts = extract_cseq_parts(inv_cseq)
        inv_num = inv_parts[0] if inv_parts else "1"
        inv_method = inv_parts[1] if inv_parts else "INVITE"

        contact = provisional.headers.get("Contact")
        if isinstance(contact, list):
            contact = contact[0] if contact else None
        target = _contact_uri(contact) if isinstance(contact, str) else invite.uri

        branch = _new_branch()
        transport_type = self._transport.transport_type.upper()
        via = (
            f"SIP/2.0/{transport_type} "
            f"{self._config.local_host}:{self._config.local_port};branch={branch}"
        )
        if self._config.rport and transport_type == "UDP":
            via += ";rport"

        headers: dict[str, str | list[str]] = {
            "Via": via,
            "From": from_hdr,
            "To": to_hdr,
            "Call-ID": call_id,
            "CSeq": f"{prack_cseq} PRACK",
            "Max-Forwards": "70",
            "RAck": f"{rseq.strip()} {inv_num} {inv_method}",
            "User-Agent": self._config.user_agent,
        }
        prack = Request(
            method="PRACK",
            uri=target,
            headers=headers,
            body=None,
            transport=self._transport,
        )
        await self._send_request(prack, _parse_remote(target))
        return True

    async def request(self, method: str, uri: str, **kwargs: Any) -> Response:
        """Send a SIP request with an arbitrary method (curl-like escape hatch).

        Args:
            method: SIP method name (e.g. ``OPTIONS``, ``INFO``, ``PING``).
            uri: Target SIP URI.
            **kwargs: ``body`` plus extra headers merged into the request.

        Returns:
            The SIP response.

        Raises:
            TimeoutError: If no response is received within the configured timeout.
        """
        request = self._build_request(method.upper(), uri, **kwargs)
        remote = _parse_remote(uri)
        return await self._send_request(request, remote)

    def dialog(self, call_id: str) -> Dialog | None:
        """Return the tracked dialog for *call_id*, if any."""
        return self._dialogs.get(call_id)

    async def ack(self, call_id: str) -> None:
        """Send an ACK for a confirmed INVITE dialog (RFC 3261 §13.2.2.4).

        Args:
            call_id: Call-ID of the dialog created by a previous ``invite()``.

        Raises:
            ProtocolError: If no dialog is tracked for *call_id*.
        """
        dialog = self._dialogs.get(call_id)
        if dialog is None:
            raise ProtocolError(
                f"no dialog tracked for Call-ID {call_id!r}",
                rfc_ref="RFC 3261 §13.2.2.4",
            )

        request = self._build_in_dialog_request(dialog, "ACK")
        remote = _parse_remote(_contact_uri(dialog.remote_target))
        await run_hooks(self._event_hooks, "request", request)
        await self._transport.send(request.to_bytes(), remote)

    async def bye(self, call_id: str) -> Response:
        """Send a BYE to terminate a confirmed INVITE dialog (RFC 3261 §15).

        Args:
            call_id: Call-ID of the dialog created by a previous ``invite()``.

        Returns:
            The SIP response to the BYE (typically 200 OK).

        Raises:
            ProtocolError: If no dialog is tracked for *call_id*.
            TimeoutError: If no response is received within the configured timeout.
        """
        dialog = self._dialogs.get(call_id)
        if dialog is None:
            raise ProtocolError(
                f"no dialog tracked for Call-ID {call_id!r}",
                rfc_ref="RFC 3261 §15",
            )

        request = self._build_in_dialog_request(dialog, "BYE")
        remote = _parse_remote(_contact_uri(dialog.remote_target))
        response = await self._send_request(request, remote)

        if 200 <= response.status_code < 300:
            dialog.terminate()
            self._dialogs.pop(call_id, None)

        return response

    def _build_in_dialog_request(self, dialog: Dialog, method: str) -> Request:
        """Build an in-dialog request (ACK/BYE) from dialog state."""
        cseq = dialog.next_cseq(method)
        branch = _new_branch()
        transport_type = self._transport.transport_type.upper()
        local_host = self._config.local_host
        local_port = self._config.local_port

        headers: dict[str, str | list[str]] = {
            "Via": f"SIP/2.0/{transport_type} {local_host}:{local_port};branch={branch}",
            "From": dialog.local_uri,
            "To": dialog.remote_uri,
            "Call-ID": dialog.call_id,
            "CSeq": f"{cseq} {method}",
            "Max-Forwards": "70",
            "User-Agent": self._config.user_agent,
        }
        if dialog.route_set:
            headers["Route"] = list(dialog.route_set)

        return Request(
            method=method,
            uri=_contact_uri(dialog.remote_target),
            headers=headers,
            body=None,
            transport=self._transport,
        )

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
        call_id = request.headers.get("Call-ID")
        if isinstance(call_id, str) and call_id:
            self._pending_invites[call_id] = _PendingInvite(request, remote)
        try:
            response = await self._send_request(request, remote)
        finally:
            if isinstance(call_id, str) and call_id:
                self._pending_invites.pop(call_id, None)

        if 200 <= response.status_code < 300:
            if isinstance(call_id, str) and call_id:
                try:
                    dialog = Dialog.from_invite(request, response)
                    self._dialogs[call_id] = dialog
                except Exception:
                    pass
        elif response.status_code >= 300:
            # RFC 3261 §17.1.1.3: the client transaction must ACK a non-2xx
            # final response on the same Via branch as the INVITE.
            await self._send_failure_ack(response, remote)

        return response

    async def _send_failure_ack(
        self, response: Response, remote: tuple[str, int]
    ) -> None:
        """Send ACK for a non-2xx INVITE final response (RFC 3261 §17.1.1.3).

        The ACK reuses the INVITE's Request-URI and top Via branch and carries
        the To header (with tag) from the response, per §17.1.1.3.
        """
        invite = response.request
        if invite is None or invite.method != "INVITE":
            return

        via = invite.headers.get("Via")
        from_hdr = invite.headers.get("From")
        call_id = invite.headers.get("Call-ID")
        cseq = invite.headers.get("CSeq")
        to_hdr = response.headers.get("To") or invite.headers.get("To")
        if not (
            isinstance(via, str)
            and isinstance(from_hdr, str)
            and isinstance(call_id, str)
            and isinstance(cseq, str)
        ):
            return
        if isinstance(to_hdr, list):
            to_hdr = to_hdr[0] if to_hdr else ""
        cseq_parts = extract_cseq_parts(cseq)
        cseq_num = cseq_parts[0] if cseq_parts else "1"

        headers: dict[str, str | list[str]] = {
            "Via": via,
            "From": from_hdr,
            "To": to_hdr or "",
            "Call-ID": call_id,
            "CSeq": f"{cseq_num} ACK",
            "Max-Forwards": "70",
            "User-Agent": self._config.user_agent,
        }
        ack = Request(
            method="ACK",
            uri=invite.uri,
            headers=headers,
            body=None,
            transport=self._transport,
        )
        await run_hooks(self._event_hooks, "request", ack)
        await self._transport.send(ack.to_bytes(), remote)

    async def cancel(self, call_id: str) -> Response:
        """Cancel a pending INVITE (RFC 3261 §9).

        Sends a CANCEL matching an in-flight INVITE (same Request-URI, Call-ID,
        From, To, CSeq number, and top Via branch). Must be called while an
        ``invite()`` for *call_id* is still awaiting its final response,
        typically from a concurrent task.

        Args:
            call_id: Call-ID of the pending INVITE created by ``invite()``.

        Returns:
            The SIP response to the CANCEL (typically 200 OK).

        Raises:
            ProtocolError: If no INVITE is pending for *call_id*.
            TimeoutError: If no response is received within the configured timeout.
        """
        pending = self._pending_invites.get(call_id)
        if pending is None:
            raise ProtocolError(
                f"no pending INVITE for Call-ID {call_id!r}",
                rfc_ref="RFC 3261 §9.1",
            )

        invite = pending.request
        via = invite.headers.get("Via")
        from_hdr = invite.headers.get("From")
        to_hdr = invite.headers.get("To")
        cseq = invite.headers.get("CSeq")
        if not (
            isinstance(via, str)
            and isinstance(from_hdr, str)
            and isinstance(to_hdr, str)
            and isinstance(cseq, str)
        ):
            raise ProtocolError(
                "pending INVITE is missing headers required to build CANCEL",
                rfc_ref="RFC 3261 §9.1",
            )
        cseq_parts = extract_cseq_parts(cseq)
        cseq_num = cseq_parts[0] if cseq_parts else "1"

        headers: dict[str, str | list[str]] = {
            "Via": via,
            "From": from_hdr,
            "To": to_hdr,
            "Call-ID": call_id,
            "CSeq": f"{cseq_num} CANCEL",
            "Max-Forwards": "70",
            "User-Agent": self._config.user_agent,
        }
        cancel = Request(
            method="CANCEL",
            uri=invite.uri,
            headers=headers,
            body=None,
            transport=self._transport,
        )
        return await self._send_request(cancel, pending.remote)

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

        kwargs["Content-Type"] = kwargs.get("Content-Type", "text/plain")

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
