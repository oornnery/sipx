"""
SIP URI parser per RFC 3261 Section 19.1.

URI format:
    sip:user:password@host:port;uri-parameters?headers
    sips:user@host:port;transport=tcp

Examples:
    sip:alice@atlanta.com
    sip:alice:secret@atlanta.com:5060;transport=tcp
    sips:bob@biloxi.com
    sip:+1-212-555-1212:1234@gateway.com;user=phone
    sip:atlanta.com;method=REGISTER?to=alice%40atlanta.com
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote


@dataclass
class SipURI:
    """Parsed SIP URI (RFC 3261 Section 19.1)."""

    scheme: str = "sip"
    user: str = ""
    password: str = ""
    host: str = ""
    port: int | None = None
    params: dict[str, str | None] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_secure(self) -> bool:
        return self.scheme.lower() == "sips"

    @property
    def transport(self) -> str | None:
        return self.params.get("transport")

    @property
    def user_param(self) -> str | None:
        return self.params.get("user")

    @property
    def method(self) -> str | None:
        return self.params.get("method")

    @property
    def maddr(self) -> str | None:
        return self.params.get("maddr")

    @property
    def ttl(self) -> int | None:
        v = self.params.get("ttl")
        return int(v) if v else None

    @property
    def lr(self) -> bool:
        return "lr" in self.params

    @property
    def host_port(self) -> str:
        if self.port:
            return f"{self.host}:{self.port}"
        return self.host

    @property
    def default_port(self) -> int:
        return 5061 if self.is_secure else 5060

    @property
    def effective_port(self) -> int:
        return self.port or self.default_port

    def to_string(self) -> str:
        """Serialize back to SIP URI string."""
        parts = [f"{self.scheme}:"]

        # userinfo
        if self.user:
            parts.append(self.user)
            if self.password:
                parts.append(f":{self.password}")
            parts.append("@")

        # host:port
        parts.append(self.host)
        if self.port:
            parts.append(f":{self.port}")

        # params
        for k, v in self.params.items():
            if v is None:
                parts.append(f";{k}")
            else:
                parts.append(f";{k}={v}")

        # headers
        if self.headers:
            header_parts = [f"{k}={v}" for k, v in self.headers.items()]
            parts.append("?" + "&".join(header_parts))

        return "".join(parts)

    def __str__(self) -> str:
        return self.to_string()

    @classmethod
    def parse(cls, uri: str) -> SipURI:
        """
        Parse a SIP/SIPS URI string.

        Handles the full RFC 3261 Section 19.1 format:
            sip:user:password@host:port;param=value;flag?header=value

        Args:
            uri: SIP URI string

        Returns:
            Parsed SipURI object
        """
        result = cls()

        if not uri:
            return result

        # Extract scheme
        match = re.match(r"^(sips?|tel):", uri, re.IGNORECASE)
        if not match:
            # No scheme — treat entire string as host
            result.host = uri
            return result

        result.scheme = match.group(1).lower()
        rest = uri[match.end():]

        # Extract headers (after ?)
        if "?" in rest:
            rest, header_str = rest.split("?", 1)
            for part in header_str.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result.headers[unquote(k)] = unquote(v)

        # Extract params (after ;)
        # Must be careful: params come after host:port, not after user
        # Split from the right is wrong — we need to find where hostport ends
        # Strategy: split on @ first to separate userinfo from hostport+params

        if "@" in rest:
            userinfo, hostpart = rest.split("@", 1)

            # Parse userinfo (user:password)
            if ":" in userinfo:
                result.user, result.password = userinfo.split(":", 1)
            else:
                result.user = userinfo
        else:
            hostpart = rest

        # Parse hostport;params from hostpart
        # Params are separated by ;
        parts = hostpart.split(";")
        hostport = parts[0]

        # Parse params
        for param in parts[1:]:
            if "=" in param:
                k, v = param.split("=", 1)
                result.params[k.lower()] = v
            else:
                result.params[param.lower()] = None

        # Parse host:port
        # Handle IPv6: [::1]:5060
        if hostport.startswith("["):
            # IPv6
            bracket_end = hostport.find("]")
            if bracket_end != -1:
                result.host = hostport[1:bracket_end]
                after = hostport[bracket_end + 1:]
                if after.startswith(":"):
                    result.port = int(after[1:])
        elif ":" in hostport:
            host, port_str = hostport.rsplit(":", 1)
            result.host = host
            try:
                result.port = int(port_str)
            except ValueError:
                # port is not a number, treat as part of host
                result.host = hostport
        else:
            result.host = hostport

        return result

    def to_dict(self) -> dict[str, str]:
        """Convert to dict (backward compat with MessageParser.parse_uri)."""
        params_str = ";".join(
            f"{k}={v}" if v else k for k, v in self.params.items()
        )
        return {
            "scheme": self.scheme,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": str(self.port) if self.port else "",
            "params": params_str,
        }


__all__ = ["SipURI"]
