from __future__ import annotations

from enum import StrEnum
from typing import Any


class RuntimeCapability(StrEnum):
    ARTIFACTS = "artifacts"
    ASTERISK_ARI = "asterisk_ari"
    CALL_CONTROL = "call_control"
    DTMF = "dtmf"
    MEDIA = "media"
    MOCK = "mock"
    REPLAY = "replay"
    SIP_WIRE = "sip_wire"
    TIMELINE = "timeline"


class UnsupportedExpectation(AssertionError):
    def __init__(self, capability: RuntimeCapability | str, target: object) -> None:
        self.capability = RuntimeCapability(capability)
        self.target = target
        target_name = type(target).__name__
        super().__init__(
            f"{target_name} does not support expectation capability "
            f"{self.capability.value!r}"
        )


def target_supports(target: object, capability: RuntimeCapability | str) -> bool:
    normalized = RuntimeCapability(capability)
    supports = getattr(target, "supports", None)
    if callable(supports):
        return bool(supports(normalized))

    capabilities: Any = getattr(target, "capabilities", ())
    return normalized in {RuntimeCapability(item) for item in capabilities}
