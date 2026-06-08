import pytest

from sipx import AudioFrame, BargeInPolicy, BargeInSignal, TranscriptEvent


def test_audio_frame_exposes_safe_metadata() -> None:
    frame = AudioFrame(
        pcm=bytes(160),
        sample_rate=8000,
        channels=1,
        duration_ms=20,
        timestamp_ns=1,
        source="rtp",
    )

    assert frame.byte_length == 160
    assert frame.to_dict() == {
        "byte_length": 160,
        "sample_rate": 8000,
        "channels": 1,
        "duration_ms": 20,
        "timestamp_ns": 1,
        "source": "rtp",
    }


def test_audio_frame_validates_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        AudioFrame(
            pcm=b"",
            sample_rate=0,
            channels=1,
            duration_ms=20,
            timestamp_ns=1,
            source="rtp",
        )


def test_barge_in_policy_controls_interrupt_signals() -> None:
    policy = BargeInPolicy(interrupt_on_dtmf=False)

    assert policy.should_interrupt(BargeInSignal.SPEECH)
    assert not policy.should_interrupt(BargeInSignal.DTMF)
    assert not BargeInPolicy(interruptible=False).should_interrupt("speech")


def test_transcript_event_validates_confidence() -> None:
    event = TranscriptEvent(
        text="hello", is_final=False, timestamp_ns=1, confidence=0.5
    )

    assert event.kind == "partial"

    with pytest.raises(ValueError):
        TranscriptEvent(text="bad", is_final=True, timestamp_ns=1, confidence=1.5)
