import asyncio


class UDP(asyncio.DatagramProtocol):
    def __init__(self, stack):
        self.stack = stack

    def connection_made(self, transport):
        self.transport = transport
        print("UDP transport started")

    def datagram_received(self, data, addr):
        message = data.decode()
        asyncio.create_task(self.stack.handle_message(message, addr))

    def error_received(self, exc):
        print(f"Erro UDP: {exc}")

    def send(self, data, addr):
        self.transport.sendto(data.encode(), addr)
