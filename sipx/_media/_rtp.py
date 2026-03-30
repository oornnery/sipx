"""
RTP (Real-time Transport Protocol) implementation per RFC 3550.

Provides RTPPacket for serialization/deserialization and RTPSession for
sending and receiving audio over UDP.
"""

from __future__ import annotations

import queue
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ._codecs import PCMA, PCMU, Codec

if TYPE_CHECKING:
    from sipx._models._body import SDPBody


@dataclass
class RTPPacket:
    """
    RTP packet per RFC 3550.

    Header format (12 bytes minimum):
        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |V=2|P|X|  CC   |M|     PT      |       sequence number         |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                           timestamp                           |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |           synchronization source (SSRC) identifier            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    version: int = 2
    padding: bool = False
    extension: bool = False
    csrc_count: int = 0
    marker: bool = False
    payload_type: int = 0
    sequence_number: int = 0
    timestamp: int = 0
    ssrc: int = 0
    payload: bytes = b""

    def to_bytes(self) -> bytes:
        """Serialize to raw bytes (12-byte header + payload)."""
        byte0 = (
            (self.version << 6)
            | (int(self.padding) << 5)
            | (int(self.extension) << 4)
            | (self.csrc_count & 0x0F)
        )
        byte1 = (int(self.marker) << 7) | (self.payload_type & 0x7F)

        header = struct.pack(
            "!BBHII",
            byte0,
            byte1,
            self.sequence_number & 0xFFFF,
            self.timestamp & 0xFFFFFFFF,
            self.ssrc & 0xFFFFFFFF,
        )
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> RTPPacket:
        """Parse an RTPPacket from raw bytes."""
        if len(data) < 12:
            raise ValueError(f"RTP packet too short: {len(data)} bytes (minimum 12)")

        byte0, byte1, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])

        version = (byte0 >> 6) & 0x03
        padding = bool((byte0 >> 5) & 0x01)
        extension = bool((byte0 >> 4) & 0x01)
        csrc_count = byte0 & 0x0F
        marker = bool((byte1 >> 7) & 0x01)
        payload_type = byte1 & 0x7F

        header_len = 12 + csrc_count * 4
        payload = data[header_len:] if len(data) > header_len else b""

        return cls(
            version=version,
            padding=padding,
            extension=extension,
            csrc_count=csrc_count,
            marker=marker,
            payload_type=payload_type,
            sequence_number=seq,
            timestamp=ts,
            ssrc=ssrc,
            payload=payload,
        )


# Codec registry for lookup by payload type
_CODEC_REGISTRY: dict[int, type[Codec]] = {
    0: PCMU,
    8: PCMA,
}


class RTPSession:
    """
    RTP media session using a UDP socket.

    Manages sending and receiving RTP packets on a dedicated UDP port,
    separate from SIP signaling transport.
    """

    def __init__(
        self,
        local_ip: str,
        local_port: int,
        remote_ip: str,
        remote_port: int,
        payload_type: int = 0,
        clock_rate: int = 8000,
        codec: Optional[Codec] = None,
    ) -> None:
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.payload_type = payload_type
        self.clock_rate = clock_rate

        # Resolve codec
        if codec is not None:
            self.codec = codec
        elif payload_type in _CODEC_REGISTRY:
            self.codec = _CODEC_REGISTRY[payload_type]()
        else:
            self.codec = PCMU()  # default fallback

        # RTP state
        self._ssrc = random.randint(0, 0xFFFFFFFF)
        self._sequence_number = random.randint(0, 0xFFFF)
        self._timestamp = random.randint(0, 0xFFFFFFFF)

        # Packetization: 20ms at clock_rate
        self._samples_per_packet = clock_rate // 50  # 160 for 8 kHz

        # Socket
        self._socket: Optional[socket.socket] = None

        # Threading
        self._recv_buffer: queue.Queue[RTPPacket] = queue.Queue()
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind the UDP socket and start the receive thread."""
        if self._running:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.local_ip, self.local_port))
        self._socket.settimeout(0.5)

        self._running = True
        self._recv_thread = threading.Thread(
            target=self._recv_loop, daemon=True, name="rtp-recv"
        )
        self._recv_thread.start()

    def stop(self) -> None:
        """Stop threads and close the socket."""
        self._running = False
        if self._recv_thread is not None:
            self._recv_thread.join(timeout=2.0)
            self._recv_thread = None
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RTPSession":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send_packet(self, packet: RTPPacket) -> None:
        """Send a raw RTP packet to the remote endpoint."""
        if self._socket is None:
            raise RuntimeError("RTPSession is not started")
        data = packet.to_bytes()
        self._socket.sendto(data, (self.remote_ip, self.remote_port))

    def send_audio(self, pcm_data: bytes) -> None:
        """
        Encode PCM data and send as RTP packets at 20 ms intervals.

        Args:
            pcm_data: 16-bit signed little-endian PCM audio.
        """
        # bytes per 20ms packet (16-bit samples)
        bytes_per_packet = self._samples_per_packet * 2

        offset = 0
        while offset < len(pcm_data):
            chunk = pcm_data[offset : offset + bytes_per_packet]
            if not chunk:
                break

            encoded = self.codec.encode(chunk)

            packet = RTPPacket(
                payload_type=self.payload_type,
                sequence_number=self._sequence_number & 0xFFFF,
                timestamp=self._timestamp & 0xFFFFFFFF,
                ssrc=self._ssrc,
                payload=encoded,
            )
            self.send_packet(packet)

            self._sequence_number += 1
            self._timestamp += self._samples_per_packet
            offset += bytes_per_packet

            # Pace at ~20 ms
            time.sleep(0.020)

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    def recv_packet(self, timeout: float = 1.0) -> Optional[RTPPacket]:
        """Receive a single RTP packet (blocking with timeout)."""
        try:
            return self._recv_buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    def recv_audio(self, timeout: float = 1.0) -> Optional[bytes]:
        """Receive an RTP packet, decode, and return PCM audio."""
        packet = self.recv_packet(timeout=timeout)
        if packet is None:
            return None
        return self.codec.decode(packet.payload)

    def _recv_loop(self) -> None:
        """Background thread: read UDP datagrams and enqueue RTP packets."""
        while self._running:
            if self._socket is None:
                break
            try:
                data, _addr = self._socket.recvfrom(4096)
                if len(data) >= 12:
                    packet = RTPPacket.from_bytes(data)
                    self._recv_buffer.put(packet)
            except socket.timeout:
                continue
            except OSError:
                break

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_sdp(
        cls,
        sdp_body: "SDPBody",
        local_ip: str,
        local_port: int,
    ) -> "RTPSession":
        """
        Create an RTPSession from an SDP body.

        Uses the first audio media description to determine remote IP/port
        and codec payload type.

        Args:
            sdp_body: Parsed SDPBody (typically from a 200 OK).
            local_ip: Local IP address to bind.
            local_port: Local UDP port to bind.

        Returns:
            Configured (but not started) RTPSession.
        """
        remote_ip = sdp_body.get_connection_address() or "127.0.0.1"
        ports = sdp_body.get_media_ports()
        remote_port = ports.get("audio", 0)

        # Determine payload type from first accepted codec
        codecs = sdp_body.get_accepted_codecs(0)
        payload_type = 0
        clock_rate = 8000
        if codecs:
            payload_type = int(codecs[0]["payload"])
            if "rate" in codecs[0]:
                clock_rate = int(codecs[0]["rate"])

        return cls(
            local_ip=local_ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            payload_type=payload_type,
            clock_rate=clock_rate,
        )
