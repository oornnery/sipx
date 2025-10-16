"""
Stack SIP assíncrona, orquestra transações, diálogos e transporte.

Implementa envio e recebimento básico, gerenciamento de sessões.
"""

import asyncio

from fsm import SIPTransaction
from uri import URI


class AsyncSIPStack:
    def __init__(self, local_uri: URI):
        self.transactions = {}
        self.dialogs = {}
        self.local_uri = local_uri

    async def send(self, message: str):
        # Aqui deve estar o envio real UDP/TCP - placeholder print
        print("Sending to network:")
        print(message)

    async def invite(self, dest_uri: URI):
        branch = "z9hG4bK-%d" % asyncio.get_event_loop().time()
        call_id = "call-%d" % asyncio.get_event_loop().time()
        start_line = f"INVITE sip:{dest_uri.user}@{dest_uri.host} SIP/2.0"
        msg = (
            f"{start_line}\r\n"
            f"Via: SIP/2.0/UDP {self.local_uri.host};branch={branch}\r\n"
            f"Max-Forwards: 70\r\n"
            f"To: <sip:{dest_uri.user}@{dest_uri.host}>\r\n"
            f"From: <sip:{self.local_uri.user}@{self.local_uri.host}>;tag=1234\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: 1 INVITE\r\n"
            f"Contact: <sip:{self.local_uri.user}@{self.local_uri.host}>\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        transaction = SIPTransaction(call_id, msg, self.send)
        self.transactions[call_id] = transaction
        asyncio.create_task(transaction.start())
