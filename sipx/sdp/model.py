"""Structured SDP session description and serialization.

Dataclasses for SDP lines (origin, connection, time, media, codecs) plus an
``AudioMedia`` convenience view and ``to_sdp`` text generation. Supports both
structured media descriptions and a simplified audio shortcut.

References:
    RFC 4566 §5 - SDP Specification (v=, o=, s=, c=, t=, m=, a= fields)
    RFC 4566 §6 - SDP Attributes (rtpmap, fmtp, direction)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SdpDirection = Literal["sendrecv", "sendonly", "recvonly", "inactive"]
DIRECTIONS = {"sendrecv", "sendonly", "recvonly", "inactive"}


@dataclass(frozen=True, slots=True)
class SdpCodec:
    payload_type: int
    name: str
    clock_rate: int
    channels: int = 1
    fmtp: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.payload_type <= 127:
            raise ValueError("payload_type must be between 0 and 127")
        if not self.name:
            raise ValueError("codec name is required")
        if self.clock_rate <= 0:
            raise ValueError("clock_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")

    @property
    def rtpmap(self) -> str:
        channel_suffix = f"/{self.channels}" if self.channels != 1 else ""
        return f"{self.payload_type} {self.name}/{self.clock_rate}{channel_suffix}"


@dataclass(frozen=True, slots=True)
class Origin:
    """Structured SDP origin (o= line)."""

    username: str
    session_id: str
    session_version: str
    nettype: str
    addrtype: str
    address: str


@dataclass(frozen=True, slots=True)
class Connection:
    """Structured SDP connection (c= line)."""

    nettype: str
    addrtype: str
    address: str


@dataclass(frozen=True, slots=True)
class Time:
    """Structured SDP time (t= line)."""

    start: int
    stop: int


@dataclass(slots=True)
class MediaDescription:
    """Structured SDP media description (m= line with attributes)."""

    media_type: str
    port: int
    proto: str
    fmt: list[str]
    attributes: list[tuple[str, str | None]] = field(default_factory=list)


@dataclass(slots=True)
class AudioMedia:
    port: int
    payload_types: list[int]
    protocol: str = "RTP/AVP"
    codecs: dict[int, SdpCodec] = field(default_factory=dict)
    direction: SdpDirection = "sendrecv"

    def __post_init__(self) -> None:
        if not 0 <= self.port <= 65535:
            raise ValueError("audio port must be between 0 and 65535")
        self.payload_types = list(self.payload_types)
        if self.direction not in DIRECTIONS:
            raise ValueError(f"unsupported SDP direction: {self.direction}")

    def codec_by_name(self, name: str) -> SdpCodec | None:
        target = name.upper()
        for codec in self.codecs.values():
            if codec.name.upper() == target:
                return codec
        return None

    def has_codec(self, name: str) -> bool:
        return self.codec_by_name(name) is not None

    def has_dtmf_transport(self) -> bool:
        return self.has_codec("telephone-event")


@dataclass(slots=True)
class SessionDescription:
    """SDP session description supporting both structured and legacy APIs."""

    origin: str | Origin = ""
    session_name: str = "-"
    connection_address: str = ""
    audio: AudioMedia | None = None
    version: int = 0
    connection: Connection | None = None
    time: Time | None = None
    media: list[MediaDescription] = field(default_factory=list)

    def has_codec(self, name: str) -> bool:
        return bool(self.audio and self.audio.has_codec(name))

    def has_dtmf_transport(self) -> bool:
        return bool(self.audio and self.audio.has_dtmf_transport())

    def to_sdp(self) -> str:
        """Generate SDP text from structured or legacy fields."""
        lines = [f"v={self.version}"]

        if isinstance(self.origin, Origin):
            lines.append(
                f"o={self.origin.username} {self.origin.session_id} "
                f"{self.origin.session_version} {self.origin.nettype} "
                f"{self.origin.addrtype} {self.origin.address}"
            )
        else:
            lines.append(f"o={self.origin}")

        lines.append(f"s={self.session_name}")

        if self.connection is not None:
            lines.append(
                f"c={self.connection.nettype} {self.connection.addrtype} "
                f"{self.connection.address}"
            )
        elif self.connection_address:
            lines.append(f"c=IN IP4 {self.connection_address}")

        if self.time is not None:
            lines.append(f"t={self.time.start} {self.time.stop}")
        else:
            lines.append("t=0 0")

        # Media lines: prefer structured media, fall back to legacy audio
        if self.media:
            for md in self.media:
                fmt_str = " ".join(md.fmt)
                lines.append(f"m={md.media_type} {md.port} {md.proto} {fmt_str}")
                for attr_name, attr_value in md.attributes:
                    if attr_value is not None:
                        lines.append(f"a={attr_name}:{attr_value}")
                    else:
                        lines.append(f"a={attr_name}")
        elif self.audio:
            payloads = " ".join(str(payload) for payload in self.audio.payload_types)
            lines.append(f"m=audio {self.audio.port} {self.audio.protocol} {payloads}")
            lines.append(f"a={self.audio.direction}")
            for payload_type in self.audio.payload_types:
                codec = self.audio.codecs.get(payload_type)
                if codec is None:
                    continue
                lines.append(f"a=rtpmap:{codec.rtpmap}")
                if codec.fmtp:
                    lines.append(f"a=fmtp:{codec.payload_type} {codec.fmtp}")

        return "\r\n".join(lines) + "\r\n"
