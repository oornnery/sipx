import pytest

from sipx import HeaderMap, SipParseError, SipRequest, SipResponse, SipUri
from sipx.sip import parse_sip_message


def test_sip_uri_round_trip_with_parameters() -> None:
    uri = SipUri.parse("sip:alice@example.com:5060;transport=udp;lr")

    assert uri.scheme == "sip"
    assert uri.user == "alice"
    assert uri.host == "example.com"
    assert uri.port == 5060
    assert uri.parameters == {"transport": "udp", "lr": None}
    assert str(uri) == "sip:alice@example.com:5060;transport=udp;lr"


def test_header_map_is_case_insensitive_and_expands_compact_names() -> None:
    headers = HeaderMap()
    headers.add("f", "<sip:alice@example.com>")
    headers.add("Via", "SIP/2.0/UDP host;branch=z9")

    assert headers.get("From") == "<sip:alice@example.com>"
    assert headers.get("from") == "<sip:alice@example.com>"
    assert "v" in headers
    assert list(headers.items())[0] == ("From", "<sip:alice@example.com>")


def test_parse_request_and_serialize_content_length() -> None:
    raw = (
        b"INVITE sip:bob@example.com SIP/2.0\r\n"
        b"Via: SIP/2.0/UDP caller;branch=z9\r\n"
        b"From: <sip:alice@example.com>\r\n"
        b"To: <sip:bob@example.com>\r\n"
        b"Call-ID: call-1\r\n"
        b"CSeq: 1 INVITE\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"hello"
    )

    message = parse_sip_message(raw)

    assert isinstance(message, SipRequest)
    assert message.method == "INVITE"
    assert message.uri.host == "example.com"
    assert message.body == b"hello"
    assert b"Content-Length: 5" in message.to_bytes()


def test_parse_response() -> None:
    message = parse_sip_message(
        b"SIP/2.0 200 OK\r\nCall-ID: call-1\r\nContent-Length: 0\r\n\r\n"
    )

    assert isinstance(message, SipResponse)
    assert message.status_code == 200
    assert message.reason == "OK"


def test_parse_rejects_content_length_mismatch() -> None:
    with pytest.raises(SipParseError):
        parse_sip_message(b"SIP/2.0 200 OK\r\nContent-Length: 4\r\n\r\nabc")


def test_parse_rejects_oversized_message() -> None:
    with pytest.raises(SipParseError):
        parse_sip_message(
            b"SIP/2.0 200 OK\r\nContent-Length: 0\r\n\r\n",
            max_size=10,
        )


def test_serializer_rewrites_content_length() -> None:
    headers = HeaderMap()
    headers.set("Content-Length", "999")
    response = SipResponse(
        status_code=486, reason="Busy Here", headers=headers, body=b"no"
    )

    assert b"Content-Length: 2" in response.to_bytes()
