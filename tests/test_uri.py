"""Tests for sipx._uri (SipURI parser)."""

from __future__ import annotations

from sipx._uri import SipURI


class TestSipURIParse:
    def test_parse_basic_sip_uri(self):
        uri = SipURI.parse("sip:alice@atlanta.com")
        assert uri.scheme == "sip"
        assert uri.user == "alice"
        assert uri.host == "atlanta.com"
        assert uri.port is None
        assert uri.is_secure is False

    def test_parse_sips_uri(self):
        uri = SipURI.parse("sips:bob@biloxi.com")
        assert uri.scheme == "sips"
        assert uri.user == "bob"
        assert uri.host == "biloxi.com"
        assert uri.is_secure is True

    def test_parse_with_password(self):
        uri = SipURI.parse("sip:alice:secret@atlanta.com")
        assert uri.user == "alice"
        assert uri.password == "secret"
        assert uri.host == "atlanta.com"

    def test_parse_with_port(self):
        uri = SipURI.parse("sip:alice@atlanta.com:5060")
        assert uri.host == "atlanta.com"
        assert uri.port == 5060

    def test_parse_with_transport_param(self):
        uri = SipURI.parse("sip:alice@atlanta.com;transport=tcp")
        assert uri.transport == "tcp"
        assert uri.params["transport"] == "tcp"

    def test_parse_with_lr_param(self):
        uri = SipURI.parse("sip:proxy.example.com;lr")
        assert uri.lr is True
        assert uri.params["lr"] is None

    def test_parse_with_maddr_param(self):
        uri = SipURI.parse("sip:atlanta.com;maddr=239.255.255.1")
        assert uri.maddr == "239.255.255.1"

    def test_parse_with_ttl_param(self):
        uri = SipURI.parse("sip:atlanta.com;ttl=16")
        assert uri.ttl == 16

    def test_parse_with_user_phone_param(self):
        uri = SipURI.parse("sip:+1-212-555-1212@gateway.com;user=phone")
        assert uri.user_param == "phone"
        assert uri.user == "+1-212-555-1212"

    def test_parse_with_method_param(self):
        uri = SipURI.parse("sip:atlanta.com;method=REGISTER")
        assert uri.method == "REGISTER"

    def test_parse_with_headers(self):
        uri = SipURI.parse("sip:atlanta.com?to=alice%40atlanta.com")
        assert uri.headers["to"] == "alice@atlanta.com"

    def test_parse_ipv6(self):
        uri = SipURI.parse("sip:alice@[::1]:5060")
        assert uri.host == "::1"
        assert uri.port == 5060

    def test_parse_ipv6_no_port(self):
        uri = SipURI.parse("sip:alice@[::1]")
        assert uri.host == "::1"
        assert uri.port is None

    def test_parse_tel_uri(self):
        uri = SipURI.parse("tel:+1-212-555-1212")
        assert uri.scheme == "tel"

    def test_parse_no_scheme(self):
        uri = SipURI.parse("atlanta.com")
        assert uri.host == "atlanta.com"
        assert uri.scheme == "sip"  # default

    def test_parse_empty_string(self):
        uri = SipURI.parse("")
        assert uri.host == ""
        assert uri.user == ""

    def test_parse_multiple_params(self):
        uri = SipURI.parse("sip:alice@atlanta.com:5060;transport=tcp;lr;maddr=10.0.0.1")
        assert uri.transport == "tcp"
        assert uri.lr is True
        assert uri.maddr == "10.0.0.1"
        assert uri.port == 5060


class TestSipURIToString:
    def test_roundtrip_basic(self):
        original = "sip:alice@atlanta.com"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_sips(self):
        original = "sips:bob@biloxi.com"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_with_password(self):
        original = "sip:alice:secret@atlanta.com"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_with_port(self):
        original = "sip:alice@atlanta.com:5060"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_with_params(self):
        original = "sip:alice@atlanta.com;transport=tcp"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_with_lr(self):
        original = "sip:proxy.example.com;lr"
        assert SipURI.parse(original).to_string() == original

    def test_roundtrip_with_headers(self):
        uri = SipURI.parse("sip:atlanta.com?to=alice%40atlanta.com")
        result = uri.to_string()
        assert "?to=" in result

    def test_str_delegates_to_to_string(self):
        uri = SipURI.parse("sip:alice@atlanta.com")
        assert str(uri) == uri.to_string()


class TestSipURIProperties:
    def test_is_secure_sip(self):
        uri = SipURI(scheme="sip", host="example.com")
        assert uri.is_secure is False

    def test_is_secure_sips(self):
        uri = SipURI(scheme="sips", host="example.com")
        assert uri.is_secure is True

    def test_transport_none_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.transport is None

    def test_lr_false_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.lr is False

    def test_effective_port_default_sip(self):
        uri = SipURI(scheme="sip", host="example.com")
        assert uri.effective_port == 5060

    def test_effective_port_default_sips(self):
        uri = SipURI(scheme="sips", host="example.com")
        assert uri.effective_port == 5061

    def test_effective_port_explicit(self):
        uri = SipURI(scheme="sip", host="example.com", port=5080)
        assert uri.effective_port == 5080

    def test_default_port_sip(self):
        uri = SipURI(scheme="sip", host="example.com")
        assert uri.default_port == 5060

    def test_default_port_sips(self):
        uri = SipURI(scheme="sips", host="example.com")
        assert uri.default_port == 5061

    def test_host_port_with_port(self):
        uri = SipURI(host="example.com", port=5080)
        assert uri.host_port == "example.com:5080"

    def test_host_port_without_port(self):
        uri = SipURI(host="example.com")
        assert uri.host_port == "example.com"

    def test_method_none_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.method is None

    def test_maddr_none_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.maddr is None

    def test_ttl_none_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.ttl is None

    def test_user_param_none_when_absent(self):
        uri = SipURI(host="example.com")
        assert uri.user_param is None


class TestSipURIToDict:
    def test_to_dict_basic(self):
        uri = SipURI.parse("sip:alice@atlanta.com:5060;transport=tcp")
        d = uri.to_dict()
        assert d["scheme"] == "sip"
        assert d["user"] == "alice"
        assert d["host"] == "atlanta.com"
        assert d["port"] == "5060"
        assert "transport=tcp" in d["params"]

    def test_to_dict_no_port(self):
        uri = SipURI.parse("sip:alice@atlanta.com")
        d = uri.to_dict()
        assert d["port"] == ""

    def test_to_dict_with_password(self):
        uri = SipURI.parse("sip:alice:secret@atlanta.com")
        d = uri.to_dict()
        assert d["password"] == "secret"

    def test_to_dict_flag_param(self):
        uri = SipURI.parse("sip:proxy.example.com;lr")
        d = uri.to_dict()
        assert "lr" in d["params"]


class TestSipURIEdgeCases:
    def test_parse_host_with_colon_invalid_port(self):
        """When port part is not numeric, treat whole thing as host."""
        uri = SipURI.parse("sip:host:abc")
        assert uri.host == "host:abc"
        assert uri.port is None
