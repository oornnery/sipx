from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass(slots=True)
class SessionDescription:
    """Minimal SDP representation focusing on a single media stream."""

    origin: str
    session_name: str
    connection: str
    timings: List[str]
    media: List[str]
    attributes: List[str]
    raw: str

    def media_payloads(self) -> List[str]:
        payloads: List[str] = []
        for line in self.media:
            if not line.startswith("m="):
                continue
            parts = line.split()
            if len(parts) >= 4:
                payloads.extend(parts[3:])
        return payloads


def build_audio_sdp(
    host: str,
    port: int,
    payloads: Sequence[int] | None = None,
    *,
    session_name: str = "sipx-session",
    direction: str = "sendrecv",
    fmtp: Optional[Dict[int, str]] = None,
) -> str:
    payload_list = [0, 8, 101] if payloads is None else list(payloads)
    body = [
        "v=0",
        f"o=- 0 0 IN IP4 {host}",
        f"s={session_name}",
        f"c=IN IP4 {host}",
        "t=0 0",
        f"m=audio {port} RTP/AVP {' '.join(str(p) for p in payload_list)}",
    ]
    codec_map = {
        0: "PCMU/8000",
        8: "PCMA/8000",
        9: "G722/8000",
        101: "telephone-event/8000",
    }
    for payload in payload_list:
        codec = codec_map.get(payload)
        if codec:
            body.append(f"a=rtpmap:{payload} {codec}")
        if fmtp and payload in fmtp:
            body.append(f"a=fmtp:{payload} {fmtp[payload]}")
    body.append(f"a={direction}")
    return "\r\n".join(body) + "\r\n"


def parse_sdp(raw: str) -> SessionDescription:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty SDP")

    origin = next((line[2:] for line in lines if line.startswith("o=")), "")
    session_name = next((line[2:] for line in lines if line.startswith("s=")), "")
    connection = next((line[2:] for line in lines if line.startswith("c=")), "")
    timings = [line[2:] for line in lines if line.startswith("t=")]
    media = [line for line in lines if line.startswith("m=")]
    attributes = [line for line in lines if line.startswith("a=")]
    return SessionDescription(
        origin=origin,
        session_name=session_name,
        connection=connection,
        timings=timings,
        media=media,
        attributes=attributes,
        raw="\r\n".join(lines) + "\r\n",
    )


def find_media_port(
    sdp: SessionDescription, media_type: str = "audio"
) -> Optional[int]:
    prefix = f"m={media_type} "
    for line in sdp.media:
        if not line.startswith(prefix):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


__all__ = [
    "SessionDescription",
    "build_audio_sdp",
    "parse_sdp",
    "find_media_port",
]
