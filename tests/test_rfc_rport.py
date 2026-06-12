"""Tests for RFC 3581 rport support in UdpTransport."""

from __future__ import annotations

from sipx.models import Request, Response
from sipx.transport.udp import UdpTransport


def test_convenience_constructor() -> None:
    """UdpTransport must accept local_host and local_port directly."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    assert transport._config.local_host == "127.0.0.1"
    assert transport._config.local_port == 5060


def test_add_via_header_includes_rport() -> None:
    """add_via_header must add Via header with rport parameter."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    req = Request(method="OPTIONS", uri="sip:bob@example.com", headers={}, body=None)
    transport.add_via_header(req)
    via = req.headers["Via"]
    assert "rport" in via
    assert "SIP/2.0/UDP" in via
    assert "127.0.0.1:5060" in via
    assert "branch=z9hG4bK" in via


def test_add_via_header_generates_unique_branch() -> None:
    """add_via_header must generate unique branch parameters."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    req1 = Request(method="OPTIONS", uri="sip:bob@example.com", headers={}, body=None)
    req2 = Request(method="OPTIONS", uri="sip:bob@example.com", headers={}, body=None)
    transport.add_via_header(req1)
    transport.add_via_header(req2)
    assert req1.headers["Via"] != req2.headers["Via"]


def test_parse_via_rport_with_values() -> None:
    """parse_via_rport must extract rport and received values."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    resp = Response(
        200,
        "OK",
        headers={
            "Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bK123;rport=5060;received=192.168.1.1"
        },
        body=None,
    )
    rport, received = transport.parse_via_rport(resp)
    assert rport == 5060
    assert received == "192.168.1.1"


def test_parse_via_rport_empty_rport() -> None:
    """parse_via_rport must handle empty rport parameter."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    resp = Response(
        200,
        "OK",
        headers={"Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bK123;rport"},
        body=None,
    )
    rport, received = transport.parse_via_rport(resp)
    assert rport is None
    assert received is None


def test_parse_via_rport_no_rport() -> None:
    """parse_via_rport must return None when rport is absent."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    resp = Response(
        200,
        "OK",
        headers={"Via": "SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bK123"},
        body=None,
    )
    rport, received = transport.parse_via_rport(resp)
    assert rport is None
    assert received is None


def test_parse_via_rport_no_via_header() -> None:
    """parse_via_rport must handle missing Via header."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    resp = Response(200, "OK", headers={}, body=None)
    rport, received = transport.parse_via_rport(resp)
    assert rport is None
    assert received is None


def test_get_response_destination_with_rport() -> None:
    """get_response_destination must use source address when rport is present."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    via = "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK123;rport"
    source = ("192.168.1.100", 12345)
    dest = transport.get_response_destination(via, source)
    assert dest == ("192.168.1.100", 12345)


def test_get_response_destination_with_rport_and_received() -> None:
    """get_response_destination must use received IP when both rport and received are present."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    via = "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK123;rport;received=203.0.113.5"
    source = ("192.168.1.100", 12345)
    dest = transport.get_response_destination(via, source)
    assert dest == ("203.0.113.5", 12345)


def test_get_response_destination_without_rport() -> None:
    """get_response_destination must use Via address when rport is absent."""
    transport = UdpTransport(local_host="127.0.0.1", local_port=5060)
    via = "SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK123"
    source = ("192.168.1.100", 12345)
    dest = transport.get_response_destination(via, source)
    assert dest == ("10.0.0.1", 5060)
