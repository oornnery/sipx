import pytest

import sipx
import sipx.media as media
from sipx import (
    AudioFrame,
    BargeInPolicy,
    BargeInSignal,
    PyAudioError,
    PyAudioInputSource,
    SyntheticAudioSource,
)
from sipx.media import pyaudio as pyaudio_media


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


def test_synthetic_audio_source_generates_silence_frame() -> None:
    source = SyntheticAudioSource(
        mode="silence", sample_rate=8000, frame_duration_ms=20
    )

    frame = source.next_frame(timestamp_ns=123)

    assert frame.pcm.tobytes() == bytes(320)
    assert frame.sample_rate == 8000
    assert frame.channels == 1
    assert frame.duration_ms == 20
    assert frame.timestamp_ns == 123
    assert frame.source == "silence"


def test_synthetic_audio_source_generates_deterministic_noise() -> None:
    first = SyntheticAudioSource(mode="noise", noise_level=0.01, seed=7)
    second = SyntheticAudioSource(mode="noise", noise_level=0.01, seed=7)

    first_frame = first.next_frame(timestamp_ns=1)
    second_frame = second.next_frame(timestamp_ns=1)

    assert first_frame.pcm.tobytes() == second_frame.pcm.tobytes()
    assert first_frame.pcm.tobytes() != bytes(first.bytes_per_frame)
    assert first_frame.source == "noise"


def test_root_media_does_not_export_speech_adapter_protocols() -> None:
    assert not hasattr(sipx, "TranscriptEvent")
    assert not hasattr(sipx, "SttEngine")
    assert not hasattr(sipx, "SttStream")
    assert not hasattr(sipx, "TtsEngine")
    assert not hasattr(media, "TranscriptEvent")
    assert not hasattr(media, "SttEngine")
    assert not hasattr(media, "SttStream")
    assert not hasattr(media, "TtsEngine")


def test_pyaudio_optional_dependency_fails_loud(monkeypatch) -> None:
    def fake_import_module(name: str):
        raise ImportError(name)

    monkeypatch.setattr(pyaudio_media.importlib, "import_module", fake_import_module)

    with pytest.raises(PyAudioError, match="optional dependency 'pyaudio'"):
        pyaudio_media.ensure_pyaudio_available()


def test_pyaudio_input_source_uses_lazy_module(monkeypatch) -> None:
    calls = {"terminated": False, "closed": False}

    class FakeStream:
        def read(self, frames_per_buffer, *, exception_on_overflow):
            assert frames_per_buffer == 160
            assert exception_on_overflow is False
            return bytes(320)

        def stop_stream(self) -> None:
            calls["closed"] = True

        def close(self) -> None:
            calls["closed"] = True

    class FakePyAudio:
        def open(self, **kwargs):
            assert kwargs["rate"] == 8000
            assert kwargs["channels"] == 1
            assert kwargs["input"] is True
            return FakeStream()

        def terminate(self) -> None:
            calls["terminated"] = True

    class FakeModule:
        paInt16 = object()

        @staticmethod
        def PyAudio():
            return FakePyAudio()

    monkeypatch.setattr(
        pyaudio_media.importlib,
        "import_module",
        lambda name: FakeModule,
    )

    source = PyAudioInputSource()
    source.start()
    frame = source.next_frame()
    source.close()

    assert frame.pcm.tobytes() == bytes(320)
    assert frame.source == "pyaudio"
    assert calls == {"terminated": True, "closed": True}
