from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, MutableMapping, Optional, Tuple

CRLF = "\r\n"
CRLFCRLF = "\r\n\r\n"
_HEADER_FOLD_RE = re.compile(r"^\s")


def _normalize(name: str) -> str:
    return name.lower()


def _canonical(name: str) -> str:
    # RFC 3261 recommends capitalizing each token separated by '-'
    return "-".join(part.capitalize() for part in name.split("-"))


class SIPHeaders(MutableMapping[str, str]):
    """Case-insensitive headers preserving insertion order and original casing."""

    __slots__ = ("_store", "_order")

    def __init__(
        self,
        headers: Optional[Iterable[Tuple[str, str]] | Dict[str, str]] = None,
    ) -> None:
        self._store: Dict[str, Tuple[str, str]] = {}
        self._order: List[str] = []
        if headers:
            self.update(headers)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):  # type: ignore[unreachable]
            return False
        return _normalize(key) in self._store

    def __getitem__(self, key: str) -> str:
        norm = _normalize(key)
        if norm not in self._store:
            raise KeyError(key)
        return self._store[norm][1]

    def __setitem__(self, key: str, value: str) -> None:
        norm = _normalize(key)
        canonical = key if key == key.upper() else _canonical(key)
        if norm not in self._store:
            self._order.append(norm)
        self._store[norm] = (canonical, value)

    def __delitem__(self, key: str) -> None:
        norm = _normalize(key)
        if norm not in self._store:
            raise KeyError(key)
        del self._store[norm]
        self._order.remove(norm)

    def __iter__(self) -> Iterator[str]:
        for norm in self._order:
            yield self._store[norm][0]

    def __len__(self) -> int:
        return len(self._order)

    def items(self) -> Iterator[Tuple[str, str]]:  # type: ignore[override]
        for norm in self._order:
            original, value = self._store[norm]
            yield original, value

    def update(  # type: ignore[override]
        self,
        headers: Iterable[Tuple[str, str]] | Dict[str, str],
    ) -> None:
        if isinstance(headers, dict):
            iterable = headers.items()
        else:
            iterable = headers
        for key, value in iterable:
            self[key] = value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:  # type: ignore[override]
        norm = _normalize(key)
        if norm not in self._store:
            return default
        return self._store[norm][1]

    def popitem(self):  # pragma: no cover - not used in code paths
        norm = self._order.pop()
        return self._store.pop(norm)

    def clear(self) -> None:
        self._store.clear()
        self._order.clear()

    def to_lines(self) -> List[str]:
        return [f"{name}: {value}" for name, value in self.items()]


@dataclass(slots=True)
class SIPMessage:
    start_line: str
    headers: SIPHeaders
    body: str
    raw: str
    is_request: bool
    method: Optional[str] = None
    status_code: Optional[int] = None
    status_text: Optional[str] = None

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.headers.get(name, default)


def parse_sip_message(raw: str) -> SIPMessage:
    # Normalize CRLF pairs
    if CRLFCRLF not in raw:
        raw = raw.replace("\n\n", CRLFCRLF).replace("\n", CRLF)

    head, _, body = raw.partition(CRLFCRLF)
    if not head:
        raise ValueError("Invalid SIP message: missing start line")

    lines = head.split(CRLF)
    start_line = lines[0]
    header_lines: List[str] = []
    for line in lines[1:]:
        if not line:
            continue
        if header_lines and _HEADER_FOLD_RE.match(line):
            header_lines[-1] += f" {line.strip()}"
        else:
            header_lines.append(line)

    headers = SIPHeaders()
    for line in header_lines:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()

    if start_line.startswith("SIP/2.0"):
        parts = start_line.split(" ", 2)
        status_code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        status_text = parts[2] if len(parts) > 2 else None
        return SIPMessage(
            start_line=start_line,
            headers=headers,
            body=body,
            raw=raw,
            is_request=False,
            method=None,
            status_code=status_code,
            status_text=status_text,
        )

    parts = start_line.split(" ", 2)
    method = parts[0] if parts else None
    return SIPMessage(
        start_line=start_line,
        headers=headers,
        body=body,
        raw=raw,
        is_request=True,
        method=method,
    )


def build_request(
    method: str,
    uri: str,
    headers: SIPHeaders | Iterable[Tuple[str, str]] | Dict[str, str],
    body: str = "",
) -> str:
    if not isinstance(headers, SIPHeaders):
        header_obj = SIPHeaders(headers)
    else:
        header_obj = headers

    payload = body or ""
    content_length = len(payload.encode("utf-8"))
    if "content-length" not in header_obj:
        header_obj["Content-Length"] = str(content_length)

    header_lines = CRLF.join(header_obj.to_lines())
    return f"{method} {uri} SIP/2.0{CRLF}{header_lines}{CRLF}{CRLF}{payload}"


def build_response(
    status_code: int,
    reason: str,
    headers: SIPHeaders | Iterable[Tuple[str, str]] | Dict[str, str],
    body: str = "",
) -> str:
    if not isinstance(headers, SIPHeaders):
        header_obj = SIPHeaders(headers)
    else:
        header_obj = headers

    payload = body or ""
    content_length = len(payload.encode("utf-8"))
    header_obj["Content-Length"] = str(content_length)

    header_lines = CRLF.join(header_obj.to_lines())
    return f"SIP/2.0 {status_code} {reason}{CRLF}{header_lines}{CRLF}{CRLF}{payload}"


def header_params(value: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    if ";" not in value:
        return params
    for part in value.split(";")[1:]:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().lower()] = val.strip('" ')
        else:
            params[part.lower()] = ""
    return params


__all__ = [
    "CRLF",
    "CRLFCRLF",
    "SIPHeaders",
    "SIPMessage",
    "build_request",
    "build_response",
    "header_params",
    "parse_sip_message",
]
