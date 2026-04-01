"""Shared helpers for SIP client implementations."""

from __future__ import annotations

import re
import uuid
from collections.abc import MutableMapping

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
    """Collects multiple 200 OK responses from a forked INVITE (RFC 3261 §19.3).

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


def _ack_and_bye_forked(transport, response: Response, destination) -> None:
    """Auto-ACK + fire-and-forget BYE for an extra forked 200 OK (sync transport)."""
    from ..models._message import Request as SipRequest

    request = response.request
    if not request:
        return
    cseq_num = int((request.headers.get("CSeq") or "1 INVITE").split()[0])
    base = {
        "Via": request.headers.get("Via", ""),
        "From": request.headers.get("From", ""),
        "To": response.headers.get("To", ""),
        "Call-ID": request.headers.get("Call-ID", ""),
        "Max-Forwards": "70",
        "Content-Length": "0",
    }
    ack = SipRequest(
        method="ACK",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num} ACK"},
    )
    transport.send(ack.to_bytes(), destination)
    bye = SipRequest(
        method="BYE",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num + 1} BYE"},
    )
    transport.send(bye.to_bytes(), destination)
    logger.debug("Forked leg terminated (ACK+BYE): %s", response.headers.get("To"))


async def _ack_and_bye_forked_async(transport, response: Response, destination) -> None:
    """Auto-ACK + fire-and-forget BYE for an extra forked 200 OK (async transport)."""
    from ..models._message import Request as SipRequest

    request = response.request
    if not request:
        return
    cseq_num = int((request.headers.get("CSeq") or "1 INVITE").split()[0])
    base = {
        "Via": request.headers.get("Via", ""),
        "From": request.headers.get("From", ""),
        "To": response.headers.get("To", ""),
        "Call-ID": request.headers.get("Call-ID", ""),
        "Max-Forwards": "70",
        "Content-Length": "0",
    }
    ack = SipRequest(
        method="ACK",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num} ACK"},
    )
    await transport.send(ack.to_bytes(), destination)
    bye = SipRequest(
        method="BYE",
        uri=request.uri,
        headers={**base, "CSeq": f"{cseq_num + 1} BYE"},
    )
    await transport.send(bye.to_bytes(), destination)
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
