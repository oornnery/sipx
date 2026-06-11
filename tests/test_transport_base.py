import asyncio
from collections.abc import AsyncIterator
from typing import Literal

import pytest

from sipx.transport.base import Transport, TransportConfig


class MockTransport(Transport):
    def __init__(
        self,
        local_address: tuple[str, int] = ("127.0.0.1", 5060),
        transport_type: Literal["udp", "tcp", "tls"] = "udp",
    ) -> None:
        self._local_address = local_address
        self._transport_type = transport_type
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self._inbox: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self.closed = False

    @property
    def local_address(self) -> tuple[str, int]:
        return self._local_address

    @property
    def transport_type(self) -> Literal["udp", "tcp", "tls"]:
        return self._transport_type

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        self.sent.append((data, remote))

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        while True:
            item = await self._inbox.get()
            yield item

    async def close(self) -> None:
        self.closed = True

    def inject(self, data: bytes, remote: tuple[str, int]) -> None:
        self._inbox.put_nowait((data, remote))


class StoppingMockTransport(Transport):
    """Mock that stops receiving after a fixed number of messages."""

    def __init__(self, messages: list[tuple[bytes, tuple[str, int]]]) -> None:
        self._messages = messages
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.closed = False

    @property
    def local_address(self) -> tuple[str, int]:
        return ("127.0.0.1", 5060)

    @property
    def transport_type(self) -> Literal["udp", "tcp", "tls"]:
        return "udp"

    async def send(self, data: bytes, remote: tuple[str, int]) -> None:
        self.sent.append((data, remote))

    async def receive(self) -> AsyncIterator[tuple[bytes, tuple[str, int]]]:
        for msg in self._messages:
            yield msg

    async def close(self) -> None:
        self.closed = True


def test_transport_is_abstract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Transport()


def test_transport_config_defaults() -> None:
    config = TransportConfig()
    assert config.local_host == "0.0.0.0"
    assert config.local_port == 0
    assert config.timeout == 30.0
    assert config.max_message_size == 65535


def test_transport_config_override() -> None:
    config = TransportConfig(local_host="192.168.1.1", local_port=5060, timeout=5.0, max_message_size=1500)
    assert config.local_host == "192.168.1.1"
    assert config.local_port == 5060
    assert config.timeout == 5.0
    assert config.max_message_size == 1500


def test_mock_transport_send_and_properties() -> None:
    asyncio.run(_mock_transport_send_and_properties())


async def _mock_transport_send_and_properties() -> None:
    transport = MockTransport(local_address=("0.0.0.0", 5060), transport_type="tcp")
    await transport.send(b"hello", ("10.0.0.1", 5060))

    assert transport.sent == [(b"hello", ("10.0.0.1", 5060))]
    assert transport.local_address == ("0.0.0.0", 5060)
    assert transport.transport_type == "tcp"
    assert not transport.closed


def test_mock_transport_receive() -> None:
    asyncio.run(_mock_transport_receive())


async def _mock_transport_receive() -> None:
    transport = StoppingMockTransport(
        messages=[
            (b"msg1", ("10.0.0.1", 5060)),
            (b"msg2", ("10.0.0.2", 5060)),
        ]
    )
    received = []
    async for data, remote in transport.receive():
        received.append((data, remote))

    assert received == [
        (b"msg1", ("10.0.0.1", 5060)),
        (b"msg2", ("10.0.0.2", 5060)),
    ]


def test_mock_transport_close() -> None:
    asyncio.run(_mock_transport_close())


async def _mock_transport_close() -> None:
    transport = MockTransport()
    await transport.close()
    assert transport.closed
