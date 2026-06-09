from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from sipx.core.capabilities import (
    BackendCapability,
    UnsupportedExpectation,
    target_supports,
)
from sipx.core.timeline import Timeline


@dataclass(slots=True)
class CallLeg:
    leg_id: str
    actor_id: str
    backend_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg_id": self.leg_id,
            "actor_id": self.actor_id,
            "backend_name": self.backend_name,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class Call:
    call_id: str
    actor_id: str
    target: str
    backend: object
    timeline: Timeline
    legs: list[CallLeg] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_leg_id(self) -> str | None:
        return self.legs[0].leg_id if self.legs else None

    async def hangup(self) -> None:
        hangup = getattr(self.backend, "hangup", None)
        if not callable(hangup):
            raise UnsupportedExpectation(BackendCapability.CALL_CONTROL, self.backend)
        await hangup(self)

    async def send_dtmf(self, digits: str) -> None:
        if not target_supports(self.backend, BackendCapability.DTMF):
            raise UnsupportedExpectation(BackendCapability.DTMF, self.backend)
        send_dtmf = getattr(self.backend, "send_dtmf", None)
        if not callable(send_dtmf):
            raise UnsupportedExpectation(BackendCapability.DTMF, self.backend)
        await send_dtmf(self, digits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "actor_id": self.actor_id,
            "target": self.target,
            "legs": [leg.to_dict() for leg in self.legs],
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class Actor:
    actor_id: str
    harness: Any
    backend_name: str = "mock"
    kind: str = "actor"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def backend(self) -> object:
        return self.harness.backend(self.backend_name)

    def softphone(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("softphone", backend, metadata)

    def asterisk(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("asterisk", backend, metadata)

    def remote(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("remote", backend, metadata)

    def ai_agent(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("ai_agent", backend, metadata)

    def fake_carrier(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("fake_carrier", backend, metadata)

    def queue(self, *, backend: str | None = None, **metadata: Any) -> Actor:
        return self._clone("queue", backend, metadata)

    async def call(self, target: str, **metadata: Any) -> Call:
        backend = self.backend
        if not target_supports(backend, BackendCapability.CALL_CONTROL):
            raise UnsupportedExpectation(BackendCapability.CALL_CONTROL, backend)
        call = getattr(backend, "call", None)
        if not callable(call):
            raise UnsupportedExpectation(BackendCapability.CALL_CONTROL, backend)
        return await call(self, target, **metadata)

    def _clone(
        self,
        kind: str,
        backend: str | None,
        metadata: Mapping[str, Any],
    ) -> Actor:
        merged = dict(self.metadata)
        merged.update(metadata)
        return replace(
            self,
            kind=kind,
            backend_name=backend or self.backend_name,
            metadata=merged,
        )
