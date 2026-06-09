import pytest

from sipx_stt import TranscriptEvent


def test_transcript_event_validates_confidence() -> None:
    event = TranscriptEvent(
        text="hello",
        is_final=False,
        timestamp_ns=1,
        confidence=0.5,
    )

    assert event.kind == "partial"

    with pytest.raises(ValueError):
        TranscriptEvent(text="bad", is_final=True, timestamp_ns=1, confidence=1.5)
