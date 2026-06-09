from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from sipx_harness.capabilities import RuntimeCapability

if TYPE_CHECKING:
    from sipx_harness.actor import Actor, Call


class Runtime(ABC):
    """Base contract for harness runtimes."""

    capabilities: ClassVar[frozenset[RuntimeCapability]] = frozenset()

    def supports(self, capability: RuntimeCapability | str) -> bool:
        return RuntimeCapability(capability) in self.capabilities


class CallRuntime(Runtime):
    """Runtime that can originate and hang up harness calls."""

    @abstractmethod
    async def call(self, actor: Actor, target: str, **metadata: object) -> Call:
        raise NotImplementedError

    @abstractmethod
    async def hangup(self, call: Call) -> None:
        raise NotImplementedError


class DtmfRuntime(Runtime):
    """Runtime that can send DTMF for a harness call."""

    @abstractmethod
    async def send_dtmf(self, call: Call, digits: str) -> None:
        raise NotImplementedError
