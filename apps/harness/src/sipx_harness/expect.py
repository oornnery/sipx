from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sipx_harness.capabilities import (
    RuntimeCapability,
    UnsupportedExpectation,
    target_supports,
)
from sipx_harness.timeline import Timeline
from sipx_harness.verdict import ExpectationResult


class ExpectationFailure(AssertionError):
    def __init__(self, result: ExpectationResult) -> None:
        self.result = result
        super().__init__(result.reason or result.name)


Evaluator = Callable[[], bool | Awaitable[bool]]


@dataclass(slots=True)
class PendingExpectation:
    name: str
    evaluator: Evaluator
    target: object | None = None
    required_capability: RuntimeCapability | None = None
    details: dict[str, Any] = field(default_factory=dict)

    async def within(
        self,
        seconds: float = 0,
        *,
        poll_interval: float = 0.01,
    ) -> ExpectationResult:
        self._check_capability()
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            if await self._matches():
                return self._result("passed", f"{self.name} matched within {seconds}s")
            if time.monotonic() >= deadline:
                self._fail(f"{self.name} did not match within {seconds}s")
            await asyncio.sleep(poll_interval)

    async def during(
        self,
        seconds: float,
        *,
        poll_interval: float = 0.01,
    ) -> ExpectationResult:
        self._check_capability()
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            if not await self._matches():
                self._fail(f"{self.name} did not hold during {seconds}s")
            if time.monotonic() >= deadline:
                return self._result("passed", f"{self.name} held during {seconds}s")
            await asyncio.sleep(poll_interval)

    async def not_before(
        self,
        seconds: float,
        *,
        poll_interval: float = 0.01,
    ) -> ExpectationResult:
        self._check_capability()
        deadline = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < deadline:
            if await self._matches():
                self._fail(f"{self.name} matched before {seconds}s")
            await asyncio.sleep(poll_interval)
        return self._result("passed", f"{self.name} did not match before {seconds}s")

    async def _matches(self) -> bool:
        value = self.evaluator()
        if inspect.isawaitable(value):
            value = await value
        return bool(value)

    def _check_capability(self) -> None:
        if self.required_capability is None or self.target is None:
            return
        if not target_supports(self.target, self.required_capability):
            raise UnsupportedExpectation(self.required_capability, self.target)

    def _result(self, status: str, reason: str) -> ExpectationResult:
        return ExpectationResult(
            name=self.name,
            status=status,
            reason=reason,
            details=dict(self.details),
        )

    def _fail(self, reason: str) -> None:
        raise ExpectationFailure(self._result("failed", reason))


class ExpectationTarget:
    def __init__(self, target: object) -> None:
        self.target = target

    def capability(self, capability: RuntimeCapability | str) -> PendingExpectation:
        normalized = RuntimeCapability(capability)
        return PendingExpectation(
            name=f"capability {normalized.value}",
            evaluator=lambda: target_supports(self.target, normalized),
            target=self.target,
            required_capability=normalized,
            details={"capability": normalized.value},
        )

    def to_support(self, capability: RuntimeCapability | str) -> PendingExpectation:
        return self.capability(capability)

    def event(self, category: str, name: str) -> PendingExpectation:
        timeline = self._timeline()
        return PendingExpectation(
            name=f"event {category}.{name}",
            evaluator=lambda: any(
                event.category == category and event.name == name
                for event in timeline.events
            ),
            target=timeline,
            details={"category": category, "name": name},
        )

    def truthy(
        self,
        predicate: Callable[[object], bool | Awaitable[bool]],
        *,
        name: str = "truthy predicate",
    ) -> PendingExpectation:
        async def evaluate() -> bool:
            value = predicate(self.target)
            if inspect.isawaitable(value):
                value = await value
            return bool(value)

        return PendingExpectation(name=name, evaluator=evaluate, target=self.target)

    def _timeline(self) -> Timeline:
        if isinstance(self.target, Timeline):
            return self.target
        timeline = getattr(self.target, "timeline", None)
        if isinstance(timeline, Timeline):
            return timeline
        raise TypeError(f"{type(self.target).__name__} does not expose a Timeline")


def expect(target: object) -> ExpectationTarget:
    return ExpectationTarget(target)
