"""Tests for sipx._models._header (Headers, HeaderParser)."""

from __future__ import annotations

import pytest

from sipx._models._header import Headers, HeaderParser


# ============================================================================
# Headers: case-insensitive get / set / contains
# ============================================================================


class TestHeadersCaseInsensitive:
    def test_get_case_insensitive(self):
        h = Headers({"Via": "SIP/2.0/UDP server.com"})
        assert h["via"] == "SIP/2.0/UDP server.com"
        assert h["VIA"] == "SIP/2.0/UDP server.com"
        assert h["Via"] == "SIP/2.0/UDP server.com"

    def test_set_case_insensitive_overwrites(self):
        h = Headers()
        h["From"] = "alice@example.com"
        h["from"] = "bob@example.com"
        assert h["FROM"] == "bob@example.com"
        assert len(h) == 1

    def test_contains_case_insensitive(self):
        h = Headers({"Call-ID": "abc123"})
        assert "call-id" in h
        assert "Call-ID" in h
        assert "CALL-ID" in h

    def test_contains_returns_false_for_non_string(self):
        h = Headers({"Via": "x"})
        assert 42 not in h

    def test_del_case_insensitive(self):
        h = Headers({"From": "alice"})
        del h["from"]
        assert "From" not in h

    def test_del_missing_key_raises(self):
        h = Headers()
        with pytest.raises(KeyError):
            del h["Missing"]

    def test_getitem_missing_raises(self):
        h = Headers()
        with pytest.raises(KeyError):
            _ = h["Missing"]

    def test_get_with_default(self):
        h = Headers()
        assert h.get("Missing") is None
        assert h.get("Missing", "fallback") == "fallback"


# ============================================================================
# Compact form expansion
# ============================================================================


class TestCompactFormExpansion:
    def test_f_expands_to_from(self):
        h = Headers()
        h["f"] = "alice@example.com"
        assert h["From"] == "alice@example.com"

    def test_i_expands_to_call_id(self):
        h = Headers()
        h["i"] = "abc@host"
        assert h["Call-ID"] == "abc@host"

    def test_c_expands_to_content_type(self):
        h = Headers()
        h["c"] = "application/sdp"
        assert h["Content-Type"] == "application/sdp"

    def test_v_expands_to_via(self):
        h = Headers()
        h["v"] = "SIP/2.0/UDP server.com"
        assert h["Via"] == "SIP/2.0/UDP server.com"

    def test_t_expands_to_to(self):
        h = Headers()
        h["t"] = "bob@example.com"
        assert h["To"] == "bob@example.com"

    def test_m_expands_to_contact(self):
        h = Headers()
        h["m"] = "<sip:alice@192.168.1.1>"
        assert h["Contact"] == "<sip:alice@192.168.1.1>"

    def test_l_expands_to_content_length(self):
        h = Headers()
        h["l"] = "0"
        assert h["Content-Length"] == "0"

    def test_s_expands_to_subject(self):
        h = Headers()
        h["s"] = "Test"
        assert h["Subject"] == "Test"

    def test_k_expands_to_supported(self):
        h = Headers()
        h["k"] = "replaces"
        assert h["Supported"] == "replaces"


# ============================================================================
# RFC 3261 ordering in to_lines()
# ============================================================================


class TestToLines:
    def test_priority_order(self):
        h = Headers()
        # Insert in non-standard order
        h["Content-Length"] = "0"
        h["Content-Type"] = "application/sdp"
        h["From"] = "alice"
        h["Via"] = "SIP/2.0/UDP server"
        h["CSeq"] = "1 INVITE"
        h["To"] = "bob"
        h["Call-ID"] = "abc"

        lines = h.to_lines()
        names = [line.split(":")[0] for line in lines]

        # Via, From, To, Call-ID, CSeq should precede Content-Type, Content-Length
        assert names.index("Via") < names.index("From")
        assert names.index("From") < names.index("To")
        assert names.index("To") < names.index("Call-ID")
        assert names.index("Call-ID") < names.index("CSeq")
        # Content-Type before Content-Length
        assert names.index("Content-Type") < names.index("Content-Length")
        # Content-Length is last
        assert names[-1] == "Content-Length"

    def test_content_length_last(self):
        h = Headers({"Content-Length": "100", "Via": "x", "X-Custom": "y"})
        lines = h.to_lines()
        assert lines[-1].startswith("Content-Length")

    def test_empty_headers_to_lines(self):
        h = Headers()
        assert h.to_lines() == []


# ============================================================================
# raw() serialization
# ============================================================================


class TestRaw:
    def test_raw_produces_bytes(self):
        h = Headers({"Via": "SIP/2.0/UDP server"})
        raw = h.raw()
        assert isinstance(raw, bytes)
        assert b"Via: SIP/2.0/UDP server\r\n" in raw

    def test_raw_empty_headers(self):
        h = Headers()
        assert h.raw() == b""

    def test_raw_encoding_override(self):
        h = Headers({"From": "alice"})
        raw = h.raw(encoding="ascii")
        assert isinstance(raw, bytes)
        assert b"From: alice" in raw


# ============================================================================
# HeaderParser.parse() from bytes
# ============================================================================


class TestHeaderParserParse:
    def test_parse_bytes(self):
        data = b"Via: SIP/2.0/UDP pc33.atlanta.com\r\nFrom: alice@atlanta.com\r\n"
        headers = HeaderParser.parse(data)
        assert headers["Via"] == "SIP/2.0/UDP pc33.atlanta.com"
        assert headers["From"] == "alice@atlanta.com"

    def test_parse_string(self):
        data = "Via: SIP/2.0/UDP pc33.atlanta.com\r\nFrom: alice@atlanta.com\r\n"
        headers = HeaderParser.parse(data)
        assert headers["Via"] == "SIP/2.0/UDP pc33.atlanta.com"

    def test_parse_handles_lf_only(self):
        data = b"Via: SIP/2.0/UDP x\nFrom: alice\n"
        headers = HeaderParser.parse(data)
        assert headers["Via"] == "SIP/2.0/UDP x"
        assert headers["From"] == "alice"


# ============================================================================
# HeaderParser.parse_lines()
# ============================================================================


class TestHeaderParserParseLines:
    def test_basic_lines(self):
        lines = [b"Via: SIP/2.0/UDP host", b"From: alice"]
        headers = HeaderParser.parse_lines(lines)
        assert headers["Via"] == "SIP/2.0/UDP host"
        assert headers["From"] == "alice"

    def test_folded_lines(self):
        lines = [b"Via: SIP/2.0/UDP host", b" ;branch=z9hG4bK776"]
        headers = HeaderParser.parse_lines(lines)
        assert "branch=z9hG4bK776" in headers["Via"]

    def test_empty_lines_skipped(self):
        lines = [b"", b"Via: x", b""]
        headers = HeaderParser.parse_lines(lines)
        assert headers["Via"] == "x"
        assert len(headers) == 1

    def test_no_colon_lines_skipped(self):
        lines = [b"InvalidLine", b"Via: x"]
        headers = HeaderParser.parse_lines(lines)
        assert len(headers) == 1
        assert headers["Via"] == "x"


# ============================================================================
# HeaderParser.parse_header_value() and format_header_value()
# ============================================================================


class TestHeaderParserValues:
    def test_parse_header_value_simple(self):
        result = HeaderParser.parse_header_value("application/sdp")
        assert result == {"value": "application/sdp"}

    def test_parse_header_value_with_params(self):
        result = HeaderParser.parse_header_value("application/sdp; charset=utf-8")
        assert result["value"] == "application/sdp"
        assert result["charset"] == "utf-8"

    def test_parse_header_value_quoted_param(self):
        result = HeaderParser.parse_header_value('text/plain; boundary="abc"')
        assert result["boundary"] == "abc"

    def test_format_header_value_no_params(self):
        assert HeaderParser.format_header_value("application/sdp") == "application/sdp"

    def test_format_header_value_with_params(self):
        result = HeaderParser.format_header_value(
            "application/sdp", {"charset": "utf-8"}
        )
        assert result == "application/sdp; charset=utf-8"

    def test_format_header_value_quotes_special_chars(self):
        result = HeaderParser.format_header_value("text/plain", {"boundary": "a b"})
        assert '"a b"' in result


# ============================================================================
# copy(), clear(), update()
# ============================================================================


class TestHeadersMutation:
    def test_copy(self):
        h = Headers({"Via": "x", "From": "alice"})
        c = h.copy()
        assert c == h
        c["Via"] = "y"
        assert h["Via"] == "x"  # original unchanged

    def test_clear(self):
        h = Headers({"Via": "x", "From": "alice"})
        h.clear()
        assert len(h) == 0

    def test_update_from_dict(self):
        h = Headers({"Via": "x"})
        h.update({"From": "alice", "To": "bob"})
        assert h["From"] == "alice"
        assert h["To"] == "bob"
        assert h["Via"] == "x"

    def test_update_from_headers(self):
        h1 = Headers({"Via": "x"})
        h2 = Headers({"From": "alice"})
        h1.update(h2)
        assert h1["From"] == "alice"

    def test_update_kwargs(self):
        h = Headers()
        h.update(Via="x")
        assert h["Via"] == "x"

    def test_update_invalid_type_raises(self):
        h = Headers()
        with pytest.raises(TypeError):
            h.update("invalid")  # type: ignore[arg-type]

    def test_popitem(self):
        h = Headers({"Via": "x", "From": "alice"})
        name, value = h.popitem()
        assert len(h) == 1

    def test_popitem_empty_raises(self):
        h = Headers()
        with pytest.raises(KeyError):
            h.popitem()


# ============================================================================
# __eq__, __len__, __iter__
# ============================================================================


class TestHeadersDunder:
    def test_eq_same_content(self):
        h1 = Headers({"Via": "x", "From": "alice"})
        h2 = Headers({"Via": "x", "From": "alice"})
        assert h1 == h2

    def test_eq_different_order(self):
        h1 = Headers({"Via": "x", "From": "alice"})
        h2 = Headers({"From": "alice", "Via": "x"})
        # Different insertion order -> not equal
        assert h1 != h2

    def test_eq_not_headers(self):
        h = Headers({"Via": "x"})
        assert h != "not a headers"

    def test_len(self):
        h = Headers({"Via": "x", "From": "alice", "To": "bob"})
        assert len(h) == 3

    def test_iter(self):
        h = Headers({"Via": "x", "From": "alice"})
        keys = list(h)
        assert keys == ["Via", "From"]

    def test_items(self):
        h = Headers({"Via": "x", "From": "alice"})
        items = list(h.items())
        assert items == [("Via", "x"), ("From", "alice")]

    def test_values(self):
        h = Headers({"Via": "x", "From": "alice"})
        vals = list(h.values())
        assert vals == ["x", "alice"]

    def test_keys(self):
        h = Headers({"Via": "x", "From": "alice"})
        keys = list(h.keys())
        assert keys == ["Via", "From"]

    def test_repr(self):
        h = Headers({"Via": "x"})
        r = repr(h)
        assert "Headers" in r
        assert "Via" in r

    def test_encoding_property(self):
        h = Headers()
        assert h.encoding == "utf-8"
        h.encoding = "ascii"
        assert h.encoding == "ascii"

    def test_init_from_headers(self):
        h1 = Headers({"Via": "x"})
        h2 = Headers(h1)
        assert h2["Via"] == "x"

    def test_init_invalid_type_raises(self):
        with pytest.raises(TypeError):
            Headers("invalid")  # type: ignore[arg-type]
