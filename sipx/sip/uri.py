"""SIP and SIPS URI parsing and serialization.

``SipUri`` parses and renders ``sip:``/``sips:`` URIs including user, host,
port, URI parameters, and header parameters, with IPv6 host handling and
percent-encoding.

References:
    RFC 3261 §19.1 - SIP and SIPS URI Components
    RFC 3261 §25.1 - Basic Rules (URI ABNF)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qsl, quote, unquote


@dataclass(frozen=True, slots=True)
class SipUri:
    scheme: str
    host: str
    user: str | None = None
    port: int | None = None
    parameters: dict[str, str | None] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scheme not in {"sip", "sips"}:
            raise ValueError("SIP URI scheme must be sip or sips")
        if not self.host:
            raise ValueError("SIP URI host is required")
        if self.port is not None and not 0 < self.port < 65536:
            raise ValueError("SIP URI port must be between 1 and 65535")

    @classmethod
    def parse(cls, value: str) -> SipUri:
        scheme, separator, rest = value.partition(":")
        if separator != ":":
            raise ValueError(f"invalid SIP URI: {value!r}")

        headers: dict[str, str] = {}
        if "?" in rest:
            rest, header_text = rest.split("?", 1)
            headers = {
                unquote(key): unquote(item) for key, item in parse_qsl(header_text)
            }

        address, *parameter_parts = rest.split(";")
        parameters: dict[str, str | None] = {}
        for parameter in parameter_parts:
            if not parameter:
                continue
            key, has_value, item = parameter.partition("=")
            parameters[unquote(key)] = unquote(item) if has_value else None

        user: str | None = None
        host_port = address
        if "@" in address:
            user_text, host_port = address.rsplit("@", 1)
            user = unquote(user_text) or None

        host, port = _parse_host_port(host_port)
        return cls(
            scheme=scheme.lower(),
            user=user,
            host=host,
            port=port,
            parameters=parameters,
            headers=headers,
        )

    def __str__(self) -> str:
        user = f"{quote(self.user)}@" if self.user else ""
        host = (
            f"[{self.host}]"
            if ":" in self.host and not self.host.startswith("[")
            else self.host
        )
        port = f":{self.port}" if self.port is not None else ""
        parameters = "".join(
            f";{quote(key)}" if value is None else f";{quote(key)}={quote(value)}"
            for key, value in self.parameters.items()
        )
        headers = ""
        if self.headers:
            headers = "?" + "&".join(
                f"{quote(key)}={quote(value)}" for key, value in self.headers.items()
            )
        return f"{self.scheme}:{user}{host}{port}{parameters}{headers}"


def _parse_host_port(value: str) -> tuple[str, int | None]:
    if not value:
        raise ValueError("SIP URI host is required")
    if value.startswith("["):
        host, separator, rest = value[1:].partition("]")
        if separator != "]":
            raise ValueError(f"invalid IPv6 SIP URI host: {value!r}")
        port = _parse_port(rest[1:]) if rest.startswith(":") else None
        return host, port
    host, separator, port_text = value.rpartition(":")
    if separator and port_text.isdigit():
        return host, _parse_port(port_text)
    return value, None


def _parse_port(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"invalid SIP URI port: {value!r}") from exc
