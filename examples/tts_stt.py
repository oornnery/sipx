#!/usr/bin/env python3
"""sipx — TTS and STT adapters (text-to-speech / speech-to-text)."""

from sipx._utils import console
from sipx.media import BaseTTS, BaseSTT, FileTTS, DummySTT, ToneGenerator

# ---------------------------------------------------------------------------
# Built-in adapters
# ---------------------------------------------------------------------------

console.print("[bold]Built-in Adapters[/bold]")

# DummySTT — always returns "hello" (for testing)
stt = DummySTT()
console.print(f"  DummySTT.transcribe() = '{stt.transcribe(b'')}'")

# FileTTS — maps text keys to WAV files
tts = FileTTS(
    prompts={"greeting": "/path/to/greeting.wav", "goodbye": "/path/to/goodbye.wav"}
)
console.print(f"  FileTTS prompts: {list(tts._prompts.keys())}")
# tts.synthesize("greeting") would read the WAV file and return PCM bytes

# ---------------------------------------------------------------------------
# Custom TTS (using ToneGenerator as audio source)
# ---------------------------------------------------------------------------

console.print("\n[bold]Custom TTS (ToneGenerator-based)[/bold]")


class ToneTTS(BaseTTS):
    """TTS that generates tones instead of speech — for demos."""

    @property
    def language(self) -> str:
        return "en-US"

    @property
    def sample_rate(self) -> int:
        return 8000

    def synthesize(self, text: str) -> bytes:
        # Generate a 0.5s tone as "speech"
        tone = ToneGenerator(freq=440, sample_rate=self.sample_rate)
        return tone.generate(duration_ms=500)


tts = ToneTTS()
pcm = tts.synthesize("Hello world")
console.print(f"  ToneTTS.synthesize('Hello world') = {len(pcm)} bytes PCM")
console.print(f"  language={tts.language}, sample_rate={tts.sample_rate}")

# ---------------------------------------------------------------------------
# Custom STT
# ---------------------------------------------------------------------------

console.print("\n[bold]Custom STT[/bold]")


class EchoSTT(BaseSTT):
    """STT that 'transcribes' by returning the audio length — for demos."""

    def transcribe(self, audio: bytes) -> str:
        samples = len(audio) // 2  # 16-bit PCM
        duration_ms = samples / 8  # 8000Hz -> ms
        return f"audio: {duration_ms:.0f}ms"


stt = EchoSTT()
result = stt.transcribe(pcm)
console.print(f"  EchoSTT.transcribe({len(pcm)} bytes) = '{result}'")

# ---------------------------------------------------------------------------
# Google TTS / Whisper STT (optional deps)
# ---------------------------------------------------------------------------

console.print("\n[bold]Optional Adapters[/bold]")

try:
    from sipx.contrib._tts_google import GoogleTTS

    tts = GoogleTTS(language="pt-BR")
    console.print(f"  GoogleTTS: {tts}")
except ImportError as e:
    console.print(f"  GoogleTTS: {e}")

try:
    from sipx.contrib._stt_whisper import WhisperSTT

    stt = WhisperSTT(model="base")
    console.print(f"  WhisperSTT: {stt}")
except ImportError as e:
    console.print(f"  WhisperSTT: {e}")
