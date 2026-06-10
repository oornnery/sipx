from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from random import randrange
from typing import Literal

from sipx.media import AudioFrame, SyntheticAudioSource
from sipx.rtp.buffer import RtpJitterBuffer, RtpJitterBufferSnapshot
from sipx.rtp.g711 import G711_CHANNELS, G711_SAMPLE_RATE, decode_g711, encode_g711
from sipx.rtp.packet import RtpPacket, RtpParseError
from sipx.rtp.stats import RtpMetrics, RtpMetricsSnapshot
from sipx.sip.transport import UdpAddress


RtpAudioMode = Literal["silence", "noise"]


class RtpWireDirection(StrEnum):
    RX = "rx"
    TX = "tx"


@dataclass(frozen=True, slots=True)
class RtpWireEvent:
    direction: RtpWireDirection
    remote: UdpAddress
    raw: bytes
    packet: RtpPacket | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass(frozen=True, slots=True)
class RtpAudioSessionConfig:
    remote: UdpAddress | None = None
    local_host: str = "127.0.0.1"
    local_port: int = 0
    codec: str = "PCMU"
    payload_type: int = 0
    ptime_ms: int = 20
    jitter_buffer_ms: int = 60
    max_jitter_buffer_ms: int = 200
    ssrc: int | None = None
    event_hooks: dict[str, list[Callable[[RtpWireEvent], None]]] | None = None

    def __post_init__(self) -> None:
        if not self.local_host:
            raise ValueError("local_host is required")
        if not 0 <= self.local_port <= 65535:
            raise ValueError("local_port must be between 0 and 65535")
        if self.codec.upper() not in {"PCMU", "PCMA"}:
            raise ValueError("codec must be PCMU or PCMA")
        if not 0 <= self.payload_type <= 127:
            raise ValueError("payload_type must be between 0 and 127")
        if self.ptime_ms <= 0:
            raise ValueError("ptime_ms must be positive")
        if self.jitter_buffer_ms < 0:
            raise ValueError("jitter_buffer_ms must be non-negative")
        if self.max_jitter_buffer_ms < self.jitter_buffer_ms:
            raise ValueError(
                "max_jitter_buffer_ms must be greater than or equal to jitter_buffer_ms"
            )
        if self.ssrc is not None and not 0 <= self.ssrc <= 0xFFFFFFFF:
            raise ValueError("ssrc must be a uint32")


@dataclass(frozen=True, slots=True)
class RtpAudioSessionSnapshot:
    codec: str
    payload_type: int
    ptime_ms: int
    sample_rate: int
    channels: int
    local_address: UdpAddress
    remote: UdpAddress | None
    metrics: RtpMetricsSnapshot
    jitter_buffer: RtpJitterBufferSnapshot


@dataclass(frozen=True, slots=True)
class _RtpDatagram:
    data: bytes
    remote: UdpAddress
    arrival_time: float


class RtpAudioSession:
    def __init__(
        self,
        config: RtpAudioSessionConfig,
        transport: asyncio.DatagramTransport,
        protocol: _RtpAudioProtocol,
    ) -> None:
        self.config = config
        self._transport = transport
        self._protocol = protocol
        self._codec = config.codec.upper()
        self._sequence_number = 0
        self._timestamp = 0
        self._ssrc = (
            config.ssrc if config.ssrc is not None else randrange(0, 0xFFFFFFFF)
        )
        self._metrics = RtpMetrics()
        self._jitter_buffer = RtpJitterBuffer(
            ptime_ms=config.ptime_ms,
            target_ms=config.jitter_buffer_ms,
            max_ms=config.max_jitter_buffer_ms,
            concealment_payload=self._silence_payload(),
        )
        self._rtp_hooks: list[Callable[[RtpWireEvent], None]] = list(
            (config.event_hooks or {}).get("rtp", [])
        )

    @classmethod
    async def open(cls, config: RtpAudioSessionConfig) -> RtpAudioSession:
        loop = asyncio.get_running_loop()
        protocol = _RtpAudioProtocol()
        transport, created_protocol = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=(config.local_host, config.local_port),
        )
        return cls(config, transport, created_protocol)  # type: ignore[arg-type]

    @property
    def local_address(self) -> UdpAddress:
        host, port = self._transport.get_extra_info("sockname")
        return str(host), int(port)

    @property
    def remote(self) -> UdpAddress | None:
        return self.config.remote

    @property
    def metrics(self) -> RtpMetricsSnapshot:
        return self._metrics.snapshot()

    @property
    def jitter_buffer(self) -> RtpJitterBufferSnapshot:
        return self._jitter_buffer.snapshot()

    async def close(self) -> None:
        self._transport.close()
        await self._protocol.wait_closed()

    async def __aenter__(self) -> RtpAudioSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        await self.close()

    async def send_frame(
        self,
        frame: AudioFrame,
        *,
        remote: UdpAddress | None = None,
    ) -> RtpPacket:
        if frame.sample_rate != G711_SAMPLE_RATE:
            raise ValueError("G.711 RTP frame sample_rate must be 8000")
        if frame.channels != G711_CHANNELS:
            raise ValueError("G.711 RTP frame channels must be 1")
        target = remote or self.config.remote
        if target is None:
            raise ValueError("remote RTP address is required")
        payload = encode_g711(self._codec, frame.pcm)
        packet = RtpPacket(
            payload_type=self.config.payload_type,
            sequence_number=self._sequence_number,
            timestamp=self._timestamp,
            ssrc=self._ssrc,
            payload=payload,
        )
        raw = packet.to_bytes()
        self._transport.sendto(raw, target)
        self._metrics.record_tx(packet)
        self._sequence_number = (self._sequence_number + 1) & 0xFFFF
        self._timestamp = (self._timestamp + self._samples_per_frame()) & 0xFFFFFFFF
        self._fire_rtp_hooks(RtpWireDirection.TX, raw, packet, remote=target)
        return packet

    async def send_synthetic(
        self,
        *,
        mode: RtpAudioMode = "silence",
        frames: int = 1,
        remote: UdpAddress | None = None,
        noise_level: float = 0.03,
        seed: int | None = 1,
    ) -> tuple[RtpPacket, ...]:
        if frames <= 0:
            raise ValueError("frames must be positive")
        source = SyntheticAudioSource(
            mode=mode,
            sample_rate=G711_SAMPLE_RATE,
            channels=G711_CHANNELS,
            frame_duration_ms=self.config.ptime_ms,
            noise_level=noise_level,
            seed=seed,
        )
        packets: list[RtpPacket] = []
        next_deadline = time.monotonic()
        for _ in range(frames):
            packets.append(await self.send_frame(source.next_frame(), remote=remote))
            next_deadline += self.config.ptime_ms / 1000
            delay = next_deadline - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
        return tuple(packets)

    async def receive_packet(self, *, timeout: float = 1.0) -> RtpPacket:
        datagram = await self._protocol.receive(timeout=timeout)
        try:
            packet = RtpPacket.parse(datagram.data)
        except RtpParseError as exc:
            self._metrics.rx.record_parse_error()
            self._fire_rtp_hooks(
                RtpWireDirection.RX,
                datagram.data,
                None,
                remote=datagram.remote,
                error=str(exc),
            )
            raise
        self._metrics.record_rx(
            packet,
            arrival_time=datagram.arrival_time,
            clock_rate=G711_SAMPLE_RATE,
        )
        if packet.payload_type == self.config.payload_type:
            self._jitter_buffer.push(packet)
        self._fire_rtp_hooks(
            RtpWireDirection.RX,
            datagram.data,
            packet,
            remote=datagram.remote,
        )
        return packet

    async def receive_frame(self, *, timeout: float = 1.0) -> AudioFrame:
        await self.receive_packet(timeout=timeout)
        playout = self._jitter_buffer.pop()
        try:
            pcm = decode_g711(self._codec, playout.payload)
        except ValueError:
            self._metrics.rx.record_decode_error()
            raise
        return AudioFrame(
            pcm=pcm,
            sample_rate=G711_SAMPLE_RATE,
            channels=G711_CHANNELS,
            duration_ms=self.config.ptime_ms,
            timestamp_ns=time.monotonic_ns(),
            source="rtp",
        )

    def snapshot(self) -> RtpAudioSessionSnapshot:
        return RtpAudioSessionSnapshot(
            codec=self._codec,
            payload_type=self.config.payload_type,
            ptime_ms=self.config.ptime_ms,
            sample_rate=G711_SAMPLE_RATE,
            channels=G711_CHANNELS,
            local_address=self.local_address,
            remote=self.config.remote,
            metrics=self._metrics.snapshot(),
            jitter_buffer=self._jitter_buffer.snapshot(),
        )

    def _samples_per_frame(self) -> int:
        return G711_SAMPLE_RATE * self.config.ptime_ms // 1000

    def _fire_rtp_hooks(
        self,
        direction: RtpWireDirection,
        raw: bytes,
        packet: RtpPacket | None,
        *,
        remote: UdpAddress | None = None,
        error: str | None = None,
    ) -> None:
        if not self._rtp_hooks:
            return
        event = RtpWireEvent(
            direction=direction,
            remote=(remote or self.config.remote or ("", 0)),
            raw=raw,
            packet=packet,
            error=error,
        )
        for hook in self._rtp_hooks:
            hook(event)

    def _silence_payload(self) -> bytes:
        pcm = bytes(self._samples_per_frame() * 2)
        return encode_g711(self._codec, pcm)


class _RtpAudioProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self._datagrams: asyncio.Queue[_RtpDatagram] = asyncio.Queue()
        self._closed = asyncio.Event()

    def datagram_received(self, data: bytes, addr: object) -> None:
        remote = _remote_address(addr)
        self._datagrams.put_nowait(
            _RtpDatagram(
                data=data,
                remote=remote,
                arrival_time=time.monotonic(),
            )
        )

    def connection_lost(self, exc: Exception | None) -> None:
        self._closed.set()

    async def receive(self, *, timeout: float) -> _RtpDatagram:
        try:
            return await asyncio.wait_for(self._datagrams.get(), timeout=timeout)
        except TimeoutError as exc:
            raise TimeoutError("timed out waiting for RTP datagram") from exc

    async def wait_closed(self) -> None:
        try:
            await asyncio.wait_for(self._closed.wait(), timeout=1.0)
        except TimeoutError:
            pass


def _remote_address(addr: object) -> UdpAddress:
    if not isinstance(addr, tuple) or len(addr) < 2:
        return str(addr), 0
    host = addr[0]
    port = addr[1]
    return str(host), int(port) if isinstance(port, int) else int(str(port))
