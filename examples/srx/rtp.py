"""
Pacote RTP básico: estrutura e construção de pacotes RTP.
"""

import struct


class RTPPacket:
    def __init__(
        self, payload: bytes, ssrc: int = 11111, seq: int = 1, timestamp: int = 0
    ):
        self.header = struct.pack("!BBHII", 0x80, 0x00, seq, timestamp, ssrc)
        self.payload = payload

    def build(self) -> bytes:
        return self.header + self.payload
