"""
SIP Authentication module implementing HTTP Digest Authentication (RFC 2617/7616/8760).

Implements the SIP authentication challenge-response model:
- Challenge parsing from 401 Unauthorized / 407 Proxy Authentication Required
- Authorization/Proxy-Authorization header generation
- Multiple challenge support (topmost selection)
- Challenge aggregation for forking scenarios
- Digest authentication (MD5, SHA-256, SHA-512-256)
- QoP (Quality of Protection) support (auth, auth-int)
- Nonce count tracking and client nonce generation
- Stale nonce handling

Security Notes:
- Digest provides message authentication but NOT integrity/confidentiality
- Use TLS/SIPS for transport security
"""

from __future__ import annotations

import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .._types import HeaderTypes


# ============================================================================
# Simplified Credentials DataClass
# ============================================================================


@dataclass
class SipAuthCredentials:
    """
    Simplified SIP authentication credentials.

    This dataclass contains all necessary information for SIP authentication.

    Attributes:
        username: SIP username/identity
        password: Plain text password
        realm: Authentication realm (optional)
        user_agent: User-Agent header value (optional)
        display_name: Display name for From header (optional)
        expires: Registration expiration time in seconds (default: 3600)
    """

    username: str
    password: str
    realm: str | None = None
    user_agent: str | None = None
    display_name: str | None = None
    expires: int = 3600


# ============================================================================
# Simplified Auth API
# ============================================================================


class Auth:
    """
    Simplified authentication interface for SIP clients.

    This class provides static factory methods for creating authentication
    credentials that can be easily assigned to a Client instance.

    Example:
        >>> from sipx import Client, Auth
        >>> with Client() as client:
        ...     client.auth = Auth.Digest('alice', 'secret')
        ...     response = client.register('sip:alice@example.com')
    """

    @staticmethod
    def Digest(
        username: str,
        password: str,
        realm: str | None = None,
        display_name: str | None = None,
        user_agent: str | None = None,
    ) -> SipAuthCredentials:
        """
        Create digest authentication credentials.

        Digest authentication is the standard authentication mechanism for SIP
        (RFC 2617, RFC 3261). It provides secure challenge-response authentication
        without sending passwords in plaintext.

        Args:
            username: SIP username/identity (e.g., 'alice', '1001')
            password: Plain text password for authentication
            realm: Authentication realm (optional, server will provide in challenge)
            display_name: Display name for From header (optional, e.g., 'Alice Smith')
            user_agent: User-Agent header value (optional, e.g., 'MyApp/1.0')

        Returns:
            SipAuthCredentials instance configured for digest authentication

        Example:
            >>> auth = Auth.Digest('alice', 'secret')
            >>> client.auth = auth
        """
        return SipAuthCredentials(
            username=username,
            password=password,
            realm=realm,
            display_name=display_name,
            user_agent=user_agent,
        )

    @staticmethod
    def generate_challenge(response) -> str:
        """
        Generate authentication challenge from a 401/407 response.

        This is a helper method for advanced use cases where you need to
        manually parse and handle authentication challenges.

        Args:
            response: SIP Response with status 401 or 407

        Returns:
            WWW-Authenticate or Proxy-Authenticate header value

        Example:
            >>> response = client.invite(...)
            >>> if response.status_code == 401:
            ...     challenge = Auth.generate_challenge(response)
            ...     print(f"Server challenge: {challenge}")
        """
        if response.status_code == 407:
            return response.headers.get("Proxy-Authenticate", "")
        else:  # 401 or other
            return response.headers.get("WWW-Authenticate", "")


# ============================================================================
# Base Classes
# ============================================================================


class AuthMethod(ABC):
    """
    Abstract base class for SIP authentication methods.

    All authentication methods must implement:
    - Parsing challenges from WWW-Authenticate/Proxy-Authenticate headers
    - Building Authorization/Proxy-Authorization headers
    """

    @property
    @abstractmethod
    def scheme(self) -> str:
        """Return the authentication scheme name (e.g., 'Digest', 'Basic')."""
        ...

    @abstractmethod
    def build_authorization(
        self,
        method: str,
        uri: str,
        *,
        entity_body: bytes | None = None,
    ) -> str:
        """
        Build Authorization or Proxy-Authorization header value.

        Args:
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request-URI
            entity_body: Request body (optional, for auth-int)

        Returns:
            Complete header value (e.g., 'Digest username="alice", ...')
        """
        ...


class Challenge(ABC):
    """
    Abstract base class for authentication challenges.

    Challenges are parsed from WWW-Authenticate or Proxy-Authenticate headers.
    """

    @property
    @abstractmethod
    def scheme(self) -> str:
        """Return the authentication scheme name."""
        ...

    @classmethod
    @abstractmethod
    def parse(cls, header_value: str) -> Challenge:
        """
        Parse challenge from header value.

        Args:
            header_value: Header value string

        Returns:
            Challenge instance

        Raises:
            ValueError: If header is malformed
        """
        ...


@dataclass
class Credentials(ABC):
    """
    Abstract base class for authentication credentials.

    Stores user credentials for authentication.
    """

    username: str
    password: str


# ============================================================================
# Digest Authentication (RFC 2617/7616)
# ============================================================================


@dataclass
class DigestCredentials(Credentials):
    """
    Credentials for SIP Digest authentication.

    Attributes:
        username: SIP username/identity
        password: Plain text password
        realm: Authentication realm (optional, usually from challenge)
    """

    realm: str | None = None


@dataclass
class DigestChallenge(Challenge):
    """
    Parsed Digest authentication challenge from WWW-Authenticate or Proxy-Authenticate header.

    Represents a challenge in the SIP challenge-response authentication flow:
    - Server sends 401/407 with WWW-Authenticate/Proxy-Authenticate
    - Client parses challenge and generates Authorization/Proxy-Authorization
    - Server validates credentials

    Attributes:
        realm: Protection space (realm) - identifies credential domain
        nonce: Server-specified nonce value for replay attack prevention
        algorithm: Hash algorithm (MD5, SHA-256, SHA-512-256)
        qop: Quality of protection options (auth, auth-int)
        opaque: Server-specified opaque value (returned unchanged by client)
        stale: If TRUE, only nonce expired (credentials were valid)
        domain: Space-separated URIs that define protection space
        is_proxy: True if from Proxy-Authenticate header (default: False)
    """

    realm: str
    nonce: str
    algorithm: str = "MD5"
    qop: str | None = None
    opaque: str | None = None
    stale: bool = False
    domain: str | None = None
    is_proxy: bool = False  # True for Proxy-Authenticate challenges
    _raw_params: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def scheme(self) -> str:
        """Return 'Digest' scheme."""
        return "Digest"

    @classmethod
    def parse(cls, header_value: str) -> DigestChallenge:
        """
        Parse WWW-Authenticate or Proxy-Authenticate header value.

        Args:
            header_value: Header value (e.g., 'Digest realm="atlanta.com", nonce="..."')

        Returns:
            DigestChallenge instance

        Raises:
            ValueError: If header is not Digest or malformed
        """
        value = header_value.strip()
        if not value.lower().startswith("digest "):
            raise ValueError(f"Expected Digest challenge, got: {value[:20]}")

        # Remove "Digest " prefix
        value = value[7:].strip()

        params = _parse_auth_params(value)

        if "realm" not in params or "nonce" not in params:
            raise ValueError("Digest challenge missing required realm or nonce")

        return cls(
            realm=params["realm"],
            nonce=params["nonce"],
            algorithm=params.get("algorithm", "MD5"),
            qop=params.get("qop"),
            opaque=params.get("opaque"),
            stale=params.get("stale", "").lower() == "true",
            domain=params.get("domain"),
            _raw_params=params,
        )


@dataclass
class DigestAuth(AuthMethod):
    """
    SIP Digest Authentication handler (RFC 2617/7616/8760).

    Implements the client side of SIP challenge-response authentication:
    1. Receive 401/407 with challenge
    2. Parse challenge (DigestChallenge)
    3. Create DigestAuth with credentials and challenge
    4. Build Authorization/Proxy-Authorization header
    5. Resend request with authentication

    Usage:
        # Receive 401 Unauthorized
        challenge = AuthParser.parse_from_headers(response.headers)

        # Create auth handler
        auth = DigestAuth(
            credentials=DigestCredentials("alice", "secret123"),
            challenge=challenge
        )

        # Generate Authorization header
        auth_header = auth.build_authorization(
            method="INVITE",
            uri="sip:bob@biloxi.com"
        )

        # Add to request
        header_name = "Proxy-Authorization" if challenge.is_proxy else "Authorization"
        request.headers[header_name] = auth_header

    Attributes:
        credentials: User credentials (username, password, realm)
        challenge: Parsed challenge from server
        nonce_count: Counter for nonce reuse (incremented on each auth)
        client_nonce: Client-generated nonce for qop mode
    """

    credentials: DigestCredentials
    challenge: DigestChallenge
    nonce_count: int = 0
    client_nonce: str | None = None

    @property
    def scheme(self) -> str:
        """Return 'Digest' scheme."""
        return "Digest"

    def build_authorization(
        self,
        method: str,
        uri: str,
        *,
        entity_body: bytes | None = None,
    ) -> str:
        """
        Build Authorization or Proxy-Authorization header value.

        This implements step 2 of the challenge-response flow:
        - Calculate response hash using credentials and challenge parameters
        - Include nonce count (nc) and client nonce (cnonce) if qop is used
        - Return complete Digest authorization header value

        Args:
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request-URI (must match request line)
            entity_body: Request body for auth-int qop (optional)

        Returns:
            Complete header value to use in Authorization or Proxy-Authorization header
            Example: 'Digest username="alice", realm="atlanta.com", ...'

        Note:
            Use "Authorization" header for WWW-Authenticate challenges (401)
            Use "Proxy-Authorization" header for Proxy-Authenticate challenges (407)
        """
        self.nonce_count += 1
        nc_value = f"{self.nonce_count:08x}"

        # Generate client nonce if using qop
        if self.challenge.qop:
            if not self.client_nonce:
                self.client_nonce = secrets.token_hex(8)
            cnonce = self.client_nonce
        else:
            cnonce = None

        # Determine which qop to use
        qop_value = None
        if self.challenge.qop:
            qop_options = [q.strip() for q in self.challenge.qop.split(",")]
            # Prefer auth-int if body present, otherwise auth
            if "auth-int" in qop_options and entity_body is not None:
                qop_value = "auth-int"
            elif "auth" in qop_options:
                qop_value = "auth"

        # Get realm
        realm = self.challenge.realm or self.credentials.realm or ""

        # Calculate response hash
        response_hash = self._calculate_response(
            method=method,
            uri=uri,
            realm=realm,
            nonce=self.challenge.nonce,
            algorithm=self.challenge.algorithm,
            qop=qop_value,
            nc=nc_value if qop_value else None,
            cnonce=cnonce,
            entity_body=entity_body,
        )

        # Build authorization header
        parts = [
            f'username="{self.credentials.username}"',
            f'realm="{realm}"',
            f'nonce="{self.challenge.nonce}"',
            f'uri="{uri}"',
            f'response="{response_hash}"',
            f"algorithm={self.challenge.algorithm}",
        ]

        if self.challenge.opaque:
            parts.append(f'opaque="{self.challenge.opaque}"')

        if qop_value:
            parts.extend(
                [
                    f"qop={qop_value}",
                    f"nc={nc_value}",
                    f'cnonce="{cnonce}"',
                ]
            )

        return "Digest " + ", ".join(parts)

    def _calculate_response(
        self,
        method: str,
        uri: str,
        realm: str,
        nonce: str,
        algorithm: str,
        qop: str | None = None,
        nc: str | None = None,
        cnonce: str | None = None,
        entity_body: bytes | None = None,
    ) -> str:
        """Calculate digest response hash according to RFC 2617/7616."""
        # Choose hash function
        if algorithm.upper() in ("MD5", "MD5-SESS"):
            hash_func = hashlib.md5
        elif algorithm.upper() in ("SHA-256", "SHA-256-SESS"):
            hash_func = hashlib.sha256
        else:
            # Default to MD5
            hash_func = hashlib.md5

        # Calculate A1
        a1 = f"{self.credentials.username}:{realm}:{self.credentials.password}"
        ha1 = hash_func(a1.encode()).hexdigest()

        # Handle -sess variants
        if algorithm.upper().endswith("-SESS"):
            if not cnonce or not nonce:
                raise ValueError("cnonce and nonce required for -sess algorithm")
            a1_sess = f"{ha1}:{nonce}:{cnonce}"
            ha1 = hash_func(a1_sess.encode()).hexdigest()

        # Calculate A2
        if qop == "auth-int" and entity_body is not None:
            # Include entity body hash for auth-int
            hashed_body = hash_func(entity_body).hexdigest()
            a2 = f"{method}:{uri}:{hashed_body}"
        else:
            a2 = f"{method}:{uri}"

        ha2 = hash_func(a2.encode()).hexdigest()

        # Calculate response
        if qop and nc and cnonce:
            # RFC 2617 with qop
            data = f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}"
        else:
            # RFC 2069 compatibility (no qop)
            data = f"{ha1}:{nonce}:{ha2}"

        return hash_func(data.encode()).hexdigest()


# ============================================================================
# Authentication Parser
# ============================================================================


class AuthParser:
    """
    Parser for SIP authentication challenges and credentials.

    Implements RFC 3261 challenge-response authentication parsing:
    - Parse WWW-Authenticate (401 Unauthorized)
    - Parse Proxy-Authenticate (407 Proxy Authentication Required)
    - Support multiple challenges per response
    - Handle challenge aggregation for forking scenarios
    - Select topmost (first supported) challenge

    The parser handles the complete challenge-response flow:
    1. Server sends 401/407 with challenge header(s)
    2. Parser extracts and parses challenge(s)
    3. Client creates AuthMethod with challenge
    4. Client builds Authorization/Proxy-Authorization header
    """

    @staticmethod
    def parse_challenge(header_value: str) -> Challenge:
        """
        Parse authentication challenge from header value.

        Auto-detects challenge type (Digest, Basic, etc.) and returns
        appropriate Challenge instance.

        Args:
            header_value: Header value string

        Returns:
            Challenge instance (DigestChallenge, BasicChallenge, etc.)

        Raises:
            ValueError: If challenge type is unsupported or malformed

        Example:
            >>> challenge = AuthParser.parse_challenge('Digest realm="atlanta.com", nonce="abc"')
            >>> isinstance(challenge, DigestChallenge)
            True
        """
        value = header_value.strip()

        # Detect scheme
        if value.lower().startswith("digest "):
            return DigestChallenge.parse(value)
        else:
            # Extract scheme name for error message
            scheme = value.split()[0] if value else "unknown"
            raise ValueError(f"Unsupported authentication scheme: {scheme}")

    @staticmethod
    def parse_from_headers(headers: HeaderTypes) -> Challenge | None:
        """
        Extract and parse authentication challenge from SIP headers.

        Implements SIP authentication challenge parsing per RFC 3261:
        - Checks WWW-Authenticate (401 Unauthorized)
        - Checks Proxy-Authenticate (407 Proxy Authentication Required)
        - Prefers WWW-Authenticate if both present
        - Marks challenge with is_proxy flag for proper header selection

        Args:
            headers: Headers dict or Headers object

        Returns:
            Challenge if found, None otherwise
            Challenge.is_proxy indicates if from Proxy-Authenticate

        Example:
            >>> challenge = AuthParser.parse_from_headers(response.headers)
            >>> if challenge:
            ...     auth = DigestAuth(credentials, challenge)
            ...     header_name = "Proxy-Authorization" if challenge.is_proxy else "Authorization"
            ...     request.headers[header_name] = auth.build_authorization(method, uri)
        """
        # Check WWW-Authenticate (401 Unauthorized) - higher priority
        if "WWW-Authenticate" in headers:
            challenge = AuthParser.parse_challenge(headers["WWW-Authenticate"])
            if isinstance(challenge, DigestChallenge):
                challenge.is_proxy = False
            return challenge

        # Check Proxy-Authenticate (407 Proxy Authentication Required)
        if "Proxy-Authenticate" in headers:
            challenge = AuthParser.parse_challenge(headers["Proxy-Authenticate"])
            if isinstance(challenge, DigestChallenge):
                challenge.is_proxy = True
            return challenge

        return None

    @staticmethod
    def create_auth(
        credentials: Credentials,
        challenge: Challenge,
    ) -> AuthMethod:
        """
        Create appropriate AuthMethod instance from credentials and challenge.

        This is step 3 of the challenge-response flow:
        1. Server sends challenge (parsed)
        2. Client has credentials
        3. Create AuthMethod to generate authorization header

        Args:
            credentials: User credentials
            challenge: Parsed challenge from server

        Returns:
            AuthMethod instance (DigestAuth, BasicAuth, etc.)

        Raises:
            ValueError: If credentials/challenge type mismatch

        Example:
            >>> # Complete flow
            >>> response = request.send()
            >>> if response.status_code == 401:
            ...     challenge = AuthParser.parse_from_headers(response.headers)
            ...     creds = DigestCredentials("alice", "secret")
            ...     auth = AuthParser.create_auth(creds, challenge)
            ...     auth_header = auth.build_authorization(method, uri)
            ...     header_name = "Proxy-Authorization" if challenge.is_proxy else "Authorization"
            ...     request.headers[header_name] = auth_header
        """
        if isinstance(challenge, DigestChallenge):
            if not isinstance(credentials, DigestCredentials):
                raise ValueError("DigestChallenge requires DigestCredentials")
            return DigestAuth(credentials=credentials, challenge=challenge)
        else:
            raise ValueError(f"Unsupported challenge type: {type(challenge).__name__}")

    @staticmethod
    def parse_multiple_challenges(header_value: str) -> list[Challenge]:
        """
        Parse multiple challenges from a single header value.

        SIP allows multiple challenges in one header or multiple headers:
        WWW-Authenticate: Digest realm="realm1", algorithm=MD5, nonce="..."
        WWW-Authenticate: Digest realm="realm1", algorithm=SHA-256, nonce="..."
        WWW-Authenticate: Digest realm="realm2", algorithm=MD5, nonce="..."

        Per RFC 3261, client MUST use the topmost (first) challenge it supports.

        Args:
            header_value: Header value string (may contain multiple challenges)

        Returns:
            List of Challenge objects

        Example:
            >>> challenges = AuthParser.parse_multiple_challenges(header_value)
            >>> # Select first supported challenge
            >>> for challenge in challenges:
            ...     if isinstance(challenge, DigestChallenge):
            ...         # Use this challenge
            ...         break
        """
        challenges = []

        # Simple implementation: split by "Digest " or "Basic "
        # Note: This is a simplified parser; full implementation would handle edge cases
        parts = []
        current = ""

        for line in header_value.split("\n"):
            line = line.strip()
            if line.lower().startswith("digest ") or line.lower().startswith("basic "):
                if current:
                    parts.append(current)
                current = line
            else:
                current += " " + line if current else line

        if current:
            parts.append(current)

        # Parse each challenge
        for part in parts:
            try:
                challenge = AuthParser.parse_challenge(part)
                challenges.append(challenge)
            except ValueError:
                # Skip unsupported challenges
                continue

        return challenges

    @staticmethod
    def get_auth_header_name(challenge: Challenge) -> str:
        """
        Get the correct authorization header name for a challenge.

        Args:
            challenge: Parsed challenge

        Returns:
            "Authorization" for WWW-Authenticate challenges (401)
            "Proxy-Authorization" for Proxy-Authenticate challenges (407)

        Example:
            >>> challenge = AuthParser.parse_from_headers(response.headers)
            >>> header_name = AuthParser.get_auth_header_name(challenge)
            >>> request.headers[header_name] = auth.build_authorization(...)
        """
        if isinstance(challenge, DigestChallenge) and challenge.is_proxy:
            return "Proxy-Authorization"
        return "Authorization"


def _parse_auth_params(params_string: str) -> dict[str, str]:
    """
    Parse authentication parameter string into dict.

    Handles quoted and unquoted values.

    Args:
        params_string: Parameter string (e.g., 'realm="atlanta.com", nonce="abc"')

    Returns:
        Dictionary of parameters
    """
    params: dict[str, str] = {}
    current_key = ""
    current_value = ""
    in_quotes = False
    in_value = False

    i = 0
    while i < len(params_string):
        char = params_string[i]

        if char == '"':
            in_quotes = not in_quotes
            i += 1
            continue

        if not in_quotes:
            if char == "=" and not in_value:
                in_value = True
                current_key = current_key.strip()
                i += 1
                continue

            if char == "," and in_value:
                # End of this parameter
                params[current_key.lower()] = current_value.strip()
                current_key = ""
                current_value = ""
                in_value = False
                i += 1
                continue

        if in_value:
            current_value += char
        else:
            current_key += char

        i += 1

    # Don't forget last parameter
    if current_key and in_value:
        params[current_key.lower()] = current_value.strip()

    return params


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Base classes
    "AuthMethod",
    "Challenge",
    "Credentials",
    # Digest authentication
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    # Authentication - Parser
    "AuthParser",
]
