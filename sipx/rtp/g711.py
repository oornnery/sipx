from __future__ import annotations


G711_SAMPLE_RATE = 8000
G711_CHANNELS = 1

_PCM_MAX = 32767
_PCM_MIN = -32768
_ULAW_BIAS = 0x84
_ULAW_CLIP = 32635
_ALAW_SEG_END = (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF)


class G711Error(ValueError):
    pass


def encode_pcmu(pcm: bytes | bytearray | memoryview) -> bytes:
    data = _pcm_bytes(pcm)
    return bytes(
        _linear_to_ulaw(_sample(data, offset)) for offset in range(0, len(data), 2)
    )


def decode_pcmu(payload: bytes | bytearray | memoryview) -> bytes:
    output = bytearray()
    for value in bytes(payload):
        output.extend(
            _clip_int16(_ulaw_to_linear(value)).to_bytes(2, "little", signed=True)
        )
    return bytes(output)


def encode_pcma(pcm: bytes | bytearray | memoryview) -> bytes:
    data = _pcm_bytes(pcm)
    return bytes(
        _linear_to_alaw(_sample(data, offset)) for offset in range(0, len(data), 2)
    )


def decode_pcma(payload: bytes | bytearray | memoryview) -> bytes:
    output = bytearray()
    for value in bytes(payload):
        output.extend(
            _clip_int16(_alaw_to_linear(value)).to_bytes(2, "little", signed=True)
        )
    return bytes(output)


def encode_g711(codec: str, pcm: bytes | bytearray | memoryview) -> bytes:
    name = codec.upper()
    if name == "PCMU":
        return encode_pcmu(pcm)
    if name == "PCMA":
        return encode_pcma(pcm)
    raise G711Error(f"unsupported G.711 codec: {codec}")


def decode_g711(codec: str, payload: bytes | bytearray | memoryview) -> bytes:
    name = codec.upper()
    if name == "PCMU":
        return decode_pcmu(payload)
    if name == "PCMA":
        return decode_pcma(payload)
    raise G711Error(f"unsupported G.711 codec: {codec}")


def _pcm_bytes(pcm: bytes | bytearray | memoryview) -> bytes:
    data = bytes(pcm)
    if len(data) % 2:
        raise G711Error("PCM16 payload length must be even")
    return data


def _sample(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=True)


def _linear_to_ulaw(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    magnitude = -sample if sample < 0 else sample
    magnitude = min(magnitude, _ULAW_CLIP) + _ULAW_BIAS
    exponent = min(max(magnitude.bit_length() - 8, 0), 7)
    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def _ulaw_to_linear(value: int) -> int:
    value = (~value) & 0xFF
    sign = value & 0x80
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F
    sample = ((mantissa << 3) + _ULAW_BIAS) << exponent
    sample -= _ULAW_BIAS
    return -sample if sign else sample


def _linear_to_alaw(sample: int) -> int:
    if sample >= 0:
        mask = 0xD5
        magnitude = sample
    else:
        mask = 0x55
        magnitude = min(-sample - 1, _PCM_MAX)

    segment = _alaw_segment(magnitude >> 3)
    if segment >= 8:
        value = 0x7F
    else:
        value = segment << 4
        if segment < 2:
            value |= (magnitude >> 4) & 0x0F
        else:
            value |= (magnitude >> (segment + 3)) & 0x0F
    return value ^ mask


def _alaw_to_linear(value: int) -> int:
    value ^= 0x55
    sign = value & 0x80
    segment = (value & 0x70) >> 4
    sample = (value & 0x0F) << 4
    if segment == 0:
        sample += 8
    else:
        sample = (sample + 0x100) << (segment - 1)
    return sample if sign else -sample


def _alaw_segment(value: int) -> int:
    for index, endpoint in enumerate(_ALAW_SEG_END):
        if value <= endpoint:
            return index
    return len(_ALAW_SEG_END)


def _clip_int16(value: int) -> int:
    return min(max(value, _PCM_MIN), _PCM_MAX)
