"""Shared helpers and base class for SIP client implementations."""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from typing import Callable, Optional, Union, Any
import inspect

from .._utils import logger
from ..models._auth import (
    SipAuthCredentials,
    DigestCredentials,
    DigestAuth,
)
from .._events import Events, EventContext
from ..models._message import Request, Response, MessageParser
from ..transports import (
    TransportConfig,
    TransportAddress,
    UDPTransport,
    TCPTransport,
    TLSTransport,
)
from ..transports._udp import AsyncUDPTransport
from ..transports._tcp import AsyncTCPTransport
from ..transports._tls import AsyncTLSTransport


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------


def _create_sync_transport(protocol: str, config: TransportConfig):
    """Create a sync transport based on protocol name."""
    if protocol == "UDP":
        return UDPTransport(config)
    elif protocol == "TCP":
        return TCPTransport(config)
    elif protocol == "TLS":
        return TLSTransport(config)
    raise ValueError(f"Unsupported transport: {protocol}")


def _create_async_transport(protocol: str, config: TransportConfig):
    """Create an async transport based on protocol name."""
    if protocol == "UDP":
        return AsyncUDPTransport(config)
    elif protocol == "TCP":
        return AsyncTCPTransport(config)
    elif protocol == "TLS":
        return AsyncTLSTransport(config)
    raise ValueError(f"Unsupported transport: {protocol}")


def _extract_host_port(uri: str) -> tuple[str, int]:
    """Extract host and port from SIP URI using SipURI parser."""
    from .._uri import SipURI

    if not uri.startswith(("sip:", "sips:", "tel:")):
        uri = f"sip:{uri}"
    parsed = SipURI.parse(uri)
    return parsed.host, parsed.effective_port


def _build_auth_header(
    challenge, credentials: SipAuthCredentials, method: str, uri: str
) -> str:
    """Build Authorization header from challenge and credentials."""
    digest_credentials = DigestCredentials(
        username=credentials.username,
        password=credentials.password,
        realm=credentials.realm,
    )

    digest_auth = DigestAuth(
        credentials=digest_credentials,
        challenge=challenge,
    )

    return digest_auth.build_authorization(method=method, uri=uri)


def _get_default_from_uri(auth: SipAuthCredentials | None, host: str) -> str:
    """
    Get default FROM URI, using auth username if available.

    Returns:
        SIP URI like "sip:username@host" or "sip:user@host" if no auth.
    """
    if auth and hasattr(auth, "username"):
        username = auth.username
    else:
        username = "user"
    return f"sip:{username}@{host}"


def _ensure_required_headers(
    method: str,
    uri: str,
    headers: MutableMapping[str, str],
    local_addr,
    transport_protocol: str,
    auth: SipAuthCredentials | None,
) -> MutableMapping[str, str]:
    """Ensure all required SIP headers are present.

    Mutates and returns *headers*.
    """
    # Via
    if "Via" not in headers:
        branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
        headers["Via"] = (
            f"SIP/2.0/{transport_protocol} {local_addr.host}:{local_addr.port};"
            f"branch={branch};rport"
        )

    # From
    if "From" not in headers:
        from_uri = _get_default_from_uri(auth, local_addr.host)
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"

    # To
    if "To" not in headers:
        headers["To"] = f"<{uri}>"

    # Call-ID
    if "Call-ID" not in headers:
        headers["Call-ID"] = f"{uuid.uuid4().hex}@{local_addr.host}"

    # CSeq
    if "CSeq" not in headers:
        headers["CSeq"] = f"1 {method}"

    # Max-Forwards
    if "Max-Forwards" not in headers:
        headers["Max-Forwards"] = "70"

    # User-Agent (if auth provides it)
    if auth and auth.user_agent and "User-Agent" not in headers:
        headers["User-Agent"] = auth.user_agent

    return headers


def _detect_auth_challenge(response: Response, context: EventContext) -> None:
    """Detect and parse authentication challenges."""
    if response.status_code in (401, 407):
        from ..models._auth import AuthParser

        parser = AuthParser()
        challenge = parser.parse_from_headers(response.headers)

        if challenge:
            context.metadata["needs_auth"] = True
            context.metadata["auth_challenge"] = challenge
            logger.debug(f"Authentication challenge detected: {response.status_code}")


_FORK_WINDOW = 0.2  # seconds to wait for additional 200 OKs from forked branches


def _extract_tag(header_value: str) -> str:
    """Extract the tag parameter from a From/To header value."""
    match = re.search(r";tag=([^;,\s]+)", header_value, re.IGNORECASE)
    return match.group(1) if match else ""


class ForkTracker:
    """Collects multiple 200 OK responses from a forked INVITE (RFC 3261 S19.3).

    When a proxy forks an INVITE, the UAC may receive 200 OK from multiple
    branches (each with a different To-tag).  This tracker de-duplicates them
    by To-tag and exposes the first (``best``) plus any extras that must be
    ACK'd and BYE'd.
    """

    def __init__(self) -> None:
        self.responses: list[Response] = []

    def add(self, response: Response) -> bool:
        """Add a 200 OK.  Returns True if it carries a new To-tag."""
        to_tag = _extract_tag(response.headers.get("To", ""))
        seen = {_extract_tag(r.headers.get("To", "")) for r in self.responses}
        if to_tag not in seen:
            self.responses.append(response)
            return True
        return False

    @property
    def best(self) -> Response | None:
        """First (preferred) 200 OK, or None if none collected yet."""
        return self.responses[0] if self.responses else None

    @property
    def extra(self) -> list[Response]:
        """All 200 OKs beyond the first (forked legs to be terminated)."""
        return self.responses[1:]


def _build_forked_ack_bye(response: Response):
    """Build ACK and BYE requests for terminating a forked leg.

    Returns (ack_bytes, bye_bytes) tuple, or None if no request is attached.
    """
    request = response.request
    if not request:
        return None
    cseq_num = int((request.headers.get("CSeq") or "1 INVITE").split()[0])
    base = {
        "Via": request.headers.get("Via", ""),
        "From": request.headers.get("From", ""),
        "To": response.headers.get("To", ""),
        "Call-ID": request.headers.get("Call-ID", ""),
        "Max-Forwards": "70",
    }
    ack = Request(
        method="ACK",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num} ACK"},
    )
    bye = Request(
        method="BYE",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num + 1} BYE"},
    )
    return ack.to_bytes(), bye.to_bytes()


def _ack_and_bye_forked(transport, response: Response, destination) -> None:
    """Auto-ACK + fire-and-forget BYE for an extra forked 200 OK (sync)."""
    result = _build_forked_ack_bye(response)
    if result is None:
        return
    ack_data, bye_data = result
    transport.send(ack_data, destination)
    transport.send(bye_data, destination)
    logger.debug("Forked leg terminated (ACK+BYE): %s", response.headers.get("To"))


async def _ack_and_bye_forked_async(transport, response: Response, destination) -> None:
    """Auto-ACK + fire-and-forget BYE for an extra forked 200 OK (async)."""
    result = _build_forked_ack_bye(response)
    if result is None:
        return
    ack_data, bye_data = result
    await transport.send(ack_data, destination)
    await transport.send(bye_data, destination)
    logger.debug("Forked leg terminated (ACK+BYE): %s", response.headers.get("To"))


class DialogTracker:
    """Tracks active dialog for implicit ack/bye."""

    def __init__(self):
        self._last_invite_response: Response | None = None
        self._route_set = None

    def track(self, response: Response) -> None:
        """Track INVITE 200 OK for implicit ack/bye."""
        if (
            response.request
            and response.request.method == "INVITE"
            and response.status_code == 200
        ):
            self._last_invite_response = response
            # Store route set if present
            if "Record-Route" in response.headers:
                from .._routing import RouteSet

                self._route_set = RouteSet.from_response(response)

    @property
    def active(self) -> Response | None:
        return self._last_invite_response

    @property
    def route_set(self):
        return self._route_set

    def clear(self) -> None:
        self._last_invite_response = None
        self._route_set = None


# ---------------------------------------------------------------------------
# SIPClientBase -- shared business logic for sync and async clients
# ---------------------------------------------------------------------------


class SIPClientBase(ABC):
    """Abstract base class with shared SIP client logic.

    Subclasses must implement:
    - ``request()`` -- the core I/O loop (sync or async)
    - ``retry_with_auth()`` -- auth retry with transport I/O
    - ``close()`` / lifecycle methods
    - ``_resolve_dns()`` -- sync or async DNS resolution
    - ``enable_auto_reregister()`` / ``disable_auto_reregister()``
    """

    def __init__(
        self,
        config: TransportConfig,
        transport_protocol: str,
        transport,
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
        auto_dns: bool = True,
        fork_policy: str = "first",
    ) -> None:
        self.config = config
        self.transport_protocol = transport_protocol
        self._transport = transport
        self._state_manager = None  # Set by subclass
        self._events = events
        self._auto_auth = auto_auth
        self._closed = False
        self._dialog = DialogTracker()
        self._auto_dns = auto_dns
        self._fork_policy = fork_policy
        self._resolver = None
        self._presence_etag: Optional[str] = None  # RFC 3903 SIP-ETag

        # Convert tuple auth to SipAuthCredentials
        if isinstance(auth, tuple) and len(auth) == 2:
            self._auth: Optional[SipAuthCredentials] = SipAuthCredentials(
                username=str(auth[0]), password=str(auth[1])
            )
        elif isinstance(auth, SipAuthCredentials):
            self._auth = auth
        else:
            self._auth = None

    # --- Properties (shared) ---

    @property
    def events(self) -> Optional[Events]:
        """Get the current Events instance."""
        return self._events

    @events.setter
    def events(self, events_instance: Optional[Events]) -> None:
        """Set the Events instance for handling SIP messages."""
        self._events = events_instance

    def _get_or_create_events(self) -> Events:
        """Return the current Events instance, creating a default one if needed."""
        if self._events is None:
            self._events = Events()
        return self._events

    def on(
        self,
        method: Optional[Union[str, tuple[str, ...]]] = None,
        *,
        status: Optional[Union[int, tuple[int, ...], range]] = None,
        phase: str = "response",
        **options: Any,
    ):
        """Register a client-side request/response handler at runtime.

        Default behavior is response-phase registration, so ``@client.invite()``
        naturally handles responses for INVITE transactions. Use ``phase=`` to
        target request handlers or both phases.
        """

        def decorator(fn: Callable) -> Callable:
            self._get_or_create_events().add_handler(
                fn,
                method,
                status=status,
                phase=phase,
                **options,
            )
            return fn

        return decorator

    def handle(
        self,
        method: Optional[Union[str, tuple[str, ...]]] = None,
        *,
        status: Optional[Union[int, tuple[int, ...], range]] = None,
        phase: str = "response",
        **options: Any,
    ):
        """Alias for :meth:`on` for API symmetry with server decorators."""
        return self.on(method, status=status, phase=phase, **options)

    @staticmethod
    def _is_decorator_invocation(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        """Return True when a method call should behave as a decorator factory."""
        if args:
            return False
        if not kwargs:
            return True
        reserved = {"status", "method", "auth", "when", "name", "priority", "phase"}
        return set(kwargs).issubset(reserved)

    def invite(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("INVITE", status=status, **kwargs)
        return self._invite_request(*args, **kwargs)

    def register(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("REGISTER", status=status, **kwargs)
        return self._register_request(*args, **kwargs)

    def options(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("OPTIONS", status=status, **kwargs)
        return self._options_request(*args, **kwargs)

    def message(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("MESSAGE", status=status, **kwargs)
        return self._message_request(*args, **kwargs)

    def subscribe(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("SUBSCRIBE", status=status, **kwargs)
        return self._subscribe_request(*args, **kwargs)

    def notify(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("NOTIFY", status=status, **kwargs)
        return self._notify_request(*args, **kwargs)

    def refer(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("REFER", status=status, **kwargs)
        return self._refer_request(*args, **kwargs)

    def info(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("INFO", status=status, **kwargs)
        return self._info_request(*args, **kwargs)

    def update(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("UPDATE", status=status, **kwargs)
        return self._update_request(*args, **kwargs)

    def prack(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("PRACK", status=status, **kwargs)
        return self._prack_request(*args, **kwargs)

    def cancel(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("CANCEL", status=status, **kwargs)
        return self._cancel_request(*args, **kwargs)

    def unregister(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("REGISTER", status=status, **kwargs)
        return self._unregister_request(*args, **kwargs)

    def publish(self, *args, **kwargs):
        if self._is_decorator_invocation(args, kwargs):
            status = kwargs.pop("status", None)
            return self.on("PUBLISH", status=status, **kwargs)

        result = self._publish_request(*args, **kwargs)
        if inspect.isawaitable(result):

            async def _await_and_finalize_publish():
                response = await result
                await self._post_publish_async(response)
                return response

            return _await_and_finalize_publish()

        self._post_publish(result)
        return result

    def _prepare_request_message(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        **request_kwargs: Any,
    ) -> tuple[Request, TransportAddress, EventContext, Any]:
        """Build request, destination, transaction and context for send loop."""
        host, port = self._prepare_host_port(uri, host=host, port=port)

        request = Request(
            method=method,
            uri=uri,
            headers=headers or {},
            content=content,
            **request_kwargs,
        )

        _ensure_required_headers(
            method=request.method,
            uri=request.uri,
            headers=request.headers,
            local_addr=self._transport.local_address,
            transport_protocol=self.transport_protocol,
            auth=self._auth,
        )

        destination = TransportAddress(
            host=host,
            port=port,
            protocol=self.transport_protocol,
        )

        transaction = self._state_manager.create_transaction(request)
        context = EventContext(
            request=request,
            destination=destination,
            transaction_id=transaction.id,
            transaction=transaction,
        )

        if self._events:
            request = self._events._call_request_handlers(request, context)
            context.request = request

        return request, destination, context, transaction

    def _handle_incoming_response(
        self,
        request: Request,
        response: Response,
        source,
        context: EventContext,
    ) -> Response:
        """Apply shared response bookkeeping, events and dialog tracking."""
        response.request = request
        response.transport_info = {
            "protocol": self.transport_protocol,
            "local": str(self._transport.local_address),
            "remote": str(source),
        }
        context.response = response
        context.source = source
        _detect_auth_challenge(response, context)

        if self._events:
            response = self._events._call_response_handlers(response, context)
            context.response = response

        return response

    def _process_received_response(
        self,
        *,
        request: Request,
        response_data: bytes,
        source,
        parser: MessageParser,
        context: EventContext,
        uri: str,
    ) -> tuple[Optional[Response], Optional[Request]]:
        """Parse and enrich an incoming response for the main request loop."""
        response = parser.parse(response_data)
        if not isinstance(response, Response):
            logger.debug(
                "Skipped incoming %s, waiting for Response",
                type(response).__name__,
            )
            return None, None

        response = self._handle_incoming_response(request, response, source, context)
        self._log_incoming_response(response, source)
        prack_request = self._build_auto_prack(request, response, uri)
        return response, prack_request

    def _should_continue_waiting(
        self,
        *,
        transaction,
        fork_deadline: float | None,
        now: float,
    ) -> bool:
        """Return whether the client should keep waiting for responses."""
        if transaction.is_terminated():
            logger.debug("Transaction terminated by timer")
            return False
        if fork_deadline is not None and now >= fork_deadline:
            return False
        return True

    def _collect_response_result(
        self,
        *,
        method: str,
        response: Response,
        final_response: Optional[Response],
        fork_tracker: Optional[ForkTracker],
        fork_deadline: float | None,
        now: float,
    ) -> tuple[Optional[Response], float | None, bool]:
        """Update final response/fork tracking and signal whether to stop waiting."""
        if response.status_code >= 200:
            if (
                method == "INVITE"
                and fork_tracker is not None
                and response.status_code == 200
            ):
                fork_tracker.add(response)
                if fork_deadline is None:
                    fork_deadline = now + _FORK_WINDOW
                if now >= fork_deadline:
                    return final_response, fork_deadline, True
                return final_response, fork_deadline, False
            if fork_deadline is not None:
                return final_response, fork_deadline, True
            return response, fork_deadline, True

        if final_response is None:
            final_response = response
        return final_response, fork_deadline, False

    def _resolve_fork_final_response(
        self,
        final_response: Optional[Response],
        fork_tracker: Optional[ForkTracker],
    ) -> tuple[Optional[Response], list[Response]]:
        """Resolve winning forked response and return extra fork legs."""
        if fork_tracker is None or fork_tracker.best is None:
            return final_response, []
        return fork_tracker.best, list(fork_tracker.extra)

    def _should_auto_retry_auth(self, response: Optional[Response]) -> bool:
        """Return whether automatic auth retry should be attempted."""
        return bool(
            response is not None
            and self._auto_auth
            and self._auth
            and response.status_code in (401, 407)
        )

    def _handle_auth_retry_message(
        self,
        *,
        request: Request,
        response_data: bytes,
        source,
        parser: MessageParser,
        final_response: Optional[Response],
    ) -> tuple[Optional[Response], bool]:
        """Parse/process one auth-retry message.

        Returns ``(final_response, done)``.
        """
        response = parser.parse(response_data)
        if not isinstance(response, Response):
            return final_response, False

        response.raw = response_data
        response = self._process_auth_response(request, response, source)
        if response.status_code >= 200:
            return response, True
        if final_response is None:
            final_response = response
        return final_response, False

    def _finalize_response(self, response: Optional[Response]) -> Optional[Response]:
        """Finalize response bookkeeping shared by sync/async clients."""
        if response is not None:
            self._dialog.track(response)
        return response

    def _log_outgoing_request(
        self,
        method: str,
        uri: str,
        host: str,
        port: int,
        request: Request,
    ) -> None:
        logger.debug(
            ">>> %s %s | %s -> %s:%s | Call-ID: %s",
            method,
            uri,
            self._transport.local_address,
            host,
            port,
            request.headers.get("Call-ID", "-"),
        )
        logger.debug(request.to_string())

    def _log_incoming_response(self, response: Response, source) -> None:
        logger.debug(
            "<<< %s %s | %s -> %s | Call-ID: %s",
            response.status_code,
            response.reason_phrase,
            source,
            self._transport.local_address,
            response.headers.get("Call-ID", "-"),
        )
        logger.debug(response.to_string())

    def _build_auth_retry_request(
        self,
        response: Response,
        auth: Optional[SipAuthCredentials] = None,
    ) -> tuple[Optional[Request], Optional[TransportAddress]]:
        """Prepare a request for manual auth retry after 401/407."""
        credentials = auth or self._auth
        if not credentials:
            logger.warning("No credentials available for retry_with_auth")
            return None, None
        if response.status_code not in (401, 407):
            logger.warning(
                "retry_with_auth called on %s (expected 401/407)",
                response.status_code,
            )
            return None, None

        request = response.request
        if not request:
            logger.error("No request attached to response")
            return None, None

        from ..models._auth import AuthParser

        parser = AuthParser()
        challenge = parser.parse_from_headers(response.headers)
        if not challenge:
            logger.error("No authentication challenge found in response")
            return None, None

        host, port = _extract_host_port(request.uri)
        auth_header = _build_auth_header(
            challenge, credentials, request.method, request.uri
        )
        auth_header_name = (
            "Proxy-Authorization" if response.status_code == 407 else "Authorization"
        )
        request.headers[auth_header_name] = auth_header

        if "CSeq" in request.headers:
            cseq_parts = request.headers["CSeq"].split()
            if len(cseq_parts) == 2:
                cseq_num = int(cseq_parts[0]) + 1
                request.headers["CSeq"] = f"{cseq_num} {cseq_parts[1]}"

        if "Via" in request.headers:
            old_via = request.headers["Via"]
            new_branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
            request.headers["Via"] = re.sub(
                r"branch=z9hG4bK[^;,\s]+", f"branch={new_branch}", old_via
            )

        destination = TransportAddress(
            host=host,
            port=port,
            protocol=self.transport_protocol,
        )
        return request, destination

    def _process_auth_response(
        self,
        request: Request,
        response: Response,
        source,
    ) -> Response:
        """Shared auth retry response processing."""
        response.request = request
        response.transport_info = {
            "protocol": self.transport_protocol,
            "local": str(self._transport.local_address),
            "remote": str(source),
        }
        self._log_incoming_response(response, source)

        if self._events:
            context = EventContext(request=request, response=response, source=source)
            response = self._events._call_response_handlers(response, context)
        return response

    @property
    def auth(self) -> Optional[SipAuthCredentials]:
        """Get the current authentication credentials."""
        return self._auth

    @auth.setter
    def auth(self, credentials: Optional[Union[SipAuthCredentials, tuple]]) -> None:
        """Set authentication credentials.

        Accepts a SipAuthCredentials instance or a (username, password) tuple.
        """
        if isinstance(credentials, tuple) and len(credentials) == 2:
            self._auth = SipAuthCredentials(
                username=str(credentials[0]), password=str(credentials[1])
            )
        elif isinstance(credentials, SipAuthCredentials):
            self._auth = credentials
        else:
            self._auth = None

    @property
    def local_address(self) -> TransportAddress:
        """Get the local transport address."""
        return self._transport.local_address

    @property
    def transport(self):
        """Get the transport instance."""
        return self._transport

    @property
    def is_closed(self) -> bool:
        """Check if client is closed."""
        return self._closed

    def create_sdp(self, port: int = 0, **kwargs):
        """Create SDP using client's local address."""
        from ..models._body import SDPBody

        return SDPBody.audio(ip=self._transport.local_address.host, port=port, **kwargs)

    @staticmethod
    def _is_ip(host: str) -> bool:
        """Check if host is an IP address (not a hostname)."""
        import ipaddress

        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    # --- Shared SIP methods ---

    def _prepare_host_port(
        self,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> tuple[str, int]:
        """Extract/validate host and port for a request."""
        if host is None:
            host, extracted_port = _extract_host_port(uri)
            port = port if port is not None else extracted_port
        elif host.startswith(("sip:", "sips:")):
            host, extracted_port = _extract_host_port(host)
            port = port if port is not None else extracted_port
        else:
            port = port if port is not None else 5060
        return host, port

    def _build_invite_headers(
        self,
        to_uri: str,
        from_uri: Optional[str],
        body: Optional[str],
        reliable: bool,
        headers: dict,
    ) -> dict:
        """Build headers for an INVITE request."""
        if from_uri is None:
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        if reliable:
            headers["Require"] = "100rel"
            headers["Supported"] = "100rel"
        if body:
            headers["Content-Type"] = "application/sdp"
        return headers

    def _build_register_headers(
        self,
        aor: str,
        expires: int,
        headers: dict,
    ) -> dict:
        """Build headers for a REGISTER request. Returns (registrar, headers)."""
        headers["From"] = f"<{aor}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{aor}>"
        headers["Contact"] = (
            f"<sip:{self._transport.local_address.host}:"
            f"{self._transport.local_address.port}>;expires={expires}"
        )
        return headers

    def _build_ack(
        self,
        response: Optional[Response] = None,
        **kwargs,
    ) -> tuple[Request, TransportAddress]:
        """Build ACK request from response. Returns (ack_request, destination)."""
        if response is None:
            response = self._dialog.active
        if response is None:
            raise ValueError("No response provided and no active dialog")
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        host = kwargs.pop("host", None)
        port = kwargs.pop("port", 5060)
        if host is None:
            host, port = _extract_host_port(request.uri)
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} ACK"
        headers["Via"] = request.headers.get("Via")
        ack_request = Request(method="ACK", uri=request.uri, headers=headers)
        # Apply route set if present in dialog
        if self._dialog.route_set:
            self._dialog.route_set.apply(ack_request)
        dest = TransportAddress(host=host, port=port, protocol=self.transport_protocol)
        return ack_request, dest

    def _build_bye_headers(
        self,
        response: Optional[Response] = None,
        dialog_id: Optional[str] = None,
        **kwargs,
    ) -> tuple[str, dict]:
        """Build BYE headers from response. Returns (uri, headers)."""
        if response is None and dialog_id is None:
            response = self._dialog.active
        if response is None:
            raise ValueError("No response provided and no active dialog")
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        cseq_num = int((request.headers.get("CSeq") or "1").split()[0]) + 1
        headers["CSeq"] = f"{cseq_num} BYE"
        # Apply route set if present
        if self._dialog.route_set and not self._dialog.route_set.is_empty:
            route_value = ", ".join(f"<{r}>" for r in self._dialog.route_set.routes)
            headers["Route"] = route_value
        return request.uri, headers

    def _build_cancel_headers(
        self,
        response: Response,
        **kwargs,
    ) -> tuple[str, dict]:
        """Build CANCEL headers from response. Returns (uri, headers)."""
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = request.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} CANCEL"
        headers["Via"] = request.headers.get("Via")
        return request.uri, headers

    def _build_message_headers(
        self,
        to_uri: str,
        from_uri: Optional[str],
        content_type: str,
        headers: dict,
    ) -> dict:
        """Build MESSAGE headers."""
        if from_uri is None:
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        headers["Content-Type"] = content_type
        return headers

    def _build_prack_headers(
        self,
        response: Response,
        **kwargs,
    ) -> tuple[str, dict]:
        """Build PRACK headers from response. Returns (uri, headers)."""
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        rseq = response.headers.get("RSeq", "1")
        cseq = request.headers.get("CSeq", "1 INVITE")
        headers["RAck"] = f"{rseq} {cseq}"
        return request.uri, headers

    def _build_auto_prack(
        self,
        request: Request,
        response: Response,
        uri: str,
    ) -> Optional[Request]:
        """Build auto-PRACK for reliable provisional responses (RFC 3262).

        Returns PRACK Request or None if not needed.
        """
        if not (
            request.method == "INVITE"
            and 100 < response.status_code < 200
            and "100rel" in response.headers.get("Require", "")
        ):
            return None

        rseq = response.headers.get("RSeq", "1")
        invite_cseq = request.headers.get("CSeq", "1 INVITE")
        invite_cseq_num = int(invite_cseq.split()[0])
        prack_headers = {
            "Via": request.headers.get("Via", ""),
            "From": request.headers.get("From", ""),
            "To": response.headers.get("To", request.headers.get("To", "")),
            "Call-ID": request.headers.get("Call-ID", ""),
            "CSeq": f"{invite_cseq_num + 1} PRACK",
            "RAck": f"{rseq} {invite_cseq}",
            "Max-Forwards": "70",
        }
        return Request(method="PRACK", uri=uri, headers=prack_headers)

    def _build_auto_prack_target(
        self,
        uri: str,
        destination: TransportAddress,
    ) -> tuple[str, TransportAddress]:
        """Return target URI/destination for auto-PRACK send."""
        return uri, destination

    def _build_publish_headers(
        self,
        event: str,
        expires: int,
        etag: Optional[str],
        content: Optional[str],
        headers: dict,
    ) -> dict:
        """Build PUBLISH headers."""
        headers["Event"] = event
        headers["Expires"] = str(expires)
        if etag:
            headers["SIP-If-Match"] = etag
        if content:
            headers["Content-Type"] = "application/pidf+xml"
        return headers

    def _invite_request(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        body: Optional[str] = None,
        reliable: bool = False,
        **kwargs,
    ):
        if from_uri is None:
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )
        headers = kwargs.pop("headers", {})
        headers = self._build_invite_headers(to_uri, from_uri, body, reliable, headers)
        return self.request(
            method="INVITE",
            uri=to_uri,
            headers=headers,
            content=body,
            **kwargs,
        )

    def _register_request(
        self,
        aor: str,
        registrar: Optional[str] = None,
        expires: int = 3600,
        **kwargs,
    ):
        if registrar is None:
            registrar, _ = _extract_host_port(aor)
        headers = kwargs.pop("headers", {})
        self._build_register_headers(aor, expires, headers)
        return self.request(
            method="REGISTER",
            uri=aor,
            host=registrar,
            headers=headers,
            **kwargs,
        )

    def _options_request(self, uri: str, **kwargs):
        return self.request(method="OPTIONS", uri=uri, **kwargs)

    def _message_request(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        content: str = "",
        content_type: str = "text/plain",
        **kwargs,
    ):
        headers = kwargs.pop("headers", {})
        headers = self._build_message_headers(to_uri, from_uri, content_type, headers)
        return self.request(
            method="MESSAGE",
            uri=to_uri,
            headers=headers,
            content=content,
            **kwargs,
        )

    def _subscribe_request(
        self, uri: str, event: str = "presence", expires: int = 3600, **kwargs
    ):
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        headers["Expires"] = str(expires)
        return self.request(method="SUBSCRIBE", uri=uri, headers=headers, **kwargs)

    def _notify_request(
        self,
        uri: str,
        event: str = "presence",
        content: Optional[str] = None,
        **kwargs,
    ):
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        if content:
            headers["Content-Type"] = "application/pidf+xml"
        return self.request(
            method="NOTIFY", uri=uri, headers=headers, content=content, **kwargs
        )

    def _refer_request(self, uri: str, refer_to: str, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Refer-To"] = f"<{refer_to}>"
        return self.request(method="REFER", uri=uri, headers=headers, **kwargs)

    def _info_request(
        self,
        uri: str,
        content: Optional[str] = None,
        content_type: str = "application/dtmf-relay",
        **kwargs,
    ):
        headers = kwargs.pop("headers", {})
        if content:
            headers["Content-Type"] = content_type
        return self.request(
            method="INFO", uri=uri, headers=headers, content=content, **kwargs
        )

    def _update_request(self, uri: str, sdp_content: Optional[str] = None, **kwargs):
        headers = kwargs.pop("headers", {})
        if sdp_content:
            headers["Content-Type"] = "application/sdp"
        return self.request(
            method="UPDATE", uri=uri, headers=headers, content=sdp_content, **kwargs
        )

    def _prack_request(self, response: Response, **kwargs):
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["RAck"] = (
            f"{response.headers.get('RSeq', '1')} {request.headers.get('CSeq', '1 INVITE')}"
        )
        return self.request(method="PRACK", uri=request.uri, headers=headers, **kwargs)

    def _publish_request(
        self,
        uri: str,
        event: str = "presence",
        content: Optional[str] = None,
        expires: int = 3600,
        etag: Optional[str] = None,
        **kwargs,
    ):
        headers = kwargs.pop("headers", {})
        headers = self._build_publish_headers(event, expires, etag, content, headers)
        response = self.request(
            method="PUBLISH", uri=uri, headers=headers, content=content, **kwargs
        )
        self._post_publish(response)
        return response

    def _post_publish(self, response: Optional[Response]) -> None:
        """Post-process PUBLISH response (store SIP-ETag)."""
        if response and response.status_code == 200:
            new_etag = response.headers.get("SIP-ETag")
            if new_etag:
                self._presence_etag = new_etag

    async def _post_publish_async(self, response: Optional[Response]) -> None:
        """Async-friendly wrapper for publish post-processing."""
        self._post_publish(response)

    def _cancel_request(self, response: Response, **kwargs):
        uri, headers = self._build_cancel_headers(response, **kwargs)
        return self.request(method="CANCEL", uri=uri, headers=headers, **kwargs)

    def _unregister_request(self, aor: str, **kwargs):
        if getattr(self, "_reregister_aor", None) == aor:
            self.disable_auto_reregister()
        return self.register(aor=aor, expires=0, **kwargs)

    @abstractmethod
    def request(self, method: str, uri: str, **kwargs):
        """Send a SIP request and return its response."""
        raise NotImplementedError
