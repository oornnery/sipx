"""
Parsing e formatação de mensagens SIP.
"""


class SIPMessage:
    def __init__(self, raw: str):
        header, _, body = raw.partition("\r\n\r\n")
        lines = header.split("\r\n")
        self.start_line = lines[0]
        self.headers = {}
        for h in lines[1:]:
            if ":" in h:
                k, v = h.split(":", 1)
                self.headers[k.strip()] = v.strip()
        self.body = body

    def header(self, name: str) -> str:
        return self.headers.get(name, "")

    def __str__(self):
        headers = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items())
        return f"{self.start_line}\r\n{headers}\r\n\r\n{self.body}"
