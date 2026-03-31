"""Tests for audio generators."""

from __future__ import annotations

from sipx._media._generators import (
    DTMFToneGenerator,
    NoiseGenerator,
    SilenceGenerator,
    ToneGenerator,
)


class TestToneGenerator:
    def test_generate_100ms_returns_1600_bytes(self):
        gen = ToneGenerator(440)
        data = gen.generate(100)
        # 8000 Hz * 0.1s = 800 samples * 2 bytes = 1600
        assert len(data) == 1600

    def test_sample_rate(self):
        assert ToneGenerator(440).sample_rate == 8000

    def test_non_zero_output(self):
        data = ToneGenerator(440).generate(100)
        assert data != b"\x00" * len(data)


class TestSilenceGenerator:
    def test_generate_100ms_returns_1600_zero_bytes(self):
        data = SilenceGenerator().generate(100)
        assert len(data) == 1600
        assert data == b"\x00" * 1600

    def test_sample_rate(self):
        assert SilenceGenerator().sample_rate == 8000


class TestNoiseGenerator:
    def test_generate_100ms_returns_1600_bytes(self):
        data = NoiseGenerator().generate(100)
        assert len(data) == 1600

    def test_not_all_zero(self):
        data = NoiseGenerator().generate(100)
        assert data != b"\x00" * len(data)

    def test_sample_rate(self):
        assert NoiseGenerator().sample_rate == 8000


class TestDTMFToneGenerator:
    def test_generate_digit_100ms_returns_1600_bytes(self):
        data = DTMFToneGenerator().generate_digit("5", 100)
        assert len(data) == 1600

    def test_freqs_has_all_16_digits(self):
        expected = set("0123456789*#ABCD")
        assert set(DTMFToneGenerator.FREQS.keys()) == expected

    def test_sample_rate(self):
        assert DTMFToneGenerator().sample_rate == 8000

    def test_generate_default_uses_digit_0(self):
        gen = DTMFToneGenerator()
        default = gen.generate(100)
        explicit = gen.generate_digit("0", 100)
        assert len(default) == len(explicit)
