from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence


@dataclass(slots=True)
class RTPStreamConfig:
    payloads: Sequence[int]
    clock_rate: int = 8000
    direction: str = "sendrecv"
    fmtp: Optional[dict[int, str]] = None


def port_sequence(start: int = 40000, stop: int = 50000) -> Iterator[int]:
    if start % 2:
        start += 1
    for port in itertools.count(start, 2):
        if port >= stop:
            break
        yield port


def default_stream() -> RTPStreamConfig:
    return RTPStreamConfig(payloads=(0, 8, 101), clock_rate=8000, direction="sendrecv")


__all__ = ["RTPStreamConfig", "port_sequence", "default_stream"]
