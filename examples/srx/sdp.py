"""
Parsing e geração simplificada de SDP (Session Description Protocol).
"""


class SDP:
    def __init__(self, sdp_string: str):
        self.lines = sdp_string.strip().splitlines()
        self.media = [_ for _ in self.lines if _.startswith("m=")]

    def __str__(self) -> str:
        return "\r\n".join(self.lines) + "\r\n"


# Exemplo básico de SDP para testes
EXEMPLO_SDP = (
    "v=0\r\n"
    "o=- 123 456 IN IP4 127.0.0.1\r\n"
    "s=Stack demo\r\n"
    "c=IN IP4 127.0.0.1\r\n"
    "t=0 0\r\n"
    "m=audio 49170 RTP/AVP 0\r\n"
    "a=rtpmap:0 PCMU/8000\r\n"
)
