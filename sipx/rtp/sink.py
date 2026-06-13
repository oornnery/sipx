"""Passive RTP UDP sink that binds a port and discards inbound packets.

Opens a UDP endpoint to reserve and advertise a local RTP port (for example
in an SDP offer) without processing media. Useful when a media port must
exist but no audio is consumed.

References:
    RFC 3550 - RTP (UDP transport for media)
    RFC 4566 §5.14 - Media Descriptions (port advertised in SDP)
"""

from __future__ import annotations

import asyncio

from sipx.sip.transport import UdpAddress


class RtpSink:
    def __init__(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    @classmethod
    async def open(cls, *, host: str, port: int) -> RtpSink:
        loop = asyncio.get_running_loop()
        transport, _protocol = await loop.create_datagram_endpoint(
            _RtpSinkProtocol,
            local_addr=(host, port),
        )
        return cls(transport)  # type: ignore[arg-type]

    @property
    def local_address(self) -> UdpAddress:
        host, port = self._transport.get_extra_info("sockname")
        return str(host), int(port)

    def close(self) -> None:
        self._transport.close()


class _RtpSinkProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr: object) -> None:
        return None
