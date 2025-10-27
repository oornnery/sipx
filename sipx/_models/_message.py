"""
SIP Message models (Request and Response) and Parser.

Provides SIP message creation, manipulation, and parsing functionality
with abstract base classes for extensibility and unified MessageParser.
"""

from __future__ import annotations

import re
import typing
from abc import ABC, abstractmethod

from .._utils import BRANCH, EOL, REASON_PHRASES, SCHEME, VERSION
from .._types import HeaderTypes
from ._header import Headers, HeaderParser
from ._body import BodyParser, MessageBody

if typing.TYPE_CHECKING:
    pass


# ============================================================================
# Base Classes
# ============================================================================


class SIPMessage(ABC):
    """
    Abstract base class for SIP messages.

    All SIP message types (Request, Response) must implement:
    - Content management (body, headers)
    - Serialization to wire format
    - Common header access
    """

    @property
    @abstractmethod
    def headers(self) -> Headers:
        """Return the message headers."""
        ...

    @property
    @abstractmethod
    def content(self) -> bytes:
        """Return the message content/body as bytes."""
        ...

    @content.setter
    @abstractmethod
    def content(self, value: str | bytes | MessageBody) -> None:
        """Set the message content/body."""
        ...

    @property
    @abstractmethod
    def body(self) -> MessageBody | None:
        """Return parsed message body if Content-Type is known."""
        ...

    @body.setter
    @abstractmethod
    def body(self, value: MessageBody | None) -> None:
        """Set message body from a MessageBody object."""
        ...

    @abstractmethod
    def to_bytes(self) -> bytes:
        """Serialize message to bytes (wire format)."""
        ...

    @property
    def content_text(self) -> str:
        """Return content decoded as UTF-8 text."""
        return self.content.decode("utf-8")

    @property
    def content_type(self) -> str | None:
        """Return Content-Type header value."""
        return self.headers.get("Content-Type")

    @property
    def content_length(self) -> int:
        """Return Content-Length as integer."""
        return int(self.headers.get("Content-Length", "0"))

    # Common SIP headers as properties
    @property
    def via(self) -> str | None:
        """Return Via header."""
        return self.headers.get("Via")

    @property
    def from_header(self) -> str | None:
        """Return From header."""
        return self.headers.get("From")

    @property
    def to_header(self) -> str | None:
        """Return To header."""
        return self.headers.get("To")

    @property
    def call_id(self) -> str | None:
        """Return Call-ID header."""
        return self.headers.get("Call-ID")

    @property
    def cseq(self) -> str | None:
        """Return CSeq header."""
        return self.headers.get("CSeq")

    @property
    def contact(self) -> str | None:
        """Return Contact header."""
        return self.headers.get("Contact")

    def __str__(self) -> str:
        """Return string representation."""
        return self.to_bytes().decode("utf-8", errors="replace")


# ============================================================================
# Request Implementation
# ============================================================================


class Request(SIPMessage):
    """
    SIP Request message.

    Supported methods: INVITE, ACK, BYE, CANCEL, REGISTER, OPTIONS, SUBSCRIBE,
    NOTIFY, REFER, MESSAGE, INFO, UPDATE, PRACK, PUBLISH
    """

    __slots__ = ("method", "uri", "version", "_headers", "_content", "_body", "auth")

    def __init__(
        self,
        method: str,
        uri: str,
        *,
        headers: HeaderTypes | None = None,
        content: str | bytes | MessageBody | None = None,
        version: str | None = None,
    ) -> None:
        self.method = method.upper()
        self.uri = uri
        self.version = version if version else f"{SCHEME}/{VERSION}"
        self._headers = (
            Headers(headers) if not isinstance(headers, Headers) else headers
        )

        # Content - support str, bytes, or MessageBody
        self._body: MessageBody | None = None
        if isinstance(content, MessageBody):
            self._body = content
            self._content = content.to_bytes()
            # Auto-set Content-Type if not already set
            if "Content-Type" not in self._headers:
                self._headers["Content-Type"] = content.content_type
        elif isinstance(content, str):
            self._content = content.encode("utf-8")
        elif isinstance(content, bytes):
            self._content = content
        else:
            self._content = b""

        # Add mandatory headers (only if not already present)
        self._prepare_mandatory_headers()

    def _prepare_mandatory_headers(self) -> None:
        """Add mandatory RFC 3261 headers if not already present.

        User-provided headers always take precedence over defaults.
        """
        # Content-Length is mandatory (RFC 3261 Section 20.14)
        # Only set if user didn't provide it
        if "Content-Length" not in self._headers:
            self._headers["Content-Length"] = str(len(self._content))

        # Max-Forwards recommended default (RFC 3261 Section 20.22)
        if "Max-Forwards" not in self._headers:
            self._headers["Max-Forwards"] = "70"

    @property
    def headers(self) -> Headers:
        """Return the message headers."""
        return self._headers

    @property
    def content(self) -> bytes:
        """Return message content."""
        return self._content

    @content.setter
    def content(self, value: str | bytes | MessageBody) -> None:
        """Set message content and auto-update Content-Length header.

        Note: This will override any manually set Content-Length.
        """
        if isinstance(value, MessageBody):
            self._body = value
            self._content = value.to_bytes()
            # Auto-set Content-Type
            if "Content-Type" not in self._headers:
                self._headers["Content-Type"] = value.content_type
        elif isinstance(value, str):
            self._body = None
            self._content = value.encode("utf-8")
        else:
            self._body = None
            self._content = value
        # Always update Content-Length to match actual content
        self._headers["Content-Length"] = str(len(self._content))

    @property
    def body(self) -> MessageBody | None:
        """
        Return parsed message body if Content-Type is known, None otherwise.

        Lazily parses the body on first access based on Content-Type header.
        """
        if self._body is None and self._content and "Content-Type" in self._headers:
            try:
                self._body = BodyParser.parse(
                    self._content, self._headers["Content-Type"]
                )
            except Exception:
                # If parsing fails, return None
                pass
        return self._body

    @body.setter
    def body(self, value: MessageBody | None) -> None:
        """Set message body from a MessageBody object."""
        if value is None:
            self._body = None
            self._content = b""
            self._headers["Content-Length"] = "0"
            if "Content-Type" in self._headers:
                del self._headers["Content-Type"]
        else:
            self._body = value
            self._content = value.to_bytes()
            self._headers["Content-Type"] = value.content_type
            self._headers["Content-Length"] = str(len(self._content))

    @property
    def max_forwards(self) -> int | None:
        """Return Max-Forwards as integer."""
        value = self._headers.get("Max-Forwards")
        return int(value) if value else None

    @property
    def user_agent(self) -> str | None:
        """Return User-Agent header."""
        return self._headers.get("User-Agent")

    # Request type checks
    @property
    def is_invite(self) -> bool:
        """True if this is an INVITE request."""
        return self.method == "INVITE"

    @property
    def is_ack(self) -> bool:
        """True if this is an ACK request."""
        return self.method == "ACK"

    @property
    def is_bye(self) -> bool:
        """True if this is a BYE request."""
        return self.method == "BYE"

    @property
    def is_cancel(self) -> bool:
        """True if this is a CANCEL request."""
        return self.method == "CANCEL"

    @property
    def is_register(self) -> bool:
        """True if this is a REGISTER request."""
        return self.method == "REGISTER"

    @property
    def is_options(self) -> bool:
        """True if this is an OPTIONS request."""
        return self.method == "OPTIONS"

    def has_valid_via_branch(self) -> bool:
        """
        Check if Via header has a valid RFC 3261 compliant branch parameter.

        Returns:
            True if Via header exists and branch starts with magic cookie (z9hG4bK),
            False otherwise

        Example:
            >>> req = Request("INVITE", "sip:bob@biloxi.com",
            ...     headers={"Via": "SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds"})
            >>> req.has_valid_via_branch()
            True
        """
        if not self.via:
            return False

        # Extract branch parameter
        match = re.search(r"branch=([^;,\s]+)", self.via, re.IGNORECASE)
        if not match:
            return False

        branch_value = match.group(1)

        # Check if branch starts with RFC 3261 magic cookie
        return branch_value.startswith(BRANCH)

    def to_bytes(self) -> bytes:
        """Serialize request to bytes (wire format)."""
        lines = []
        encoding = "utf-8"

        # Request line: METHOD URI VERSION
        request_line = f"{self.method} {self.uri} {self.version}"
        lines.append(request_line.encode(encoding))

        # Headers
        header_bytes = self._headers.raw().rstrip(EOL.encode(encoding))
        if header_bytes:
            lines.append(header_bytes)

        # Empty line separating headers from body
        lines.append(b"")

        # Body (if present)
        if self._content:
            lines.append(self._content)
        else:
            # Ensure double CRLF at end even with no body
            lines.append(b"")

        return EOL.encode(encoding).join(lines)

    def to_string(self) -> str:
        """Serialize request to string for display."""
        return self.to_bytes().decode("utf-8", errors="replace")

    def add_authorization(
        self,
        credentials: typing.Any,
        challenge: typing.Any,
        *,
        entity_body: bytes | None = None,
    ) -> None:
        """
        Add Authorization or Proxy-Authorization header for authentication.

        This is a convenience method that:
        1. Creates appropriate AuthMethod from credentials and challenge
        2. Generates authorization header value
        3. Adds to correct header (Authorization or Proxy-Authorization)

        Args:
            credentials: Credentials instance (DigestCredentials, BasicCredentials)
            challenge: Challenge instance (DigestChallenge, BasicChallenge)
            entity_body: Request body for auth-int qop (optional, uses self.content if None)

        Example:
            >>> # Receive 401 Unauthorized
            >>> challenge = AuthParser.parse_from_headers(response.headers)
            >>>
            >>> # Create credentials
            >>> creds = DigestCredentials("alice", "secret123")
            >>>
            >>> # Add authorization to request
            >>> request.add_authorization(creds, challenge)
            >>>
            >>> # Request now has Authorization or Proxy-Authorization header
        """
        from ._auth import AuthParser

        # Create auth handler
        auth = AuthParser.create_auth(credentials, challenge)

        # Use entity_body if provided, otherwise use request content
        body = entity_body if entity_body is not None else self._content

        # Generate authorization header
        auth_header = auth.build_authorization(
            method=self.method, uri=self.uri, entity_body=body
        )

        # Add to appropriate header
        header_name = AuthParser.get_auth_header_name(challenge)
        self._headers[header_name] = auth_header

    def __repr__(self) -> str:
        return f"<Request({self.method!r}, {self.uri!r})>"


# ============================================================================
# Response Implementation
# ============================================================================


class Response(SIPMessage):
    """
    SIP Response message.

    Response classes:
    - 1xx: Provisional (100 Trying, 180 Ringing, 183 Session Progress)
    - 2xx: Success (200 OK)
    - 3xx: Redirection (301 Moved Permanently, 302 Moved Temporarily)
    - 4xx: Client Error (400 Bad Request, 404 Not Found, 486 Busy Here)
    - 5xx: Server Error (500 Internal Server Error, 503 Service Unavailable)
    - 6xx: Global Failure (600 Busy Everywhere, 603 Decline)
    """

    __slots__ = (
        "status_code",
        "version",
        "reason_phrase",
        "_headers",
        "_content",
        "_body",
        "_request",
        "_challenge",
    )

    def __init__(
        self,
        status_code: int,
        *,
        reason_phrase: str | None = None,
        headers: HeaderTypes | None = None,
        content: str | bytes | MessageBody | None = None,
        version: str | None = None,
        request: Request | None = None,
    ) -> None:
        self.status_code = status_code
        self.version = version if version else f"{SCHEME}/{VERSION}"
        self._headers = (
            Headers(headers) if not isinstance(headers, Headers) else headers
        )
        self._request = request
        self._challenge = None  # Lazy-loaded auth challenge

        # Reason phrase
        if reason_phrase is None:
            self.reason_phrase = REASON_PHRASES.get(status_code, "Unknown")
        else:
            self.reason_phrase = reason_phrase

        # Content - support str, bytes, or MessageBody
        self._body: MessageBody | None = None
        if isinstance(content, MessageBody):
            self._body = content
            self._content = content.to_bytes()
            # Auto-set Content-Type if not already set
            if "Content-Type" not in self._headers:
                self._headers["Content-Type"] = content.content_type
        elif isinstance(content, str):
            self._content = content.encode("utf-8")
        elif isinstance(content, bytes):
            self._content = content
        else:
            self._content = b""

        # Add mandatory headers (only if not already present)
        if "Content-Length" not in self._headers:
            self._headers["Content-Length"] = str(len(self._content))

    @property
    def headers(self) -> Headers:
        """Return the message headers."""
        return self._headers

    @property
    def content(self) -> bytes:
        """Return message content."""
        return self._content

    @content.setter
    def content(self, value: str | bytes | MessageBody) -> None:
        """Set message content and auto-update Content-Length header.

        Note: This will override any manually set Content-Length.
        """
        if isinstance(value, MessageBody):
            self._body = value
            self._content = value.to_bytes()
            # Auto-set Content-Type
            if "Content-Type" not in self._headers:
                self._headers["Content-Type"] = value.content_type
        elif isinstance(value, str):
            self._body = None
            self._content = value.encode("utf-8")
        else:
            self._body = None
            self._content = value
        # Always update Content-Length to match actual content
        self._headers["Content-Length"] = str(len(self._content))

    @property
    def body(self) -> MessageBody | None:
        """
        Return parsed message body if Content-Type is known, None otherwise.

        Lazily parses the body on first access based on Content-Type header.
        """
        if self._body is None and self._content and "Content-Type" in self._headers:
            try:
                self._body = BodyParser.parse(
                    self._content, self._headers["Content-Type"]
                )
            except Exception:
                # If parsing fails, return None
                pass
        return self._body

    @body.setter
    def body(self, value: MessageBody | None) -> None:
        """Set message body from a MessageBody object."""
        if value is None:
            self._body = None
            self._content = b""
            self._headers["Content-Length"] = "0"
            if "Content-Type" in self._headers:
                del self._headers["Content-Type"]
        else:
            self._body = value
            self._content = value.to_bytes()
            self._headers["Content-Type"] = value.content_type
            self._headers["Content-Length"] = str(len(self._content))

    @property
    def request(self) -> Request | None:
        """Return associated request if available."""
        return self._request

    @request.setter
    def request(self, value: Request | None) -> None:
        """Set associated request."""
        self._request = value

    @property
    def server(self) -> str | None:
        """Return Server header."""
        return self._headers.get("Server")

    @property
    def auth_challenge(self) -> typing.Any:
        """
        Return parsed WWW-Authenticate or Proxy-Authenticate challenge.

        Lazily parses authentication challenge from 401/407 response.
        The challenge indicates what authentication is required.

        Returns:
            Challenge instance (DigestChallenge, BasicChallenge, etc.) or None

        Example:
            >>> response = send_request(...)
            >>> if response.requires_auth:
            ...     challenge = response.auth_challenge
            ...     if isinstance(challenge, DigestChallenge):
            ...         # Handle Digest authentication
            ...         creds = DigestCredentials("alice", "secret")
            ...         request.add_authorization(creds, challenge)
        """
        if self._challenge is None and self.requires_auth:
            # Lazy import to avoid circular dependency
            from ._auth import AuthParser

            self._challenge = AuthParser.parse_from_headers(self._headers)
        return self._challenge

    def get_all_challenges(self) -> list[typing.Any]:
        """
        Get all authentication challenges from response.

        SIP allows multiple challenges in WWW-Authenticate or Proxy-Authenticate.
        Per RFC 3261, client MUST use the topmost (first supported) challenge.

        Returns:
            List of Challenge instances

        Example:
            >>> response = send_request(...)
            >>> if response.requires_auth:
            ...     challenges = response.get_all_challenges()
            ...     # Use first supported challenge
            ...     for challenge in challenges:
            ...         if isinstance(challenge, DigestChallenge):
            ...             # Use this challenge
            ...             break
        """
        from ._auth import AuthParser

        challenges = []

        # Check WWW-Authenticate
        if "WWW-Authenticate" in self._headers:
            www_challenges = AuthParser.parse_multiple_challenges(
                self._headers["WWW-Authenticate"]
            )
            for ch in www_challenges:
                if hasattr(ch, "is_proxy"):
                    ch.is_proxy = False
                challenges.extend(www_challenges)

        # Check Proxy-Authenticate
        if "Proxy-Authenticate" in self._headers:
            proxy_challenges = AuthParser.parse_multiple_challenges(
                self._headers["Proxy-Authenticate"]
            )
            for ch in proxy_challenges:
                if hasattr(ch, "is_proxy"):
                    ch.is_proxy = True
                challenges.extend(proxy_challenges)

        return challenges

    @property
    def requires_auth(self) -> bool:
        """True if response requires authentication (401 or 407)."""
        return self.status_code in (401, 407)

    # Response type checks
    @property
    def is_provisional(self) -> bool:
        """True if this is a 1xx provisional response."""
        return 100 <= self.status_code < 200

    @property
    def is_success(self) -> bool:
        """True if this is a 2xx success response."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """True if this is a 3xx redirect response."""
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        """True if this is a 4xx client error response."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """True if this is a 5xx server error response."""
        return 500 <= self.status_code < 600

    @property
    def is_global_failure(self) -> bool:
        """True if this is a 6xx global failure response."""
        return 600 <= self.status_code < 700

    @property
    def is_error(self) -> bool:
        """True if this is any error response (4xx, 5xx, 6xx)."""
        return self.status_code >= 400

    @property
    def is_final(self) -> bool:
        """True if this is a final response (>= 200)."""
        return self.status_code >= 200

    def to_bytes(self) -> bytes:
        """Serialize response to bytes (wire format)."""
        lines = []
        encoding = "utf-8"

        # Status line: VERSION STATUS_CODE REASON_PHRASE
        status_line = f"{self.version} {self.status_code} {self.reason_phrase}"
        lines.append(status_line.encode(encoding))

        # Headers
        header_bytes = self._headers.raw().rstrip(EOL.encode(encoding))
        if header_bytes:
            lines.append(header_bytes)

        # Empty line separating headers from body
        lines.append(b"")

        # Body (if present)
        if self._content:
            lines.append(self._content)
        else:
            # Ensure double CRLF at end even with no body
            lines.append(b"")

        return EOL.encode(encoding).join(lines)

    def to_string(self) -> str:
        """Serialize response to string for display."""
        return self.to_bytes().decode("utf-8", errors="replace")

    def __repr__(self) -> str:
        return f"<Response [{self.status_code} {self.reason_phrase}]>"


# ============================================================================
# Message Parser
# ============================================================================


class MessageParser:
    """
    Unified SIP message parser.

    Integrates all parsers (HeaderParser, BodyParser, AuthParser) to provide
    complete SIP message parsing functionality.

    Supports parsing both Request and Response messages from bytes or strings.
    """

    @staticmethod
    def parse(data: bytes | str) -> Request | Response:
        """
        Parse SIP message from bytes or string.

        Auto-detects message type (Request or Response) and uses appropriate
        parsers for headers, body, and authentication.

        Args:
            data: Raw SIP message

        Returns:
            Request or Response object

        Raises:
            ValueError: If message is invalid

        Example:
            >>> data = b"INVITE sip:bob@biloxi.com SIP/2.0\\r\\nVia: ...\\r\\n\\r\\n"
            >>> msg = MessageParser.parse(data)
            >>> isinstance(msg, Request)
            True
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        # Normalize line endings
        eol_bytes = EOL.encode("utf-8")
        data = data.replace(b"\r\n", b"\n").replace(b"\n", eol_bytes)

        # Split into header section and body
        double_eol = eol_bytes + eol_bytes
        if double_eol in data:
            header_data, body = data.split(double_eol, 1)
        else:
            header_data = data
            body = b""

        # Parse start line and headers
        lines = header_data.split(eol_bytes)
        if not lines or not lines[0]:
            raise ValueError("Empty SIP message")

        start_line = lines[0]

        # Determine if request or response
        if start_line.startswith(SCHEME.encode("utf-8") + b"/"):
            return MessageParser.parse_response(start_line, lines[1:], body)
        else:
            return MessageParser.parse_request(start_line, lines[1:], body)

    @staticmethod
    def parse_request(
        start_line: bytes, header_lines: list[bytes], body: bytes
    ) -> Request:
        """
        Parse SIP request using HeaderParser and BodyParser.

        Args:
            start_line: Request line bytes
            header_lines: List of header line bytes
            body: Body content bytes

        Returns:
            Request instance

        Raises:
            ValueError: If request line is invalid
        """
        # Parse request line
        parts = start_line.decode("utf-8").split(None, 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid request line: {start_line}")

        method, uri, version = parts

        # Use HeaderParser to parse headers
        headers = HeaderParser.parse_lines(header_lines)

        return Request(
            method=method,
            uri=uri,
            version=version,
            headers=headers,
            content=body,
        )

    @staticmethod
    def parse_response(
        start_line: bytes, header_lines: list[bytes], body: bytes
    ) -> Response:
        """
        Parse SIP response using HeaderParser and BodyParser.

        Args:
            start_line: Status line bytes
            header_lines: List of header line bytes
            body: Body content bytes

        Returns:
            Response instance

        Raises:
            ValueError: If status line is invalid
        """
        # Parse status line
        parts = start_line.decode("utf-8").split(None, 2)
        if len(parts) < 2:
            raise ValueError(f"Invalid status line: {start_line}")

        version = parts[0]
        status_code = int(parts[1])
        reason_phrase = parts[2] if len(parts) > 2 else ""

        # Use HeaderParser to parse headers
        headers = HeaderParser.parse_lines(header_lines)

        return Response(
            status_code=status_code,
            version=version,
            reason_phrase=reason_phrase,
            headers=headers,
            content=body,
        )

    @staticmethod
    def parse_uri(uri: str) -> dict[str, str]:
        """
        Parse SIP URI into components.

        Example: sip:user@host:5060;transport=udp

        Args:
            uri: SIP URI string

        Returns:
            Dict with keys: scheme, user, host, port, params

        Example:
            >>> MessageParser.parse_uri("sip:alice@atlanta.com:5060;transport=tcp")
            {'scheme': 'sip', 'user': 'alice', 'host': 'atlanta.com', 'port': '5060', 'params': 'transport=tcp'}
        """
        result: dict[str, str] = {
            "scheme": "",
            "user": "",
            "host": "",
            "port": "",
            "params": "",
        }

        # Extract scheme
        if ":" not in uri:
            return result

        scheme, rest = uri.split(":", 1)
        result["scheme"] = scheme

        # Extract parameters
        if ";" in rest:
            rest, params = rest.split(";", 1)
            result["params"] = params

        # Extract user@host:port
        if "@" in rest:
            user, host_port = rest.split("@", 1)
            result["user"] = user
        else:
            host_port = rest

        # Extract host and port
        if ":" in host_port:
            host, port = host_port.rsplit(":", 1)
            result["host"] = host
            result["port"] = port
        else:
            result["host"] = host_port

        return result


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Base classes
    "SIPMessage",
    # Implementations
    "Request",
    "Response",
    # Parsers
    "MessageParser",
]
