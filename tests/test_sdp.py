import pytest

from sipx import SdpNegotiationError, create_audio_answer, create_audio_offer, parse_sdp


def test_parse_sdp_audio_codecs_and_dtmf() -> None:
    sdp = parse_sdp(
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=sipx\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 4000 RTP/AVP 0 8 101\r\n"
        "a=sendrecv\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
        "a=fmtp:101 0-16\r\n"
    )

    assert sdp.connection_address == "127.0.0.1"
    assert sdp.audio is not None
    assert sdp.audio.port == 4000
    assert sdp.has_codec("PCMU")
    assert sdp.has_codec("PCMA")
    assert sdp.has_dtmf_transport()
    assert sdp.audio.direction == "sendrecv"


def test_audio_offer_serializes_static_codecs_and_telephone_event() -> None:
    offer = create_audio_offer(connection_address="10.0.0.1", port=5000)
    text = offer.to_sdp()

    assert "m=audio 5000 RTP/AVP 0 8 101" in text
    assert "a=rtpmap:0 PCMU/8000" in text
    assert "a=rtpmap:8 PCMA/8000" in text
    assert "a=rtpmap:101 telephone-event/8000" in text
    assert "a=fmtp:101 0-16" in text


def test_audio_answer_selects_common_codecs_and_inverts_sendonly() -> None:
    offer = create_audio_offer(
        connection_address="10.0.0.1",
        port=5000,
        codecs=("PCMA",),
        direction="sendonly",
    )

    answer = create_audio_answer(
        offer,
        connection_address="10.0.0.2",
        port=6000,
        supported_codecs=("PCMU", "PCMA"),
    )

    assert answer.audio is not None
    assert answer.audio.payload_types == [8, 101]
    assert answer.audio.direction == "recvonly"


def test_audio_answer_rejects_no_common_codec() -> None:
    offer = create_audio_offer(
        connection_address="10.0.0.1",
        port=5000,
        codecs=("PCMU",),
    )

    with pytest.raises(SdpNegotiationError):
        create_audio_answer(
            offer,
            connection_address="10.0.0.2",
            port=6000,
            supported_codecs=("PCMA",),
        )
