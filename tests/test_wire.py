"""Tests for SIP wire-format helpers."""

import pytest

from sipx.exceptions import ProtocolError
from sipx.models import Request
from sipx.wire import (
    extract_branch_from_via,
    extract_cseq_parts,
    extract_top_via_branch,
    sanitize_sip_token,
)


def test_sanitize_rejects_crlf_in_values() -> None:
    with pytest.raises(ProtocolError):
        sanitize_sip_token("evil\r\nInjected: yes", field="header")


def test_request_to_bytes_adds_content_length() -> None:
    req = Request(method="OPTIONS", uri="sip:bob@example.com", body=b"")
    data = req.to_bytes()
    assert b"Content-Length: 0" in data


def test_request_to_bytes_rejects_header_injection() -> None:
    req = Request(
        method="OPTIONS",
        uri="sip:bob@example.com",
        headers={"X-Evil": "line1\r\nInjected: yes"},
    )
    with pytest.raises(ProtocolError):
        req.to_bytes()


def test_extract_branch_from_via() -> None:
    via = "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bKabc"
    assert extract_branch_from_via(via) == "z9hG4bKabc"


def test_extract_top_via_branch_from_headers() -> None:
    headers = {"Via": "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bKtop"}
    assert extract_top_via_branch(headers) == "z9hG4bKtop"


def test_extract_cseq_parts() -> None:
    assert extract_cseq_parts("42 INVITE") == ("42", "INVITE")
