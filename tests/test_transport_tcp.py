"""Tests for TcpTransport implementation."""

import asyncio

import pytest

from sipx.exceptions import TransportError
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.tcp import TcpTransport


def test_import_tcp_transport() -> None:
    """TcpTransport can be imported."""
    from sipx.transport.tcp import TcpTransport

    assert TcpTransport is not None


def test_tcp_transport_is_subclass() -> None:
    """TcpTransport is a subclass of Transport."""
    assert issubclass(TcpTransport, Transport)


def test_transport_type() -> None:
    """transport_type returns 'tcp'."""
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = TcpTransport(config)
    assert transport.transport_type == "tcp"


def test_local_address() -> None:
    """local_address returns configured host and port."""
    config = TransportConfig(local_host="192.168.1.1", local_port=5060)
    transport = TcpTransport(config)
    assert transport.local_address == ("192.168.1.1", 5060)


def test_connect() -> None:
    """connect() establishes TCP connection."""
    asyncio.run(_test_connect())


async def _test_connect() -> None:
    connected = asyncio.Event()

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        connected.set()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    assert transport.is_connected_to(("127.0.0.1", port))
    assert transport.connected

    await transport.close()
    server.close()
    await server.wait_closed()


def test_send_auto_connects() -> None:
    """send() auto-connects if not connected."""
    asyncio.run(_test_send_auto_connects())


async def _test_send_auto_connects() -> None:
    received_data = asyncio.Event()
    received_bytes = b""

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        nonlocal received_bytes
        data = await reader.read(1024)
        received_bytes = data
        received_data.set()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = TcpTransport(config)

    # Send without explicit connect
    await transport.send(b"OPTIONS sip:test SIP/2.0\r\n\r\n", ("127.0.0.1", port))

    await asyncio.wait_for(received_data.wait(), timeout=1.0)
    assert received_bytes == b"OPTIONS sip:test SIP/2.0\r\n\r\n"

    await transport.close()
    server.close()
    await server.wait_closed()


def test_receive_message() -> None:
    """receive() yields complete SIP messages."""
    asyncio.run(_test_receive_message())


async def _test_receive_message() -> None:
    message = b"SIP/2.0 200 OK\r\nContent-Length: 4\r\n\r\ntest"

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(message)
        await writer.drain()
        await asyncio.sleep(0.1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0, timeout=1.0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    received = []
    async for data, remote in transport.receive():
        received.append((data, remote))
        break

    assert len(received) == 1
    assert received[0][0] == message
    assert received[0][1] == ("127.0.0.1", port)

    await transport.close()
    server.close()
    await server.wait_closed()


def test_message_framing_content_length() -> None:
    """Messages are framed by Content-Length header."""
    asyncio.run(_test_message_framing_content_length())


async def _test_message_framing_content_length() -> None:
    body = b"v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\n"
    message = f"SIP/2.0 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(message)
        await writer.drain()
        await asyncio.sleep(0.1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0, timeout=1.0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    async for data, remote in transport.receive():
        assert data == message
        break

    await transport.close()
    server.close()
    await server.wait_closed()


def test_multiple_messages_one_segment() -> None:
    """Multiple messages in one TCP segment are parsed correctly."""
    asyncio.run(_test_multiple_messages_one_segment())


async def _test_multiple_messages_one_segment() -> None:
    msg1 = b"SIP/2.0 100 Trying\r\nContent-Length: 0\r\n\r\n"
    msg2 = b"SIP/2.0 200 OK\r\nContent-Length: 2\r\n\r\nOK"
    combined = msg1 + msg2

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(combined)
        await writer.drain()
        await asyncio.sleep(0.1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0, timeout=1.0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    received = []
    async for data, remote in transport.receive():
        received.append(data)
        if len(received) == 2:
            break

    assert received == [msg1, msg2]

    await transport.close()
    server.close()
    await server.wait_closed()


def test_message_split_across_segments() -> None:
    """Messages split across TCP segments are reassembled."""
    asyncio.run(_test_message_split_across_segments())


async def _test_message_split_across_segments() -> None:
    message = b"SIP/2.0 200 OK\r\nContent-Length: 10\r\n\r\n0123456789"
    part1 = message[:20]
    part2 = message[20:]

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(part1)
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.write(part2)
        await writer.drain()
        await asyncio.sleep(0.1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0, timeout=1.0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    async for data, remote in transport.receive():
        assert data == message
        break

    await transport.close()
    server.close()
    await server.wait_closed()


def test_close() -> None:
    """close() closes all connections."""
    asyncio.run(_test_close())


async def _test_close() -> None:
    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await asyncio.sleep(1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))

    assert transport.connected
    await transport.close()
    assert not transport.connected

    server.close()
    await server.wait_closed()


def test_send_after_close_raises() -> None:
    """send() raises TransportError after close()."""
    asyncio.run(_test_send_after_close_raises())


async def _test_send_after_close_raises() -> None:
    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    transport = TcpTransport(config)
    await transport.connect(("127.0.0.1", port))
    await transport.close()

    with pytest.raises(TransportError, match="closed"):
        await transport.send(b"test", ("127.0.0.1", port))

    server.close()
    await server.wait_closed()
