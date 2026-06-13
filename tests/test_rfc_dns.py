"""Tests for RFC 3263 DNS resolution."""

from __future__ import annotations

import pytest

from sipx.exceptions import TransportError
from sipx.extensions.dns import SipDnsResolver
from sipx.transport.registry import TransportRegistry


@pytest.mark.asyncio
async def test_import_dns_resolver() -> None:
    """SipDnsResolver must be importable."""
    resolver = SipDnsResolver()
    assert resolver is not None


@pytest.mark.asyncio
async def test_resolver_with_custom_registry() -> None:
    """SipDnsResolver must accept a custom TransportRegistry."""
    registry = TransportRegistry()
    resolver = SipDnsResolver(registry=registry)
    assert resolver._registry is registry


@pytest.mark.asyncio
async def test_parse_simple_sip_uri() -> None:
    """Must parse simple sip: URI without port or transport."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri("sip:bob@example.com")
    assert scheme == "sip"
    assert host == "example.com"
    assert port is None
    assert transport is None


@pytest.mark.asyncio
async def test_parse_sips_uri() -> None:
    """Must parse sips: URI."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri("sips:alice@secure.example.com")
    assert scheme == "sips"
    assert host == "secure.example.com"
    assert port is None
    assert transport is None


@pytest.mark.asyncio
async def test_parse_uri_with_port() -> None:
    """Must parse URI with explicit port."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri("sip:bob@example.com:5080")
    assert scheme == "sip"
    assert host == "example.com"
    assert port == 5080
    assert transport is None


@pytest.mark.asyncio
async def test_parse_uri_with_transport() -> None:
    """Must parse URI with explicit transport parameter."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri(
        "sip:bob@example.com;transport=tcp"
    )
    assert scheme == "sip"
    assert host == "example.com"
    assert port is None
    assert transport == "tcp"


@pytest.mark.asyncio
async def test_parse_uri_with_port_and_transport() -> None:
    """Must parse URI with both port and transport."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri(
        "sip:bob@example.com:5061;transport=tls"
    )
    assert scheme == "sip"
    assert host == "example.com"
    assert port == 5061
    assert transport == "tls"


@pytest.mark.asyncio
async def test_parse_invalid_uri_raises() -> None:
    """Must raise ValueError for invalid SIP URI."""
    resolver = SipDnsResolver()
    with pytest.raises(ValueError, match="Not a valid SIP URI"):
        resolver._parse_uri("http://example.com")


@pytest.mark.asyncio
async def test_parse_uri_unsupported_transport_raises() -> None:
    """Must raise ValueError for unsupported transport in URI."""
    resolver = SipDnsResolver()
    with pytest.raises(ValueError, match="Unsupported transport"):
        resolver._parse_uri("sip:bob@example.com;transport=websocket")


@pytest.mark.asyncio
async def test_resolve_with_mock_records() -> None:
    """Must resolve using mock records when available."""
    resolver = SipDnsResolver()
    resolver._mock_records = {
        "example.com": [
            ("example.com", 5060, "udp"),
            ("example.com", 5060, "tcp"),
            ("example.com", 5061, "tls"),
        ]
    }
    results = await resolver.resolve("sip:bob@example.com")
    assert len(results) == 3
    assert all(r[0] == "example.com" for r in results)


@pytest.mark.asyncio
async def test_resolve_transport_preference_order() -> None:
    """Must return results sorted by transport preference (TLS > TCP > UDP)."""
    resolver = SipDnsResolver()
    resolver._mock_records = {
        "example.com": [
            ("example.com", 5060, "udp"),
            ("example.com", 5060, "tcp"),
            ("example.com", 5061, "tls"),
        ]
    }
    results = await resolver.resolve("sip:bob@example.com")
    # TLS should be first (highest preference)
    assert results[0][2] == "tls"
    assert results[1][2] == "tcp"
    assert results[2][2] == "udp"


@pytest.mark.asyncio
async def test_resolve_explicit_port_and_transport() -> None:
    """Must use explicit port and transport directly."""
    resolver = SipDnsResolver()
    results = await resolver.resolve("sip:bob@example.com:5080;transport=tcp")
    assert len(results) == 1
    assert results[0] == ("example.com", 5080, "tcp")


@pytest.mark.asyncio
async def test_resolve_sips_defaults_to_tls() -> None:
    """sips: URI without explicit transport should default to TLS."""
    resolver = SipDnsResolver()
    results = await resolver.resolve("sips:bob@example.com")
    assert len(results) >= 1
    # Should use TLS as default transport for sips:
    assert results[0][2] == "tls"
    # Should use port 5061 as default for sips:
    assert results[0][1] == 5061


@pytest.mark.asyncio
async def test_resolve_sip_defaults_to_udp() -> None:
    """sip: URI without explicit transport should default to UDP."""
    resolver = SipDnsResolver()
    results = await resolver.resolve("sip:bob@example.com")
    assert len(results) >= 1
    # Should use UDP as default transport for sip:
    assert results[0][2] == "udp"
    # Should use port 5060 as default for sip:
    assert results[0][1] == 5060


@pytest.mark.asyncio
async def test_resolve_invalid_uri_raises_transport_error() -> None:
    """Must raise TransportError for invalid URI."""
    resolver = SipDnsResolver()
    with pytest.raises(TransportError, match="Invalid SIP URI"):
        await resolver.resolve("http://example.com")


@pytest.mark.asyncio
async def test_sort_by_preference() -> None:
    """Must sort transport addresses by preference."""
    resolver = SipDnsResolver()
    unsorted = [
        ("host1", 5060, "udp"),
        ("host2", 5061, "tls"),
        ("host3", 5060, "tcp"),
    ]
    sorted_results = resolver._sort_by_preference(unsorted)
    assert sorted_results[0][2] == "tls"
    assert sorted_results[1][2] == "tcp"
    assert sorted_results[2][2] == "udp"


@pytest.mark.asyncio
async def test_resolve_with_user_part() -> None:
    """Must handle URI with user part correctly."""
    resolver = SipDnsResolver()
    resolver._mock_records = {"example.com": [("example.com", 5060, "udp")]}
    results = await resolver.resolve("sip:alice@example.com")
    assert len(results) == 1
    assert results[0][0] == "example.com"


@pytest.mark.asyncio
async def test_resolve_case_insensitive_scheme() -> None:
    """Must handle case-insensitive scheme."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri("SIP:bob@example.com")
    assert scheme == "sip"


@pytest.mark.asyncio
async def test_resolve_case_insensitive_transport_param() -> None:
    """Must handle case-insensitive transport parameter."""
    resolver = SipDnsResolver()
    scheme, host, port, transport = resolver._parse_uri(
        "sip:bob@example.com;transport=TCP"
    )
    assert transport == "tcp"
