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

from ._utils import console, logger
from ._models._auth import SipAuthCredentials, DigestCredentials, DigestAuth
from ._events import Events, EventContext
from ._fsm import StateManager
from ._models._message import Request, Response, MessageParser
from ._transports import (
    TransportAddress,
    TransportConfig,
    UDPTransport,
    TCPTransport,
    TLSTransport,
)


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
        auth: Optional[SipAuthCredentials] = None,
    ) -> None:
        """
        Initialize SIP client.

        Args:
            local_host: Local IP address to bind (default: 0.0.0.0)
            local_port: Local port to bind (default: 5060)
            transport: Transport protocol - UDP, TCP, or TLS (default: UDP)
            events: Optional Events instance for handling SIP messages
            auth: Optional authentication credentials (from Auth.Digest())
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
        self._auth = auth

        # Client state
        self._closed = False

        # Re-registration support
        self._reregister_timer: Optional[threading.Timer] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    def _create_transport(self):
        """Create transport based on protocol."""
        if self.transport_protocol == "UDP":
            return UDPTransport(self.config)
        elif self.transport_protocol == "TCP":
            return TCPTransport(self.config)
        elif self.transport_protocol == "TLS":
            return TLSTransport(self.config)
        else:
            raise ValueError(f"Unsupported transport: {self.transport_protocol}")

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
    def auth(self, credentials: Optional[SipAuthCredentials]) -> None:
        """
        Set authentication credentials.

        Example:
            >>> client.auth = Auth.Digest('alice', 'secret')
        """
        self._auth = credentials

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
        from ._models._auth import AuthParser

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

            # Log retry
            console.print(
                f"\n[bold yellow]>>> AUTH RETRY {request.method} "
                f"({self._transport.local_address} → {host}:{port}):[/bold yellow]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

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
                auth_response.raw = response_data
                auth_response.request = request
                auth_response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                console.print(
                    f"\n[bold green]<<< RECEIVED {auth_response.status_code} "
                    f"{auth_response.reason_phrase} ({source} → {self._transport.local_address}):[/bold green]"
                )
                console.print(auth_response.to_string())
                console.print("=" * 80)

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
            from ._models._auth import AuthParser

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
            host, auto_port = self._extract_host_port(uri)
            if port is None:
                port = auto_port
        elif port is None:
            port = 5060

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
        console.print(
            f"\n[bold cyan]>>> SENDING {method} ({self._transport.local_address} → {host}:{port}):[/bold cyan]"
        )
        console.print(request.to_string())
        console.print("=" * 80)

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
                response.raw = response_data
                response.request = request
                response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                console.print(
                    f"\n[bold green]<<< RECEIVED {response.status_code} {response.reason_phrase} "
                    f"({source} → {self._transport.local_address}):[/bold green]"
                )
                console.print(response.to_string())
                console.print("=" * 80)

                # Update transaction
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

            return final_response

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

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
        host = kwargs.pop("host", None)
        port = kwargs.pop("port", 5060)

        if host is None:
            host, port = self._extract_host_port(request.uri)

        # Build ACK request
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{request.headers.get('CSeq', '1').split()[0]} ACK"
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

        console.print(
            f"\n[bold cyan]>>> SENDING ACK ({self._transport.local_address} → {host}:{port}):[/bold cyan]"
        )
        console.print(ack_request.to_string())
        console.print("=" * 80)

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

        # Extract dialog info from response
        request = response.request
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = response.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")

        # Increment CSeq
        cseq_num = int(request.headers.get("CSeq", "1").split()[0]) + 1
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
        headers = kwargs.pop("headers", {})
        headers["From"] = request.headers.get("From")
        headers["To"] = request.headers.get("To")
        headers["Call-ID"] = request.headers.get("Call-ID")
        headers["CSeq"] = f"{request.headers.get('CSeq', '1').split()[0]} CANCEL"
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
    Asynchronous SIP client with simplified API.

    This client provides a clean, intuitive interface for async SIP communication:
    - Set event handlers with `client.events = MyEvents()`
    - Set authentication with `client.auth = Auth.Digest('user', 'pass')`
    - Simple method signatures: `await client.invite(to_uri, from_uri, body=sdp)`

    Example:
        >>> class MyEvents(Events):
        ...     @event_handler('INVITE', status=200)
        ...     def on_invite_ok(self, request, response, context):
        ...         print("Call accepted!")
        ...
        >>> async with AsyncClient() as client:
        ...     client.events = MyEvents()
        ...     client.auth = Auth.Digest('alice', 'secret')
        ...     response = await client.invite('sip:bob@example.com', 'sip:alice@local')
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 0,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[SipAuthCredentials] = None,
    ):
        """
        Initialize async SIP client.

        Args:
            local_host: Local IP to bind to (default: 0.0.0.0)
            local_port: Local port to bind to (default: 0 = auto-assign)
            transport: Transport protocol - UDP, TCP, or TLS
            events: Optional Events instance for handling SIP messages
            auth: Optional SipAuthCredentials for authentication
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
        self._auth = auth

        # Client state
        self._closed = False
        self._lock = asyncio.Lock()

        # Re-registration support
        self._reregister_task: Optional[asyncio.Task] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    def _create_transport(self):
        """Create transport based on protocol."""
        if self.transport_protocol == "UDP":
            return UDPTransport(self.config)
        elif self.transport_protocol == "TCP":
            return TCPTransport(self.config)
        elif self.transport_protocol == "TLS":
            return TLSTransport(self.config)
        else:
            raise ValueError(f"Unsupported transport: {self.transport_protocol}")

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
        """Set the Events instance for handling SIP messages."""
        self._events = events_instance

    @property
    def auth(self) -> Optional[SipAuthCredentials]:
        """Get the current authentication credentials."""
        return self._auth

    @auth.setter
    def auth(self, credentials: Optional[SipAuthCredentials]) -> None:
        """Set authentication credentials."""
        self._auth = credentials

    async def retry_with_auth(
        self,
        response: Response,
        auth: Optional[SipAuthCredentials] = None,
    ) -> Optional[Response]:
        """
        Retry a request with authentication (async version).

        This method allows manual control over authentication retries.
        When you receive a 401/407 response, call this method to retry
        the original request with proper authentication headers.

        Args:
            response: The 401/407 response that challenged authentication
            auth: Optional auth credentials (defaults to client.auth)

        Returns:
            New Response object, or None if retry failed

        Example:
            >>> response = await client.register(aor='sip:alice@domain.com')
            >>> if response.status_code == 401:
            ...     response = await client.retry_with_auth(response)
        """
        if not response or not response.request:
            logger.error("Cannot retry: no original request in response")
            return None

        # Use provided auth or fall back to client auth
        credentials = auth or self._auth
        if not credentials:
            logger.error("Cannot retry: no authentication credentials available")
            return None

        # Extract challenge from response
        challenge_header = (
            "WWW-Authenticate" if response.status_code == 401 else "Proxy-Authenticate"
        )
        auth_header_name = (
            "Authorization" if response.status_code == 401 else "Proxy-Authorization"
        )

        challenge = response.headers.get(challenge_header)
        if not challenge:
            logger.error(
                f"No {challenge_header} header in {response.status_code} response"
            )
            return None

        # Build auth header
        auth_header_value = self._build_auth_header(
            response.request,
            challenge,
            credentials,
        )

        if not auth_header_value:
            logger.error("Failed to build authorization header")
            return None

        # Clone original request with auth header
        original_request = response.request
        new_headers = dict(original_request.headers)
        new_headers[auth_header_name] = auth_header_value

        # Increment CSeq
        if "CSeq" in new_headers:
            cseq_parts = new_headers["CSeq"].split()
            if len(cseq_parts) >= 2:
                try:
                    cseq_num = int(cseq_parts[0])
                    new_headers["CSeq"] = f"{cseq_num + 1} {cseq_parts[1]}"
                except ValueError:
                    pass

        # Send authenticated request
        console.print(
            f"\n[bold yellow]>>> AUTH RETRY {original_request.method} ({self._transport.local_address} → {response.transport_info.get('remote', 'unknown')}):[/bold yellow]"
        )

        new_request = Request(
            method=original_request.method,
            uri=original_request.uri,
            headers=new_headers,
            body=original_request.body,
        )

        console.print(new_request.to_string())
        console.print("=" * 80)

        # Send the retry request
        return await self.request(
            method=original_request.method,
            uri=original_request.uri,
            headers=new_headers,
            body=original_request.body,
            host=response.transport_info.get("remote", "").split(":")[0]
            if response.transport_info
            else None,
        )

    def _extract_host_port(self, uri: str) -> tuple[str, int]:
        """Extract host and port from SIP URI."""
        parsed = urlparse(uri)
        host = parsed.hostname or parsed.path.split("@")[-1].split(":")[0]
        port = parsed.port or 5060
        return host, port

    def _build_auth_header(
        self, request: Request, challenge: str, credentials: SipAuthCredentials
    ) -> Optional[str]:
        """Build Authorization/Proxy-Authorization header value."""
        try:
            digest_creds = DigestCredentials(
                username=credentials.username,
                password=credentials.password,
            )
            digest_auth = DigestAuth(digest_creds)
            return digest_auth.build_authorization(request, challenge)
        except Exception as e:
            logger.error(f"Failed to build auth header: {e}")
            return None

    def _detect_auth_challenge(self, response: Response, context: EventContext):
        """Detect and store auth challenge in context."""
        if response.status_code in (401, 407):
            context.metadata["auth_challenge"] = response

    async def request(
        self,
        method: str,
        uri: str,
        headers: Optional[dict] = None,
        body: Optional[Union[str, bytes]] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs,
    ) -> Optional[Response]:
        """
        Send a SIP request (async version).

        Args:
            method: SIP method (INVITE, REGISTER, etc)
            uri: Request URI
            headers: Optional headers dict
            body: Optional message body
            host: Destination host (extracted from URI if not provided)
            port: Destination port (default 5060)

        Returns:
            Final Response object or None
        """
        async with self._lock:
            # Ensure required headers
            headers = self._ensure_required_headers(method, uri, headers or {})

            # Create request
            request = Request(method=method, uri=uri, headers=headers, body=body)

            # Determine destination
            if not host:
                host, port = self._extract_host_port(uri)
            destination = TransportAddress(host, port or 5060)

            # Create transaction
            transaction = self._state_manager.create_transaction(
                request.method, is_client=True
            )

            # Create event context
            context = EventContext(
                request=request,
                transaction=transaction,
                destination=destination,
            )

            # Call events on_request
            if self._events:
                request = self._events._call_request_handlers(request, context)

            # Log request
            console.print(
                f"\n[bold cyan]>>> SENDING {method} ({self._transport.local_address} → {destination}):[/bold cyan]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

            try:
                # Send request
                await asyncio.to_thread(
                    self._transport.send, request.to_bytes(), destination
                )

                # Receive responses
                parser = MessageParser()
                final_response = None

                while True:
                    response_data, source = await asyncio.to_thread(
                        self._transport.receive,
                        timeout=self._transport.config.read_timeout,
                    )

                    response = parser.parse(response_data)
                    response.raw = response_data
                    response.request = request
                    response.transport_info = {
                        "protocol": self.transport_protocol,
                        "local": str(self._transport.local_address),
                        "remote": str(source),
                    }

                    console.print(
                        f"\n[bold green]<<< RECEIVED {response.status_code} {response.reason_phrase} "
                        f"({source} → {self._transport.local_address}):[/bold green]"
                    )
                    console.print(response.to_string())
                    console.print("=" * 80)

                    # Update transaction
                    self._state_manager.update_transaction(transaction.id, response)

                    # Update context
                    context.response = response
                    context.source = source

                    # Detect auth challenges
                    self._detect_auth_challenge(response, context)

                    # Call events on_response
                    if self._events:
                        response = self._events._call_response_handlers(
                            response, context
                        )

                    # Check for final response
                    if response.status_code >= 200:
                        final_response = response
                        break

                return final_response

            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None

    def _ensure_required_headers(self, method: str, uri: str, headers: dict) -> dict:
        """Ensure required SIP headers are present."""
        # From
        if "From" not in headers:
            headers["From"] = (
                f"<{self._get_default_from_uri()}>;tag={uuid.uuid4().hex[:8]}"
            )

        # To
        if "To" not in headers:
            headers["To"] = f"<{uri}>"

        # Call-ID
        if "Call-ID" not in headers:
            headers["Call-ID"] = (
                f"{uuid.uuid4().hex}@{self._transport.local_address.host}"
            )

        # CSeq
        if "CSeq" not in headers:
            headers["CSeq"] = f"1 {method}"

        # Via
        if "Via" not in headers:
            branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
            headers["Via"] = (
                f"SIP/2.0/{self.transport_protocol} {self._transport.local_address.host}:"
                f"{self._transport.local_address.port};branch={branch};rport"
            )

        # Max-Forwards
        if "Max-Forwards" not in headers:
            headers["Max-Forwards"] = "70"

        # Content-Length
        if "Content-Length" not in headers:
            headers["Content-Length"] = "0"

        return headers

    async def invite(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        body: Optional[str] = None,
        **kwargs,
    ) -> Response:
        """Send INVITE request (async)."""
        if from_uri is None:
            from_uri = self._get_default_from_uri()

        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"

        if body:
            headers["Content-Type"] = kwargs.pop("content_type", "application/sdp")
            headers["Content-Length"] = str(len(body))

        return await self.request(
            "INVITE", to_uri, headers=headers, body=body, **kwargs
        )

    async def register(
        self,
        aor: str,
        registrar: Optional[str] = None,
        expires: int = 3600,
        **kwargs,
    ) -> Response:
        """Send REGISTER request (async)."""
        registrar = registrar or aor
        headers = kwargs.pop("headers", {})
        headers["Contact"] = (
            f"<sip:{self._transport.local_address.host}:{self._transport.local_address.port}>;expires={expires}"
        )
        headers["Expires"] = str(expires)
        return await self.request("REGISTER", registrar, headers=headers, **kwargs)

    async def options(self, uri: str, **kwargs) -> Response:
        """Send OPTIONS request (async)."""
        return await self.request("OPTIONS", uri, **kwargs)

    async def ack(
        self,
        to_uri: Optional[str] = None,
        from_uri: Optional[str] = None,
        response: Optional[Response] = None,
        **kwargs,
    ) -> None:
        """Send ACK request (async)."""
        if response and response.request:
            original_request = response.request
            headers = kwargs.pop("headers", {})
            headers["From"] = original_request.headers.get("From")
            headers["To"] = response.headers.get("To")
            headers["Call-ID"] = original_request.headers.get("Call-ID")
            headers["CSeq"] = original_request.headers.get("CSeq", "1 INVITE").replace(
                "INVITE", "ACK"
            )
            headers["Via"] = original_request.headers.get("Via")

            to_uri = to_uri or original_request.uri
            await self.request("ACK", to_uri, headers=headers, **kwargs)

    async def bye(
        self,
        to_uri: Optional[str] = None,
        from_uri: Optional[str] = None,
        dialog_info: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """Send BYE request (async)."""
        if from_uri is None:
            from_uri = self._get_default_from_uri()

        headers = kwargs.pop("headers", {})
        if dialog_info:
            headers["From"] = dialog_info.get("local_tag")
            headers["To"] = dialog_info.get("remote_tag")
            headers["Call-ID"] = dialog_info.get("call_id")

        return await self.request("BYE", to_uri, headers=headers, **kwargs)

    async def cancel(self, original_request: Request, **kwargs) -> Response:
        """Send CANCEL request (async)."""
        headers = kwargs.pop("headers", {})
        headers["From"] = original_request.headers.get("From")
        headers["To"] = original_request.headers.get("To")
        headers["Call-ID"] = original_request.headers.get("Call-ID")
        headers["Via"] = original_request.headers.get("Via")
        headers["CSeq"] = original_request.headers.get("CSeq", "1 INVITE").replace(
            "INVITE", "CANCEL"
        )
        return await self.request(
            "CANCEL", original_request.uri, headers=headers, **kwargs
        )

    async def message(
        self,
        to_uri: str,
        from_uri: Optional[str] = None,
        content: str = "",
        content_type: str = "text/plain",
        **kwargs,
    ) -> Response:
        """Send MESSAGE request (async)."""
        if from_uri is None:
            from_uri = self._get_default_from_uri()

        headers = kwargs.pop("headers", {})
        headers["From"] = f"<{from_uri}>;tag={uuid.uuid4().hex[:8]}"
        headers["To"] = f"<{to_uri}>"
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(content))

        return await self.request(
            "MESSAGE", to_uri, headers=headers, body=content, **kwargs
        )

    async def subscribe(self, uri: str, event: str = "presence", **kwargs) -> Response:
        """Send SUBSCRIBE request (async)."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        return await self.request("SUBSCRIBE", uri, headers=headers, **kwargs)

    async def notify(self, uri: str, event: str = "presence", **kwargs) -> Response:
        """Send NOTIFY request (async)."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        return await self.request("NOTIFY", uri, headers=headers, **kwargs)

    async def refer(self, uri: str, refer_to: str, **kwargs) -> Response:
        """Send REFER request (async)."""
        headers = kwargs.pop("headers", {})
        headers["Refer-To"] = f"<{refer_to}>"
        return await self.request("REFER", uri, headers=headers, **kwargs)

    async def info(self, uri: str, **kwargs) -> Response:
        """Send INFO request (async)."""
        return await self.request("INFO", uri, **kwargs)

    async def update(self, uri: str, **kwargs) -> Response:
        """Send UPDATE request (async)."""
        return await self.request("UPDATE", uri, **kwargs)

    async def prack(self, response: Response, **kwargs) -> Response:
        """Send PRACK request (async)."""
        if not response or not response.request:
            raise ValueError("PRACK requires a provisional response with request")

        headers = kwargs.pop("headers", {})
        rack_value = f"{response.headers.get('RSeq', '1')} {response.headers.get('CSeq', '1 INVITE')}"
        headers["RAck"] = rack_value
        return await self.request(
            "PRACK", response.request.uri, headers=headers, **kwargs
        )

    async def publish(self, uri: str, event: str = "presence", **kwargs) -> Response:
        """Send PUBLISH request (async)."""
        headers = kwargs.pop("headers", {})
        headers["Event"] = event
        return await self.request("PUBLISH", uri, headers=headers, **kwargs)

    async def close(self):
        """Close the client and cleanup resources."""
        if self._closed:
            return
        self._closed = True

        # Cancel re-registration task if active
        if self._reregister_task:
            self._reregister_task.cancel()
            try:
                await self._reregister_task
            except asyncio.CancelledError:
                pass
            self._reregister_task = None

        await asyncio.to_thread(self._transport.close)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

    @property
    def transport(self) -> str:
        """Get transport protocol."""
        return self.transport_protocol

    @property
    def local_address(self) -> TransportAddress:
        """Get local transport address."""
        return self._transport.local_address

    @property
    def is_closed(self) -> bool:
        """Check if client is closed."""
        return self._closed

    def enable_auto_reregister(
        self,
        aor: str,
        interval: int,
        callback: Optional[Callable[[Response], None]] = None,
    ) -> None:
        """
        Enable automatic re-registration (async version).

        Args:
            aor: Address of Record to register
            interval: Re-registration interval in seconds (should be < expires)
            callback: Optional callback function called after each registration

        Example:
            >>> async def on_register(response):
            ...     print(f"Re-registered: {response.status_code}")
            >>> client.enable_auto_reregister(
            ...     aor="sip:alice@domain.com",
            ...     interval=300,
            ...     callback=on_register
            ... )
        """
        self._reregister_aor = aor
        self._reregister_interval = interval
        self._reregister_callback = callback

        # Cancel existing task
        if self._reregister_task:
            self._reregister_task.cancel()

        # Start re-registration task
        self._reregister_task = asyncio.create_task(self._reregister_loop())

    def disable_auto_reregister(self) -> None:
        """Disable automatic re-registration."""
        if self._reregister_task:
            self._reregister_task.cancel()
            self._reregister_task = None
        self._reregister_aor = None
        self._reregister_interval = None
        self._reregister_callback = None

    async def _reregister_loop(self) -> None:
        """Re-registration loop (runs as background task)."""
        while not self._closed and self._reregister_aor and self._reregister_interval:
            try:
                # Wait for interval
                await asyncio.sleep(self._reregister_interval)

                # Calculate expires
                expires = self._reregister_interval + 30

                # Send REGISTER
                response = await self.register(
                    aor=self._reregister_aor, expires=expires
                )

                # Handle auth challenge
                if response and response.status_code in (401, 407):
                    response = await self.retry_with_auth(response)

                # Call callback if provided
                if self._reregister_callback and response:
                    try:
                        if asyncio.iscoroutinefunction(self._reregister_callback):
                            await self._reregister_callback(response)
                        else:
                            self._reregister_callback(response)
                    except Exception as e:
                        logger.error(f"Re-register callback error: {e}")

                if not response or response.status_code != 200:
                    logger.warning(
                        f"Re-registration failed: {response.status_code if response else 'No response'}"
                    )
                    # Retry after shorter interval on failure
                    await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Re-registration error: {e}")
                # Retry after shorter interval on error
                await asyncio.sleep(30)

    async def unregister(self, aor: str, **kwargs) -> Response:
        """
        Unregister (send REGISTER with Expires: 0).

        Args:
            aor: Address of Record to unregister
            **kwargs: Additional arguments passed to register()

        Returns:
            Response object
        """
        # Disable auto re-registration if it was set for this AOR
        if self._reregister_aor == aor:
            self.disable_auto_reregister()

        return await self.register(aor=aor, expires=0, **kwargs)

    def __repr__(self):
        return f"AsyncClient(local={self.local_address}, transport={self.transport_protocol})"
