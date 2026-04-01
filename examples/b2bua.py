"""
B2BUA (Back-to-Back User Agent) demo — loopback with two local servers.

Topology:
  Alice (client) → B2BUA (port 15064) → Bob (port 15065)

Alice calls the B2BUA.  The B2BUA forwards the INVITE to Bob, bridges
both legs, then relays BYE when Alice hangs up.

Run:
    uv run python examples/b2bua.py
"""

from __future__ import annotations

import asyncio

from sipx.server import AsyncSIPServer
from sipx.client import AsyncClient
from sipx.contrib._b2bua import AsyncB2BUA
from sipx.models._message import Request, Response


B2BUA_PORT = 15064
BOB_PORT = 15065


async def main() -> None:
    # ------------------------------------------------------------------ #
    # Bob's UA — answers every call
    # ------------------------------------------------------------------ #
    bob_server = AsyncSIPServer(local_host="127.0.0.1", local_port=BOB_PORT)

    @bob_server.invite
    def bob_on_invite(request: Request) -> Response:
        print(f"  Bob: INVITE from {request.from_header}")
        return request.ok()

    @bob_server.bye
    def bob_on_bye(request: Request) -> Response:
        print("  Bob: BYE received — call ended")
        return request.ok()

    # ------------------------------------------------------------------ #
    # B2BUA — bridges Alice → Bob
    # ------------------------------------------------------------------ #
    b2bua_server = AsyncSIPServer(local_host="127.0.0.1", local_port=B2BUA_PORT)
    b2bua_client = AsyncClient(local_host="127.0.0.1", local_port=0)

    events: list[str] = []

    b2b = AsyncB2BUA(
        server=b2bua_server,
        client=b2bua_client,
        target=f"sip:bob@127.0.0.1:{BOB_PORT}",
        on_bridge=lambda req, resp: events.append(
            f"bridge: {req.headers.get('Call-ID', '')[:8]}"
        ),
        on_terminate=lambda cid: events.append(f"terminate: {cid[:8]}"),
    )

    # ------------------------------------------------------------------ #
    # Alice's client
    # ------------------------------------------------------------------ #
    alice = AsyncClient(local_host="127.0.0.1", local_port=0)

    async with bob_server:
        async with b2bua_client:
            async with b2b:
                async with alice:
                    print(f"B2BUA listening on 127.0.0.1:{B2BUA_PORT}")
                    print(f"Bob listening on    127.0.0.1:{BOB_PORT}")
                    print()

                    # Alice calls the B2BUA
                    print("Alice: calling B2BUA…")
                    resp = await alice.invite(
                        f"sip:bob@127.0.0.1:{B2BUA_PORT}"
                    )
                    print(
                        f"Alice: INVITE → {resp.status_code} {resp.reason_phrase}"
                        if resp
                        else "Alice: INVITE → timeout"
                    )

                    if resp and resp.status_code == 200:
                        await asyncio.sleep(0.1)  # simulate brief call
                        print("Alice: hanging up…")
                        await alice.bye(response=resp)

                    await asyncio.sleep(0.1)

    print(f"\nB2BUA events: {events}")
    print(f"Active calls at end: {b2b.active_calls}")


if __name__ == "__main__":
    asyncio.run(main())
