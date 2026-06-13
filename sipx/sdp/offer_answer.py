"""SDP offer/answer construction for audio media.

Builds audio offers and computes answers by intersecting offered codecs with
locally supported ones (PCMU/PCMA, optional telephone-event) and mirroring the
stream direction, per the SDP offer/answer model.

References:
    RFC 3264 - An Offer/Answer Model with SDP
    RFC 4733 - telephone-event (DTMF) media format
    RFC 3551 - Audio payload types
"""

from __future__ import annotations

from sipx.sdp.model import AudioMedia, SdpCodec, SdpDirection, SessionDescription


STATIC_AUDIO_CODECS = {
    "PCMU": SdpCodec(payload_type=0, name="PCMU", clock_rate=8000),
    "PCMA": SdpCodec(payload_type=8, name="PCMA", clock_rate=8000),
}
TELEPHONE_EVENT = SdpCodec(
    payload_type=101,
    name="telephone-event",
    clock_rate=8000,
    fmtp="0-16",
)


class SdpNegotiationError(ValueError):
    pass


def create_audio_offer(
    *,
    connection_address: str,
    port: int,
    codecs: tuple[str, ...] = ("PCMU", "PCMA"),
    telephone_event: bool = True,
    direction: SdpDirection = "sendrecv",
) -> SessionDescription:
    audio_codecs = _codecs_from_names(codecs)
    if telephone_event:
        audio_codecs[TELEPHONE_EVENT.payload_type] = TELEPHONE_EVENT
    return SessionDescription(
        origin=f"- 0 0 IN IP4 {connection_address}",
        session_name="sipx",
        connection_address=connection_address,
        audio=AudioMedia(
            port=port,
            payload_types=list(audio_codecs),
            codecs=audio_codecs,
            direction=direction,
        ),
    )


def create_audio_answer(
    offer: SessionDescription,
    *,
    connection_address: str,
    port: int,
    supported_codecs: tuple[str, ...] = ("PCMU", "PCMA"),
    telephone_event: bool = True,
) -> SessionDescription:
    if offer.audio is None:
        raise SdpNegotiationError("offer has no audio media")

    supported = {name.upper() for name in supported_codecs}
    selected: dict[int, SdpCodec] = {}
    for payload_type in offer.audio.payload_types:
        codec = offer.audio.codecs.get(payload_type)
        if codec is None:
            continue
        codec_name = codec.name.upper()
        if codec_name in supported or (
            telephone_event and codec_name == "TELEPHONE-EVENT"
        ):
            selected[payload_type] = codec

    media_codecs = [
        codec for codec in selected.values() if codec.name.upper() != "TELEPHONE-EVENT"
    ]
    if not media_codecs:
        raise SdpNegotiationError("no supported audio codec in offer")

    return SessionDescription(
        origin=f"- 0 0 IN IP4 {connection_address}",
        session_name="sipx",
        connection_address=connection_address,
        audio=AudioMedia(
            port=port,
            payload_types=list(selected),
            codecs=selected,
            direction=_answer_direction(offer.audio.direction),
        ),
    )


def _codecs_from_names(names: tuple[str, ...]) -> dict[int, SdpCodec]:
    codecs: dict[int, SdpCodec] = {}
    for name in names:
        try:
            codec = STATIC_AUDIO_CODECS[name.upper()]
        except KeyError as exc:
            raise SdpNegotiationError(f"unsupported audio codec: {name}") from exc
        codecs[codec.payload_type] = codec
    return codecs


def _answer_direction(direction: SdpDirection) -> SdpDirection:
    if direction == "sendonly":
        return "recvonly"
    if direction == "recvonly":
        return "sendonly"
    return direction
