"""SIP header storage with canonical and compact-form names.

``HeaderMap`` preserves insertion order, supports multi-valued headers, and
normalizes names to their canonical form while mapping the single-letter
compact forms used on the wire.

References:
    RFC 3261 §7.3 - Header Fields
    RFC 3261 §7.3.3 - Compact Form
    RFC 3261 §20 - Header Field Definitions
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


COMPACT_HEADERS = {
    "a": "Accept-Contact",
    "b": "Referred-By",
    "c": "Content-Type",
    "d": "Request-Disposition",
    "e": "Content-Encoding",
    "f": "From",
    "i": "Call-ID",
    "j": "Reject-Contact",
    "k": "Supported",
    "l": "Content-Length",
    "m": "Contact",
    "o": "Event",
    "r": "Refer-To",
    "s": "Subject",
    "t": "To",
    "u": "Allow-Events",
    "v": "Via",
    "x": "Session-Expires",
}

CANONICAL_TO_COMPACT_HEADERS = {
    value.lower(): key for key, value in COMPACT_HEADERS.items()
}
CANONICAL_HEADER_NAMES = {
    "allow-events": "Allow-Events",
    "call-id": "Call-ID",
    "content-encoding": "Content-Encoding",
    "content-length": "Content-Length",
    "content-type": "Content-Type",
    "cseq": "CSeq",
    "max-forwards": "Max-Forwards",
    "proxy-authenticate": "Proxy-Authenticate",
    "proxy-authorization": "Proxy-Authorization",
    "record-route": "Record-Route",
    "referred-by": "Referred-By",
    "refer-to": "Refer-To",
    "reject-contact": "Reject-Contact",
    "request-disposition": "Request-Disposition",
    "session-expires": "Session-Expires",
    "www-authenticate": "WWW-Authenticate",
}


def canonical_header_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValueError("header name is required")
    compact = COMPACT_HEADERS.get(stripped.lower())
    if compact:
        return compact
    canonical = CANONICAL_HEADER_NAMES.get(stripped.lower())
    if canonical:
        return canonical
    return "-".join(part[:1].upper() + part[1:].lower() for part in stripped.split("-"))


@dataclass(slots=True)
class HeaderValue:
    name: str
    values: list[str]


class HeaderMap:
    def __init__(self) -> None:
        self._headers: dict[str, HeaderValue] = {}
        self._order: list[str] = []

    def add(self, name: str, value: str) -> None:
        canonical = canonical_header_name(name)
        key = canonical.lower()
        if key not in self._headers:
            self._headers[key] = HeaderValue(canonical, [])
            self._order.append(key)
        self._headers[key].values.append(value.strip())

    def set(self, name: str, value: str) -> None:
        canonical = canonical_header_name(name)
        key = canonical.lower()
        if key not in self._headers:
            self._order.append(key)
        self._headers[key] = HeaderValue(canonical, [value.strip()])

    def get(self, name: str, default: str | None = None) -> str | None:
        values = self.get_all(name)
        return values[0] if values else default

    def get_all(self, name: str) -> tuple[str, ...]:
        key = canonical_header_name(name).lower()
        header = self._headers.get(key)
        return tuple(header.values) if header else ()

    def get_int(self, name: str, default: int | None = None) -> int | None:
        value = self.get(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"header {name!r} is not an integer: {value!r}") from exc

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return canonical_header_name(name).lower() in self._headers

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return self.items()

    def items(self, *, compact: bool = False) -> Iterator[tuple[str, str]]:
        for key in self._order:
            header = self._headers[key]
            name = compact_header_name(header.name) if compact else header.name
            for value in header.values:
                yield name, value

    def copy(self) -> HeaderMap:
        copied = HeaderMap()
        for name, value in self.items():
            copied.add(name, value)
        return copied


def compact_header_name(name: str) -> str:
    canonical = canonical_header_name(name)
    return CANONICAL_TO_COMPACT_HEADERS.get(canonical.lower(), canonical)
