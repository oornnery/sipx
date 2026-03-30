"""Tests for sipx._models._body (SDPBody, RawBody, BodyParser)."""

from __future__ import annotations

import pytest

from sipx._models._body import SDPBody, RawBody, BodyParser


# ============================================================================
# SDPBody.create_offer()
# ============================================================================


class TestSDPBodyCreateOffer:
    def test_create_offer_basic(self):
        offer = SDPBody.create_offer(
            session_name="VoIP Call",
            origin_username="alice",
            origin_address="192.168.1.100",
            connection_address="192.168.1.100",
            session_id="12345",
            media_specs=[
                {
                    "media": "audio",
                    "port": 49170,
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                    ],
                }
            ],
        )
        assert offer.session_name == "VoIP Call"
        assert offer.origin_username == "alice"
        assert offer.origin_address == "192.168.1.100"
        assert offer.connection == "IN IP4 192.168.1.100"
        assert len(offer.media_descriptions) == 1
        assert offer.media_descriptions[0]["media"] == "audio"
        assert offer.media_descriptions[0]["port"] == 49170
        assert offer.media_descriptions[0]["formats"] == ["0", "8"]

    def test_create_offer_auto_session_id(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [{"payload": "0", "name": "PCMU", "rate": "8000"}],
                }
            ],
        )
        # session_id should be auto-generated (numeric string)
        assert offer.origin_session_id.isdigit()

    def test_create_offer_with_fmtp(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="100",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [
                        {
                            "payload": "101",
                            "name": "telephone-event",
                            "rate": "8000",
                            "fmtp": "0-16",
                        }
                    ],
                }
            ],
        )
        attrs = offer.media_descriptions[0].get("attributes", {})
        assert "fmtp:101" in attrs
        assert attrs["fmtp:101"] == "0-16"

    def test_create_offer_with_codec_params(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="100",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [
                        {"payload": "9", "name": "G722", "rate": "8000", "params": "1"},
                    ],
                }
            ],
        )
        attrs = offer.media_descriptions[0].get("attributes", {})
        assert attrs["rtpmap:9"] == "G722/8000/1"

    def test_create_offer_multiple_media(self):
        offer = SDPBody.create_offer(
            session_name="AV Call",
            origin_username="-",
            origin_address="10.0.0.1",
            connection_address="10.0.0.1",
            session_id="999",
            media_specs=[
                {
                    "media": "audio",
                    "port": 5000,
                    "codecs": [{"payload": "0", "name": "PCMU", "rate": "8000"}],
                },
                {
                    "media": "video",
                    "port": 6000,
                    "codecs": [{"payload": "96", "name": "H264", "rate": "90000"}],
                },
            ],
        )
        assert len(offer.media_descriptions) == 2
        assert offer.media_descriptions[0]["media"] == "audio"
        assert offer.media_descriptions[1]["media"] == "video"

    def test_create_offer_with_session_attributes(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="100",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [{"payload": "0", "name": "PCMU", "rate": "8000"}],
                }
            ],
            attributes={"sendrecv": None},
        )
        assert "sendrecv" in offer.attributes


# ============================================================================
# SDPBody.create_answer()
# ============================================================================


class TestSDPBodyCreateAnswer:
    def _make_offer(self):
        return SDPBody.create_offer(
            session_name="VoIP Call",
            origin_username="alice",
            origin_address="192.168.1.100",
            connection_address="192.168.1.100",
            session_id="12345",
            media_specs=[
                {
                    "media": "audio",
                    "port": 49170,
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                        {"payload": "101", "name": "telephone-event", "rate": "8000"},
                    ],
                }
            ],
        )

    def test_create_answer_accept_subset(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
            accepted_media=[
                {"index": 0, "port": 49170, "codecs": ["0", "8"]},
            ],
        )
        assert answer.origin_username == "bob"
        assert answer.connection == "IN IP4 192.168.1.101"
        assert len(answer.media_descriptions) == 1
        assert answer.media_descriptions[0]["formats"] == ["0", "8"]

    def test_create_answer_default_accepts_all(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
        )
        assert len(answer.media_descriptions) == 1
        assert answer.media_descriptions[0]["formats"] == ["0", "8", "101"]

    def test_create_answer_increments_version(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
        )
        assert int(answer.origin_session_version) == int(offer.origin_session_version) + 1

    def test_create_answer_reject_media(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
            accepted_media=[
                {"index": 0, "port": 0, "codecs": ["0"]},
            ],
        )
        assert answer.media_descriptions[0]["port"] == 0
        assert answer.is_media_rejected(0) is True

    def test_create_answer_copies_rtpmap_attributes(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
            accepted_media=[
                {"index": 0, "port": 49170, "codecs": ["0"]},
            ],
        )
        attrs = answer.media_descriptions[0].get("attributes", {})
        assert "rtpmap:0" in attrs
        assert attrs["rtpmap:0"] == "PCMU/8000"

    def test_create_answer_out_of_range_index_skipped(self):
        offer = self._make_offer()
        answer = SDPBody.create_answer(
            offer=offer,
            origin_username="bob",
            origin_address="192.168.1.101",
            connection_address="192.168.1.101",
            accepted_media=[
                {"index": 99, "port": 8000, "codecs": ["0"]},
            ],
        )
        assert len(answer.media_descriptions) == 0


# ============================================================================
# SDPBody.to_string() / to_bytes() roundtrip
# ============================================================================


class TestSDPBodySerialization:
    def test_to_string_and_back(self):
        sdp = SDPBody(
            session_name="Test",
            origin_username="-",
            origin_session_id="123",
            origin_session_version="0",
            connection="IN IP4 192.168.1.100",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0", "8"])

        text = sdp.to_string()
        assert "v=0" in text
        assert "s=Test" in text
        assert "m=audio 8000 RTP/AVP 0 8" in text
        assert text.endswith("\r\n")

        # Roundtrip
        parsed = BodyParser.parse_sdp(text.encode("utf-8"))
        assert parsed.session_name == "Test"
        assert parsed.origin_session_id == "123"
        assert len(parsed.media_descriptions) == 1
        assert parsed.media_descriptions[0]["port"] == 8000

    def test_to_bytes_produces_bytes(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        raw = sdp.to_bytes()
        assert isinstance(raw, bytes)

    def test_content_type(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.content_type == "application/sdp"

    def test_str_returns_serialized(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert str(sdp) == sdp.to_string()


# ============================================================================
# SDPBody.get_codecs_summary()
# ============================================================================


class TestGetCodecsSummary:
    def test_single_media(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="1",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [
                        {"payload": "0", "name": "PCMU", "rate": "8000"},
                        {"payload": "8", "name": "PCMA", "rate": "8000"},
                    ],
                }
            ],
        )
        summary = offer.get_codecs_summary()
        assert "audio" in summary
        assert "PCMU" in summary["audio"]
        assert "PCMA" in summary["audio"]

    def test_multiple_media(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="127.0.0.1",
            connection_address="127.0.0.1",
            session_id="1",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [{"payload": "0", "name": "PCMU", "rate": "8000"}],
                },
                {
                    "media": "video",
                    "port": 9000,
                    "codecs": [{"payload": "96", "name": "H264", "rate": "90000"}],
                },
            ],
        )
        summary = offer.get_codecs_summary()
        assert "audio" in summary
        assert "video" in summary
        assert "PCMU" in summary["audio"]
        assert "H264" in summary["video"]

    def test_empty_media(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.get_codecs_summary() == {}


# ============================================================================
# SDPBody.get_media_info()
# ============================================================================


class TestGetMediaInfo:
    def test_returns_info_dict(self):
        offer = SDPBody.create_offer(
            session_name="Test",
            origin_username="-",
            origin_address="10.0.0.1",
            connection_address="10.0.0.1",
            session_id="1",
            media_specs=[
                {
                    "media": "audio",
                    "port": 8000,
                    "codecs": [{"payload": "0", "name": "PCMU", "rate": "8000"}],
                }
            ],
        )
        info = offer.get_media_info(0)
        assert info is not None
        assert info["type"] == "audio"
        assert info["port"] == 8000
        assert info["protocol"] == "RTP/AVP"
        assert info["rejected"] is False
        assert info["connection"] == "IN IP4 10.0.0.1"

    def test_returns_none_for_out_of_range(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.get_media_info(0) is None


# ============================================================================
# SDPBody.get_connection_address()
# ============================================================================


class TestGetConnectionAddress:
    def test_extracts_ipv4(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
            connection="IN IP4 192.168.1.100",
        )
        assert sdp.get_connection_address() == "192.168.1.100"

    def test_extracts_ipv6(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
            connection="IN IP6 ::1",
        )
        assert sdp.get_connection_address() == "::1"

    def test_returns_none_when_no_connection(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.get_connection_address() is None


# ============================================================================
# SDPBody.get_media_ports()
# ============================================================================


class TestGetMediaPorts:
    def test_returns_ports(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0"])
        sdp.add_media("video", 9000, "RTP/AVP", ["96"])
        ports = sdp.get_media_ports()
        assert ports == {"audio": 8000, "video": 9000}

    def test_empty(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.get_media_ports() == {}


# ============================================================================
# SDPBody.has_early_media()
# ============================================================================


class TestHasEarlyMedia:
    def test_session_level_sendrecv(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
            attributes={"sendrecv": None},
        )
        assert sdp.has_early_media() is True

    def test_media_level_sendonly(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0"], attributes={"sendonly": None})
        assert sdp.has_early_media() is True

    def test_no_directional_attrs(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0"])
        assert sdp.has_early_media() is False

    def test_rejected_media_not_early(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 0, "RTP/AVP", ["0"], attributes={"sendrecv": None})
        assert sdp.has_early_media() is False


# ============================================================================
# SDPBody.is_media_rejected()
# ============================================================================


class TestIsMediaRejected:
    def test_port_zero_is_rejected(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 0, "RTP/AVP", ["0"])
        assert sdp.is_media_rejected(0) is True

    def test_valid_port_not_rejected(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0"])
        assert sdp.is_media_rejected(0) is False

    def test_out_of_range_is_rejected(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        assert sdp.is_media_rejected(0) is True


# ============================================================================
# BodyParser.parse()
# ============================================================================


class TestBodyParser:
    def test_parse_sdp(self):
        sdp_text = (
            "v=0\r\n"
            "o=- 123 0 IN IP4 127.0.0.1\r\n"
            "s=Test\r\n"
            "c=IN IP4 192.168.1.1\r\n"
            "t=0 0\r\n"
            "m=audio 8000 RTP/AVP 0\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
        )
        body = BodyParser.parse(sdp_text.encode("utf-8"), "application/sdp")
        assert isinstance(body, SDPBody)
        assert body.session_name == "Test"
        assert body.get_connection_address() == "192.168.1.1"

    def test_parse_sdp_with_charset_param(self):
        sdp_text = "v=0\r\no=- 1 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
        body = BodyParser.parse(sdp_text.encode("utf-8"), "application/sdp; charset=utf-8")
        assert isinstance(body, SDPBody)

    def test_parse_text_plain_returns_raw(self):
        content = b"Hello SIP World"
        body = BodyParser.parse(content, "text/plain")
        assert isinstance(body, RawBody)
        assert body.to_bytes() == content
        assert body.to_string() == "Hello SIP World"
        assert body.content_type == "text/plain"

    def test_parse_empty_content_returns_raw(self):
        body = BodyParser.parse(b"", "application/sdp")
        assert isinstance(body, RawBody)
        assert body.to_bytes() == b""

    def test_parse_unknown_type_returns_raw(self):
        content = b"<xml>data</xml>"
        body = BodyParser.parse(content, "application/xml")
        assert isinstance(body, RawBody)
        assert body.to_bytes() == content


# ============================================================================
# RawBody
# ============================================================================


class TestRawBody:
    def test_init_and_properties(self):
        rb = RawBody(b"some data", "text/plain")
        assert rb.to_bytes() == b"some data"
        assert rb.to_string() == "some data"
        assert rb.content_type == "text/plain"

    def test_repr(self):
        rb = RawBody(b"data", "text/plain")
        r = repr(rb)
        assert "RawBody" in r
        assert "text/plain" in r
        assert "4 bytes" in r
