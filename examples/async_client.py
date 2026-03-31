#!/usr/bin/env python3
"""
sipx — AsyncClient example: register, call, message.

Requires: cd docker/asterisk && docker-compose up -d
"""

import asyncio

from sipx import AsyncClient
from sipx._utils import console


async def main():
    console.print("[bold]sipx — AsyncClient[/bold]")
    console.print("Requires Asterisk: cd docker/asterisk && docker-compose up -d\n")

    async with AsyncClient(local_port=5061) as client:
        client.auth = ("1111", "1111xxx")

        # Register
        r = await client.register("sip:1111@127.0.0.1")
        if not r:
            console.print("[red]REGISTER failed — is Asterisk running?[/red]")
            return
        console.print(f"REGISTER: {r.status_code}")

        # Options
        r = await client.options("sip:127.0.0.1")
        console.print(f"OPTIONS: {r.status_code if r else 'timeout'}")

        # Call
        sdp = client.create_sdp(port=8000)
        r = await client.invite(
            to_uri="sip:100@127.0.0.1",
            body=sdp.to_string(),
            headers={
                "Contact": f"<sip:1111@{client.local_address.host}:{client.local_address.port}>"
            },
        )
        console.print(f"INVITE: {r.status_code if r else 'timeout'}")

        if r and r.status_code == 200:
            await client.ack()
            await asyncio.sleep(2)
            bye_r = await client.bye()
            console.print(f"BYE: {bye_r.status_code if bye_r else 'timeout'}")

        # Message
        r = await client.message(to_uri="sip:2222@127.0.0.1", content="Hello async!")
        console.print(f"MESSAGE: {r.status_code if r else 'timeout'}")

        # Unregister
        await client.unregister("sip:1111@127.0.0.1")


if __name__ == "__main__":
    asyncio.run(main())
