"""
Máquina de estados para transações SIP (INVITE, non-INVITE) com timers retransmissão.
"""

import asyncio


class SIPTransaction:
    def __init__(self, tid: str, message: str, send_cb):
        self.tid = tid
        self.message = message
        self.send_cb = send_cb
        self.state = "calling"
        self.attempts = 0

    async def start(self):
        await self.transmit()

    async def transmit(self):
        interval = 0.5  # T1 timer padrão
        while self.attempts < 7 and self.state not in ["completed", "terminated"]:
            await self.send_cb(self.message)
            await asyncio.sleep(interval)
            self.attempts += 1
            interval = min(interval * 2, 4)  # Dobrar até máximo de T2 (4s)

    def on_response(self, code: str):
        if code.startswith("1"):
            self.state = "proceeding"
        elif code.startswith("2"):
            self.state = "completed"
        elif code.startswith(("4", "5", "6")):
            self.state = "terminated"
