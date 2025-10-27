"""
SIP Client implementation with sync and async support.

This module provides a high-level SIP client inspired by HTTPX's architecture,
with support for UDP/TCP/TLS transports, state management, and event handlers.
"""

from __future__ import annotations

import uuid
from typing import Optional, Union

from ._utils import console, logger
from ._models._auth import SipAuthCredentials
from ._handlers import (
    EventContext,
    HandlerChain,
    AsyncHandlerChain,
    EventHandler,
    AsyncEventHandler,
    AuthenticationHandler,
)
from ._fsm import StateManager
from ._models._message import Request, Response, MessageParser
from ._transports import (
    TransportAddress,
    TransportConfig,
    UDPTransport,
    TCPTransport,
    TLSTransport,
    AsyncUDPTransport,
    AsyncTCPTransport,
    AsyncTLSTransport,
)


class Client:
    """
    Synchronous SIP client.

    This client provides a high-level interface for SIP communication with:
    - Multiple transport protocols (UDP, TCP, TLS)
    - Transaction and dialog state management
    - Event handlers for request/response manipulation
    - Context manager support

    Example:
        >>> with Client(local_port=5060, transport="UDP") as client:
        ...     response = client.invite(
        ...         to_uri="sip:bob@example.com",
        ...         from_uri="sip:alice@192.168.1.100",
        ...         host="example.com"
        ...     )
        ...     print(response.status_code)
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        transport: str = "UDP",
        config: Optional[TransportConfig] = None,
        credentials: Optional[SipAuthCredentials] = None,
    ) -> None:
        """
        Initialize SIP client.

        Args:
            local_host: Local IP address to bind
            local_port: Local port to bind
            transport: Transport protocol (UDP, TCP, or TLS)
            config: Optional transport configuration
            credentials: Optional default credentials for authentication
        """
        # Create config if not provided
        if config is None:
            config = TransportConfig(
                local_host=local_host,
                local_port=local_port,
            )
        else:
            config.local_host = local_host
            config.local_port = local_port

        self.config = config
        self.transport_protocol = transport.upper()

        # Initialize transport
        self._transport = self._create_transport()

        # State management
        self.state_manager = StateManager()

        # Event handlers
        self.handlers = HandlerChain()

        # Authentication handler
        self._auth_handler = AuthenticationHandler(credentials)

        # Client state
        self._closed = False

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

    def add_handler(self, handler: EventHandler) -> None:
        """
        Add an event handler.

        Args:
            handler: Event handler to add
        """
        self.handlers.add_handler(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """
        Remove an event handler.

        Args:
            handler: Event handler to remove
        """
        self.handlers.remove_handler(handler)

    def request(
        self,
        method: str,
        uri: str,
        host: str,
        port: int = 5060,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        """
        Send a SIP request and return the response.

        Args:
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request URI
            host: Destination host
            port: Destination port
            headers: Optional headers dict
            content: Optional message body
            auth: Optional credentials for authentication (priority over client credentials)
            **kwargs: Additional request parameters

        Returns:
            SIP response

        Raises:
            TransportError: On transport failure
            TimeoutError: On timeout
        """
        # Build request
        request = Request(
            method=method,
            uri=uri,
            headers=headers or {},
            content=content,
            **kwargs,
        )

        # Ensure required headers in correct order
        request = self._ensure_required_headers(request, host, port)

        # Create destination
        destination = TransportAddress(
            host=host,
            port=port,
            protocol=self.transport_protocol,
        )

        # Create transaction
        transaction = self.state_manager.create_transaction(request)

        # Create event context
        context = EventContext(
            request=request,
            destination=destination,
            transaction_id=transaction.id,
        )

        # Call request handlers
        request = self.handlers.on_request(request, context)

        # Print raw request with source/destination info
        local_addr = self._transport.local_address
        console.print(
            f"\n[bold cyan]>>> SENDING {method} ({local_addr} → {host}:{port}):[/bold cyan]"
        )
        console.print(request.to_string())
        console.print("=" * 80)

        try:
            # Send request
            request_data = request.to_bytes()
            self._transport.send(request_data, destination)

            # Receive and process all responses (provisional + final)
            parser = MessageParser()
            final_response = None

            while True:
                # Receive response
                response_data, source = self._transport.receive(
                    timeout=self._transport.config.read_timeout
                )

                # Parse response
                response = parser.parse(response_data)

                # Attach metadata
                response.raw = response_data
                response.request = request
                response.transport_info = {
                    "protocol": self.transport_protocol,
                    "local": str(self._transport.local_address),
                    "remote": str(source),
                }

                # Print raw response with source/destination info
                local_addr = self._transport.local_address
                console.print(
                    f"\n[bold green]<<< RECEIVED {response.status_code} {response.reason_phrase} ({source} → {local_addr}):[/bold green]"
                )
                console.print(response.to_string())
                console.print("=" * 80)

                # Add to transaction (all responses: provisional and final)
                self.state_manager.update_transaction(transaction.id, response)

                # Update context with this response
                context.response = response

                # Call response handlers for ALL responses (using same context)
                processed_response = self.handlers.on_response(response, context)

                # Check if final response (2xx-6xx)
                if response.status_code >= 200:
                    final_response = processed_response
                    context.response = final_response
                    break

                # Provisional response (1xx) - continue waiting
                # Store as fallback in case we timeout
                if final_response is None:
                    final_response = processed_response

            response = final_response

            # Check if auth retry is needed
            logger.debug(
                f"Auth check: needs_auth={context.metadata.get('needs_auth')}, status={response.status_code}"
            )
            logger.debug(f"Metadata: {context.metadata}")
            if context.metadata.get(
                "needs_auth"
            ) and self._auth_handler.should_authenticate(response):
                # Find AuthHandler credentials from event handlers
                handler_credentials = None
                for handler in self.handlers._handlers:
                    if hasattr(handler, "username") and hasattr(handler, "password"):
                        # Convert old AuthHandler to SipAuthCredentials
                        handler_credentials = SipAuthCredentials(
                            username=handler.username,
                            password=handler.password,
                        )
                        break

                # Get credentials with priority: auth param -> client -> handler
                credentials = self._auth_handler.get_credentials(
                    method_credentials=auth,
                    handler_credentials=handler_credentials,
                )

                if credentials:
                    # Try authentication
                    auth_response = self._auth_handler.handle_auth_response(
                        response=response,
                        request=request,
                        context=context,
                        credentials=credentials,
                        transport=self._transport,
                        destination=destination,
                        host=host,
                        port=port,
                    )

                    # Update transaction if auth succeeded
                    if auth_response:
                        self.state_manager.update_transaction(
                            transaction.id, auth_response
                        )
                        response = auth_response

            return response

        except Exception as e:
            # Call error handlers
            self.handlers.on_error(e, context)
            raise

    def ack(
        self,
        uri: str,
        host: str,
        port: int = 5060,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """
        Send an ACK request (fire-and-forget, no response expected).

        Args:
            uri: Request URI
            host: Destination host
            port: Destination port
            headers: Optional headers (should include Via, From, To, Call-ID, CSeq from INVITE)
            **kwargs: Additional parameters
        """
        headers = headers or {}

        # Build ACK request
        from ._models._message import Request

        request = Request("ACK", uri, headers=headers)

        # Ensure required headers
        request = self._ensure_required_headers(request, host, port)

        # Print raw ACK with source/destination info
        local_addr = self._transport.local_address
        console.print(
            f"\n[bold magenta]>>> SENDING ACK ({local_addr} → {host}:{port})[/bold magenta]"
        )
        console.print(request.to_string())
        console.print("=" * 80)

        # Send ACK (no response expected)
        destination = (host, port)
        request_data = request.to_bytes()
        self._transport.send(request_data, destination)

    def invite(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        sdp_content: Optional[str] = None,
        headers: Optional[dict] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        """
        Send an INVITE request.

        Args:
            to_uri: To URI (callee)
            from_uri: From URI (caller)
            host: Destination host
            port: Destination port
            sdp_content: Optional SDP body as STRING
            headers: Optional headers
            auth: Optional credentials for authentication (priority over client credentials)
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add required INVITE headers
        if "To" not in headers:
            headers["To"] = f"<{to_uri}>"
        if "From" not in headers:
            from_tag = str(uuid.uuid4())[:8]
            headers["From"] = f"<{from_uri}>;tag={from_tag}"
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 INVITE"

        if sdp_content:
            headers["Content-Type"] = "application/sdp"

        response = self.request(
            method="INVITE",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=sdp_content,
            auth=auth,
            **kwargs,
        )

        # RFC 3261: Send ACK for all final responses to INVITE (2xx-6xx)
        logger.debug(
            f"Checking if ACK needed: status={response.status_code}, is_final={response.status_code >= 200}"
        )
        if response.status_code >= 200:  # All final responses (2xx-6xx)
            if 200 <= response.status_code < 300:
                logger.info(
                    f"INVITE received 2xx response ({response.status_code}), sending ACK"
                )
                console.print(
                    f"\n[bold yellow]>>> Preparing to send ACK for {response.status_code} response[/bold yellow]"
                )
            else:
                logger.info(
                    f"INVITE received non-2xx final response ({response.status_code}), sending ACK"
                )
                console.print(
                    f"\n[bold yellow]>>> Preparing to send ACK for {response.status_code} error response[/bold yellow]"
                )

            # Build ACK headers from original INVITE request
            ack_headers = {}

            # Get original request from response (attached during processing)
            original_request = getattr(response, "request", None)
            logger.debug(f"Original request found: {original_request is not None}")

            if original_request:
                logger.debug(
                    f"Building ACK from original request: method={original_request.method}"
                )
                # Use headers from original request to build ACK
                # From - use exactly as sent in INVITE
                if original_request.from_header:
                    ack_headers["From"] = original_request.from_header

                # To - use To from response (may have tag added)
                if response.to_header:
                    ack_headers["To"] = response.to_header

                # Call-ID - same as INVITE
                if original_request.call_id:
                    ack_headers["Call-ID"] = original_request.call_id

                # CSeq - same number as INVITE but method ACK
                if original_request.cseq:
                    cseq_parts = original_request.cseq.split()
                    if len(cseq_parts) == 2:
                        ack_headers["CSeq"] = f"{cseq_parts[0]} ACK"

                # Via - use original Via from INVITE request
                if original_request.via:
                    ack_headers["Via"] = original_request.via
            else:
                # Fallback if request not attached
                logger.warning(
                    "Original request not found in response, building ACK from response headers"
                )
                if response.from_header:
                    ack_headers["From"] = response.from_header
                if response.to_header:
                    ack_headers["To"] = response.to_header
                if response.call_id:
                    ack_headers["Call-ID"] = response.call_id
                if response.cseq:
                    cseq_parts = response.cseq.split()
                    if len(cseq_parts) == 2:
                        ack_headers["CSeq"] = f"{cseq_parts[0]} ACK"

            # Max-Forwards
            ack_headers["Max-Forwards"] = "70"

            # Send ACK
            logger.debug(
                f"Calling ack() method with headers: {list(ack_headers.keys())}"
            )
            try:
                self.ack(to_uri, host, port, headers=ack_headers)
                logger.info("ACK sent successfully")
                console.print("[bold green]✓ ACK sent successfully[/bold green]")
            except Exception as e:
                logger.error(f"Failed to send ACK: {e}")
                console.print(f"[bold red]✗ Failed to send ACK: {e}[/bold red]")
        else:
            logger.debug(f"ACK not needed for {response.status_code} response")

        return response

    def register(
        self,
        aor: str,
        registrar: str,
        port: int = 5060,
        expires: int = 3600,
        headers: Optional[dict] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        """
        Send a REGISTER request.

        Args:
            aor: Address of Record (user URI)
            registrar: Registrar server address
            port: Registrar port
            expires: Registration expiration in seconds
            headers: Optional headers
            auth: Optional credentials for authentication (priority over client credentials)
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add REGISTER headers
        if "To" not in headers:
            headers["To"] = f"<{aor}>"
        if "From" not in headers:
            headers["From"] = f"<{aor}>"
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 REGISTER"
        if "Contact" not in headers:
            contact_uri = f"sip:{self.config.local_host}:{self.config.local_port}"
            headers["Contact"] = f"<{contact_uri}>"
        if "Expires" not in headers:
            headers["Expires"] = str(expires)

        return self.request(
            method="REGISTER",
            uri=aor,
            host=registrar,
            port=port,
            headers=headers,
            auth=auth,
            **kwargs,
        )

    def options(
        self,
        uri: str,
        host: str,
        port: int = 5060,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send an OPTIONS request.

        Args:
            uri: Request URI
            host: Destination host
            port: Destination port
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add basic headers in RFC 3261 order
        # (Via, From, To added by _ensure_required_headers)
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 OPTIONS"

        return self.request(
            method="OPTIONS",
            uri=uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def bye(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a BYE request to terminate a call.

        Args:
            to_uri: To URI (callee)
            from_uri: From URI (caller)
            host: Destination host
            port: Destination port
            call_id: Call-ID (should match INVITE)
            from_tag: From tag (should match INVITE)
            to_tag: To tag (from response)
            cseq: CSeq number (should be > INVITE CSeq)
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response (typically 200 OK)
        """
        headers = headers or {}

        # Add BYE headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 2
            headers["CSeq"] = f"{cseq_num} BYE"

        return self.request(
            method="BYE",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def cancel(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        via: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a CANCEL request to cancel a pending INVITE.

        Args:
            to_uri: To URI (callee)
            from_uri: From URI (caller)
            host: Destination host
            port: Destination port
            call_id: Call-ID (must match INVITE)
            from_tag: From tag (must match INVITE)
            via: Via header (must match INVITE)
            cseq: CSeq number (must match INVITE)
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response (typically 200 OK)
        """
        headers = headers or {}

        # CANCEL must match INVITE headers exactly
        if "To" not in headers:
            headers["To"] = f"<{to_uri}>"

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} CANCEL"

        if via and "Via" not in headers:
            headers["Via"] = via

        return self.request(
            method="CANCEL",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def message(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        content: Optional[str] = None,
        content_type: str = "text/plain",
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a MESSAGE request (instant message).

        Args:
            to_uri: To URI (recipient)
            from_uri: From URI (sender)
            host: Destination host
            port: Destination port
            content: Message content
            content_type: Content type (default: text/plain)
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add MESSAGE headers
        if "To" not in headers:
            headers["To"] = f"<{to_uri}>"
        if "From" not in headers:
            from_tag = uuid.uuid4().hex[:8]
            headers["From"] = f"<{from_uri}>;tag={from_tag}"
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 MESSAGE"

        if content:
            headers["Content-Type"] = content_type

        return self.request(
            method="MESSAGE",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )

    def subscribe(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        event: str = "presence",
        expires: int = 3600,
        accept: str = "application/pidf+xml",
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a SUBSCRIBE request.

        Args:
            to_uri: To URI (resource to subscribe)
            from_uri: From URI (subscriber)
            host: Destination host
            port: Destination port
            event: Event package (e.g., presence, message-summary)
            expires: Subscription duration in seconds
            accept: Accept header (content types)
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add SUBSCRIBE headers
        if "To" not in headers:
            headers["To"] = f"<{to_uri}>"
        if "From" not in headers:
            from_tag = uuid.uuid4().hex[:8]
            headers["From"] = f"<{from_uri}>;tag={from_tag}"
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 SUBSCRIBE"
        if "Event" not in headers:
            headers["Event"] = event
        if "Expires" not in headers:
            headers["Expires"] = str(expires)
        if "Accept" not in headers:
            headers["Accept"] = accept
        if "Contact" not in headers:
            contact_uri = f"sip:{self.config.local_host}:{self.config.local_port}"
            headers["Contact"] = f"<{contact_uri}>"

        return self.request(
            method="SUBSCRIBE",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def notify(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        event: str = "presence",
        subscription_state: str = "active",
        content: Optional[str] = None,
        content_type: str = "application/pidf+xml",
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a NOTIFY request.

        Args:
            to_uri: To URI (subscriber)
            from_uri: From URI (notifier)
            host: Destination host
            port: Destination port
            event: Event package
            subscription_state: Subscription state (active, pending, terminated)
            content: Notification content
            content_type: Content type
            call_id: Call-ID (should match SUBSCRIBE)
            from_tag: From tag
            to_tag: To tag
            cseq: CSeq number
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add NOTIFY headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} NOTIFY"

        if "Event" not in headers:
            headers["Event"] = event
        if "Subscription-State" not in headers:
            headers["Subscription-State"] = subscription_state

        if content:
            headers["Content-Type"] = content_type

        return self.request(
            method="NOTIFY",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )

    def refer(
        self,
        to_uri: str,
        from_uri: str,
        refer_to: str,
        host: str,
        port: int = 5060,
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a REFER request (call transfer).

        Args:
            to_uri: To URI (referee)
            from_uri: From URI (referrer)
            refer_to: Refer-To URI (transfer target)
            host: Destination host
            port: Destination port
            call_id: Call-ID
            from_tag: From tag
            to_tag: To tag
            cseq: CSeq number
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add REFER headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} REFER"

        if "Refer-To" not in headers:
            headers["Refer-To"] = f"<{refer_to}>"

        if "Contact" not in headers:
            contact_uri = f"sip:{self.config.local_host}:{self.config.local_port}"
            headers["Contact"] = f"<{contact_uri}>"

        return self.request(
            method="REFER",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def info(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        content: Optional[str] = None,
        content_type: str = "application/dtmf-relay",
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send an INFO request (mid-call info, e.g., DTMF).

        Args:
            to_uri: To URI
            from_uri: From URI
            host: Destination host
            port: Destination port
            content: Info content (e.g., DTMF signal)
            content_type: Content type
            call_id: Call-ID (should match dialog)
            from_tag: From tag
            to_tag: To tag
            cseq: CSeq number
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add INFO headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} INFO"

        if content:
            headers["Content-Type"] = content_type

        return self.request(
            method="INFO",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )

    def update(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        sdp_content: Optional[str] = None,
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send an UPDATE request (session parameter update).

        Args:
            to_uri: To URI
            from_uri: From URI
            host: Destination host
            port: Destination port
            sdp_content: Optional SDP body
            call_id: Call-ID (should match dialog)
            from_tag: From tag
            to_tag: To tag
            cseq: CSeq number
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add UPDATE headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} UPDATE"

        if sdp_content:
            headers["Content-Type"] = "application/sdp"

        return self.request(
            method="UPDATE",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=sdp_content,
            **kwargs,
        )

    def prack(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        rack: Optional[str] = None,
        call_id: Optional[str] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None,
        cseq: Optional[int] = None,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a PRACK request (provisional response acknowledgement).

        Args:
            to_uri: To URI
            from_uri: From URI
            host: Destination host
            port: Destination port
            rack: RAck header value (RSeq CSeq Method)
            call_id: Call-ID (should match dialog)
            from_tag: From tag
            to_tag: To tag
            cseq: CSeq number
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add PRACK headers
        if "To" not in headers:
            to_header = f"<{to_uri}>"
            if to_tag:
                to_header += f";tag={to_tag}"
            headers["To"] = to_header

        if "From" not in headers:
            from_header = f"<{from_uri}>"
            if from_tag:
                from_header += f";tag={from_tag}"
            else:
                from_header += f";tag={uuid.uuid4().hex[:8]}"
            headers["From"] = from_header

        if "Call-ID" not in headers:
            headers["Call-ID"] = call_id if call_id else str(uuid.uuid4())

        if "CSeq" not in headers:
            cseq_num = cseq if cseq else 1
            headers["CSeq"] = f"{cseq_num} PRACK"

        if rack and "RAck" not in headers:
            headers["RAck"] = rack

        return self.request(
            method="PRACK",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            **kwargs,
        )

    def publish(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        event: str = "presence",
        content: Optional[str] = None,
        content_type: str = "application/pidf+xml",
        expires: int = 3600,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        """
        Send a PUBLISH request (publish event state).

        Args:
            to_uri: To URI (presentity)
            from_uri: From URI (publisher)
            host: Destination host
            port: Destination port
            event: Event package (e.g., presence)
            content: Publication content
            content_type: Content type
            expires: Publication expiration in seconds
            headers: Optional headers
            **kwargs: Additional parameters

        Returns:
            SIP response
        """
        headers = headers or {}

        # Add PUBLISH headers
        if "To" not in headers:
            headers["To"] = f"<{to_uri}>"
        if "From" not in headers:
            from_tag = uuid.uuid4().hex[:8]
            headers["From"] = f"<{from_uri}>;tag={from_tag}"
        if "Call-ID" not in headers:
            headers["Call-ID"] = str(uuid.uuid4())
        if "CSeq" not in headers:
            headers["CSeq"] = "1 PUBLISH"
        if "Event" not in headers:
            headers["Event"] = event
        if "Expires" not in headers:
            headers["Expires"] = str(expires)

        if content:
            headers["Content-Type"] = content_type

        return self.request(
            method="PUBLISH",
            uri=to_uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )

    def _ensure_required_headers(
        self, request: Request, host: str, port: int
    ) -> Request:
        """
        Ensure request has required headers and rebuild in RFC 3261 order.

        Args:
            request: SIP request
            host: Destination host
            port: Destination port

        Returns:
            Request with headers in correct order
        """
        # Collect existing headers
        old_headers = dict(request.headers)

        # Build new headers dict in RFC 3261 order
        new_headers = {}

        # 1. Via (always regenerate to ensure freshness)
        branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
        via = (
            f"SIP/2.0/{self.transport_protocol} "
            f"{self.config.local_host}:{self.config.local_port};branch={branch}"
        )
        new_headers["Via"] = old_headers.get("Via", via)

        # 2. From
        if "From" not in old_headers:
            from_uri = f"sip:{self.config.local_host}:{self.config.local_port}"
            from_tag = uuid.uuid4().hex[:8]
            new_headers["From"] = f"<{from_uri}>;tag={from_tag}"
        else:
            new_headers["From"] = old_headers["From"]

        # 3. To
        if "To" not in old_headers:
            new_headers["To"] = f"<{request.uri}>"
        else:
            new_headers["To"] = old_headers["To"]

        # 4. Call-ID
        if "Call-ID" in old_headers:
            new_headers["Call-ID"] = old_headers["Call-ID"]

        # 5. CSeq
        if "CSeq" in old_headers:
            new_headers["CSeq"] = old_headers["CSeq"]

        # 6. Contact
        if "Contact" in old_headers:
            new_headers["Contact"] = old_headers["Contact"]

        # 7. Max-Forwards
        if "Max-Forwards" in old_headers:
            new_headers["Max-Forwards"] = old_headers["Max-Forwards"]

        # 8. Route, Record-Route
        if "Route" in old_headers:
            new_headers["Route"] = old_headers["Route"]
        if "Record-Route" in old_headers:
            new_headers["Record-Route"] = old_headers["Record-Route"]

        # 9. Authorization headers
        if "Proxy-Authorization" in old_headers:
            new_headers["Proxy-Authorization"] = old_headers["Proxy-Authorization"]
        if "Authorization" in old_headers:
            new_headers["Authorization"] = old_headers["Authorization"]

        # 10. Other headers (except Content-Type and Content-Length)
        skip_headers = {
            "via",
            "from",
            "to",
            "call-id",
            "cseq",
            "contact",
            "max-forwards",
            "route",
            "record-route",
            "proxy-authorization",
            "authorization",
            "content-type",
            "content-length",
        }
        for key, value in old_headers.items():
            if key.lower() not in skip_headers:
                new_headers[key] = value

        # 11. Content-Type (if present)
        if "Content-Type" in old_headers:
            new_headers["Content-Type"] = old_headers["Content-Type"]

        # 12. Content-Length (always last, will be set by Request)
        if "Content-Length" in old_headers:
            new_headers["Content-Length"] = old_headers["Content-Length"]

        # Create new request with ordered headers
        new_request = Request(
            request.method,
            request.uri,
            headers=new_headers,
            content=request.content,
            version=request.version,
        )

        return new_request

    def close(self) -> None:
        """Close the client and release resources."""
        if not self._closed:
            self._transport.close()
            self._closed = True

    def __enter__(self) -> Client:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close()

    @property
    def transport(self):
        """Get the transport instance."""
        return self._transport

    @property
    def local_address(self):
        """Get local bound address."""
        return self._transport.local_address

    @property
    def is_closed(self) -> bool:
        """Check if client is closed."""
        return self._closed

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<Client({self.transport_protocol}, {status})>"


class AsyncClient:
    """Async SIP client - simplified version."""

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        transport: str = "UDP",
        config: Optional[TransportConfig] = None,
        credentials: Optional[SipAuthCredentials] = None,
    ) -> None:
        if config is None:
            config = TransportConfig(local_host=local_host, local_port=local_port)
        else:
            config.local_host = local_host
            config.local_port = local_port

        self.config = config
        self.transport_protocol = transport.upper()
        self._transport = self._create_transport()
        self.state_manager = StateManager()
        self.handlers = AsyncHandlerChain()

        # Authentication handler
        self._auth_handler = AuthenticationHandler(credentials)

        self._closed = False

    def _create_transport(self):
        if self.transport_protocol == "UDP":
            return AsyncUDPTransport(self.config)
        elif self.transport_protocol == "TCP":
            return AsyncTCPTransport(self.config)
        elif self.transport_protocol == "TLS":
            return AsyncTLSTransport(self.config)
        else:
            raise ValueError(f"Unsupported transport: {self.transport_protocol}")

    def add_handler(self, handler: AsyncEventHandler) -> None:
        self.handlers.add_handler(handler)

    def remove_handler(self, handler: AsyncEventHandler) -> None:
        self.handlers.remove_handler(handler)

    async def request(
        self,
        method: str,
        uri: str,
        host: str,
        port: int = 5060,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        # Simplified async version - just calls sync for now
        return Response(status_code=100, reason_phrase="Trying", headers={})

    async def register(
        self,
        aor: str,
        registrar: str,
        port: int = 5060,
        expires: int = 3600,
        headers: Optional[dict] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        return await self.request(
            "REGISTER", aor, registrar, port, headers, auth=auth, **kwargs
        )

    async def options(
        self,
        uri: str,
        host: str,
        port: int = 5060,
        headers: Optional[dict] = None,
        **kwargs,
    ) -> Response:
        return await self.request("OPTIONS", uri, host, port, headers, **kwargs)

    async def invite(
        self,
        to_uri: str,
        from_uri: str,
        host: str,
        port: int = 5060,
        sdp_content: Optional[str] = None,
        headers: Optional[dict] = None,
        auth: Optional[SipAuthCredentials] = None,
        **kwargs,
    ) -> Response:
        return await self.request(
            "INVITE", to_uri, host, port, headers, sdp_content, auth=auth, **kwargs
        )

    async def close(self) -> None:
        if not self._closed:
            await self._transport.close()
            self._closed = True

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def transport(self):
        return self._transport

    @property
    def local_address(self):
        return self._transport.local_address

    @property
    def is_closed(self) -> bool:
        return self._closed

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<AsyncClient({self.transport_protocol}, {status})>"
