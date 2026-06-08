from __future__ import annotations

from dataclasses import dataclass


DIGIT_TO_EVENT = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "*": 10,
    "#": 11,
    "A": 12,
    "B": 13,
    "C": 14,
    "D": 15,
}
EVENT_TO_DIGIT = {event: digit for digit, event in DIGIT_TO_EVENT.items()}


@dataclass(frozen=True, slots=True)
class DtmfEvent:
    digit: str
    event: int
    end: bool
    volume: int
    duration: int

    def __post_init__(self) -> None:
        if self.event not in EVENT_TO_DIGIT:
            raise ValueError("unsupported DTMF event")
        if self.digit != EVENT_TO_DIGIT[self.event]:
            raise ValueError("DTMF digit does not match event code")
        if not 0 <= self.volume <= 63:
            raise ValueError("DTMF volume must be between 0 and 63")
        if not 0 <= self.duration <= 65535:
            raise ValueError("DTMF duration must be between 0 and 65535")


def encode_dtmf_event(
    digit: str,
    *,
    end: bool = False,
    volume: int = 10,
    duration: int = 160,
) -> bytes:
    normalized = digit.upper()
    try:
        event = DIGIT_TO_EVENT[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported DTMF digit: {digit!r}") from exc
    dtmf = DtmfEvent(
        digit=normalized,
        event=event,
        end=end,
        volume=volume,
        duration=duration,
    )
    flags = (0x80 if dtmf.end else 0) | dtmf.volume
    return bytes([dtmf.event, flags, (dtmf.duration >> 8) & 0xFF, dtmf.duration & 0xFF])


def decode_dtmf_event(payload: bytes) -> DtmfEvent:
    if len(payload) != 4:
        raise ValueError("DTMF event payload must be exactly 4 bytes")
    event = payload[0]
    flags = payload[1]
    duration = (payload[2] << 8) | payload[3]
    try:
        digit = EVENT_TO_DIGIT[event]
    except KeyError as exc:
        raise ValueError(f"unsupported DTMF event: {event}") from exc
    return DtmfEvent(
        digit=digit,
        event=event,
        end=bool(flags & 0x80),
        volume=flags & 0x3F,
        duration=duration,
    )
