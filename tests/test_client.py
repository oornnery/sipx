"""Tests for AsyncClient core functionality."""

from __future__ import annotations

import pytest

from sipx.client import AsyncClient
from sipx.config import Settings
from sipx.protocol.auth import AuthDigest
from sipx.transport.tcp import TcpTransport
from sipx.transport.tls import TlsTransport
from sipx.transport.udp import UdpTransport


def test_asyncclient_import():
    """AsyncClient must be importable from sipx.client."""
    from sipx.client import AsyncClient

    assert AsyncClient is not None


def test_asyncclient_default_construction():
    """AsyncClient must construct with default parameters."""
    client = AsyncClient()
    assert client is not None
    assert client.is_closed
    assert client.config is not None
    assert client.transport is not None


def test_asyncclient_default_transport_is_udp():
    """Default transport must be UDP."""
    client = AsyncClient()
    assert isinstance(client.transport, UdpTransport)


def test_asyncclient_udp_transport():
    """AsyncClient must create UDP transport when requested."""
    client = AsyncClient(transport="udp")
    assert isinstance(client.transport, UdpTransport)


def test_asyncclient_tcp_transport():
    """AsyncClient must create TCP transport when requested."""
    client = AsyncClient(transport="tcp")
    assert isinstance(client.transport, TcpTransport)


def test_asyncclient_tls_transport():
    """AsyncClient must create TLS transport when requested."""
    client = AsyncClient(transport="tls")
    assert isinstance(client.transport, TlsTransport)


def test_asyncclient_invalid_transport_raises():
    """AsyncClient must raise ValueError for invalid transport."""
    with pytest.raises(ValueError, match="Unsupported transport type"):
        AsyncClient(transport="invalid")


def test_asyncclient_custom_config():
    """AsyncClient must accept custom Settings."""
    settings = Settings(
        local_host="127.0.0.1",
        local_port=5060,
        timeout=60.0,
        user_agent="test-agent",
    )
    client = AsyncClient(settings=settings)
    assert client.config.local_host == "127.0.0.1"
    assert client.config.local_port == 5060
    assert client.config.timeout == 60.0
    assert client.config.user_agent == "test-agent"


def test_asyncclient_event_hooks():
    """AsyncClient must store event hooks."""
    hooks = {"request": [lambda req: None], "response": [lambda resp: None]}
    client = AsyncClient(event_hooks=hooks)
    assert client.event_hooks == hooks
    assert "request" in client.event_hooks
    assert "response" in client.event_hooks


def test_asyncclient_auth_flow():
    """AsyncClient must store auth flow."""
    auth = AuthDigest(username="alice", password="secret")
    client = AsyncClient(auth=auth)
    assert client.auth is auth
    assert client.auth.username == "alice"
    assert client.auth.password == "secret"


@pytest.mark.asyncio
async def test_asyncclient_context_manager():
    """AsyncClient must work as async context manager."""
    async with AsyncClient() as client:
        assert not client.is_closed
    assert client.is_closed


@pytest.mark.asyncio
async def test_asyncclient_aclose():
    """AsyncClient.aclose() must close the client."""
    client = AsyncClient()
    assert client.is_closed
    await client.__aenter__()
    assert not client.is_closed
    await client.aclose()
    assert client.is_closed


@pytest.mark.asyncio
async def test_asyncclient_aclose_idempotent():
    """AsyncClient.aclose() must be safe to call multiple times."""
    client = AsyncClient()
    await client.aclose()
    await client.aclose()  # Should not raise
    assert client.is_closed


@pytest.mark.asyncio
async def test_asyncclient_transport_property():
    """AsyncClient.transport must return the transport instance."""
    client = AsyncClient(transport="tcp")
    transport = client.transport
    assert isinstance(transport, TcpTransport)
    await client.aclose()


@pytest.mark.asyncio
async def test_asyncclient_config_property():
    """AsyncClient.config must return the configuration."""
    settings = Settings(user_agent="test/1.0")
    client = AsyncClient(settings=settings)
    assert client.config.user_agent == "test/1.0"
    await client.aclose()
