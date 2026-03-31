"""Tests for DTMF encoding/decoding (RFC 4733)."""

from __future__ import annotations

from sipx._media._dtmf import (
    DTMF_EVENTS,
    decode_dtmf_event,
    encode_dtmf_event,
    event_to_digit,
)


class TestEncodeDecode:
    def test_roundtrip(self):
        data = encode_dtmf_event(event=5, end=False, volume=10, duration=800)
        result = decode_dtmf_event(data)
        assert result["event"] == 5
        assert result["end"] is False
        assert result["volume"] == 10
        assert result["duration"] == 800

    def test_end_bit_set(self):
        data = encode_dtmf_event(event=0, end=True, volume=0, duration=0)
        result = decode_dtmf_event(data)
        assert result["end"] is True

    def test_end_bit_clear(self):
        data = encode_dtmf_event(event=0, end=False, volume=0, duration=0)
        result = decode_dtmf_event(data)
        assert result["end"] is False

    def test_volume_preserved(self):
        for vol in (0, 10, 63):
            data = encode_dtmf_event(event=0, end=False, volume=vol, duration=0)
            assert decode_dtmf_event(data)["volume"] == vol

    def test_duration_preserved(self):
        for dur in (0, 160, 1280, 65535):
            data = encode_dtmf_event(event=0, end=False, volume=0, duration=dur)
            assert decode_dtmf_event(data)["duration"] == dur

    def test_all_events_roundtrip(self):
        for digit, code in DTMF_EVENTS.items():
            data = encode_dtmf_event(event=code, end=True, volume=10, duration=160)
            result = decode_dtmf_event(data)
            assert result["event"] == code


class TestDTMFEvents:
    def test_all_16_digits(self):
        expected = set("0123456789*#ABCD")
        assert set(DTMF_EVENTS.keys()) == expected
        assert len(DTMF_EVENTS) == 16


class TestEventToDigit:
    def test_all_codes_0_to_15(self):
        expected = list("0123456789*#ABCD")
        for code in range(16):
            assert event_to_digit(code) == expected[code]

    def test_invalid_code_returns_none(self):
        assert event_to_digit(16) is None
        assert event_to_digit(99) is None
        assert event_to_digit(-1) is None
