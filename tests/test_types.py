"""Tests for sipx.types core type aliases."""

from typing import Union, get_origin

from sipx.types import HeaderName, HeaderValue, SipMethod, StatusCode, Uri


class TestTypeAliases:
    def test_sip_method_status_code_uri(self) -> None:
        assert SipMethod is str
        assert StatusCode is int
        assert Uri is str

    def test_header_name_and_value(self) -> None:
        assert HeaderName is str
        assert get_origin(HeaderValue) is Union
        args = set(HeaderValue.__args__)  # type: ignore[attr-defined]
        assert args == {str, list[str]}

    def test_types_are_importable_from_root(self) -> None:
        from sipx import HeaderName, HeaderValue, SipMethod, StatusCode, Uri

        assert SipMethod is str
        assert StatusCode is int
        assert Uri is str
        assert HeaderName is str
        assert get_origin(HeaderValue) is Union
