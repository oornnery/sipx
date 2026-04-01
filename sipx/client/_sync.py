"""Synchronous SIP Client implementation."""

from __future__ import annotations

import threading
import uuid
from typing import Optional, Union, Callable

from .._utils import logger
from ..models._auth import SipAuthCredentials
from .._events import Events, EventContext
from ..fsm import StateManager, TimerManager
from ..models._message import Request, Response, MessageParser
from ..transports import TransportAddress, TransportConfig
from ._base import (
    DialogTracker,
    _create_sync_transport,
    _extract_host_port,
    _build_auth_header,
    _get_default_from_uri,
    _ensure_required_headers,
    _detect_auth_challenge,
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
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
        auto_dns: bool = True,
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
            auto_dns: Automatically resolve SIP URIs via DNS SRV (default: True)
        """
        # Transport configuration
        self.config = TransportConfig(
            local_host=local_host,
            local_port=local_port,
        )
        self.transport_protocol = transport.upper()

        # Initialize transport
        self._transport = _create_sync_transport(self.transport_protocol, self.config)

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
        self._dialog = DialogTracker()
        self._auto_dns = auto_dns
        self._resolver = None

        # Re-registration support
        self._reregister_timer: Optional[threading.Timer] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Thin wrappers around standalone helpers (backward compat)
    # ------------------------------------------------------------------

    def _extract_host_port(self, uri: str) -> tuple[str, int]:
        """Extract host and port from SIP URI."""
        return _extract_host_port(uri)

    def _build_auth_header(
        self, challenge, credentials: SipAuthCredentials, method: str, uri: str
    ) -> str:
        """Build Authorization header from challenge and credentials."""
        return _build_auth_header(challenge, credentials, method, uri)

    def _get_default_from_uri(self) -> str:
        """Get default FROM URI, using auth username if available."""
        return _get_default_from_uri(self._auth, self._transport.local_address.host)

    def _ensure_required_headers(
        self, request: Request, host: str, port: int
    ) -> Request:
        """Ensure all required SIP headers are present."""
        _ensure_required_headers(
            method=request.method,
            uri=request.uri,
            headers=request.headers,
            local_addr=self._transport.local_address,
            transport_protocol=self.transport_protocol,
            auth=self._auth,
        )
        # Content-Length
        content_length = len(request.content) if request.content else 0
        request.headers["Content-Length"] = str(content_length)
        return request

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
        from ..models._auth import AuthParser

        parser = AuthParser()
        challenge = parser.parse_from_headers(response.headers)

        if not challenge:
            logger.error("No authentication challenge found in response")
            return None

        # Extract host/port from original request
        host, port = _extract_host_port(request.uri)

        try:
            # Build authorization header
            auth_header = _build_auth_header(
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

    def request(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        **kwargs,
    ) -> Optional[Response]:
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
            SIP response, or None if request timed out.
        """
        # Auto-extract host/port from URI if not provided
        if host is None:
            host, extracted_port = _extract_host_port(uri)
            port = port if port is not None else extracted_port
        elif host.startswith(("sip:", "sips:")):
            # Caller passed a full SIP URI as host (e.g. "sip:127.0.0.1:5060")
            host, extracted_port = _extract_host_port(host)
            port = port if port is not None else extracted_port
        else:
            port = port if port is not None else 5060

        # Auto DNS resolution for non-IP hostnames
        if self._auto_dns and not self._is_ip(host):
            resolved = self._resolve_dns(host)
            if resolved:
                host = resolved.host
                port = resolved.port

        # Build request
        request = Request(
            method=method,
            uri=uri,
            headers=headers or {},
            content=content,
            **kwargs,
        )

        # Ensure required headers
        _ensure_required_headers(
            method=request.method,
            uri=request.uri,
            headers=request.headers,
            local_addr=self._transport.local_address,
            transport_protocol=self.transport_protocol,
            auth=self._auth,
        )

        # Content-Length (depends on request.content which is set above)
        content_length = len(request.content) if request.content else 0
        request.headers["Content-Length"] = str(content_length)

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

        # Trigger initial state timers (Timer A/E for retransmission)
        transaction._on_state_change(transaction.state, transaction.state)

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
            ">>> %s %s | %s -> %s:%s | Call-ID: %s",
            method,
            uri,
            self._transport.local_address,
            host,
            port,
            request.headers.get("Call-ID", "-"),
        )
        logger.debug(request.to_string())

        try:
            import time as _time

            # Send request
            self._transport.send(request.to_bytes(), destination)

            # Receive responses with short timeout polling.
            # This allows FSM timers (Timer A/E) to retransmit in background
            # while we wait for a response. Total deadline = Timer B/F (32s).
            parser = MessageParser()
            final_response = None
            deadline = _time.monotonic() + self._transport.config.read_timeout
            poll_interval = 0.1  # 100ms -- responsive to Ctrl+C and FSM timers

            while _time.monotonic() < deadline:
                try:
                    response_data, source = self._transport.receive(
                        timeout=poll_interval
                    )
                except Exception:
                    # Timeout on this poll -- loop again (timers retransmit in background)
                    if transaction.is_terminated():
                        logger.debug("Transaction terminated by timer")
                        break
                    continue

                response = parser.parse(response_data)

                # Skip incoming requests (e.g. re-INVITE from server)
                if not isinstance(response, Response):
                    logger.debug(
                        "Skipped incoming %s, waiting for Response",
                        type(response).__name__,
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
                    "<<< %s %s | %s -> %s | Call-ID: %s",
                    response.status_code,
                    response.reason_phrase,
                    source,
                    self._transport.local_address,
                    response.headers.get("Call-ID", "-"),
                )
                logger.debug(response.to_string())

                # Update transaction (triggers state change, cancels retransmit timers)
                self._state_manager.update_transaction(transaction.id, response)

                # Update context
                context.response = response
                context.source = source

                # Detect auth challenges
                _detect_auth_challenge(response, context)

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

            if final_response is None:
                logger.warning(
                    "Request timed out after %.0fs",
                    self._transport.config.read_timeout,
                )
                return None

            # Auto-retry on 401/407 if auth is set
            if (
                self._auto_auth
                and self._auth
                and final_response.status_code in (401, 407)
            ):
                retry_result = self.retry_with_auth(final_response)
                if retry_result:
                    final_response = retry_result

            # Track dialog state for implicit ack/bye
            self._dialog.track(final_response)

            return final_response

        except Exception:
            raise
        finally:
            # Clean up all timers for this transaction
            timer_manager.cancel_all()

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
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )

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
            registrar, _ = _extract_host_port(aor)

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
        response: Optional[Response] = None,
        **kwargs,
    ) -> None:
        """
        Send ACK for INVITE response.

        Args:
            response: The INVITE response to acknowledge (uses tracked dialog if omitted)
            **kwargs: Additional parameters
        """
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

        # Apply route set if present in dialog
        if self._dialog.route_set:
            self._dialog.route_set.apply(ack_request)

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
            response = self._dialog.active
        if response is None:
            raise ValueError("No response provided and no active dialog")

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

        # Apply route set if present
        if self._dialog.route_set and not self._dialog.route_set.is_empty:
            route_value = ", ".join(f"<{r}>" for r in self._dialog.route_set.routes)
            headers["Route"] = route_value

        result = self.request(
            method="BYE",
            uri=request.uri,
            headers=headers,
            **kwargs,
        )

        # Clear dialog after BYE
        self._dialog.clear()

        return result

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
            from_uri = _get_default_from_uri(
                self._auth, self._transport.local_address.host
            )

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

    def create_sdp(self, port: int = 0, **kwargs):
        """Create SDP using client's local address.

        Returns:
            SDPBody configured with the client's local IP.
        """
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

    def _resolve_dns(self, host: str):
        """Resolve hostname via SIP DNS SRV (lazy init)."""
        if self._resolver is None:
            from ..dns._sync import SipResolver

            self._resolver = SipResolver()
        targets = self._resolver.resolve(host, self.transport_protocol)
        return targets[0] if targets else None

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
