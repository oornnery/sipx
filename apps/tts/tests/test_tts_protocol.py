import sipx_tts


def test_tts_protocol_exports_tts_engine() -> None:
    assert "TtsEngine" in sipx_tts.__all__
    assert sipx_tts.TtsEngine is not None
