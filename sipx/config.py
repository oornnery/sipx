from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any


@dataclass
class ClientConfig:
    """Configuration for SIP client behavior.

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
    headers: dict[str, str] | None = None
    params: dict[str, str] | None = None
    cookies: dict[str, str] | None = None

    def merge(self, overrides: dict[str, Any] | "ClientConfig" | None = None, **kwargs: Any) -> "ClientConfig":
        """Merge overrides into this config and return a new ClientConfig.

        Supports merging headers, params, cookies (dicts are shallow-merged).
        Simple fields are overridden.  None values in overrides are ignored
        so that ``merge(timeout=None)`` does not wipe the default.

        Args:
            overrides: Mapping or ClientConfig with override values.
            **kwargs: Additional override keyword arguments.

        Returns:
            New ClientConfig with merged values.
        """
        if overrides is None:
            overrides = {}

        if isinstance(overrides, ClientConfig):
            overrides = {
                f.name: getattr(overrides, f.name)
                for f in fields(ClientConfig)
            }
        else:
            overrides = dict(overrides)

        overrides.update(kwargs)

        current = {
            f.name: getattr(self, f.name)
            for f in fields(ClientConfig)
        }

        merged: dict[str, Any] = {}
        for f in fields(ClientConfig):
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

        return ClientConfig(**merged)
