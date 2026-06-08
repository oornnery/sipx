from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from sipx.sip.headers import HeaderMap
from sipx.sip.uri import SipUri


DEFAULT_MAX_MESSAGE_SIZE = 65535


class SipParseError(ValueError):
    pass


@dataclass(slots=True)
class SipRequest:
    method: str
    uri: SipUri
    headers: HeaderMap
    body: bytes = b""
    version: str = "SIP/2.0"

    def to_bytes(self) -> bytes:
        return _serialize(
            f"{self.method} {self.uri} {self.version}",
            self.headers,
            self.body,
        )


@dataclass(slots=True)
class SipResponse:
    status_code: int
    reason: str
    headers: HeaderMap
    body: bytes = b""
    version: str = "SIP/2.0"

    def to_bytes(self) -> bytes:
        return _serialize(
            f"{self.version} {self.status_code} {self.reason}",
            self.headers,
            self.body,
        )


SipMessage: TypeAlias = SipRequest | SipResponse


def parse_sip_message(
    raw: bytes | str,
    *,
    max_size: int = DEFAULT_MAX_MESSAGE_SIZE,
) -> SipMessage:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > max_size:
        raise SipParseError("SIP message exceeds maximum size")

    header_part, body_part = _split_message(data)
    lines = _unfold_header_lines(header_part.decode("utf-8"))
    if not lines or not lines[0]:
        raise SipParseError("SIP start line is required")

    headers = HeaderMap()
    for line in lines[1:]:
        if ":" not in line:
            raise SipParseError(f"invalid SIP header line: {line!r}")
        name, value = line.split(":", 1)
        headers.add(name, value)

    content_length = headers.get_int("Content-Length", 0) or 0
    if content_length != len(body_part):
        raise SipParseError(
            "SIP body length does not match Content-Length: "
            f"expected {content_length}, got {len(body_part)}"
        )

    start_line = lines[0]
    if start_line.startswith("SIP/"):
        return _parse_response(start_line, headers, body_part)
    return _parse_request(start_line, headers, body_part)


def _split_message(data: bytes) -> tuple[bytes, bytes]:
    for separator in (b"\r\n\r\n", b"\n\n"):
        if separator in data:
            header_part, body_part = data.split(separator, 1)
            return header_part, body_part
    raise SipParseError("SIP message missing header/body separator")


def _unfold_header_lines(header_text: str) -> list[str]:
    raw_lines = header_text.replace("\r\n", "\n").split("\n")
    lines: list[str] = []
    for raw_line in raw_lines:
        if raw_line.startswith((" ", "\t")):
            if not lines:
                raise SipParseError("folded header has no previous header")
            lines[-1] = f"{lines[-1]} {raw_line.strip()}"
        else:
            lines.append(raw_line)
    return lines


def _parse_request(start_line: str, headers: HeaderMap, body: bytes) -> SipRequest:
    parts = start_line.split()
    if len(parts) != 3:
        raise SipParseError(f"invalid SIP request line: {start_line!r}")
    method, uri_text, version = parts
    if version != "SIP/2.0":
        raise SipParseError(f"unsupported SIP version: {version!r}")
    return SipRequest(
        method=method, uri=SipUri.parse(uri_text), headers=headers, body=body
    )


def _parse_response(start_line: str, headers: HeaderMap, body: bytes) -> SipResponse:
    parts = start_line.split(maxsplit=2)
    if len(parts) < 2:
        raise SipParseError(f"invalid SIP response line: {start_line!r}")
    version, status_text = parts[:2]
    if version != "SIP/2.0":
        raise SipParseError(f"unsupported SIP version: {version!r}")
    try:
        status_code = int(status_text)
    except ValueError as exc:
        raise SipParseError(f"invalid SIP status code: {status_text!r}") from exc
    reason = parts[2] if len(parts) == 3 else ""
    return SipResponse(
        status_code=status_code,
        reason=reason,
        headers=headers,
        body=body,
    )


def _serialize(start_line: str, headers: HeaderMap, body: bytes) -> bytes:
    output_headers = headers.copy()
    output_headers.set("Content-Length", str(len(body)))
    lines = [start_line]
    lines.extend(f"{name}: {value}" for name, value in output_headers.items())
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + body
