#!/usr/bin/env python3
"""sipx — AsyncSIPServer + AsyncSIPClient (self-contained, no Asterisk)."""

import asyncio
from typing import Annotated
from sipx import AsyncSIPClient, AsyncSIPServer, Request, FromHeader
from rich.console import Console

console = Console()

HOST = "127.0.0.1"
PORT = 15090

server = AsyncSIPServer(local_host=HOST, local_port=PORT)


@server.register()
def on_register(request: Request, caller: Annotated[str, FromHeader]):
    console.print(f"  server: REGISTER from {caller}")
    return request.ok()


@server.message()
def on_message(request: Request, caller: Annotated[str, FromHeader]):
    body = request.content.decode() if request.content else ""
    console.print(f"  server: MESSAGE from {caller}: {body}")
    return request.ok()


async def main():
    console.print(f"[bold]sipx — Async Server + Client ({HOST}:{PORT})[/bold]\n")

    await server.start()
    await asyncio.sleep(0.5)

    try:
        async with AsyncSIPClient(local_host=HOST, local_port=PORT + 1) as client:
            # Register
            r = await client.request(
                "REGISTER", f"sip:test@{HOST}", host=HOST, port=PORT
            )
            console.print(f"REGISTER: {r.status_code if r else 'None'}")

            # Message
            r = await client.message(
                to_uri=f"sip:test@{HOST}:{PORT}",
                host=HOST,
                port=PORT,
                content="Hello async!",
            )
            console.print(f"MESSAGE: {r.status_code if r else 'None'}")

            # Options
            r = await client.options(f"sip:{HOST}:{PORT}", host=HOST, port=PORT)
            console.print(f"OPTIONS: {r.status_code if r else 'None'}")

        console.print("\n[bold green]All async operations completed![/bold green]")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
