"""
PRACK / 100rel (RFC 3262) demo — local loopback with no real network.

Shows:
  - Server sending reliable 180 Ringing (RSeq + Require: 100rel)
  - Client auto-sending PRACK with RAck header
  - Server handling PRACK and returning 200 OK
  - INVITE completing with final 200 OK

Run:
    uv run python examples/prack.py
"""

from __future__ import annotations

import asyncio

from sipx import AsyncSIPServer, AsyncSIPClient, Request


SERVER_PORT = 15062


async def main() -> None:
    server = AsyncSIPServer(local_host="127.0.0.1", local_port=SERVER_PORT)

    @server.invite()
    def on_invite(request: Request):
        """Return 180 Ringing — server will add RSeq/Require: 100rel automatically."""
        return request.ringing()

    @server.prack()
    def on_prack(request: Request):
        """Acknowledge the PRACK."""
        return request.ok()

    async with server:
        print(f"Server listening on 127.0.0.1:{SERVER_PORT}")

        async with AsyncSIPClient(local_host="127.0.0.1", local_port=0) as client:
            print("Client: sending INVITE with Require: 100rel")
            response = await client.invite(
                f"sip:bob@127.0.0.1:{SERVER_PORT}",
                reliable=True,
            )

        if response:
            print(f"Final response: {response.status_code} {response.reason_phrase}")
        else:
            print("No final response (timeout)")


if __name__ == "__main__":
    asyncio.run(main())
