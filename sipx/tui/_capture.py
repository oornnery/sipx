"""Packet capture engine for SIP message tracing (sngrep-style)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Direction(Enum):
    """Packet direction."""

    SENT = ">>>"
    RECV = "<<<"


@dataclass(slots=True)
class CapturedPacket:
    """A single captured SIP packet."""

    timestamp: float
    direction: Direction
    src_host: str
    src_port: int
    dst_host: str
    dst_port: int
    protocol: str
    raw: bytes
    method: str = ""
    status_code: int = 0
    reason: str = ""
    call_id: str = ""
    cseq: str = ""
    from_header: str = ""
    to_header: str = ""
    content_length: int = 0

    @property
    def summary(self) -> str:
        """One-line summary like sngrep."""
        if self.method:
            return self.method
        if self.status_code:
            return f"{self.status_code} {self.reason}"
        return "???"

    @property
    def src(self) -> str:
        return f"{self.src_host}:{self.src_port}"

    @property
    def dst(self) -> str:
        return f"{self.dst_host}:{self.dst_port}"

    @property
    def size(self) -> int:
        return len(self.raw)

    @property
    def decoded(self) -> str:
        return self.raw.decode("utf-8", errors="replace")

    @classmethod
    def from_raw(
        cls,
        raw: bytes,
        direction: Direction,
        src_host: str,
        src_port: int,
        dst_host: str,
        dst_port: int,
        protocol: str = "UDP",
    ) -> CapturedPacket:
        """Parse raw SIP bytes into a CapturedPacket."""
        text = raw.decode("utf-8", errors="replace")
        lines = text.replace("\r\n", "\n").split("\n")

        method = ""
        status_code = 0
        reason = ""
        call_id = ""
        cseq = ""
        from_hdr = ""
        to_hdr = ""
        content_length = 0

        if lines:
            first = lines[0]
            # Request: METHOD URI SIP/2.0
            if first.startswith("SIP/"):
                parts = first.split(None, 2)
                if len(parts) >= 2:
                    try:
                        status_code = int(parts[1])
                    except ValueError:
                        pass
                    if len(parts) >= 3:
                        reason = parts[2]
            else:
                parts = first.split(None, 2)
                if parts:
                    method = parts[0]

        for line in lines[1:]:
            if not line or line[0] in (" ", "\t"):
                continue
            low = line.lower()
            if low.startswith("call-id:") or low.startswith("i:"):
                call_id = line.split(":", 1)[1].strip()
            elif low.startswith("cseq:"):
                cseq = line.split(":", 1)[1].strip()
            elif low.startswith("from:") or low.startswith("f:"):
                from_hdr = line.split(":", 1)[1].strip()
            elif low.startswith("to:") or low.startswith("t:"):
                to_hdr = line.split(":", 1)[1].strip()
            elif low.startswith("content-length:") or low.startswith("l:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        return cls(
            timestamp=time.monotonic(),
            direction=direction,
            src_host=src_host,
            src_port=src_port,
            dst_host=dst_host,
            dst_port=dst_port,
            protocol=protocol,
            raw=raw,
            method=method,
            status_code=status_code,
            reason=reason,
            call_id=call_id,
            cseq=cseq,
            from_header=from_hdr,
            to_header=to_hdr,
            content_length=content_length,
        )


@dataclass
class PacketStore:
    """Thread-safe packet store with call-id grouping."""

    _packets: list[CapturedPacket] = field(default_factory=list)
    _by_call_id: dict[str, list[CapturedPacket]] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.monotonic)

    @property
    def packets(self) -> list[CapturedPacket]:
        return self._packets

    def add(self, pkt: CapturedPacket) -> None:
        """Add a captured packet."""
        self._packets.append(pkt)
        if pkt.call_id:
            self._by_call_id.setdefault(pkt.call_id, []).append(pkt)

    def get_dialog(self, call_id: str) -> list[CapturedPacket]:
        """Get all packets for a Call-ID."""
        return self._by_call_id.get(call_id, [])

    @property
    def call_ids(self) -> list[str]:
        """All unique Call-IDs seen."""
        return list(self._by_call_id.keys())

    def clear(self) -> None:
        """Clear all captured packets."""
        self._packets.clear()
        self._by_call_id.clear()
        self._start_time = time.monotonic()

    def elapsed(self, pkt: CapturedPacket) -> float:
        """Seconds since capture started."""
        return pkt.timestamp - self._start_time

    def __len__(self) -> int:
        return len(self._packets)
