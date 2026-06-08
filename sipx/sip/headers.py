from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


COMPACT_HEADERS = {
    "c": "Content-Type",
    "f": "From",
    "i": "Call-ID",
    "l": "Content-Length",
    "m": "Contact",
    "t": "To",
    "v": "Via",
}


def canonical_header_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValueError("header name is required")
    compact = COMPACT_HEADERS.get(stripped.lower())
    if compact:
        return compact
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

    def items(self) -> Iterator[tuple[str, str]]:
        for key in self._order:
            header = self._headers[key]
            for value in header.values:
                yield header.name, value

    def copy(self) -> HeaderMap:
        copied = HeaderMap()
        for name, value in self.items():
            copied.add(name, value)
        return copied
