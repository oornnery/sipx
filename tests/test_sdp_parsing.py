import pytest

from sipx.sdp.model import (
    Connection,
    MediaDescription,
    Origin,
    SessionDescription,
    Time,
)
from sipx.sdp.parser import SdpParseError, parse_sdp


def test_parse_basic_sdp_with_all_fields() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 123 456 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendrecv\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert sdp.version == 0
    assert isinstance(sdp.origin, Origin)
    assert sdp.origin.session_id == "123"
    assert sdp.origin.session_version == "456"
    assert sdp.origin.username == "-"
    assert sdp.origin.nettype == "IN"
    assert sdp.origin.addrtype == "IP4"
    assert sdp.origin.address == "127.0.0.1"
    assert sdp.session_name == "-"
    assert isinstance(sdp.connection, Connection)
    assert sdp.connection.address == "127.0.0.1"
    assert isinstance(sdp.time, Time)
    assert sdp.time.start == 0
    assert sdp.time.stop == 0
    assert len(sdp.media) == 1
    assert sdp.media[0].media_type == "audio"
    assert sdp.media[0].port == 5004


def test_parse_audio_media() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 4000 RTP/AVP 0 8 101\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert len(sdp.media) == 1
    media = sdp.media[0]
    assert media.media_type == "audio"
    assert media.port == 4000
    assert media.proto == "RTP/AVP"
    assert media.fmt == ["0", "8", "101"]


def test_parse_video_media() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=video 5006 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert len(sdp.media) == 1
    media = sdp.media[0]
    assert media.media_type == "video"
    assert media.port == 5006
    assert media.proto == "RTP/AVP"
    assert media.fmt == ["96"]
    assert ("rtpmap", "96 H264/90000") in media.attributes


def test_parse_rtpmap_attribute() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("rtpmap", "0 PCMU/8000") in media.attributes


def test_parse_fmtp_attribute() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 101\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
        "a=fmtp:101 0-16\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("rtpmap", "101 telephone-event/8000") in media.attributes
    assert ("fmtp", "101 0-16") in media.attributes


def test_parse_sendrecv_direction() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=sendrecv\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("sendrecv", None) in media.attributes


def test_parse_sendonly_direction() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=sendonly\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("sendonly", None) in media.attributes


def test_parse_recvonly_direction() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=recvonly\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("recvonly", None) in media.attributes


def test_parse_inactive_direction() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=inactive\r\n"
    )
    sdp = parse_sdp(sdp_text)

    media = sdp.media[0]
    assert ("inactive", None) in media.attributes


def test_generate_sdp_from_model() -> None:
    sdp = SessionDescription(
        version=0,
        origin=Origin(
            username="-",
            session_id="123",
            session_version="456",
            nettype="IN",
            addrtype="IP4",
            address="127.0.0.1",
        ),
        session_name="-",
        connection=Connection(nettype="IN", addrtype="IP4", address="127.0.0.1"),
        time=Time(start=0, stop=0),
        media=[
            MediaDescription(
                media_type="audio",
                port=5004,
                proto="RTP/AVP",
                fmt=["0"],
                attributes=[("rtpmap", "0 PCMU/8000"), ("sendrecv", None)],
            )
        ],
    )
    sdp_text = sdp.to_sdp()

    assert "v=0" in sdp_text
    assert "o=- 123 456 IN IP4 127.0.0.1" in sdp_text
    assert "s=-" in sdp_text
    assert "c=IN IP4 127.0.0.1" in sdp_text
    assert "t=0 0" in sdp_text
    assert "m=audio 5004 RTP/AVP 0" in sdp_text
    assert "a=rtpmap:0 PCMU/8000" in sdp_text
    assert "a=sendrecv" in sdp_text


def test_round_trip_parse_generate_parse() -> None:
    original_text = (
        "v=0\r\n"
        "o=- 123 456 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=sendrecv\r\n"
    )
    sdp1 = parse_sdp(original_text)
    generated_text = sdp1.to_sdp()
    sdp2 = parse_sdp(generated_text)

    assert sdp2.version == sdp1.version
    assert sdp2.origin == sdp1.origin
    assert sdp2.session_name == sdp1.session_name
    assert sdp2.connection == sdp1.connection
    assert sdp2.time == sdp1.time
    assert len(sdp2.media) == len(sdp1.media)
    assert sdp2.media[0].media_type == sdp1.media[0].media_type
    assert sdp2.media[0].port == sdp1.media[0].port


def test_parse_malformed_sdp_raises_error() -> None:
    with pytest.raises(SdpParseError):
        parse_sdp("invalid line without equals")


def test_parse_multiple_media_lines() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "m=video 5006 RTP/AVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert len(sdp.media) == 2
    assert sdp.media[0].media_type == "audio"
    assert sdp.media[0].port == 5004
    assert sdp.media[1].media_type == "video"
    assert sdp.media[1].port == 5006


def test_parse_sdp_with_bytes_input() -> None:
    sdp_bytes = (
        b"v=0\r\n"
        b"o=- 123 456 IN IP4 127.0.0.1\r\n"
        b"s=-\r\n"
        b"c=IN IP4 127.0.0.1\r\n"
        b"t=0 0\r\n"
        b"m=audio 5004 RTP/AVP 0\r\n"
    )
    sdp = parse_sdp(sdp_bytes)

    assert sdp.version == 0
    assert isinstance(sdp.origin, Origin)
    assert sdp.origin.session_id == "123"
    assert len(sdp.media) == 1


def test_parse_sdp_with_connection_info() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 192.168.1.1\r\n"
        "s=-\r\n"
        "c=IN IP4 192.168.1.1\r\n"
        "t=0 0\r\n"
        "m=audio 5004 RTP/AVP 0\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert isinstance(sdp.connection, Connection)
    assert sdp.connection.nettype == "IN"
    assert sdp.connection.addrtype == "IP4"
    assert sdp.connection.address == "192.168.1.1"
    assert sdp.connection_address == "192.168.1.1"


def test_generate_sdp_with_video_media() -> None:
    sdp = SessionDescription(
        version=0,
        origin=Origin(
            username="-",
            session_id="789",
            session_version="101",
            nettype="IN",
            addrtype="IP4",
            address="10.0.0.1",
        ),
        session_name="test",
        connection=Connection(nettype="IN", addrtype="IP4", address="10.0.0.1"),
        time=Time(start=100, stop=200),
        media=[
            MediaDescription(
                media_type="video",
                port=6000,
                proto="RTP/AVP",
                fmt=["96"],
                attributes=[("rtpmap", "96 H264/90000")],
            )
        ],
    )
    sdp_text = sdp.to_sdp()

    assert "m=video 6000 RTP/AVP 96" in sdp_text
    assert "a=rtpmap:96 H264/90000" in sdp_text
    assert "t=100 200" in sdp_text


def test_backward_compat_legacy_audio_field() -> None:
    sdp_text = (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 4000 RTP/AVP 0 8 101\r\n"
        "a=sendrecv\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
        "a=fmtp:101 0-16\r\n"
    )
    sdp = parse_sdp(sdp_text)

    assert sdp.audio is not None
    assert sdp.audio.port == 4000
    assert sdp.has_codec("PCMU")
    assert sdp.has_codec("PCMA")
    assert sdp.has_dtmf_transport()
    assert sdp.audio.direction == "sendrecv"
    assert sdp.connection_address == "127.0.0.1"
