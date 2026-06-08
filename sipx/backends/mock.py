from __future__ import annotations

from uuid import uuid4

from sipx.core.actor import Actor, Call, CallLeg
from sipx.core.capabilities import BackendCapability


class MockBackend:
    """Deterministic backend for unit tests and local scenario skeletons."""

    capabilities = frozenset(
        {
            BackendCapability.ARTIFACTS,
            BackendCapability.CALL_CONTROL,
            BackendCapability.DTMF,
            BackendCapability.MOCK,
            BackendCapability.TIMELINE,
        }
    )

    def supports(self, capability: BackendCapability | str) -> bool:
        return BackendCapability(capability) in self.capabilities

    async def call(self, actor: Actor, target: str, **metadata: object) -> Call:
        call_id = str(metadata.get("call_id") or f"mock-{uuid4().hex}")
        leg = CallLeg(
            leg_id=f"{call_id}-leg-1",
            actor_id=actor.actor_id,
            backend_name=actor.backend_name,
            metadata={"target": target},
        )
        call = Call(
            call_id=call_id,
            actor_id=actor.actor_id,
            target=target,
            backend=self,
            timeline=actor.harness.timeline,
            legs=[leg],
            metadata=dict(metadata),
        )

        actor.harness.timeline.record(
            "call",
            "started",
            actor_id=actor.actor_id,
            call_id=call_id,
            leg_id=leg.leg_id,
            data={"target": target, "backend": actor.backend_name},
        )
        actor.harness.timeline.record(
            "sip",
            "final_response",
            actor_id=actor.actor_id,
            call_id=call_id,
            leg_id=leg.leg_id,
            data={"status_code": 200, "reason": "OK", "mock": True},
        )
        return call

    async def hangup(self, call: Call) -> None:
        call.timeline.record(
            "call",
            "ended",
            actor_id=call.actor_id,
            call_id=call.call_id,
            leg_id=call.primary_leg_id,
            data={"reason": "hangup", "mock": True},
        )

    async def send_dtmf(self, call: Call, digits: str) -> None:
        call.timeline.record(
            "dtmf",
            "tx",
            actor_id=call.actor_id,
            call_id=call.call_id,
            leg_id=call.primary_leg_id,
            data={"digits": digits, "mock": True},
        )
