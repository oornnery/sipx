from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sipx_harness.actor import Actor


@dataclass(frozen=True, slots=True)
class MixedActorSpec:
    actor_id: str
    runtime: str
    kind: str = "actor"
    metadata: dict[str, Any] = field(default_factory=dict)


class MixedScenario:
    def __init__(self, *actors: MixedActorSpec, name: str = "mixed") -> None:
        if not actors:
            raise ValueError("mixed scenario requires at least one actor")
        self.name = name
        self.actors = tuple(actors)

    def bind(self, harness: Any) -> dict[str, Actor]:
        bound: dict[str, Actor] = {}
        for spec in self.actors:
            actor = harness.actor(
                spec.actor_id,
                runtime=spec.runtime,
                kind=spec.kind,
                **spec.metadata,
            )
            harness.timeline.record(
                "mixed_scenario",
                "actor_bound",
                actor_id=actor.actor_id,
                data={"runtime": actor.runtime_name, "kind": actor.kind},
            )
            bound[actor.actor_id] = actor
        return bound
