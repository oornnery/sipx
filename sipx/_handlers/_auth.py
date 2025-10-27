"""
Authentication handler for SIP digest authentication.

This module handles SIP authentication challenges (401/407) and automatically
retries requests with proper authorization headers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._base import EventHandler, EventContext
from .._utils import console, logger

if TYPE_CHECKING:
    from .._models._message import Request, Response
    from .._models._auth import Challenge, SipAuthCredentials
    from .._types import TransportAddress


class AuthenticationHandler(EventHandler):
    """
    Handler for SIP digest authentication.

    This handler:
    1. Detects authentication challenges (401/407)
    2. Selects credentials based on priority (method > client > handler)
    3. Builds authorization headers using digest authentication
    4. Automatically retries requests with authentication

    Credential Priority:
    - Method-level: Credentials passed to specific method call (invite/register)
    - Client-level: Credentials passed to Client.__init__
    - Handler-level: Credentials from legacy AuthHandler (backwards compatibility)
    """

    def __init__(self, credentials: Optional["SipAuthCredentials"] = None):
        """
        Initialize authentication handler.

        Args:
            credentials: Default credentials for authentication (client-level)
        """
        self.default_credentials = credentials

    def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Handle authentication challenges (401/407).

        This method detects authentication challenges and sets metadata
        so the Client can trigger an auth retry.

        Args:
            response: SIP response
            context: Event context

        Returns:
            Original response (unmodified)
        """
        from .._models._auth import AuthParser

        if response.status_code in (401, 407):
            # Parse challenge
            parser = AuthParser()
            challenge = parser.parse_from_headers(response.headers)

            if challenge:
                # Signal that auth retry should happen
                context.metadata["needs_auth"] = True
                context.metadata["auth_challenge"] = challenge

                logger.debug(
                    f"Authentication challenge received: {response.status_code}"
                )

        return response

    def should_authenticate(self, response: Response) -> bool:
        """
        Check if response requires authentication.

        Args:
            response: SIP response to check

        Returns:
            True if 401 Unauthorized or 407 Proxy Authentication Required
        """
        return response.status_code in (401, 407)

    def get_credentials(
        self,
        method_credentials: Optional["SipAuthCredentials"] = None,
        handler_credentials: Optional["SipAuthCredentials"] = None,
    ) -> Optional["SipAuthCredentials"]:
        """
        Select credentials with proper priority.

        Priority order:
        1. Method credentials (passed to invite/register/etc)
        2. Client credentials (passed to Client.__init__)
        3. Handler credentials (from AuthHandler in chain)

        Args:
            method_credentials: Credentials from method call
            handler_credentials: Credentials from handler

        Returns:
            Selected credentials or None
        """
        # Priority 1: Method-level credentials
        if method_credentials:
            logger.debug("Using method-level credentials")
            return method_credentials

        # Priority 2: Client-level credentials
        if self.default_credentials:
            logger.debug("Using client-level credentials")
            return self.default_credentials

        # Priority 3: Handler-level credentials (backwards compatibility)
        if handler_credentials:
            logger.debug("Using handler-level credentials")
            return handler_credentials

        logger.debug("No credentials available")
        return None

    def build_auth_header(
        self,
        credentials: "SipAuthCredentials",
        challenge: "Challenge",
        method: str,
        uri: str,
    ) -> str:
        """
        Build authorization header from credentials and challenge.

        Args:
            credentials: SIP authentication credentials
            challenge: Authentication challenge from server
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request URI

        Returns:
            Authorization header value

        Raises:
            ValueError: If challenge or credentials are invalid
        """
        from .._models._auth import DigestCredentials, DigestAuth

        # Convert SipAuthCredentials to DigestCredentials
        digest_credentials = DigestCredentials(
            username=credentials.username,
            password=credentials.password,
            realm=credentials.realm,
        )

        # Create digest auth handler
        digest_auth = DigestAuth(
            credentials=digest_credentials,
            challenge=challenge,
        )

        # Generate authorization header
        auth_header = digest_auth.build_authorization(
            method=method,
            uri=uri,
        )

        logger.debug(f"Built authorization header for {method} {uri}")
        return auth_header

    def handle_auth_response(
        self,
        response: Response,
        request: Request,
        context: EventContext,
        credentials: Optional["SipAuthCredentials"],
        transport,
        destination: TransportAddress,
        host: str,
        port: int,
    ) -> Optional[Response]:
        """
        Handle authentication challenge and retry request.

        This method:
        1. Extracts challenge from response
        2. Builds authorization header
        3. Updates request with auth and incremented CSeq
        4. Resends request
        5. Collects and returns final response

        Args:
            response: Original 401/407 response
            request: Original request that was challenged
            context: Event context
            credentials: Credentials to use
            transport: Transport instance
            destination: Transport destination
            host: Destination host
            port: Destination port

        Returns:
            Final response after authentication, or None if auth failed
        """
        if not credentials:
            logger.debug("No credentials available for authentication")
            return None

        # Get auth challenge from context
        challenge = context.metadata.get("auth_challenge")
        if not challenge:
            logger.debug("No authentication challenge found in context")
            return None

        try:
            # Build authorization header
            auth_header_value = self.build_auth_header(
                credentials=credentials,
                challenge=challenge,
                method=request.method,
                uri=request.uri,
            )

            # Determine header name based on status code
            auth_header_name = (
                "Proxy-Authorization"
                if response.status_code == 407
                else "Authorization"
            )

            # Update request with authorization
            request.headers[auth_header_name] = auth_header_value

            # Increment CSeq for retry
            if "CSeq" in request.headers:
                cseq_parts = request.headers["CSeq"].split()
                if len(cseq_parts) == 2:
                    cseq_num = int(cseq_parts[0]) + 1
                    request.headers["CSeq"] = f"{cseq_num} {cseq_parts[1]}"

            # Log authentication retry
            local_addr = transport.local_address
            console.print(
                f"\n[bold yellow]>>> SENDING {request.method} AUTH RETRY "
                f"({local_addr} → {host}:{port}):[/bold yellow]"
            )
            console.print(request.to_string())
            console.print("=" * 80)

            # Send authenticated request
            request_data = request.to_bytes()
            transport.send(request_data, destination)

            # Receive and process responses
            from .._models._message import MessageParser

            parser = MessageParser()
            auth_final_response = None

            while True:
                # Receive response
                response_data, source = transport.receive(
                    timeout=transport.config.read_timeout
                )

                # Parse response
                auth_response = parser.parse(response_data)
                auth_response.raw = response_data
                auth_response.request = request
                auth_response.transport_info = {
                    "protocol": transport.__class__.__name__.replace(
                        "Transport", ""
                    ).upper(),
                    "local": str(transport.local_address),
                    "remote": str(source),
                }

                # Log auth response
                local_addr = transport.local_address
                console.print(
                    f"\n[bold green]<<< RECEIVED {auth_response.status_code} "
                    f"{auth_response.reason_phrase} AUTH ({source} → {local_addr}):[/bold green]"
                )
                console.print(auth_response.to_string())
                console.print("=" * 80)

                # Check if final response (2xx-6xx)
                if auth_response.status_code >= 200:
                    auth_final_response = auth_response
                    context.response = auth_final_response
                    break

                # Provisional response (1xx) - continue waiting
                if auth_final_response is None:
                    auth_final_response = auth_response

            logger.info(f"Authentication successful: {auth_final_response.status_code}")
            return auth_final_response

        except Exception as e:
            logger.error(f"Authentication retry failed: {e}")
            return None
