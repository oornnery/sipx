from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from sipx_harness.capabilities import (
    RuntimeCapability,
    UnsupportedExpectation,
    target_supports,
)
from sipx_harness.timeline import Timeline


@dataclass(slots=True)
class CallLeg:
    leg_id: str
    actor_id: str
    runtime_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg_id": self.leg_id,
            "actor_id": self.actor_id,
            "runtime_name": self.runtime_name,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class Call:
    call_id: str
    actor_id: str
    target: str
    runtime: object
    timeline: Timeline
    legs: list[CallLeg] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_leg_id(self) -> str | None:
        return self.legs[0].leg_id if self.legs else None

    async def hangup(self) -> None:
        hangup = getattr(self.runtime, "hangup", None)
        if not callable(hangup):
            raise UnsupportedExpectation(RuntimeCapability.CALL_CONTROL, self.runtime)
        await hangup(self)

    async def send_dtmf(self, digits: str) -> None:
        if not target_supports(self.runtime, RuntimeCapability.DTMF):
            raise UnsupportedExpectation(RuntimeCapability.DTMF, self.runtime)
        send_dtmf = getattr(self.runtime, "send_dtmf", None)
        if not callable(send_dtmf):
            raise UnsupportedExpectation(RuntimeCapability.DTMF, self.runtime)
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
    runtime_name: str = "mock"
    kind: str = "actor"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def runtime(self) -> object:
        return self.harness.runtime(self.runtime_name)

    def softphone(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("softphone", runtime, metadata)

    def asterisk(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("asterisk", runtime, metadata)

    def remote(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("remote", runtime, metadata)

    def ai_agent(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("ai_agent", runtime, metadata)

    def fake_carrier(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("fake_carrier", runtime, metadata)

    def queue(self, *, runtime: str | None = None, **metadata: Any) -> Actor:
        return self._clone("queue", runtime, metadata)

    async def call(self, target: str, **metadata: Any) -> Call:
        runtime = self.runtime
        if not target_supports(runtime, RuntimeCapability.CALL_CONTROL):
            raise UnsupportedExpectation(RuntimeCapability.CALL_CONTROL, runtime)
        call = getattr(runtime, "call", None)
        if not callable(call):
            raise UnsupportedExpectation(RuntimeCapability.CALL_CONTROL, runtime)
        return await call(self, target, **metadata)

    def _clone(
        self,
        kind: str,
        runtime: str | None,
        metadata: Mapping[str, Any],
    ) -> Actor:
        merged = dict(self.metadata)
        merged.update(metadata)
        return replace(
            self,
            kind=kind,
            runtime_name=runtime or self.runtime_name,
            metadata=merged,
        )
