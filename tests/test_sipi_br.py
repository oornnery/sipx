"""Tests for sipx.contrib._sipi_br (Brazilian SIP-I extensions)."""

from __future__ import annotations

from unittest.mock import MagicMock

from sipx.contrib._sipi_br import (
    ATI,
    ATIResult,
    SipIBR,
    VALID_DDD,
    is_mobile,
    is_valid_br_number,
    normalize_br_number,
)
from sipx._models._message import Request, Response


class TestNormalizeBrNumber:
    def test_with_country_code_55(self):
        assert normalize_br_number("+55 11 98765-4321") == "11987654321"

    def test_with_trunk_prefix_0(self):
        assert normalize_br_number("011987654321") == "11987654321"

    def test_already_normalized(self):
        assert normalize_br_number("11987654321") == "11987654321"

    def test_with_parens_and_dashes(self):
        assert normalize_br_number("(11) 98765-4321") == "11987654321"

    def test_with_spaces(self):
        assert normalize_br_number("11 98765 4321") == "11987654321"

    def test_landline_10_digits(self):
        assert normalize_br_number("1132345678") == "1132345678"

    def test_country_code_without_plus(self):
        assert normalize_br_number("5511987654321") == "11987654321"

    def test_short_number_no_strip(self):
        # 10 digits, starts with 0 but len <= 10, should not strip
        assert normalize_br_number("0123456789") == "0123456789"


class TestIsValidBrNumber:
    def test_valid_mobile(self):
        assert is_valid_br_number("11987654321") is True

    def test_valid_landline(self):
        assert is_valid_br_number("1132345678") is True

    def test_invalid_ddd(self):
        assert is_valid_br_number("0087654321") is False

    def test_too_short(self):
        assert is_valid_br_number("123456") is False

    def test_too_long(self):
        assert is_valid_br_number("119876543210") is False

    def test_valid_with_formatting(self):
        assert is_valid_br_number("+55 (21) 98765-4321") is True

    def test_invalid_ddd_20(self):
        # DDD 20 does not exist
        assert is_valid_br_number("2087654321") is False


class TestIsMobile:
    def test_mobile_number(self):
        assert is_mobile("11987654321") is True

    def test_landline_number(self):
        assert is_mobile("1132345678") is False

    def test_mobile_with_formatting(self):
        assert is_mobile("+55 (11) 98765-4321") is True


class TestATIResult:
    def test_from_redirect_ported(self):
        result = ATIResult.from_redirect("sip:11987654321-12345@ati.carrier.com.br")
        assert result.number == "11987654321"
        assert result.rn1 == "12345"
        assert result.ported is True
        assert result.not_found is False

    def test_from_redirect_not_found(self):
        result = ATIResult.from_redirect("sip:11987654321-55999@ati.carrier.com.br")
        assert result.number == "11987654321"
        assert result.rn1 == "55999"
        assert result.ported is False
        assert result.not_found is True

    def test_from_redirect_no_rn1(self):
        result = ATIResult.from_redirect("sip:11987654321@ati.carrier.com.br")
        assert result.number == "11987654321"
        assert result.rn1 == ""
        assert result.ported is False

    def test_from_redirect_invalid_uri(self):
        result = ATIResult.from_redirect("invalid-uri")
        assert result.number == ""
        assert result.rn1 == ""

    def test_from_redirect_sips_scheme(self):
        result = ATIResult.from_redirect("sips:11987654321-12345@ati.carrier.com.br")
        assert result.ported is True


class TestSipIBRPreferredIdentity:
    def test_add_and_get_preferred_identity(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SipIBR.add_preferred_identity(req, "sip:alice@carrier.com.br")
        assert SipIBR.get_preferred_identity(req) == "sip:alice@carrier.com.br"

    def test_get_preferred_identity_absent(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        assert SipIBR.get_preferred_identity(req) is None

    def test_get_preferred_identity_from_response(self):
        resp = Response(
            status_code=200,
            headers={"P-Preferred-Identity": "sip:alice@carrier.com.br"},
        )
        assert SipIBR.get_preferred_identity(resp) == "sip:alice@carrier.com.br"


class TestSipIBRChargingFunctionAddresses:
    def test_add_and_get_ccf(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SipIBR.add_charging_function_addresses(req, ccf=["ccf1.carrier.com"])
        result = SipIBR.get_charging_function_addresses(req)
        assert result["ccf"] == ["ccf1.carrier.com"]
        assert result["ecf"] == []

    def test_add_ccf_and_ecf(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        SipIBR.add_charging_function_addresses(
            req,
            ccf=["ccf1.carrier.com", "ccf2.carrier.com"],
            ecf=["ecf1.carrier.com"],
        )
        result = SipIBR.get_charging_function_addresses(req)
        assert len(result["ccf"]) == 2
        assert result["ecf"] == ["ecf1.carrier.com"]

    def test_get_charging_absent(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        result = SipIBR.get_charging_function_addresses(req)
        assert result == {"ccf": [], "ecf": []}


class TestSipIBRReason:
    def test_add_and_get_reason(self):
        req = Request(method="BYE", uri="sip:bob@example.com")
        SipIBR.add_reason(req, cause=16, text="Normal call clearing")
        reason = SipIBR.get_reason(req)
        assert reason is not None
        assert reason["protocol"] == "Q.850"
        assert reason["cause"] == 16
        assert reason["text"] == "Normal call clearing"

    def test_add_reason_with_location(self):
        req = Request(method="BYE", uri="sip:bob@example.com")
        SipIBR.add_reason(req, cause=31, text="Normal, unspecified", location="LN")
        reason = SipIBR.get_reason(req)
        assert reason is not None
        assert reason["location"] == "LN"

    def test_add_reason_no_text(self):
        req = Request(method="BYE", uri="sip:bob@example.com")
        SipIBR.add_reason(req, cause=16)
        reason = SipIBR.get_reason(req)
        assert reason is not None
        assert reason["text"] is None

    def test_get_reason_absent(self):
        req = Request(method="BYE", uri="sip:bob@example.com")
        assert SipIBR.get_reason(req) is None

    def test_add_reason_custom_protocol(self):
        resp = Response(status_code=200)
        SipIBR.add_reason(resp, cause=403, protocol="SIP", text="Forbidden")
        reason = SipIBR.get_reason(resp)
        assert reason is not None
        assert reason["protocol"] == "SIP"
        assert reason["cause"] == 403


class TestATIQuery:
    def test_query_ported_number(self):
        from sipx._models._message import Response

        client = MagicMock()
        resp = Response(
            status_code=302,
            headers={"Contact": "<sip:11987654321-12345@ati.carrier.com.br>"},
        )
        client.invite.return_value = resp

        ati = ATI(client=client, ati_server="ati.carrier.com.br")
        result = ati.query("11987654321")
        assert result.ported is True
        assert result.rn1 == "12345"

    def test_query_not_ported(self):
        from sipx._models._message import Response

        client = MagicMock()
        resp = Response(status_code=200)
        client.invite.return_value = resp

        ati = ATI(client=client, ati_server="ati.carrier.com.br")
        result = ati.query("11987654321")
        assert result.ported is False

    def test_query_none_response(self):
        client = MagicMock()
        client.invite.return_value = None

        ati = ATI(client=client, ati_server="ati.carrier.com.br")
        result = ati.query("11987654321")
        assert result.ported is False

    def test_query_normalizes_number(self):
        from sipx._models._message import Response

        client = MagicMock()
        resp = Response(status_code=200)
        client.invite.return_value = resp

        ati = ATI(client=client, ati_server="ati.carrier.com.br")
        result = ati.query("+55 (11) 98765-4321")
        # Should have normalized the number
        assert result.number == "11987654321"


class TestValidDDD:
    def test_contains_sao_paulo(self):
        assert 11 in VALID_DDD

    def test_contains_rio(self):
        assert 21 in VALID_DDD

    def test_contains_df(self):
        assert 61 in VALID_DDD

    def test_does_not_contain_invalid(self):
        assert 20 not in VALID_DDD
        assert 0 not in VALID_DDD
        assert 100 not in VALID_DDD

    def test_all_codes_two_digits(self):
        for code in VALID_DDD:
            assert 10 <= code <= 99
