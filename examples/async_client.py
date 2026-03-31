#!/usr/bin/env python3
"""sipx — AsyncClient example: register, call, message."""

import asyncio
from sipx import AsyncClient, SDPBody
from sipx._utils import console


async def main():
    console.print("[bold]sipx — AsyncClient[/bold]\n")

    async with AsyncClient(local_port=5061) as client:
        client.auth = ("1111", "1111xxx")

        # Register
        r = await client.register("sip:1111@127.0.0.1")
        console.print(f"REGISTER: {r.status_code}")

        # Options
        r = await client.options("sip:127.0.0.1")
        console.print(f"OPTIONS: {r.status_code}")

        # Call
        sdp = SDPBody.audio(ip=client.local_address.host, port=8000)
        r = await client.invite(
            to_uri="sip:100@127.0.0.1",
            body=sdp.to_string(),
            headers={
                "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
            },
        )
        console.print(f"INVITE: {r.status_code}")

        if r.status_code == 200:
            await client.ack(response=r)
            await asyncio.sleep(2)
            bye_r = await client.bye(response=r)
            console.print(f"BYE: {bye_r.status_code}")

        # Message
        r = await client.message(to_uri="sip:2222@127.0.0.1", content="Hello async!")
        console.print(f"MESSAGE: {r.status_code}")

        # Unregister
        await client.unregister("sip:1111@127.0.0.1")


if __name__ == "__main__":
    asyncio.run(main())
