import pytest

from sipx import (
    RtpPacket,
    RtpParseError,
    SipParseError,
    decode_dtmf_event,
    parse_sdp,
    parse_sip_message,
)


def test_sip_parser_fuzz_rejects_malformed_inputs_without_crashing() -> None:
    samples = [
        b"",
        b"\x00" * 32,
        b"INVITE sip:a SIP/2.0\r\nContent-Length: 5\r\n\r\nx",
        b"SIP/2.0 nope\r\n\r\n",
        b"INVITE missing-version\r\n\r\n",
    ]

    for sample in samples:
        with pytest.raises((SipParseError, ValueError, UnicodeDecodeError)):
            parse_sip_message(sample, max_size=64)


def test_sip_parser_fuzz_enforces_size_limit() -> None:
    with pytest.raises(SipParseError, match="maximum size"):
        parse_sip_message(b"A" * 65, max_size=64)


def test_sdp_parser_fuzz_rejects_bad_media_without_crashing() -> None:
    samples = [
        "not-sdp",
        "v=0\r\nc=IN BAD 127.0.0.1\r\n",
        "v=0\r\nm=audio nope RTP/AVP 0\r\n",
        "v=0\r\nm=audio 4000 RTP/AVP x\r\n",
        "v=0\r\nm=audio 4000 RTP/AVP 0\r\na=rtpmap:bad\r\n",
    ]

    for sample in samples:
        with pytest.raises((ValueError, IndexError)):
            parse_sdp(sample)


def test_rtp_parser_fuzz_rejects_bad_packets_without_crashing() -> None:
    samples = [b"", b"short", b"\x00" * 12, b"\x90\x00" + b"\x00" * 10]

    for sample in samples:
        with pytest.raises(RtpParseError):
            RtpPacket.parse(sample)


def test_dtmf_parser_fuzz_rejects_invalid_payloads_without_crashing() -> None:
    samples = [b"", b"abc", bytes([99, 0, 0, 1])]

    for sample in samples:
        with pytest.raises(ValueError):
            decode_dtmf_event(sample)
