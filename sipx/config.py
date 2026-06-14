"""Client settings for the sipx AsyncClient.

Holds connection defaults (transport, bind address, timeout, max message
size) and httpx-style request defaults (User-Agent, headers, params,
cookies) that are merged into every outgoing request. ``Settings.merge``
returns a new config with per-call overrides without mutating the base.

References:
    RFC 3261 §18 - Transport (UDP/TCP/TLS selection)
    RFC 3261 §20.41 - User-Agent header field
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any


@dataclass
class Settings:
    """Default SIP client settings merged into every outgoing request.

    Defaults match existing sipx behavior where applicable.
    New httpx-like fields (user_agent, headers, params, cookies) are added
    for the evolving API.

    Attributes:
        transport: Transport protocol ("udp", "tcp", or "tls").
        local_host: Local address to bind to.
        local_port: Local port to bind to (0 for auto-assign).
        timeout: Default timeout in seconds for SIP transactions.
        max_message_size: Maximum SIP message size in bytes.
        user_agent: User-Agent header value.
        from_uri: Default From URI (optional).
        contact_uri: Default Contact URI (optional).
        rport: Add the ``rport`` parameter to outgoing Via headers (RFC 3581).
        retransmit: Retransmit requests on unreliable transports (RFC 3261 §17).
        headers: Default headers merged into every request.
        params: Default query parameters.
        cookies: Default cookies (rarely used in SIP).
    """

    transport: str = "udp"
    local_host: str = "0.0.0.0"
    local_port: int = 0
    timeout: float = 30.0
    max_message_size: int = 65535
    user_agent: str = "sipx/2.0"
    from_uri: str | None = None
    contact_uri: str | None = None
    rport: bool = True
    retransmit: bool = True
    headers: dict[str, str] | None = None
    params: dict[str, str] | None = None
    cookies: dict[str, str] | None = None

    def merge(
        self, overrides: dict[str, Any] | "Settings" | None = None, **kwargs: Any
    ) -> "Settings":
        """Merge overrides into these settings and return a new ``Settings``.

        Supports merging headers, params, cookies (dicts are shallow-merged).
        Simple fields are overridden.  None values in overrides are ignored
        so that ``merge(timeout=None)`` does not wipe the default.

        Args:
            overrides: Mapping or Settings with override values.
            **kwargs: Additional override keyword arguments.

        Returns:
            New Settings with merged values.
        """
        if overrides is None:
            overrides = {}

        if isinstance(overrides, Settings):
            overrides = {
                f.name: getattr(overrides, f.name) for f in fields(Settings)
            }
        else:
            overrides = dict(overrides)

        overrides.update(kwargs)

        current = {f.name: getattr(self, f.name) for f in fields(Settings)}

        merged: dict[str, Any] = {}
        for f in fields(Settings):
            name = f.name
            old = current[name]
            new = overrides.get(name)

            if name in ("headers", "params", "cookies"):
                # Shallow-merge dict fields; None means "no addition".
                left = old if old is not None else {}
                right = new if new is not None else {}
                merged[name] = {**left, **right}
                if not merged[name]:
                    merged[name] = None
            elif new is not None:
                merged[name] = new
            else:
                merged[name] = deepcopy(old)

        return Settings(**merged)


# Deprecated alias; removed in a future release.
ClientConfig = Settings
