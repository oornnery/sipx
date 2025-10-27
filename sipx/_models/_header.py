"""
SIP Headers implementation.

Provides a case-insensitive, order-preserving headers container with
abstract base classes for extensibility and a unified HeaderParser.
"""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from collections.abc import Mapping

from .._utils import HEADERS, HEADERS_COMPACT, EOL
from .._types import HeaderTypes


# ============================================================================
# Base Classes
# ============================================================================


class HeaderContainer(ABC, typing.MutableMapping[str, str]):
    """
    Abstract base class for SIP header containers.

    All header container implementations must provide:
    - Case-insensitive header name lookups
    - Preservation of insertion order
    - Serialization to wire format (raw bytes)
    """

    @abstractmethod
    def to_lines(self) -> list[str]:
        """
        Convert headers to list of 'Name: Value' strings.

        Returns:
            List of header lines in 'Name: Value' format
        """
        ...

    @abstractmethod
    def raw(self, encoding: str | None = None) -> bytes:
        """
        Serialize headers to raw bytes format for SIP messages.

        Args:
            encoding: Character encoding to use

        Returns:
            Serialized headers as bytes
        """
        ...

    @property
    @abstractmethod
    def encoding(self) -> str:
        """Get the character encoding used for serialization."""
        ...

    @encoding.setter
    @abstractmethod
    def encoding(self, value: str) -> None:
        """Set the character encoding used for serialization."""
        ...


# ============================================================================
# Headers Implementation
# ============================================================================


class Headers(HeaderContainer):
    """Case-insensitive SIP headers preserving insertion order and original casing.

    This class implements MutableMapping to provide a dict-like interface while
    maintaining SIP-specific requirements:
    - Case-insensitive header name lookups (RFC 3261)
    - Preservation of original header name casing
    - Insertion order preservation
    - Support for compact header forms

    Examples:
        >>> h = Headers({"Via": "SIP/2.0/UDP server.com", "from": "alice@example.com"})
        >>> h["FROM"]  # Case-insensitive access
        'alice@example.com'
        >>> h["Content-Type"] = "application/sdp"
        >>> list(h.keys())  # Preserves canonical casing
        ['Via', 'From', 'Content-Type']
    """

    __slots__ = ("_store", "_order", "_encoding")

    @staticmethod
    def _canonical(name: str) -> str:
        """
        Convert header name to canonical form.

        Logic:
        - If len() == 1: Check HEADERS_COMPACT (compact form)
        - If islower(): Check HEADERS (known lowercase header)
        - If already capitalized: Check HEADERS by lowercase, or return as-is
        - Fallback: Title-Case

        Examples:
        - 'i' -> 'Call-ID' (compact form)
        - 'cseq' -> 'CSeq' (mapped header)
        - 'call-id' -> 'Call-ID' (mapped header)
        - 'Content-Type' -> 'Content-Type' (already capitalized)
        - 'X-Custom' -> 'X-Custom' (capitalized, return as-is)
        - 'x-custom' -> 'X-Custom' (lowercase, title-case fallback)
        """
        name = name.strip()

        # Check if it's a single-character compact form
        if len(name) == 1 and name.lower() in HEADERS_COMPACT:
            # Expand compact form to lowercase name, then lookup canonical
            expanded = HEADERS_COMPACT[name.lower()]
            # Now lookup the canonical form
            return HEADERS.get(expanded, expanded)

        # Check if it's all lowercase
        if name.islower():
            if name in HEADERS:
                # Known header in lowercase -> return canonical
                return HEADERS[name]
            # Fallback to Title-Case for unknown lowercase headers
            return "-".join(part.capitalize() for part in name.split("-"))

        # Check if first character is uppercase (already capitalized/mixed case)
        if not name[0].islower():
            # Try to find it by lowercasing first
            lower_name = name.lower()
            if lower_name in HEADERS:
                return HEADERS[lower_name]
            # Return as-is if already capitalized
            return name

        # Fallback: Title-Case
        return "-".join(part.capitalize() for part in name.split("-"))

    def __init__(
        self,
        headers: HeaderTypes | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """
        Initialize Headers container.

        Args:
            headers: Initial headers as Headers instance or Mapping
            encoding: Character encoding for serialization (default: utf-8)
        """
        # _store maps canonical_name -> (display_name, value)
        self._store: dict[str, tuple[str, str]] = {}
        # _order tracks insertion order of canonical names
        self._order: list[str] = []
        self._encoding = encoding

        if isinstance(headers, Headers):
            self._store = headers._store.copy()
            self._order = headers._order.copy()
            self._encoding = headers._encoding
        elif isinstance(headers, Mapping):
            for key, value in headers.items():
                self[key] = value
        elif headers is not None:
            raise TypeError("headers must be Headers or Mapping")

    def __getitem__(self, key: str) -> str:
        """Get header value for the given key (case-insensitive)."""
        canonical = self._canonical(key)
        if canonical not in self._store:
            raise KeyError(key)
        return self._store[canonical][1]

    def __setitem__(self, key: str, value: str) -> None:
        """
        Set a header value, replacing any existing values for this key.

        Header names are automatically converted to canonical form.
        """
        canonical = self._canonical(key)

        if canonical not in self._store:
            self._order.append(canonical)

        # Store with canonical name as display name
        self._store[canonical] = (canonical, str(value))

    def __delitem__(self, key: str) -> None:
        """Delete header with the given key (case-insensitive)."""
        canonical = self._canonical(key)
        if canonical not in self._store:
            raise KeyError(key)
        del self._store[canonical]
        self._order.remove(canonical)

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over header names (in canonical casing, insertion order)."""
        for canonical in self._order:
            yield self._store[canonical][0]

    def __len__(self) -> int:
        """Return the number of headers."""
        return len(self._order)

    def __contains__(self, key: object) -> bool:
        """Check if a header exists (case-insensitive)."""
        if not isinstance(key, str):
            return False
        return self._canonical(key) in self._store

    def __eq__(self, other: object) -> bool:
        """Compare headers for equality."""
        if not isinstance(other, Headers):
            return NotImplemented
        return self._store == other._store and self._order == other._order

    def __repr__(self) -> str:
        """Return a string representation of the headers."""
        items = ", ".join(f"{k!r}: {v!r}" for k, v in self.items())
        return f"Headers({{{items}}})"

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a header value with a default fallback."""
        try:
            return self[key]
        except KeyError:
            return default

    def items(self) -> typing.Iterator[tuple[str, str]]:  # type: ignore[override]
        """Iterate over all header name-value pairs."""
        for canonical in self._order:
            original, value = self._store[canonical]
            yield original, value

    def keys(self) -> typing.Iterator[str]:  # type: ignore[override]
        """Iterate over header names."""
        return iter(self)

    def values(self) -> typing.Iterator[str]:  # type: ignore[override]
        """Iterate over header values."""
        for canonical in self._order:
            yield self._store[canonical][1]

    def update(  # type: ignore[override]
        self,
        other: Mapping[str, str] | Headers | None = None,
        **kwargs: str,
    ) -> None:
        """Update headers from another mapping or keyword arguments."""
        if other is not None:
            if isinstance(other, (Headers, Mapping)):
                for key, value in other.items():
                    self[key] = value
            else:
                raise TypeError("update() argument must be Mapping or Headers")

        for key, value in kwargs.items():
            self[key] = value

    def copy(self) -> Headers:
        """Create a copy of this Headers instance."""
        return Headers(self, encoding=self._encoding)

    def clear(self) -> None:
        """Remove all headers."""
        self._store.clear()
        self._order.clear()

    def popitem(self) -> tuple[str, str]:
        """Remove and return an arbitrary header as a (name, value) pair."""
        if not self._order:
            raise KeyError("Headers is empty")
        canonical = self._order.pop()
        original, value = self._store.pop(canonical)
        return original, value

    def to_lines(self) -> list[str]:
        """Convert headers to list of 'Name: Value' strings in RFC 3261 order."""
        # RFC 3261 recommended order (Section 20)
        priority_order = [
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
            "www-authenticate",
            "proxy-authenticate",
            "expires",
            "user-agent",
            "server",
            "allow",
            "supported",
        ]

        # Collect headers in priority order first
        ordered_headers = []
        seen = set()

        # Add priority headers in order
        for priority_name in priority_order:
            for name, value in self.items():
                if name.lower() == priority_name:
                    ordered_headers.append((name, value))
                    seen.add(name.lower())
                    break

        # Add remaining headers (except Content-Type and Content-Length which go last)
        for name, value in self.items():
            if name.lower() not in seen and name.lower() not in (
                "content-type",
                "content-length",
            ):
                ordered_headers.append((name, value))
                seen.add(name.lower())

        # Add Content-Type before Content-Length if present
        for name, value in self.items():
            if name.lower() == "content-type":
                ordered_headers.append((name, value))
                break

        # Add Content-Length last if present
        for name, value in self.items():
            if name.lower() == "content-length":
                ordered_headers.append((name, value))
                break

        return [f"{name}: {value}" for name, value in ordered_headers]

    @property
    def encoding(self) -> str:
        """Get the character encoding used for serialization."""
        return self._encoding

    @encoding.setter
    def encoding(self, value: str) -> None:
        """Set the character encoding used for serialization."""
        self._encoding = value

    def raw(self, encoding: str | None = None) -> bytes:
        """
        Serialize headers to raw bytes format for SIP messages.

        Returns headers in the format:
            Header-Name: value\r\n
            Another-Header: value\r\n

        Args:
            encoding: Character encoding to use (defaults to instance encoding)

        Returns:
            Serialized headers as bytes
        """
        enc = encoding or self._encoding
        lines = []
        for name, value in self.items():
            lines.append(f"{name}: {value}".encode(enc))
        if not lines:
            return b""
        return EOL.encode(enc).join(lines) + EOL.encode(enc)


# ============================================================================
# Header Parser
# ============================================================================


class HeaderParser:
    """
    Parser for SIP headers.

    Handles parsing of header lines with support for:
    - Line folding (RFC 3261 Section 7.3.1)
    - Compact header forms
    - Case-insensitive header names
    """

    @staticmethod
    def parse(header_data: bytes | str, encoding: str = "utf-8") -> Headers:
        """
        Parse SIP headers from raw data.

        Args:
            header_data: Raw header data (bytes or string)
            encoding: Character encoding to use

        Returns:
            Headers instance

        Example:
            >>> data = b"Via: SIP/2.0/UDP pc33.atlanta.com\\r\\nFrom: alice@atlanta.com\\r\\n"
            >>> headers = HeaderParser.parse(data)
            >>> headers["Via"]
            'SIP/2.0/UDP pc33.atlanta.com'
        """
        if isinstance(header_data, str):
            header_data = header_data.encode(encoding)

        # Normalize line endings
        eol_bytes = EOL.encode(encoding)
        header_data = header_data.replace(b"\r\n", b"\n").replace(b"\n", eol_bytes)

        # Split into lines
        lines = header_data.split(eol_bytes)

        return HeaderParser.parse_lines(lines, encoding=encoding)

    @staticmethod
    def parse_lines(header_lines: list[bytes], encoding: str = "utf-8") -> Headers:
        """
        Parse headers from list of header lines.

        Supports line folding per RFC 3261 Section 7.3.1.

        Args:
            header_lines: List of header line bytes
            encoding: Character encoding to use

        Returns:
            Headers instance
        """
        headers = Headers(encoding=encoding)
        current_name: str | None = None
        current_value: str = ""

        for line in header_lines:
            if not line:
                continue

            # Check for folded line (starts with whitespace)
            if line[0:1] in (b" ", b"\t"):
                if current_name is None:
                    continue  # Folded line without a header, skip
                # Append to current header value
                current_value += " " + line.decode(encoding).strip()
            else:
                # Save previous header if exists
                if current_name is not None:
                    headers[current_name] = current_value

                # Parse new header
                if b":" not in line:
                    continue  # Invalid header line, skip

                name, _, value = line.partition(b":")
                current_name = name.decode(encoding).strip()
                current_value = value.decode(encoding).strip()

        # Save last header
        if current_name is not None:
            headers[current_name] = current_value

        return headers

    @staticmethod
    def parse_header_value(value: str) -> dict[str, str]:
        """
        Parse a header value into main value and parameters.

        Example:
            >>> HeaderParser.parse_header_value('application/sdp; charset=utf-8')
            {'value': 'application/sdp', 'charset': 'utf-8'}

        Args:
            value: Header value string

        Returns:
            Dictionary with 'value' key and parameter keys
        """
        result: dict[str, str] = {}

        # Split by semicolon for parameters
        parts = value.split(";")
        result["value"] = parts[0].strip()

        # Parse parameters
        for part in parts[1:]:
            if "=" in part:
                key, val = part.split("=", 1)
                result[key.strip().lower()] = val.strip().strip('"')

        return result

    @staticmethod
    def format_header_value(value: str, params: dict[str, str] | None = None) -> str:
        """
        Format a header value with parameters.

        Args:
            value: Main header value
            params: Dictionary of parameters

        Returns:
            Formatted header value string

        Example:
            >>> HeaderParser.format_header_value('application/sdp', {'charset': 'utf-8'})
            'application/sdp; charset=utf-8'
        """
        if not params:
            return value

        parts = [value]
        for key, val in params.items():
            # Quote value if it contains special characters
            if any(c in val for c in (" ", ";", ",")):
                parts.append(f'{key}="{val}"')
            else:
                parts.append(f"{key}={val}")

        return "; ".join(parts)


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Base classes
    "HeaderContainer",
    # Implementations
    "Headers",
    # Parser
    "HeaderParser",
]
