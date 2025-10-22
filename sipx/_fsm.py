from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CallState(str, Enum):
    INITIATING = "initiating"
    PROCEEDING = "proceeding"
    CONNECTED = "connected"
    TERMINATED = "terminated"
    FAILED = "failed"


class TransactionState(str, Enum):
    TRYING = "trying"
    CALLING = "calling"
    PROCEEDING = "proceeding"
    COMPLETED = "completed"
    ACCEPTED = "accepted"
    TERMINATED = "terminated"


@dataclass(slots=True)
class StateChange:
    previous: CallState
    current: CallState
    reason: Optional[str] = None


class CallFSM:
    """Lightweight helper to keep track of SIP call state transitions."""

    __slots__ = ("_state",)

    def __init__(self) -> None:
        self._state = CallState.INITIATING

    @property
    def state(self) -> CallState:
        return self._state

    def advance_to(
        self, target: CallState, *, reason: Optional[str] = None
    ) -> StateChange:
        previous = self._state
        if previous == target:
            return StateChange(previous, target, reason)
        # Basic monotonic rules
        allowed = {
            CallState.INITIATING: {
                CallState.PROCEEDING,
                CallState.CONNECTED,
                CallState.FAILED,
                CallState.TERMINATED,
            },
            CallState.PROCEEDING: {
                CallState.CONNECTED,
                CallState.FAILED,
                CallState.TERMINATED,
            },
            CallState.CONNECTED: {CallState.TERMINATED, CallState.FAILED},
            CallState.TERMINATED: set(),
            CallState.FAILED: {CallState.TERMINATED},
        }
        if target not in allowed[self._state]:
            raise ValueError(f"Invalid state transition: {self._state} -> {target}")
        self._state = target
        return StateChange(previous, target, reason)


__all__ = ["CallFSM", "CallState", "StateChange", "TransactionState"]
