from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


ScenarioFunc = Callable[[Any], Awaitable[Any] | Any]


@dataclass(slots=True)
class Scenario:
    name: str
    func: ScenarioFunc
    metadata: dict[str, Any] = field(default_factory=dict)

    async def run(self, harness: Any) -> Any:
        harness.timeline.record(
            "scenario",
            "started",
            data={"name": self.name},
        )
        try:
            result = self.func(harness)
            if inspect.isawaitable(result):
                result = await result
            return result
        finally:
            harness.timeline.record(
                "scenario",
                "ended",
                data={"name": self.name},
            )


def scenario(name: str | ScenarioFunc | None = None, **metadata: Any):
    if callable(name):
        func = name
        return Scenario(name=func.__name__, func=func, metadata=dict(metadata))

    def decorate(func: ScenarioFunc) -> Scenario:
        return Scenario(
            name=str(name or func.__name__),
            func=func,
            metadata=dict(metadata),
        )

    return decorate
