"""Shared DNS resolution data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(order=True)
class ResolvedTarget:
    """A resolved SIP target with priority/weight for load balancing."""

    priority: int = 0
    weight: int = 0
    host: str = field(default="", compare=False)
    port: int = field(default=5060, compare=False)
    transport: str = field(default="UDP", compare=False)

    def __repr__(self) -> str:
        return f"{self.transport}:{self.host}:{self.port} (pri={self.priority} w={self.weight})"
