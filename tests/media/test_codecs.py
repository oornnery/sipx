"""Tests for G.711 PCMU and PCMA codecs."""

from __future__ import annotations

import struct

from sipx._media._codecs import PCMA, PCMU


class TestPCMUProperties:
    def test_name(self):
        assert PCMU().name == "PCMU"

    def test_payload_type(self):
        assert PCMU().payload_type == 0

    def test_clock_rate(self):
        assert PCMU().clock_rate == 8000

    def test_sample_size(self):
        assert PCMU().sample_size == 1


class TestPCMAProperties:
    def test_name(self):
        assert PCMA().name == "PCMA"

    def test_payload_type(self):
        assert PCMA().payload_type == 8

    def test_clock_rate(self):
        assert PCMA().clock_rate == 8000

    def test_sample_size(self):
        assert PCMA().sample_size == 1


class TestPCMUEncodeDecode:
    def test_encode_320_bytes_to_160(self):
        pcm = b"\x00" * 320  # 160 samples of silence
        encoded = PCMU().encode(pcm)
        assert len(encoded) == 160

    def test_decode_160_bytes_to_320(self):
        data = b"\xff" * 160  # mu-law silence is 0xFF
        decoded = PCMU().decode(data)
        assert len(decoded) == 320

    def test_roundtrip_fidelity(self):
        """decode(encode(pcm)) should produce reasonable approximation."""
        codec = PCMU()
        # Generate a simple PCM signal (16-bit LE samples)
        pcm = b""
        for i in range(160):
            sample = int(8000 * (i / 160))  # ramp
            pcm += struct.pack("<h", sample)
        encoded = codec.encode(pcm)
        decoded = codec.decode(encoded)
        # Check that decoded samples are within ~2% of 32768 range
        for i in range(160):
            orig = struct.unpack_from("<h", pcm, i * 2)[0]
            recon = struct.unpack_from("<h", decoded, i * 2)[0]
            assert abs(orig - recon) < 2000, f"Sample {i}: {orig} vs {recon}"


class TestPCMAEncodeDecode:
    def test_encode_320_bytes_to_160(self):
        pcm = b"\x00" * 320
        encoded = PCMA().encode(pcm)
        assert len(encoded) == 160

    def test_decode_160_bytes_to_320(self):
        data = b"\xd5" * 160  # A-law silence
        decoded = PCMA().decode(data)
        assert len(decoded) == 320

    def test_roundtrip_fidelity(self):
        codec = PCMA()
        pcm = b""
        for i in range(160):
            sample = int(8000 * (i / 160))
            pcm += struct.pack("<h", sample)
        encoded = codec.encode(pcm)
        decoded = codec.decode(encoded)
        for i in range(160):
            orig = struct.unpack_from("<h", pcm, i * 2)[0]
            recon = struct.unpack_from("<h", decoded, i * 2)[0]
            assert abs(orig - recon) < 2000, f"Sample {i}: {orig} vs {recon}"
