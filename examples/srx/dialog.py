"""
Gerenciamento de Dialog SIP, acompanhamento da sessão.

Classe SIPDialog para armazenar estado, tags e IDs da sessão.
"""


class SIPDialog:
    def __init__(self, call_id: str, local_tag: str, remote_tag: str):
        self.call_id = call_id
        self.local_tag = local_tag
        self.remote_tag = remote_tag
        self.state = "early"  # Estados possíveis: early, confirmed, terminated
