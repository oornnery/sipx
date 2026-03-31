"""
SIP Client implementation with simplified Events and Auth API.

This module provides a high-level SIP client with:
- Declarative event handling via Events class
- Simple authentication via Auth.Digest()
- Automatic transaction and dialog state management
- Multiple transport protocols (UDP, TCP, TLS)
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Optional, Union, Callable
from urllib.parse import urlparse

from ._utils import logger
from .models._auth import SipAuthCredentials, DigestCredentials, DigestAuth
from ._events import Events, EventContext
from ._fsm import StateManager, TimerManager
from .models._message import Request, Response, MessageParser
from .transports import (
    TransportAddress,
    TransportConfig,
    UDPTransport,
    TCPTransport,
    TLSTransport,
)
from .transports._udp import AsyncUDPTransport
from .transports._tcp import AsyncTCPTransport
from .transports._tls import AsyncTLSTransport


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


class Client:
    """
    Synchronous SIP client with simplified API.

    This client provides a clean, intuitive interface for SIP communication:
    - Set event handlers with `client.events = MyEvents()`
    - Set authentication with `client.auth = Auth.Digest('user', 'pass')`
    - Simple method signatures: `invite(to_uri, from_uri, body=sdp)`

    Example:
        >>> class MyEvents(Events):
        ...     @event_handler('INVITE', status=200)
        ...     def on_invite_ok(self, request, response, context):
        ...         print("Call accepted!")
        ...
        >>> with Client() as client:
        ...     client.events = MyEvents()
        ...     client.auth = Auth.Digest('alice', 'secret')
        ...     response = client.invite('sip:bob@example.com', 'sip:alice@local')
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
    ) -> None:
        """
        Initialize SIP client.

        Args:
            local_host: Local IP address to bind (default: 0.0.0.0)
            local_port: Local port to bind (default: 5060)
            transport: Transport protocol - UDP, TCP, or TLS (default: UDP)
            events: Optional Events instance for handling SIP messages
            auth: Optional authentication credentials (from Auth.Digest() or tuple)
            auto_auth: Automatically retry on 401/407 if auth is set (default: True)
        """
        # Transport configuration
        self.config = TransportConfig(
            local_host=local_host,
            local_port=local_port,
        )
        self.transport_protocol = transport.upper()

        # Initialize transport
        self._transport = self._create_transport()

        # State management (internal)
        self._state_manager = StateManager()

        # Events and Auth
        self._events = events
        self._auto_auth = auto_auth

        # Convert tuple auth to SipAuthCredentials
        if isinstance(auth, tuple) and len(auth) == 2:
            self._auth: Optional[SipAuthCredentials] = SipAuthCredentials(
                username=str(auth[0]), password=str(auth[1])
            )
        elif isinstance(auth, SipAuthCredentials):
            self._auth = auth
        else:
            self._auth = None

        # Client state
        self._closed = False

        # Re-registration support
        self._reregister_timer: Optional[threading.Timer] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    def _create_transport(self):
        """Create transport based on protocol."""
        return _create_sync_transport(self.transport_protocol, self.config)

    def _get_default_from_uri(self) -> str:
        """
        Get default FROM URI, using auth username if available.

        Returns:
            SIP URI like "sip:username@host" or "sip:user@host" if no auth.
        """
        host = self._transport.local_address.host
        if self._auth and hasattr(self._auth, "username"):
            username = self._auth.username
        else:
            username = "user"
        return f"sip:{username}@{host}"

    @property
    def events(self) -> Optional[Events]:
        """Get the current Events instance."""
        return self._events

    @events.setter
    def events(self, events_instance: Optional[Events]) -> None:
        """
        Set the Events instance for handling SIP messages.

        Example:
            >>> class MyEvents(Events):
            ...     @event_handler('INVITE', status=200)
            ...     def on_invite_ok(self, request, response, context):
            ...         print("Call accepted!")
            ...
            >>> client.events = MyEvents()
        """
        self._events = events_instance

    @property
    def auth(self) -> Optional[SipAuthCredentials]:
        """Get the current authentication credentials."""
        return self._auth

    @auth.setter
    def auth(self, credentials: Optional[Union[SipAuthCredentials, tuple]]) -> None:
        """
        Set authentication credentials.

        Accepts a SipAuthCredentials instance or a (username, password) tuple.

        Example:
            >>> client.auth = Auth.Digest('alice', 'secret')
            >>> client.auth = ('alice', 'secret')  # tuple shorthand
        """
        if isinstance(credentials, tuple) and len(credentials) == 2:
            self._auth = SipAuthCredentials(
                username=str(credentials[0]), password=str(credentials[1])
            )
        elif isinstance(credentials, SipAuthCredentials):
            self._auth = credentials
        else:
            self._auth = None

    def retry_with_auth(
        self, response: Response, auth: Optional[SipAuthCredentials] = None
    ) -> Optional[Response]:
        """
        Retry a request with authentication after receiving 401/407.

        This method allows the user to manually handle authentication challenges.
        Unlike automatic retry, this gives full control over when and how to retry.

        Args:
            response: The 401/407 response that triggered authentication
            auth: Optional credentials to use (overrides client.auth if provided)

        Returns:
            Final response after authentication, or None if auth failed

        Example:
            >>> # Using client.auth
            >>> response = client.invite('sip:bob@example.com')
            >>> if response.status_code == 401:
            ...     response = client.retry_with_auth(response)
            ...     if response.status_code == 200:
            ...         client.ack(response=response)

        Example:
            >>> # Using custom auth
            >>> response = client.invite('sip:bob@example.com')
            >>> if response.status_code == 401:
            ...     custom_auth = Auth.Digest('alice', 'secret')
            ...     response = client.retry_with_auth(response, auth=custom_auth)
        """
        # Use provided auth or fall back to client auth
        credentials = auth or self._auth

        if not credentials:
            logger.warning("No credentials available for retry_with_auth")
            return None

        if response.status_code not in (401, 407):
            logger.warning(
                f"retry_with_auth called on {response.status_code} (expected 401/407)"
            )
            return None

        # Get original request
        request = response.request
        if not request:
            logger.error("No request attached to response")
            return None

        # Parse challenge
        from .models._auth import AuthParser

        parser = AuthParser()
        challenge = parser.parse_from_headers(response.headers)

        if not challenge:
            logger.error("No authentication challenge found in response")
            return None

        # Extract host/port from original request
        host, port = self._extract_host_port(request.uri)

        try:
            # Build authorization header
            auth_header = self._build_auth_header(
                challenge, credentials, request.method, request.uri
            )

            # Determine header name
            auth_header_name = (
                "Proxy-Authorization"
                if response.status_code == 407
                else "Authorization"
            )

            # Update request with authorization
            request.headers[auth_header_name] = auth_header

            # Increment CSeq
            if "CSeq" in request.headers:
                cseq_parts = request.headers["CSeq"].split()
                if len(cseq_parts) == 2:
                    cseq_num = int(cseq_parts[0]) + 1
                    request.headers["CSeq"] = f"{cseq_num} {cseq_parts[1]}"

            # Generate new Via branch (new transaction)
            if "Via" in request.headers:
                old_via = request.headers["Via"]
                new_branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
                import re as _re

                request.headers["Via"] = _re.sub(
                    r"branch=z9hG4bK[^;,\s]+", f"branch={new_branch}", old_via
                )

            # Log retry
            logger.debug(
                ">>> AUTH RETRY %s (%s -> %s:%s)",
                request.method,
                self._transport.local_address,
                host,
                port,
            )
            logger.debug(request.to_string())

            # Send authenticated request
            destination = TransportAddress(
                host=host, port=port, protocol=self.transport_protocol
            )
            self._transport.send(request.to_bytes(), destination)

            # Receive response
            parser = MessageParser()
            final_response = None

            while True:
                response_data, source = self._transport.receive(
                    timeout=self._transport.config.read_timeout
                )

                auth_response = parser.parse(response_data)

                # Skip incoming requests (e.g. re-INVITE from server)
                if not isinstance(auth_response, Response):
                    continue

                auth_response.raw = response_data
                auth_response.request = request
                auth_response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                logger.debug(
                    "<<< RECEIVED %s %s (%s -> %s)",
                    auth_response.status_code,
                    auth_response.reason_phrase,
                    source,
                    self._transport.local_address,
                )
                logger.debug(auth_response.to_string())

                # Call events on response
                if self._events:
                    context = EventContext(
                        request=request,
                        response=auth_response,
                        source=source,
                    )
                    auth_response = self._events._call_response_handlers(
                        auth_response, context
                    )

                if auth_response.status_code >= 200:
                    final_response = auth_response
                    break

                if final_response is None:
                    final_response = auth_response

            return final_response

        except Exception as e:
            logger.error(f"Auth retry failed: {e}")
            return None

    def _extract_host_port(self, uri: str) -> tuple[str, int]:
        """Extract host and port from SIP URI."""
        if not uri.startswith("sip:") and not uri.startswith("sips:"):
            uri = f"sip:{uri}"

        parsed = urlparse(uri)
        host = parsed.hostname or parsed.path.split("@")[-1].split(":")[0]
        port = parsed.port or 5060

        return host, port

    def _build_auth_header(
        self, challenge, credentials: SipAuthCredentials, method: str, uri: str
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

    def _detect_auth_challenge(self, response: Response, context: EventContext) -> None:
        """Detect and parse authentication challenges."""
        if response.status_code in (401, 407):
            from .models._auth import AuthParser

            parser = AuthParser()
            challenge = parser.parse_from_headers(response.headers)

            if challenge:
                context.metadata["needs_auth"] = True
                context.metadata["auth_challenge"] = challenge
                logger.debug(
                    f"Authentication challenge detected: {response.status_code}"
                )

    def request(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        **kwargs,
    ) -> Response:
        """
        Send a SIP request and return the response.

        Args:
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request URI
            host: Destination host (auto-extracted from uri if not provided)
            port: Destination port (default: 5060)
            headers: Optional headers dict
            content: Optional message body
            **kwargs: Additional request parameters

        Returns:
            SIP response
        """
        # Auto-extract host/port from URI if not provided
        if host is None:
            host, extracted_port = self._extract_host_port(uri)
            port = port if port is not None else extracted_port
        else:
            port = port if port is not None else 5060

        # Build request
        request = Request(
            method=method,
            uri=uri,
            headers=headers or {},
            content=content,
            **kwargs,
        )

        # Ensure required headers
        request = self._ensure_required_headers(request, host, port)

        # Create destination
        destination = TransportAddress(
            host=host,
            port=port,
            protocol=self.transport_protocol,
        )

        # Create transaction
        transaction = self._state_manager.create_transaction(request)

        # Wire up timer manager for automatic retransmissions
        timer_manager = TimerManager()
        transaction.timer_manager = timer_manager
        transaction.transport = self.transport_protocol
        transaction._retransmit_fn = lambda: self._transport.send(
            request.to_bytes(), destination
        )

        # Create event context
        context = EventContext(
            request=request,
            destination=destination,
            transaction_id=transaction.id,
            transaction=transaction,
        )

        # Call events on_request
        if self._events:
            request = self._events._call_request_handlers(request, context)

        # Log request
        logger.debug(
            ">>> SENDING %s (%s -> %s:%s)",
            method,
            self._transport.local_address,
            host,
            port,
        )
        logger.debug(request.to_string())

        try:
            # Send request
            self._transport.send(request.to_bytes(), destination)

            # Receive responses
            parser = MessageParser()
            final_response = None

            while True:
                response_data, source = self._transport.receive(
                    timeout=self._transport.config.read_timeout
                )

                response = parser.parse(response_data)

                # Skip incoming requests (e.g. re-INVITE from server)
                if not isinstance(response, Response):
                    logger.debug(
                        f"Skipped incoming {type(response).__name__}, waiting for Response"
                    )
                    continue

                response.raw = response_data
                response.request = request
                response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                logger.debug(
                    "<<< RECEIVED %s %s (%s -> %s)",
                    response.status_code,
                    response.reason_phrase,
                    source,
                    self._transport.local_address,
                )
                logger.debug(response.to_string())

                # Update transaction (triggers state change which cancels timers)
                self._state_manager.update_transaction(transaction.id, response)

                # Update context
                context.response = response
                context.source = source

                # Detect auth challenges
                self._detect_auth_challenge(response, context)

                # Call events on_response
                if self._events:
                    response = self._events._call_response_handlers(response, context)

                # Check for final response
                if response.status_code >= 200:
                    final_response = response
                    break

                # Store provisional response
                if final_response is None:
                    final_response = response

            # Auto-retry on 401/407 if auth is set
            if (
                self._auto_auth
                and self._auth
                and final_response
                and final_response.status_code in (401, 407)
            ):
                retry_result = self.retry_with_auth(final_response)
                if retry_result:
                    final_response = retry_result

            return final_response

        except Exception as e:
            logger.error("Request failed: %s", e)
            return None
        finally:
            # Clean up all timers for this transaction
            timer_manager.cancel_all()

    def _ensure_required_headers(
        self, request: Request, host: str, port: int
    ) -> Request:
        """Ensure all required SIP headers are present."""
        headers = request.headers

        # Via
        if "Via" not in headers:
            branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
            local_addr = self._transport.local_address
            headers["Via"] = (
                f"SIP/2.0/{self.transport_protocol} {local_addr.host}:{local_addr.port};"
                f"branch={branch};rport"
            )

        # From
        if "From" not in headers:
            headers["From"] = (
                f"<{self._get_default_from_uri()}>;tag={uuid.uuid4().hex[:8]}"
            )

        # To
        if "To" not in headers:
            headers["To"] = f"<{request.uri}>"

        # Call-ID
        if "Call-ID" not in headers:
            headers["Call-ID"] = (
                f"{uuid.uuid4().hex}@{self._transport.local_address.host}"
            )

        # CSeq
        if "CSeq" not in headers:
            headers["CSeq"] = f"1 {request.method}"

        # Max-Forwards
        if "Max-Forwards" not in headers:
            headers["Max-Forwards"] = "70"

        # Content-Length
        content_length = len(request.content) if request.content else 0
        headers["Content-Length"] = str(content_length)

        # User-Agent (if auth provides it)
        if self._auth and self._auth.user_agent and "User-Agent" not in headers:
            headers["User-Agent"] = self._auth.user_agent

        return request

    def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        body: Optional[str] = None,
        **kwargs,
    ) -> Response:
        """
        Send INVITE request to establish a call.

        Args:
            to_uri: Destination URI (e.g., 'sip:bob@example.com')
            from_uri: Source URI (auto-generated if not provided)
            body: SDP body content
            **kwargs: Additional parameters (host, port, headers, etc.)

        Returns:
            SIP response

        Example:
            >>> sdp = SDPBody.offer(local_ip='192.168.1.100', local_port=8000, audio=True)
            >>> response = client.invite('sip:bob@example.com', body=sdp.to_string())
        """
        # Auto-generate from_uri if not provided
        if from_uri is None:
            from_uri = self._get_default_from_uri()

        # Build headers
        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"

        if body:
            headers["Content-Type"] = "application/sdp"

        return self.request(
            method="INVITE",
            uri=to_uri,
            headers=headers,
            content=body,
            **kwargs,
        )

    def register(
        self,
        aor: str,
        registrar: Optional[str] = None,
        expires: int = 3600,
        **kwargs,
    ) -> Response:
        """
        Send REGISTER request.

        Args:
            aor: Address of Record (e.g., 'sip:alice@example.com')
            registrar: Registrar host (auto-extracted from aor if not provided)
            expires: Registration expiry in seconds (default: 3600)
            **kwargs: Additional parameters

        Returns:
            SIP response

        Example:
            >>> response = client.register('sip:alice@example.com')
        """
        # Extract registrar from aor if not provided
        if registrar is None:
            registrar, _ = self._extract_host_port(aor)

        # Build headers
        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{aor}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{aor}>"
        headers["Contact"] = (
            f"<sip:{self._transport.local_address.host}:{self._transport.local_address.port}>;expires={expires}"
        )

        return self.request(
            method="REGISTER",
            uri=aor,
            host=registrar,
            headers=headers,
            **kwargs,
        )

    def options(
        self,
        uri: str,
        **kwargs,
    ) -> Response:
        """
        Send OPTIONS request.

        Args:
            uri: Target URI
            **kwargs: Additional parameters

        Returns:
            SIP response

        Example:
            >>> response = client.options('sip:example.com')
        """
        return self.request(method="OPTIONS", uri=uri, **kwargs)

    def ack(
        self,
        response: Response,
        **kwargs,
    ) -> None:
        """
        Send ACK for INVITE response.

        Args:
            response: The INVITE response to acknowledge
            **kwargs: Additional parameters
        """
        # Extract destination from response
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        host = kwargs.pop("host", None)
        port = kwargs.pop("port", 5060)

        if host is None:
            host, port = self._extract_host_port(request.uri)

        # Build ACK request
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} ACK"
        headers["Via"] = request.headers.get("Via")

        ack_request = Request(
            method="ACK",
            uri=request.uri,
            headers=headers,
        )

        # Send ACK (no response expected)
        destination = TransportAddress(
            host=host, port=port, protocol=self.transport_protocol
        )
        self._transport.send(ack_request.to_bytes(), destination)

        logger.debug(
            ">>> SENDING ACK (%s -> %s:%s)", self._transport.local_address, host, port
        )
        logger.debug(ack_request.to_string())

    def bye(
        self,
        response: Optional[Response] = None,
        dialog_id: Optional[str] = None,
        **kwargs,
    ) -> Response:
        """
        Send BYE request to terminate a call.

        Args:
            response: Previous INVITE response (to extract dialog info)
            dialog_id: Dialog ID (if not using response)
            **kwargs: Additional parameters

        Returns:
            SIP response

        Example:
            >>> invite_response = client.invite('sip:bob@example.com', body=sdp)
            >>> bye_response = client.bye(response=invite_response)
        """
        if response is None and dialog_id is None:
            raise ValueError("Either response or dialog_id must be provided")
        if response is None:
            raise ValueError("Response is required when dialog_id is not implemented")

        # Extract dialog info from response
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")

        # Increment CSeq
        cseq_num = int((request.headers.get("CSeq") or "1").split()[0]) + 1
        headers["CSeq"] = f"{cseq_num} BYE"

        return self.request(
            method="BYE",
            uri=request.uri,
            headers=headers,
            **kwargs,
        )

    def cancel(
        self,
        response: Response,
        **kwargs,
    ) -> Response:
        """
        Send CANCEL to cancel a pending INVITE.

        Args:
            response: Provisional response to the INVITE
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = request.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{(request.headers.get('CSeq') or '1').split()[0]} CANCEL"
        headers["Via"] = request.headers.get("Via")

        return self.request(
            method="CANCEL",
            uri=request.uri,
            headers=headers,
            **kwargs,
        )

    def message(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        content: str = "",
        content_type: str = "text/plain",
        **kwargs,
    ) -> Response:
        """
        Send MESSAGE (instant message).

        Args:
            to_uri: Destination URI
            from_uri: Source URI (auto-generated if not provided)
            content: Message content
            content_type: Content type (default: text/plain)
            **kwargs: Additional parameters

        Returns:
            SIP response

        Example:
            >>> response = client.message('sip:bob@example.com', content='Hello!')
        """
        if from_uri is None:
            from_uri = self._get_default_from_uri()

        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        headers["Content-Type"] = content_type

        return self.request(
            method="MESSAGE",
            uri=to_uri,
            headers=headers,
            content=content,
            **kwargs,
        )

    def subscribe(
        self,
        uri: str,
        event: str = "presence",
        expires: int = 3600,
        **kwargs,
    ) -> Response:
        """Send SUBSCRIBE request."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        headers["Expires"] = str(expires)

        return self.request(method="SUBSCRIBE", uri=uri, headers=headers, **kwargs)

    def notify(
        self,
        uri: str,
        event: str = "presence",
        content: Optional[str] = None,
        **kwargs,
    ) -> Response:
        """Send NOTIFY request."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event

        if content:
            headers["Content-Type"] = "application/pidf+xml"

        return self.request(
            method="NOTIFY", uri=uri, headers=headers, content=content, **kwargs
        )

    def refer(
        self,
        uri: str,
        refer_to: str,
        **kwargs,
    ) -> Response:
        """Send REFER request."""
        headers = kwargs.pop("headers", {})
        headers["Refer-To"] = f"<{refer_to}>"

        return self.request(method="REFER", uri=uri, headers=headers, **kwargs)

    def info(
        self,
        uri: str,
        content: Optional[str] = None,
        content_type: str = "application/dtmf-relay",
        **kwargs,
    ) -> Response:
        """Send INFO request."""
        headers = kwargs.pop("headers", {})

        if content:
            headers["Content-Type"] = content_type

        return self.request(
            method="INFO", uri=uri, headers=headers, content=content, **kwargs
        )

    def update(
        self,
        uri: str,
        sdp_content: Optional[str] = None,
        **kwargs,
    ) -> Response:
        """Send UPDATE request."""
        headers = kwargs.pop("headers", {})

        if sdp_content:
            headers["Content-Type"] = "application/sdp"

        return self.request(
            method="UPDATE", uri=uri, headers=headers, content=sdp_content, **kwargs
        )

    def prack(
        self,
        response: Response,
        **kwargs,
    ) -> Response:
        """Send PRACK (Provisional Response Acknowledgement)."""
        request = response.request
        if request is None:
            raise ValueError("Response has no associated request")
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")

        # RAck header
        rseq = response.headers.get("RSeq", "1")
        cseq = request.headers.get("CSeq", "1 INVITE")
        headers["RAck"] = f"{rseq} {cseq}"

        return self.request(
            method="PRACK",
            uri=request.uri,
            headers=headers,
            **kwargs,
        )

    def publish(
        self,
        uri: str,
        event: str = "presence",
        content: Optional[str] = None,
        expires: int = 3600,
        **kwargs,
    ) -> Response:
        """Send PUBLISH request."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        headers["Expires"] = str(expires)

        if content:
            headers["Content-Type"] = "application/pidf+xml"

        return self.request(
            method="PUBLISH", uri=uri, headers=headers, content=content, **kwargs
        )

    def close(self) -> None:
        """Close the transport."""
        if not self._closed:
            self._transport.close()
            self._closed = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    @property
    def transport(self):
        """Get the transport instance."""
        return self._transport

    @property
    def local_address(self):
        """Get the local transport address."""
        return self._transport.local_address

    @property
    def is_closed(self):
        """Check if client is closed."""
        return self._closed

    def enable_auto_reregister(
        self,
        aor: str,
        interval: int,
        callback: Optional[Callable[[Response], None]] = None,
    ) -> None:
        """
        Enable automatic re-registration.

        Args:
            aor: Address of Record to register
            interval: Re-registration interval in seconds (should be < expires)
            callback: Optional callback function called after each registration
                      with the Response object as argument

        Example:
            >>> def on_register(response):
            ...     print(f"Re-registered: {response.status_code}")
            >>> client.enable_auto_reregister(
            ...     aor="sip:alice@domain.com",
            ...     interval=300,  # Re-register every 5 minutes
            ...     callback=on_register
            ... )
        """
        self._reregister_aor = aor
        self._reregister_interval = interval
        self._reregister_callback = callback
        self._schedule_reregister()

    def disable_auto_reregister(self) -> None:
        """
        Disable automatic re-registration.

        Cancels any pending re-registration timer.
        """
        if self._reregister_timer:
            self._reregister_timer.cancel()
            self._reregister_timer = None
        self._reregister_aor = None
        self._reregister_interval = None
        self._reregister_callback = None

    def _schedule_reregister(self) -> None:
        """Schedule the next re-registration."""
        if not self._reregister_interval or not self._reregister_aor:
            return

        # Cancel existing timer
        if self._reregister_timer:
            self._reregister_timer.cancel()

        # Schedule new timer
        self._reregister_timer = threading.Timer(
            self._reregister_interval, self._do_reregister
        )
        self._reregister_timer.daemon = True
        self._reregister_timer.start()

    def _do_reregister(self) -> None:
        """Perform re-registration (called by timer)."""
        if self._closed or not self._reregister_aor:
            return

        try:
            # Calculate expires as interval + buffer (30 seconds)
            expires = self._reregister_interval + 30

            # Send REGISTER
            response = self.register(aor=self._reregister_aor, expires=expires)

            # Handle auth challenge
            if response and response.status_code in (401, 407):
                response = self.retry_with_auth(response)

            # Call callback if provided
            if self._reregister_callback and response:
                try:
                    self._reregister_callback(response)
                except Exception as e:
                    logger.error(f"Re-register callback error: {e}")

            # Schedule next re-registration
            if response and response.status_code == 200:
                self._schedule_reregister()
            else:
                logger.warning(
                    f"Re-registration failed: {response.status_code if response else 'No response'}"
                )
                # Retry after shorter interval on failure
                if self._reregister_interval:
                    retry_timer = threading.Timer(30, self._do_reregister)
                    retry_timer.daemon = True
                    retry_timer.start()

        except Exception as e:
            logger.error(f"Re-registration error: {e}")
            # Retry after shorter interval on error
            if self._reregister_interval:
                retry_timer = threading.Timer(30, self._do_reregister)
                retry_timer.daemon = True
                retry_timer.start()

    def unregister(self, aor: str, **kwargs) -> Response:
        """
        Unregister (send REGISTER with Expires: 0).

        Args:
            aor: Address of Record to unregister
            **kwargs: Additional arguments passed to register()

        Returns:
            Response object

        Example:
            >>> response = client.unregister(aor="sip:alice@domain.com")
            >>> if response.status_code == 200:
            ...     print("Unregistered successfully")
        """
        # Disable auto re-registration if it was set for this AOR
        if self._reregister_aor == aor:
            self.disable_auto_reregister()

        return self.register(aor=aor, expires=0, **kwargs)

    def __repr__(self):
        return (
            f"Client(local={self.local_address}, transport={self.transport_protocol})"
        )


class AsyncClient:
    """
    Asynchronous SIP client.

    Wraps the sync Client and runs all blocking I/O in a thread pool
    via ``asyncio.to_thread``. Same API as Client but with ``await``.

    Example::

        async with AsyncClient() as client:
            client.auth = ("alice", "secret")
            r = await client.register("sip:alice@pbx.com")
            r = await client.invite("sip:bob@pbx.com", body=sdp)
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 0,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
    ):
        self._sync = Client(
            local_host=local_host,
            local_port=local_port,
            transport=transport,
            events=events,
            auth=auth,
            auto_auth=auto_auth,
        )
        self._reregister_task: Optional[asyncio.Task] = None

    # --- Properties (delegate to sync client) ---

    @property
    def events(self) -> Optional[Events]:
        return self._sync.events

    @events.setter
    def events(self, v):
        self._sync.events = v

    @property
    def auth(self):
        return self._sync.auth

    @auth.setter
    def auth(self, v):
        self._sync.auth = v

    @property
    def local_address(self):
        return self._sync.local_address

    @property
    def is_closed(self):
        return self._sync.is_closed

    @property
    def transport(self):
        return self._sync.transport

    # --- Async SIP methods (delegate to sync via to_thread) ---

    async def request(self, method, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.request, method, uri, **kwargs)

    async def invite(self, to_uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.invite, to_uri, **kwargs)

    async def register(self, aor, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.register, aor, **kwargs)

    async def options(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.options, uri, **kwargs)

    async def ack(self, **kwargs) -> None:
        return await asyncio.to_thread(self._sync.ack, **kwargs)

    async def bye(self, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.bye, **kwargs)

    async def cancel(self, response, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.cancel, response, **kwargs)

    async def message(self, to_uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.message, to_uri, **kwargs)

    async def subscribe(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.subscribe, uri, **kwargs)

    async def notify(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.notify, uri, **kwargs)

    async def refer(self, uri, refer_to, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.refer, uri, refer_to, **kwargs)

    async def info(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.info, uri, **kwargs)

    async def update(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.update, uri, **kwargs)

    async def prack(self, response, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.prack, response, **kwargs)

    async def publish(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.publish, uri, **kwargs)

    async def retry_with_auth(self, response, auth=None) -> Optional[Response]:
        return await asyncio.to_thread(self._sync.retry_with_auth, response, auth)

    async def unregister(self, aor, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.unregister, aor, **kwargs)

    # --- Auto re-registration (async) ---

    def enable_auto_reregister(self, aor, interval, callback=None):
        self._sync._reregister_aor = aor
        self._sync._reregister_interval = interval
        self._sync._reregister_callback = callback
        if self._reregister_task:
            self._reregister_task.cancel()
        self._reregister_task = asyncio.create_task(self._reregister_loop())

    def disable_auto_reregister(self):
        if self._reregister_task:
            self._reregister_task.cancel()
            self._reregister_task = None
        self._sync.disable_auto_reregister()

    async def _reregister_loop(self):
        while not self._sync._closed and self._sync._reregister_aor:
            try:
                await asyncio.sleep(self._sync._reregister_interval or 300)
                r = await self.register(
                    aor=self._sync._reregister_aor,
                    expires=(self._sync._reregister_interval or 300) + 30,
                )
                if self._sync._reregister_callback and r:
                    self._sync._reregister_callback(r)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)

    # --- Lifecycle ---

    async def close(self):
        if self._reregister_task:
            self._reregister_task.cancel()
        self._sync.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __repr__(self):
        return f"AsyncClient({self._sync!r})"
