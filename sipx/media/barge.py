"""Barge-in policy for interrupting audio playback.

Models whether in-progress playback should be interrupted when the remote
party starts speaking or sends a DTMF digit, a common IVR / voice-bot
behavior. A pure policy object with no I/O.

References:
    RFC 4733 - RTP Payload for DTMF Digits (DTMF interruption signal)
    RFC 3550 - RTP (speech detected on the audio plane)
"""

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
