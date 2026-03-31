"""Tests for sipx._models._message (Request, Response, MessageParser)."""

from __future__ import annotations

import pytest

from sipx._models._message import Request, Response, MessageParser
from sipx._models._body import SDPBody, RawBody


# ============================================================================
# Request creation
# ============================================================================


class TestRequestCreation:
    def test_basic_invite(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={
                "Via": "SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds",
                "From": "<sip:alice@atlanta.com>;tag=1928301774",
                "To": "<sip:bob@biloxi.com>",
                "Call-ID": "a84b4c76e66710@pc33.atlanta.com",
                "CSeq": "314159 INVITE",
            },
        )
        assert req.method == "INVITE"
        assert req.uri == "sip:bob@biloxi.com"
        assert req.version == "SIP/2.0"

    def test_method_uppercased(self):
        req = Request("invite", "sip:bob@biloxi.com")
        assert req.method == "INVITE"

    def test_auto_content_length(self):
        req = Request("OPTIONS", "sip:bob@biloxi.com")
        assert req.headers["Content-Length"] == "0"

    def test_auto_max_forwards(self):
        req = Request("REGISTER", "sip:registrar.example.com")
        assert req.headers["Max-Forwards"] == "70"

    def test_user_provided_max_forwards_preserved(self):
        req = Request(
            "REGISTER",
            "sip:registrar.example.com",
            headers={"Max-Forwards": "20"},
        )
        assert req.headers["Max-Forwards"] == "20"

    def test_content_as_string(self):
        req = Request("MESSAGE", "sip:bob@biloxi.com", content="Hello")
        assert req.content == b"Hello"
        assert req.headers["Content-Length"] == "5"

    def test_content_as_bytes(self):
        req = Request("MESSAGE", "sip:bob@biloxi.com", content=b"Hello")
        assert req.content == b"Hello"

    def test_content_as_message_body(self):
        sdp = SDPBody(
            session_name="Test",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
            connection="IN IP4 127.0.0.1",
        )
        sdp.add_media("audio", 8000, "RTP/AVP", ["0"])
        req = Request("INVITE", "sip:bob@biloxi.com", content=sdp)
        assert req.headers["Content-Type"] == "application/sdp"
        assert int(req.headers["Content-Length"]) > 0

    def test_repr(self):
        req = Request("INVITE", "sip:bob@biloxi.com")
        assert "INVITE" in repr(req)
        assert "bob@biloxi.com" in repr(req)


# ============================================================================
# Request.to_bytes()
# ============================================================================


class TestRequestToBytes:
    def test_format(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={"Via": "SIP/2.0/UDP server.com"},
        )
        raw = req.to_bytes()
        assert raw.startswith(b"INVITE sip:bob@biloxi.com SIP/2.0\r\n")
        # Headers are present
        assert b"Via: SIP/2.0/UDP server.com" in raw
        # Double CRLF separating headers from body
        assert b"\r\n\r\n" in raw

    def test_to_string(self):
        req = Request("OPTIONS", "sip:host.example.com")
        text = req.to_string()
        assert isinstance(text, str)
        assert text.startswith("OPTIONS")


# ============================================================================
# Request properties
# ============================================================================


class TestRequestProperties:
    def _make_request(self, method="INVITE"):
        return Request(
            method,
            "sip:bob@biloxi.com",
            headers={
                "Via": "SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds",
                "From": "<sip:alice@atlanta.com>;tag=1928301774",
                "To": "<sip:bob@biloxi.com>",
                "Call-ID": "a84b4c76e66710@pc33.atlanta.com",
                "CSeq": "1 INVITE",
                "Contact": "<sip:alice@192.168.1.1>",
            },
        )

    def test_is_invite(self):
        assert self._make_request("INVITE").is_invite is True
        assert self._make_request("BYE").is_invite is False

    def test_is_register(self):
        assert self._make_request("REGISTER").is_register is True
        assert self._make_request("INVITE").is_register is False

    def test_is_ack(self):
        assert self._make_request("ACK").is_ack is True

    def test_is_bye(self):
        assert self._make_request("BYE").is_bye is True

    def test_is_cancel(self):
        assert self._make_request("CANCEL").is_cancel is True

    def test_is_options(self):
        assert self._make_request("OPTIONS").is_options is True

    def test_via(self):
        req = self._make_request()
        assert req.via is not None
        assert "pc33.atlanta.com" in req.via

    def test_call_id(self):
        req = self._make_request()
        assert req.call_id == "a84b4c76e66710@pc33.atlanta.com"

    def test_from_header(self):
        req = self._make_request()
        assert "alice@atlanta.com" in req.from_header

    def test_to_header(self):
        req = self._make_request()
        assert "bob@biloxi.com" in req.to_header

    def test_cseq(self):
        req = self._make_request()
        assert req.cseq == "1 INVITE"

    def test_contact(self):
        req = self._make_request()
        assert req.contact is not None

    def test_content_type_none_when_unset(self):
        req = Request("OPTIONS", "sip:host")
        assert req.content_type is None

    def test_content_length(self):
        req = Request("OPTIONS", "sip:host")
        assert req.content_length == 0

    def test_content_text(self):
        req = Request("MESSAGE", "sip:bob@biloxi.com", content="Hello")
        assert req.content_text == "Hello"

    def test_max_forwards(self):
        req = Request("OPTIONS", "sip:host")
        assert req.max_forwards == 70

    def test_user_agent(self):
        req = Request("OPTIONS", "sip:host", headers={"User-Agent": "test/1.0"})
        assert req.user_agent == "test/1.0"

    def test_user_agent_none(self):
        req = Request("OPTIONS", "sip:host")
        assert req.user_agent is None


# ============================================================================
# Request.has_valid_via_branch()
# ============================================================================


class TestHasValidViaBranch:
    def test_valid_branch(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={"Via": "SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds"},
        )
        assert req.has_valid_via_branch() is True

    def test_invalid_branch(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={"Via": "SIP/2.0/UDP pc33.atlanta.com;branch=invalidprefix"},
        )
        assert req.has_valid_via_branch() is False

    def test_no_branch(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={"Via": "SIP/2.0/UDP pc33.atlanta.com"},
        )
        assert req.has_valid_via_branch() is False

    def test_no_via(self):
        req = Request("INVITE", "sip:bob@biloxi.com")
        # No Via header set explicitly, none from auto
        # Via is not auto-added, so this should return False
        assert req.has_valid_via_branch() is False


# ============================================================================
# Request body/content setter
# ============================================================================


class TestRequestBodySetter:
    def test_set_body(self):
        req = Request("INVITE", "sip:bob@biloxi.com")
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        req.body = sdp
        assert req.body is sdp
        assert req.headers["Content-Type"] == "application/sdp"
        assert int(req.headers["Content-Length"]) > 0

    def test_set_body_none(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        req = Request("INVITE", "sip:bob@biloxi.com", content=sdp)
        req.body = None
        assert req.body is None
        assert req.content == b""
        assert req.headers["Content-Length"] == "0"

    def test_set_content_string(self):
        req = Request("MESSAGE", "sip:bob@biloxi.com")
        req.content = "Hello"
        assert req.content == b"Hello"
        assert req.headers["Content-Length"] == "5"

    def test_set_content_bytes(self):
        req = Request("MESSAGE", "sip:bob@biloxi.com")
        req.content = b"Hello"
        assert req.content == b"Hello"

    def test_lazy_body_parse(self):
        req = Request(
            "INVITE",
            "sip:bob@biloxi.com",
            headers={"Content-Type": "text/plain"},
            content=b"Hello",
        )
        body = req.body
        assert isinstance(body, RawBody)


# ============================================================================
# Response creation
# ============================================================================


class TestResponseCreation:
    def test_200_ok(self):
        resp = Response(200)
        assert resp.status_code == 200
        assert resp.reason_phrase == "OK"
        assert resp.version == "SIP/2.0"

    def test_custom_reason_phrase(self):
        resp = Response(200, reason_phrase="All Good")
        assert resp.reason_phrase == "All Good"

    def test_unknown_status_code(self):
        resp = Response(999)
        assert resp.reason_phrase == "Unknown"

    def test_with_headers(self):
        resp = Response(200, headers={"Via": "SIP/2.0/UDP x", "From": "alice"})
        assert resp.headers["Via"] == "SIP/2.0/UDP x"

    def test_auto_content_length(self):
        resp = Response(200)
        assert resp.headers["Content-Length"] == "0"

    def test_content_string(self):
        resp = Response(200, content="OK body")
        assert resp.content == b"OK body"

    def test_content_message_body(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        resp = Response(200, content=sdp)
        assert resp.headers["Content-Type"] == "application/sdp"

    def test_repr(self):
        resp = Response(200)
        assert "200" in repr(resp)
        assert "OK" in repr(resp)


# ============================================================================
# Response properties
# ============================================================================


class TestResponseProperties:
    def test_is_provisional(self):
        assert Response(100).is_provisional is True
        assert Response(180).is_provisional is True
        assert Response(183).is_provisional is True
        assert Response(200).is_provisional is False

    def test_is_success(self):
        assert Response(200).is_success is True
        assert Response(202).is_success is True
        assert Response(100).is_success is False
        assert Response(400).is_success is False

    def test_is_error(self):
        assert Response(400).is_error is True
        assert Response(500).is_error is True
        assert Response(600).is_error is True
        assert Response(200).is_error is False

    def test_is_final(self):
        assert Response(200).is_final is True
        assert Response(400).is_final is True
        assert Response(100).is_final is False

    def test_requires_auth(self):
        assert Response(401).requires_auth is True
        assert Response(407).requires_auth is True
        assert Response(200).requires_auth is False

    def test_is_redirect(self):
        assert Response(301).is_redirect is True
        assert Response(302).is_redirect is True
        assert Response(200).is_redirect is False

    def test_is_client_error(self):
        assert Response(400).is_client_error is True
        assert Response(404).is_client_error is True
        assert Response(500).is_client_error is False

    def test_is_server_error(self):
        assert Response(500).is_server_error is True
        assert Response(503).is_server_error is True
        assert Response(400).is_server_error is False

    def test_is_global_failure(self):
        assert Response(600).is_global_failure is True
        assert Response(603).is_global_failure is True
        assert Response(500).is_global_failure is False

    def test_server_header(self):
        resp = Response(200, headers={"Server": "TestServer/1.0"})
        assert resp.server == "TestServer/1.0"

    def test_server_header_none(self):
        resp = Response(200)
        assert resp.server is None

    def test_request_property(self):
        req = Request("INVITE", "sip:bob@biloxi.com")
        resp = Response(200, request=req)
        assert resp.request is req

    def test_set_request(self):
        resp = Response(200)
        req = Request("INVITE", "sip:bob@biloxi.com")
        resp.request = req
        assert resp.request is req


# ============================================================================
# Response.to_bytes()
# ============================================================================


class TestResponseToBytes:
    def test_format(self):
        resp = Response(
            200,
            headers={"Via": "SIP/2.0/UDP server.com", "From": "alice"},
        )
        raw = resp.to_bytes()
        assert raw.startswith(b"SIP/2.0 200 OK\r\n")
        assert b"Via: SIP/2.0/UDP server.com" in raw
        assert b"\r\n\r\n" in raw

    def test_to_string(self):
        resp = Response(404)
        text = resp.to_string()
        assert "404 Not Found" in text

    def test_str_magic(self):
        resp = Response(200)
        assert "200 OK" in str(resp)


# ============================================================================
# Response body/content setter
# ============================================================================


class TestResponseBodySetter:
    def test_set_body(self):
        resp = Response(200)
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        resp.body = sdp
        assert resp.body is sdp
        assert resp.headers["Content-Type"] == "application/sdp"

    def test_set_body_none(self):
        sdp = SDPBody(
            session_name="X",
            origin_username="-",
            origin_session_id="1",
            origin_session_version="0",
        )
        resp = Response(200, content=sdp)
        resp.body = None
        assert resp.body is None
        assert resp.content == b""
        assert "Content-Type" not in resp.headers

    def test_set_content_string(self):
        resp = Response(200)
        resp.content = "body text"
        assert resp.content == b"body text"
        assert resp.headers["Content-Length"] == "9"


# ============================================================================
# MessageParser.parse() auto-detects Request vs Response
# ============================================================================


class TestMessageParser:
    def test_parse_request(self):
        data = (
            b"INVITE sip:bob@biloxi.com SIP/2.0\r\n"
            b"Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776\r\n"
            b"From: <sip:alice@atlanta.com>;tag=123\r\n"
            b"To: <sip:bob@biloxi.com>\r\n"
            b"Call-ID: abc@pc33\r\n"
            b"CSeq: 1 INVITE\r\n"
            b"Content-Length: 0\r\n"
            b"\r\n"
        )
        msg = MessageParser.parse(data)
        assert isinstance(msg, Request)
        assert msg.method == "INVITE"
        assert msg.uri == "sip:bob@biloxi.com"
        assert msg.call_id == "abc@pc33"

    def test_parse_response(self):
        data = (
            b"SIP/2.0 200 OK\r\n"
            b"Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776\r\n"
            b"From: <sip:alice@atlanta.com>;tag=123\r\n"
            b"To: <sip:bob@biloxi.com>;tag=456\r\n"
            b"Call-ID: abc@pc33\r\n"
            b"CSeq: 1 INVITE\r\n"
            b"Content-Length: 0\r\n"
            b"\r\n"
        )
        msg = MessageParser.parse(data)
        assert isinstance(msg, Response)
        assert msg.status_code == 200
        assert msg.reason_phrase == "OK"

    def test_parse_from_string(self):
        data = (
            "SIP/2.0 180 Ringing\r\n"
            "Via: SIP/2.0/UDP server\r\n"
            "Content-Length: 0\r\n"
            "\r\n"
        )
        msg = MessageParser.parse(data)
        assert isinstance(msg, Response)
        assert msg.status_code == 180

    def test_parse_with_body(self):
        sdp_body = "v=0\r\no=- 1 0 IN IP4 127.0.0.1\r\ns=Test\r\nt=0 0\r\n"
        data = (
            f"INVITE sip:bob@biloxi.com SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP server\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp_body)}\r\n"
            f"\r\n"
            f"{sdp_body}"
        )
        msg = MessageParser.parse(data)
        assert isinstance(msg, Request)
        assert len(msg.content) > 0
        body = msg.body
        assert isinstance(body, SDPBody)
        assert body.session_name == "Test"

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError):
            MessageParser.parse(b"")

    def test_parse_invalid_request_line_raises(self):
        with pytest.raises(ValueError):
            MessageParser.parse(b"BROKEN\r\n\r\n")


# ============================================================================
# MessageParser.parse_uri()
# ============================================================================


class TestParseUri:
    def test_full_uri(self):
        result = MessageParser.parse_uri("sip:alice@atlanta.com:5060;transport=tcp")
        assert result["scheme"] == "sip"
        assert result["user"] == "alice"
        assert result["host"] == "atlanta.com"
        assert result["port"] == "5060"
        assert result["params"] == "transport=tcp"

    def test_uri_without_port(self):
        result = MessageParser.parse_uri("sip:alice@atlanta.com")
        assert result["scheme"] == "sip"
        assert result["user"] == "alice"
        assert result["host"] == "atlanta.com"
        assert result["port"] == ""

    def test_uri_without_user(self):
        result = MessageParser.parse_uri("sip:atlanta.com:5060")
        assert result["scheme"] == "sip"
        assert result["user"] == ""
        assert result["host"] == "atlanta.com"
        assert result["port"] == "5060"

    def test_sips_scheme(self):
        result = MessageParser.parse_uri("sips:alice@secure.com")
        assert result["scheme"] == "sips"

    def test_no_colon(self):
        result = MessageParser.parse_uri("invaliduri")
        # No scheme prefix — parser treats as host, defaults scheme to "sip"
        assert result["host"] == "invaliduri"

    def test_uri_host_only(self):
        result = MessageParser.parse_uri("sip:server.example.com")
        assert result["host"] == "server.example.com"
        assert result["user"] == ""
        assert result["port"] == ""
