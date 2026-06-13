"""Parser for SDP text into the structured session model.

Reads ``<type>=<value>`` SDP lines into ``SessionDescription``, extracting
audio media, rtpmap/fmtp codec attributes, and stream direction, and fills in
well-known static payload types (PCMU=0, PCMA=8).

References:
    RFC 4566 §5 - SDP field grammar
    RFC 4566 §6 - rtpmap/fmtp attributes
    RFC 3551 - Static payload type assignments
"""

from __future__ import annotations

from sipx.sdp.model import (
    DIRECTIONS,
    AudioMedia,
    Connection,
    MediaDescription,
    Origin,
    SdpCodec,
    SdpDirection,
    SessionDescription,
    Time,
)


STATIC_PAYLOADS = {
    0: SdpCodec(payload_type=0, name="PCMU", clock_rate=8000),
    8: SdpCodec(payload_type=8, name="PCMA", clock_rate=8000),
}


class SdpParseError(ValueError):
    pass


def parse_sdp(raw: str | bytes) -> SessionDescription:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw

    version = 0
    origin: str | Origin = ""
    session_name = "-"
    connection: Connection | None = None
    connection_address = ""
    time_desc: Time | None = None
    media_list: list[MediaDescription] = []

    current_media: MediaDescription | None = None
    current_audio: AudioMedia | None = None

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        if not raw_line:
            continue
        if len(raw_line) < 2 or raw_line[1] != "=":
            raise SdpParseError(f"invalid SDP line: {raw_line!r}")
        prefix = raw_line[0]
        value = raw_line[2:]

        if prefix == "v":
            version = int(value)
        elif prefix == "o":
            origin = _parse_origin(value)
        elif prefix == "s":
            session_name = value
        elif prefix == "c":
            connection = _parse_connection(value)
            connection_address = connection.address
        elif prefix == "t":
            time_desc = _parse_time(value)
        elif prefix == "m":
            current_media = _parse_media_description(value)
            media_list.append(current_media)
            if current_media.media_type == "audio":
                try:
                    current_audio = _parse_audio_media(value)
                except SdpParseError:
                    current_audio = None
            else:
                current_audio = None
        elif prefix == "a":
            if current_media is not None:
                _parse_media_attribute(current_media, value)
            if current_audio is not None:
                _parse_audio_attribute(current_audio, value)

    if current_audio is not None:
        for payload_type in current_audio.payload_types:
            if (
                payload_type in STATIC_PAYLOADS
                and payload_type not in current_audio.codecs
            ):
                current_audio.codecs[payload_type] = STATIC_PAYLOADS[payload_type]

    return SessionDescription(
        version=version,
        origin=origin,
        session_name=session_name,
        connection_address=connection_address,
        audio=current_audio,
        connection=connection,
        time=time_desc,
        media=media_list,
    )


def _parse_origin(value: str) -> Origin:
    parts = value.split()
    if len(parts) != 6:
        raise SdpParseError(f"invalid SDP origin: {value!r}")
    return Origin(
        username=parts[0],
        session_id=parts[1],
        session_version=parts[2],
        nettype=parts[3],
        addrtype=parts[4],
        address=parts[5],
    )


def _parse_connection(value: str) -> Connection:
    parts = value.split()
    if len(parts) != 3 or parts[0] != "IN" or parts[1] not in {"IP4", "IP6"}:
        raise SdpParseError(f"unsupported SDP connection: {value!r}")
    return Connection(nettype=parts[0], addrtype=parts[1], address=parts[2])


def _parse_time(value: str) -> Time:
    parts = value.split()
    if len(parts) != 2:
        raise SdpParseError(f"invalid SDP time: {value!r}")
    return Time(start=int(parts[0]), stop=int(parts[1]))


def _parse_media_description(value: str) -> MediaDescription:
    parts = value.split()
    if len(parts) < 4:
        raise SdpParseError(f"invalid SDP media: {value!r}")
    return MediaDescription(
        media_type=parts[0],
        port=int(parts[1]),
        proto=parts[2],
        fmt=parts[3:],
    )


def _parse_media_attribute(media: MediaDescription, value: str) -> None:
    if value in DIRECTIONS:
        media.attributes.append((value, None))
        return
    if ":" in value:
        attr_name, attr_value = value.split(":", 1)
        media.attributes.append((attr_name, attr_value))
    else:
        media.attributes.append((value, None))


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
