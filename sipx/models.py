from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sipx.types import HeaderName, HeaderValue, SipMethod, StatusCode, Uri

if TYPE_CHECKING:
    from sipx.transport.base import Transport


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
        lines = [f"{self.method} {self.uri} SIP/2.0"]
        for name, value in self.headers.items():
            if isinstance(value, list):
                for v in value:
                    lines.append(f"{name}: {v}")
            else:
                lines.append(f"{name}: {value}")
        lines.append("")
        lines.append("")
        body = self.body or b""
        return "\r\n".join(lines).encode("utf-8") + body


@dataclass
class Response:
    """First-class SIP response model."""

    status_code: StatusCode
    reason: str
    headers: dict[HeaderName, HeaderValue] = field(default_factory=dict)
    body: bytes | None = None
    request: Request | None = None

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
        lines = [f"SIP/2.0 {self.status_code} {self.reason}"]
        for name, value in self.headers.items():
            if isinstance(value, list):
                for v in value:
                    lines.append(f"{name}: {v}")
            else:
                lines.append(f"{name}: {value}")
        lines.append("")
        lines.append("")
        body = self.body or b""
        return "\r\n".join(lines).encode("utf-8") + body
