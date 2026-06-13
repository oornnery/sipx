"""First-class SIP request and response models used by the AsyncClient.

Lightweight, typed dataclasses that hold a SIP message (method/URI or
status/reason, headers, optional body) and serialize back to wire bytes.
``Response.history`` records the intermediate provisional (1xx) and
authentication-challenge (401/407) responses that preceded a final response.

References:
    RFC 3261 §7 - SIP Messages (requests, responses, headers, bodies)
    RFC 3261 §7.1 - Requests
    RFC 3261 §7.2 - Responses
    RFC 3261 §25 - Augmented BNF for the SIP Protocol
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sipx.types import HeaderName, HeaderValue, SipMethod, StatusCode, Uri
from sipx.wire import sanitize_sip_token

if TYPE_CHECKING:
    from sipx.transport.base import Transport


def _sanitize_headers(
    headers: dict[HeaderName, HeaderValue],
) -> dict[HeaderName, HeaderValue]:
    """Reject CR/LF injection in header names and values."""
    clean: dict[HeaderName, HeaderValue] = {}
    for name, value in headers.items():
        safe_name = sanitize_sip_token(name, field="header name")
        if isinstance(value, list):
            clean[safe_name] = [
                sanitize_sip_token(v, field=f"header {safe_name}") for v in value
            ]
        else:
            clean[safe_name] = sanitize_sip_token(value, field=f"header {safe_name}")
    return clean


def _content_length(headers: dict[HeaderName, HeaderValue], body_len: int) -> None:
    """Set Content-Length when absent (required for stream transports)."""
    if not any(k.lower() == "content-length" for k in headers):
        headers["Content-Length"] = str(body_len)


@dataclass
class Request:
    """First-class SIP request model."""

    method: SipMethod
    uri: Uri
    headers: dict[HeaderName, HeaderValue] = field(default_factory=dict)
    body: bytes | None = None
    transport: Transport | None = None

    @classmethod
    def build(
        cls,
        method: SipMethod,
        uri: Uri,
        headers: dict[HeaderName, HeaderValue] | None = None,
        **extra_headers: HeaderValue,
    ) -> Request:
        """Build a Request from method, uri, and header kwargs."""
        merged = dict(headers) if headers else {}
        merged.update(extra_headers)
        return cls(method=method, uri=uri, headers=merged, body=None, transport=None)

    def to_bytes(self) -> bytes:
        """Serialize to raw SIP request bytes."""
        method = sanitize_sip_token(self.method, field="method")
        uri = sanitize_sip_token(self.uri, field="URI")
        headers = _sanitize_headers(dict(self.headers))
        body = self.body or b""
        _content_length(headers, len(body))
        lines = [f"{method} {uri} SIP/2.0"]
        for name, value in headers.items():
            if isinstance(value, list):
                for v in value:
                    lines.append(f"{name}: {v}")
            else:
                lines.append(f"{name}: {value}")
        lines.append("")
        lines.append("")
        return "\r\n".join(lines).encode("utf-8") + body


@dataclass
class Response:
    """First-class SIP response model."""

    status_code: StatusCode
    reason: str
    headers: dict[HeaderName, HeaderValue] = field(default_factory=dict)
    body: bytes | None = None
    request: Request | None = None
    history: list[Response] = field(default_factory=list)
    """Intermediate responses (provisional 1xx + 401/407 auth challenges).

    Populated by the client on the final response in arrival order. Each
    entry carries its own ``request`` so the full exchange is reconstructable.
    """

    @classmethod
    def from_request(
        cls,
        request: Request,
        status_code: StatusCode,
        reason: str,
        headers: dict[HeaderName, HeaderValue] | None = None,
        **extra_headers: HeaderValue,
    ) -> Response:
        """Build a Response linked to a Request."""
        merged = dict(headers) if headers else {}
        merged.update(extra_headers)
        return cls(
            status_code=status_code,
            reason=reason,
            headers=merged,
            body=None,
            request=request,
        )

    def to_bytes(self) -> bytes:
        """Serialize to raw SIP response bytes."""
        reason = sanitize_sip_token(self.reason, field="reason phrase")
        headers = _sanitize_headers(dict(self.headers))
        body = self.body or b""
        _content_length(headers, len(body))
        lines = [f"SIP/2.0 {self.status_code} {reason}"]
        for name, value in headers.items():
            if isinstance(value, list):
                for v in value:
                    lines.append(f"{name}: {v}")
            else:
                lines.append(f"{name}: {value}")
        lines.append("")
        lines.append("")
        return "\r\n".join(lines).encode("utf-8") + body
