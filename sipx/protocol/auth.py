"""Generator-based authentication flow for SIP requests.

This module implements an httpx-style generator-based auth flow that
handles 401/407 challenge/response automatically.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Generator

from sipx.exceptions import AuthError
from sipx.models import Request, Response


def _first_header_value(value: str | list[str] | None) -> str | None:
    if isinstance(value, list):
        return value[0] if value else None
    return value


# Supported Digest algorithms mapped to (hashlib name, session-variant flag).
# MD5 per RFC 7616; SHA-256/SHA-256-sess per RFC 8760.
_DIGEST_ALGORITHMS: dict[str, tuple[str, bool]] = {
    "MD5": ("md5", False),
    "MD5-SESS": ("md5", True),
    "SHA-256": ("sha256", False),
    "SHA-256-SESS": ("sha256", True),
}


@dataclass(frozen=True, slots=True)
class DigestChallenge:
    """Parsed Digest authentication challenge."""

    realm: str
    nonce: str
    algorithm: str = "MD5"
    qop: str | None = None
    opaque: str | None = None


class AuthFlow:
    """Generator-based authentication flow.

    Usage:
        auth = AuthFlow(username='alice', password='secret')
        flow = auth.auth_flow(request)

        # First request (no auth)
        req = next(flow)

        # Receive 401 challenge
        resp = Response(401, 'Unauthorized', headers={'WWW-Authenticate': '...'})

        # Second request (with auth)
        req = flow.send(resp)
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        max_retries: int = 1,
    ) -> None:
        self.username = username
        self.password = password
        self.max_retries = max_retries

    def auth_flow(
        self,
        request: Request,
    ) -> Generator[Request, Response, None]:
        """Generator that handles authentication challenges.

        Yields requests and receives responses. Automatically handles
        401/407 challenges by retrying with appropriate auth headers.
        """
        # First request without auth
        response = yield request

        retries = 0
        while retries < self.max_retries:
            # Check if response requires auth
            challenge_info = self._extract_challenge(response)
            if challenge_info is None:
                # No auth required or non-auth error
                return

            header_name, challenge_value = challenge_info

            # Parse challenge and build auth header
            try:
                challenge = self._parse_digest_challenge(challenge_value)
            except ValueError as exc:
                raise AuthError(
                    f"Failed to parse auth challenge: {exc}",
                    rfc_ref="RFC 7616",
                ) from exc

            # Build authorization header
            auth_header = self._build_digest_authorization(
                request=request,
                challenge=challenge,
            )

            # Create new request with auth header
            new_headers = dict(request.headers)
            new_headers[header_name] = auth_header
            authenticated_request = Request(
                method=request.method,
                uri=request.uri,
                headers=new_headers,
                body=request.body,
                transport=request.transport,
            )

            # Yield authenticated request and wait for response
            response = yield authenticated_request
            retries += 1

        # Max retries exceeded
        if response.status_code in (401, 407):
            raise AuthError(
                f"Authentication failed after {self.max_retries} retries",
                details={"status_code": response.status_code},
                rfc_ref="RFC 7616",
            )

    def _extract_challenge(self, response: Response) -> tuple[str, str] | None:
        """Extract authentication challenge from response."""
        if response.status_code == 401:
            value = _first_header_value(response.headers.get("WWW-Authenticate"))
            return ("Authorization", value) if value else None
        if response.status_code == 407:
            value = _first_header_value(response.headers.get("Proxy-Authenticate"))
            return ("Proxy-Authorization", value) if value else None
        return None

    def _parse_digest_challenge(self, value: str) -> DigestChallenge:
        """Parse a Digest authentication challenge header."""
        text = value.strip()
        if text.lower().startswith("digest "):
            text = text[7:].strip()

        fields = self._parse_digest_fields(text)

        try:
            realm = fields["realm"]
            nonce = fields["nonce"]
        except KeyError as exc:
            raise ValueError("Digest challenge requires realm and nonce") from exc

        return DigestChallenge(
            realm=realm,
            nonce=nonce,
            algorithm=fields.get("algorithm", "MD5"),
            qop=fields.get("qop"),
            opaque=fields.get("opaque"),
        )

    def _build_digest_authorization(
        self,
        request: Request,
        challenge: DigestChallenge,
    ) -> str:
        """Build a Digest authorization header value."""
        algo_spec = _DIGEST_ALGORITHMS.get(challenge.algorithm.upper())
        if algo_spec is None:
            raise AuthError(
                f"Unsupported Digest algorithm: {challenge.algorithm}",
                rfc_ref="RFC 8760",
            )
        hash_name, session = algo_spec

        def digest(value: str) -> str:
            return hashlib.new(
                hash_name, value.encode("utf-8"), usedforsecurity=False
            ).hexdigest()

        # Select qop
        qop = self._select_qop(challenge.qop)

        # Generate cnonce and nonce count
        cnonce = self._generate_cnonce()
        nonce_count = "00000001"

        # Calculate HA1 (with -sess variant) and HA2
        ha1 = digest(f"{self.username}:{challenge.realm}:{self.password}")
        if session:
            ha1 = digest(f"{ha1}:{challenge.nonce}:{cnonce}")
        ha2 = digest(f"{request.method}:{request.uri}")

        # Calculate response
        if qop:
            response = digest(
                f"{ha1}:{challenge.nonce}:{nonce_count}:{cnonce}:{qop}:{ha2}"
            )
        else:
            response = digest(f"{ha1}:{challenge.nonce}:{ha2}")

        # Build header parts
        parts = [
            f'username="{self.username}"',
            f'realm="{challenge.realm}"',
            f'nonce="{challenge.nonce}"',
            f'uri="{request.uri}"',
            f'response="{response}"',
            f'algorithm="{challenge.algorithm}"',
        ]

        if challenge.opaque:
            parts.append(f'opaque="{challenge.opaque}"')

        if qop:
            parts.extend(
                [
                    f"qop={qop}",
                    f"nc={nonce_count}",
                    f'cnonce="{cnonce}"',
                ]
            )

        return "Digest " + ", ".join(parts)

    def _parse_digest_fields(self, value: str) -> dict[str, str]:
        """Parse Digest challenge fields."""
        fields: dict[str, str] = {}
        for part in self._split_quoted_commas(value):
            name, separator, item = part.partition("=")
            if not separator:
                continue
            fields[name.strip().lower()] = item.strip().strip('"')
        return fields

    def _split_quoted_commas(self, value: str) -> list[str]:
        """Split comma-separated values, respecting quotes."""
        parts: list[str] = []
        current: list[str] = []
        in_quotes = False
        for char in value:
            if char == '"':
                in_quotes = not in_quotes
            if char == "," and not in_quotes:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            parts.append("".join(current).strip())
        return parts

    def _select_qop(self, value: str | None) -> str | None:
        """Select qop option from challenge."""
        if value is None:
            return None
        options = {item.strip() for item in value.split(",")}
        return "auth" if "auth" in options else None

    def _generate_cnonce(self) -> str:
        """Generate a client nonce value."""
        return os.urandom(8).hex()
