#!/usr/bin/env python3
"""sipx — Audio generators demo (no network needed)."""

from sipx._utils import console
from sipx.media import (
    ToneGenerator,
    SilenceGenerator,
    NoiseGenerator,
    DTMFToneGenerator,
)

# Tone generator (440Hz sine wave)
tone = ToneGenerator(freq=440, sample_rate=8000)
pcm = tone.generate(duration_ms=500)
console.print(
    f"440Hz tone: {len(pcm)} bytes ({len(pcm) // 2} samples, {len(pcm) / 16000:.1f}s)"
)

# Silence
silence = SilenceGenerator()
pcm = silence.generate(duration_ms=200)
console.print(f"Silence: {len(pcm)} bytes ({len(pcm) / 16000:.1f}s)")

# White noise
noise = NoiseGenerator(amplitude=0.3)
pcm = noise.generate(duration_ms=100)
console.print(f"Noise: {len(pcm)} bytes, non-zero: {any(b != 0 for b in pcm)}")

# DTMF tones (real dual-frequency)
dtmf = DTMFToneGenerator()
for digit in "0123456789*#ABCD":
    pcm = dtmf.generate_digit(digit, duration_ms=100)
    freqs = DTMFToneGenerator.FREQS[digit]
    console.print(f"  DTMF '{digit}': {freqs[0]}+{freqs[1]}Hz = {len(pcm)} bytes")
