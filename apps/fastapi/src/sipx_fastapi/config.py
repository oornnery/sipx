"""Environment-based settings for the sipx FastAPI service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved configuration from SIPX_* environment variables."""

    aor: str
    registrar: str
    username: str
    password: str
    local_host: str
    local_port: int
    timeout: float
    transport: str
    user_agent: str
    host: str
    port: int

    @property
    def auth_configured(self) -> bool:
        return bool(self.username and self.password)


def load_settings() -> Settings:
    """Load service settings from environment variables."""
    return Settings(
        aor=os.getenv("SIPX_AOR", "sip:1001@example.com"),
        registrar=os.getenv("SIPX_REGISTRAR", "sip:example.com:5060"),
        username=os.getenv("SIPX_USERNAME", ""),
        password=os.getenv("SIPX_PASSWORD", ""),
        local_host=os.getenv("SIPX_LOCAL_HOST", "0.0.0.0"),
        local_port=int(os.getenv("SIPX_LOCAL_PORT", "0")),
        timeout=float(os.getenv("SIPX_TIMEOUT", "10")),
        transport=os.getenv("SIPX_TRANSPORT", "udp"),
        user_agent=os.getenv("SIPX_USER_AGENT", "sipx-fastapi/0.1"),
        host=os.getenv("SIPX_FASTAPI_HOST", "127.0.0.1"),
        port=int(os.getenv("SIPX_FASTAPI_PORT", "8000")),
    )
