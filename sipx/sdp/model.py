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
    origin: str
    session_name: str
    connection_address: str
    audio: AudioMedia | None = None
    version: int = 0

    def has_codec(self, name: str) -> bool:
        return bool(self.audio and self.audio.has_codec(name))

    def has_dtmf_transport(self) -> bool:
        return bool(self.audio and self.audio.has_dtmf_transport())

    def to_sdp(self) -> str:
        lines = [
            f"v={self.version}",
            f"o={self.origin}",
            f"s={self.session_name}",
            f"c=IN IP4 {self.connection_address}",
            "t=0 0",
        ]
        if self.audio:
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
