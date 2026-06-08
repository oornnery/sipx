from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BargeInSignal(StrEnum):
    SPEECH = "speech"
    DTMF = "dtmf"


@dataclass(frozen=True, slots=True)
class BargeInPolicy:
    interruptible: bool = True
    interrupt_on_speech: bool = True
    interrupt_on_dtmf: bool = True
    clear_output_on_interrupt: bool = True

    def should_interrupt(self, signal: BargeInSignal | str) -> bool:
        if not self.interruptible:
            return False

        normalized = BargeInSignal(signal)
        if normalized is BargeInSignal.SPEECH:
            return self.interrupt_on_speech
        if normalized is BargeInSignal.DTMF:
            return self.interrupt_on_dtmf
        return False
