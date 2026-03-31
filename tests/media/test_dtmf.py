"""Tests for DTMF encoding/decoding (RFC 4733)."""

from __future__ import annotations

from sipx._media._dtmf import DTMF_EVENTS, DTMFEvent


class TestDTMFEvent:
    def test_roundtrip(self):
        evt = DTMFEvent(event=5, end=False, volume=10, duration=800)
        data = evt.to_bytes()
        parsed = DTMFEvent.from_bytes(data)
        assert parsed.event == 5
        assert parsed.end is False
        assert parsed.volume == 10
        assert parsed.duration == 800

    def test_end_bit_set(self):
        evt = DTMFEvent(event=0, end=True)
        parsed = DTMFEvent.from_bytes(evt.to_bytes())
        assert parsed.end is True

    def test_end_bit_clear(self):
        evt = DTMFEvent(event=0, end=False)
        parsed = DTMFEvent.from_bytes(evt.to_bytes())
        assert parsed.end is False

    def test_volume_preserved(self):
        for vol in (0, 10, 63):
            evt = DTMFEvent(event=0, volume=vol)
            assert DTMFEvent.from_bytes(evt.to_bytes()).volume == vol

    def test_duration_preserved(self):
        for dur in (0, 160, 1280, 65535):
            evt = DTMFEvent(event=0, duration=dur)
            assert DTMFEvent.from_bytes(evt.to_bytes()).duration == dur

    def test_all_events_roundtrip(self):
        for digit, code in DTMF_EVENTS.items():
            evt = DTMFEvent(event=code, end=True, volume=10, duration=160)
            parsed = DTMFEvent.from_bytes(evt.to_bytes())
            assert parsed.event == code

    def test_from_bytes_short_data(self):
        evt = DTMFEvent.from_bytes(b"\x00")
        assert evt.event == 0

    def test_digit_property(self):
        expected = list("0123456789*#ABCD")
        for code in range(16):
            assert DTMFEvent(event=code).digit == expected[code]

    def test_digit_invalid(self):
        assert DTMFEvent(event=16).digit is None
        assert DTMFEvent(event=99).digit is None

    def test_from_digit(self):
        evt = DTMFEvent.from_digit("5", volume=10, duration=160)
        assert evt.event == 5
        assert evt.volume == 10
        assert evt.duration == 160

    def test_from_digit_all(self):
        for digit in "0123456789*#ABCD":
            evt = DTMFEvent.from_digit(digit)
            assert evt.digit == digit

    def test_from_digit_invalid(self):
        import pytest
        with pytest.raises(ValueError):
            DTMFEvent.from_digit("X")


class TestDTMFEvents:
    def test_all_16_digits(self):
        expected = set("0123456789*#ABCD")
        assert set(DTMF_EVENTS.keys()) == expected
        assert len(DTMF_EVENTS) == 16
