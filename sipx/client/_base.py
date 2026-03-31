"""Shared helpers for SIP client implementations."""

from __future__ import annotations

import uuid
from urllib.parse import urlparse

from .._utils import logger
from ..models._auth import (
    SipAuthCredentials,
    DigestCredentials,
    DigestAuth,
)
from .._events import EventContext
from ..models._message import Response
from ..transports import (
    TransportConfig,
    UDPTransport,
    TCPTransport,
    TLSTransport,
)
from ..transports._udp import AsyncUDPTransport
from ..transports._tcp import AsyncTCPTransport
from ..transports._tls import AsyncTLSTransport


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
    """Extract host and port from SIP URI."""
    if not uri.startswith("sip:") and not uri.startswith("sips:"):
        uri = f"sip:{uri}"

    parsed = urlparse(uri)
    host = parsed.hostname or parsed.path.split("@")[-1].split(":")[0]
    port = parsed.port or 5060

    return host, port


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
    headers: dict,
    local_addr,
    transport_protocol: str,
    auth: SipAuthCredentials | None,
) -> dict:
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
            logger.debug(
                f"Authentication challenge detected: {response.status_code}"
            )
