from __future__ import annotations

from sipx.sdp.model import (
    DIRECTIONS,
    AudioMedia,
    SdpCodec,
    SdpDirection,
    SessionDescription,
)


STATIC_PAYLOADS = {
    0: SdpCodec(payload_type=0, name="PCMU", clock_rate=8000),
    8: SdpCodec(payload_type=8, name="PCMA", clock_rate=8000),
}


class SdpParseError(ValueError):
    pass


def parse_sdp(raw: str | bytes) -> SessionDescription:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    session = SessionDescription(
        origin="- 0 0 IN IP4 0.0.0.0", session_name="-", connection_address="0.0.0.0"
    )
    current_audio: AudioMedia | None = None

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        if not raw_line:
            continue
        if len(raw_line) < 2 or raw_line[1] != "=":
            raise SdpParseError(f"invalid SDP line: {raw_line!r}")
        prefix = raw_line[0]
        value = raw_line[2:]

        if prefix == "v":
            session.version = int(value)
        elif prefix == "o":
            session.origin = value
        elif prefix == "s":
            session.session_name = value
        elif prefix == "c":
            session.connection_address = _parse_connection_address(value)
        elif prefix == "m":
            current_audio = _parse_audio_media(value)
            session.audio = current_audio
        elif prefix == "a" and current_audio is not None:
            _parse_audio_attribute(current_audio, value)

    if session.audio is not None:
        for payload_type in session.audio.payload_types:
            if (
                payload_type in STATIC_PAYLOADS
                and payload_type not in session.audio.codecs
            ):
                session.audio.codecs[payload_type] = STATIC_PAYLOADS[payload_type]
    return session


def _parse_connection_address(value: str) -> str:
    parts = value.split()
    if len(parts) != 3 or parts[0] != "IN" or parts[1] not in {"IP4", "IP6"}:
        raise SdpParseError(f"unsupported SDP connection: {value!r}")
    return parts[2]


def _parse_audio_media(value: str) -> AudioMedia:
    parts = value.split()
    if len(parts) < 4 or parts[0] != "audio":
        raise SdpParseError(f"unsupported SDP media: {value!r}")
    return AudioMedia(
        port=int(parts[1]),
        protocol=parts[2],
        payload_types=[int(payload) for payload in parts[3:]],
    )


def _parse_audio_attribute(audio: AudioMedia, value: str) -> None:
    if value in DIRECTIONS:
        audio.direction = _sdp_direction(value)
        return
    if value.startswith("rtpmap:"):
        payload_text, codec_text = value.removeprefix("rtpmap:").split(maxsplit=1)
        payload_type = int(payload_text)
        name, clock_rate, channels = _parse_rtpmap_codec(codec_text)
        existing = audio.codecs.get(payload_type)
        audio.codecs[payload_type] = SdpCodec(
            payload_type=payload_type,
            name=name,
            clock_rate=clock_rate,
            channels=channels,
            fmtp=existing.fmtp if existing is not None else None,
        )
        return
    if value.startswith("fmtp:"):
        payload_text, fmtp = value.removeprefix("fmtp:").split(maxsplit=1)
        payload_type = int(payload_text)
        existing = audio.codecs.get(payload_type)
        if existing is None:
            audio.codecs[payload_type] = SdpCodec(
                payload_type=payload_type,
                name="unknown",
                clock_rate=8000,
                fmtp=fmtp,
            )
        else:
            audio.codecs[payload_type] = SdpCodec(
                payload_type=existing.payload_type,
                name=existing.name,
                clock_rate=existing.clock_rate,
                channels=existing.channels,
                fmtp=fmtp,
            )


def _parse_rtpmap_codec(value: str) -> tuple[str, int, int]:
    parts = value.split("/")
    if len(parts) not in {2, 3}:
        raise SdpParseError(f"invalid rtpmap codec: {value!r}")
    return parts[0], int(parts[1]), int(parts[2]) if len(parts) == 3 else 1


def _sdp_direction(value: str) -> SdpDirection:
    if value == "sendrecv":
        return "sendrecv"
    if value == "sendonly":
        return "sendonly"
    if value == "recvonly":
        return "recvonly"
    if value == "inactive":
        return "inactive"
    raise SdpParseError(f"unsupported SDP direction: {value!r}")
