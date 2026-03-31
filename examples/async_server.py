#!/usr/bin/env python3
"""sipx — AsyncSIPServer + AsyncClient (self-contained, no Asterisk)."""

import asyncio
from typing import Annotated
from sipx import AsyncClient, Request, Response, FromHeader
from sipx.server import AsyncSIPServer
from sipx._utils import console

HOST = "127.0.0.1"
PORT = 15090

server = AsyncSIPServer(local_host=HOST, local_port=PORT)


@server.register
def on_register(request: Request, caller: Annotated[str, FromHeader]) -> Response:
    console.print(f"  server: REGISTER from {caller}")
    return Response(
        status_code=200,
        headers={
            "Via": request.via or "",
            "From": request.from_header or "",
            "To": request.to_header or "",
            "Call-ID": request.call_id or "",
            "CSeq": request.cseq or "",
            "Content-Length": "0",
        },
    )


@server.message
def on_message(request: Request, caller: Annotated[str, FromHeader]) -> Response:
    body = request.content.decode() if request.content else ""
    console.print(f"  server: MESSAGE from {caller}: {body}")
    return Response(
        status_code=200,
        headers={
            "Via": request.via or "",
            "From": request.from_header or "",
            "To": request.to_header or "",
            "Call-ID": request.call_id or "",
            "CSeq": request.cseq or "",
            "Content-Length": "0",
        },
    )


async def main():
    console.print(f"[bold]sipx — Async Server + Client ({HOST}:{PORT})[/bold]\n")

    await server.start()
    await asyncio.sleep(0.5)

    try:
        async with AsyncClient(local_host=HOST, local_port=PORT + 1) as client:
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
