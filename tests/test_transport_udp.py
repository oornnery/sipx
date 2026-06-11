"""Tests for UdpTransport implementation.

Uses real loopback UDP sockets (127.0.0.1:0) for testing.
"""

from __future__ import annotations

import asyncio

import pytest

from sipx.exceptions import TransportError
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.udp import UdpTransport


def test_udp_transport_implements_transport() -> None:
    """UdpTransport must be a subclass of Transport."""
    assert issubclass(UdpTransport, Transport)


def test_udp_transport_type() -> None:
    """transport_type must return 'udp'."""
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = UdpTransport(config)
    assert transport.transport_type == "udp"


def test_udp_transport_config_validation_empty_host() -> None:
    """Empty local_host must raise TransportError."""
    config = TransportConfig(local_host="", local_port=0)
    with pytest.raises(TransportError, match="local_host is required"):
        UdpTransport(config)


def test_udp_transport_config_validation_invalid_port() -> None:
    """Invalid port must raise TransportError."""
    config = TransportConfig(local_host="127.0.0.1", local_port=70000)
    with pytest.raises(TransportError, match="local_port must be between"):
        UdpTransport(config)


def test_udp_transport_config_validation_invalid_max_size() -> None:
    """Non-positive max_message_size must raise TransportError."""
    config = TransportConfig(local_host="127.0.0.1", local_port=0, max_message_size=0)
    with pytest.raises(TransportError, match="max_message_size must be positive"):
        UdpTransport(config)


def test_udp_transport_start_and_local_address() -> None:
    """start() must bind socket and local_address must return bound address."""
    asyncio.run(_test_start_and_local_address())


async def _test_start_and_local_address() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = UdpTransport(config)
    await transport.start()
    try:
        host, port = transport.local_address
        assert host == "127.0.0.1"
        assert port > 0  # OS assigned a port
    finally:
        await transport.close()


def test_udp_transport_send_not_started() -> None:
    """send() before start() must raise TransportError."""
    asyncio.run(_test_send_not_started())


async def _test_send_not_started() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = UdpTransport(config)
    with pytest.raises(TransportError, match="not started"):
        await transport.send(b"hello", ("127.0.0.1", 5060))


def test_udp_transport_send_oversized() -> None:
    """send() with oversized message must raise TransportError."""
    asyncio.run(_test_send_oversized())


async def _test_send_oversized() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0, max_message_size=10)
    transport = UdpTransport(config)
    await transport.start()
    try:
        with pytest.raises(TransportError, match="exceeds maximum"):
            await transport.send(b"x" * 100, ("127.0.0.1", 5060))
    finally:
        await transport.close()


def test_udp_transport_send_receive_roundtrip() -> None:
    """Two transports must be able to send and receive datagrams."""
    asyncio.run(_test_send_receive_roundtrip())


async def _test_send_receive_roundtrip() -> None:
    # Create two transports on loopback
    config_a = TransportConfig(local_host="127.0.0.1", local_port=0)
    config_b = TransportConfig(local_host="127.0.0.1", local_port=0)

    transport_a = UdpTransport(config_a)
    transport_b = UdpTransport(config_b)

    await transport_a.start()
    await transport_b.start()

    try:
        addr_b = transport_b.local_address

        # Send from A to B
        await transport_a.send(b"hello from A", addr_b)

        # Receive on B with timeout
        received = await asyncio.wait_for(_receive_one(transport_b), timeout=2.0)

        data, remote = received
        assert data == b"hello from A"
        assert remote == transport_a.local_address
    finally:
        await transport_a.close()
        await transport_b.close()


async def _receive_one(transport: UdpTransport) -> tuple[bytes, tuple[str, int]]:
    """Receive exactly one datagram from transport."""
    async for item in transport.receive():
        return item
    raise RuntimeError("Transport closed before receiving")


def test_udp_transport_close() -> None:
    """close() must release resources and be idempotent."""
    asyncio.run(_test_close())


async def _test_close() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = UdpTransport(config)
    await transport.start()

    # First close
    await transport.close()

    # Second close should not raise
    await transport.close()

    # send() after close must raise
    with pytest.raises(TransportError, match="not started"):
        await transport.send(b"hello", ("127.0.0.1", 5060))


def test_udp_transport_context_manager() -> None:
    """async with must start and close transport."""
    asyncio.run(_test_context_manager())


async def _test_context_manager() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0)

    async with UdpTransport(config) as transport:
        host, port = transport.local_address
        assert host == "127.0.0.1"
        assert port > 0

    # After context exit, transport should be closed
    with pytest.raises(TransportError, match="not started"):
        await transport.send(b"hello", ("127.0.0.1", 5060))
