"""Tests for TransportRegistry and create_transport factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal

import pytest

from sipx.transport.base import Transport, TransportConfig
from sipx.transport.registry import TransportRegistry, create_transport
from sipx.transport.tcp import TcpTransport
from sipx.transport.tls import TlsTransport
from sipx.transport.udp import UdpTransport


class FakeTransport(Transport):
    """Fake transport for testing registration."""

    def __init__(self, config: TransportConfig) -> None:
        self._config = config

    @property
    def local_address(self) -> tuple[str, int]:
        return ("127.0.0.1", 0)

    @property
    def transport_type(self) -> Literal["udp", "tcp", "tls"]:
        return "udp"

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        pass

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        yield b"", ("", 0)

    async def close(self) -> None:
        pass


def test_default_transports_registered() -> None:
    """Default transports (udp, tcp, tls) must be pre-registered."""
    registry = TransportRegistry()
    types = registry.get_supported_types()
    assert types == ["tcp", "tls", "udp"]


def test_create_udp_transport() -> None:
    """create() must return a UdpTransport instance for 'udp'."""
    registry = TransportRegistry()
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = registry.create("udp", config)
    assert isinstance(transport, UdpTransport)


def test_create_tcp_transport() -> None:
    """create() must return a TcpTransport instance for 'tcp'."""
    registry = TransportRegistry()
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = registry.create("tcp", config)
    assert isinstance(transport, TcpTransport)


def test_create_tls_transport() -> None:
    """create() must return a TlsTransport instance for 'tls'."""
    registry = TransportRegistry()
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = registry.create("tls", config)
    assert isinstance(transport, TlsTransport)


def test_create_unknown_transport_raises() -> None:
    """create() must raise ValueError for unregistered transport types."""
    registry = TransportRegistry()
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    with pytest.raises(ValueError, match="Unsupported transport type"):
        registry.create("ws", config)


def test_register_custom_transport() -> None:
    """register() must allow adding a new transport type."""
    registry = TransportRegistry()
    registry.register("fake", FakeTransport)
    types = registry.get_supported_types()
    assert "fake" in types
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = registry.create("fake", config)
    assert isinstance(transport, FakeTransport)


def test_register_overwrite_transport() -> None:
    """register() must allow overwriting an existing transport type."""
    registry = TransportRegistry()
    registry.register("udp", FakeTransport)
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = registry.create("udp", config)
    assert isinstance(transport, FakeTransport)


def test_create_transport_factory() -> None:
    """create_transport factory function must create transports."""
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = create_transport("udp", config)
    assert isinstance(transport, UdpTransport)
